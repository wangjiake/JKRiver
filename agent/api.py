
import asyncio
import logging
import os
import secrets
import uuid
from datetime import datetime
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, File, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

UPLOAD_DIR = "/tmp/jkriver_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

from agent.config import load_config
from agent.core import SessionManager, run_cycle_async
from agent.storage import get_db_connection, load_current_profile, load_full_current_profile
from agent.utils.time_context import set_current_time
from agent.routers import _state

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _state._config = load_config()
    _state._manager = SessionManager(_state._config)
    # Reset tasks stuck in running/planning state from a previous server crash
    try:
        from agent.storage.outsource import list_tasks, update_task as _ot_update
        for _t in list_tasks(limit=200):
            if _t.get("status") in ("running", "planning"):
                _ot_update(_t["task_id"], status="failed",
                           result="Server restarted — task was interrupted.")
    except Exception:
        pass
    # Auto-update AGENT.md on startup (if scan is enabled)
    scan_cfg = (_state._config or {}).get("agent_doc_scan", {}) or {}
    if scan_cfg.get("enabled", True):
        try:
            from agent.tools.system_manage import _update_agent_doc
            _update_agent_doc(_state._config)
        except Exception as e:
            logger.warning("Failed to update AGENT.md on startup: %s", e)

        # Schedule periodic re-scan
        async def _periodic_scan():
            import asyncio as _asyncio
            while True:
                cfg2 = (_state._config or {}).get("agent_doc_scan", {}) or {}
                interval_hours = cfg2.get("interval_hours", 24)
                await _asyncio.sleep(interval_hours * 3600)
                try:
                    cfg2 = (_state._config or {}).get("agent_doc_scan", {}) or {}
                    if cfg2.get("enabled", True):
                        from agent.tools.system_manage import _update_agent_doc
                        _update_agent_doc(_state._config)
                        logger.info("AGENT.md periodic scan complete.")
                except Exception as e:
                    logger.warning("AGENT.md periodic scan failed: %s", e)
        asyncio.create_task(_periodic_scan())
    yield


def _api_token_valid(token: str) -> bool:
    pm = _state._config.get("public_mode", {}) if _state._config else {}
    if not pm.get("enabled", False):
        return True
    expected = pm.get("access_token", "")
    if not expected:
        return True
    try:
        return secrets.compare_digest(token.encode(), str(expected).encode())
    except Exception:
        return False


app = FastAPI(title="Riverse Agent API", version="2.4.0", lifespan=lifespan)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)
    token = request.headers.get("X-Device-Token", "") or request.query_params.get("token", "")
    if not _api_token_valid(token):
        return JSONResponse(status_code=401, content={"detail": "unauthorized"})
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Include routers ───────────────────────────────────────────────────────────
from agent.routers import outsource, sessions, system as system_router
app.include_router(outsource.router)
app.include_router(sessions.router)
app.include_router(system_router.router)


# ── Models ────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = ""
    session_id: str | None = None
    input_type: str = "text"
    file_path: str | None = None
    client_time: str | None = None

class ChatResponse(BaseModel):
    response: str
    session_id: str
    category: str
    intent: str

class SessionResponse(BaseModel):
    session_id: str
    created_at: str

class ProfileEntry(BaseModel):
    category: str
    field: str
    value: str

class HypothesisEntry(BaseModel):
    id: int
    category: str
    subject: str
    claim: str
    confidence: float
    status: str

class TaskRequest(BaseModel):
    task: str
    max_steps: int = 20

class TaskResponse(BaseModel):
    success: bool
    result: str
    steps: list
    files_changed: list


# ── Core endpoints ────────────────────────────────────────────────────────────

_TOOL_FOR_INPUT = {"image": "image_describe", "voice": "voice_transcribe"}

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if req.client_time:
        try:
            set_current_time(datetime.fromisoformat(req.client_time))
        except (ValueError, TypeError):
            pass
    session = _state._manager.get_or_create(req.session_id)
    try:
        required_tool = _TOOL_FOR_INPUT.get(req.input_type)
        if required_tool and required_tool not in session.tool_registry._tools:
            from agent.config.prompts import get_labels
            L = get_labels("context.labels", _state._config.get("language", "en"))
            return ChatResponse(
                response=L.get(f"{req.input_type}_not_supported",
                               f"{req.input_type} input is not supported: {required_tool} tool is not configured."),
                session_id=session.id,
                category="error",
                intent="",
            )

        if req.input_type == "text" and not req.file_path:
            user_input = req.message
        else:
            user_input = {
                "type": req.input_type,
                "text": req.message,
                "file_path": req.file_path or "",
            }

        result = await run_cycle_async(user_input, session)
        return ChatResponse(
            response=result["response"],
            session_id=session.id,
            category=result["perception"].get("category", "chat"),
            intent=result["perception"].get("intent", ""),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/capabilities")
async def get_capabilities():
    session = _state._manager.get_or_create()
    tools = session.tool_registry._tools
    return {
        "image": "image_describe" in tools,
        "voice": "voice_transcribe" in tools,
    }


@app.post("/session/new", response_model=SessionResponse)
async def new_session():
    session = _state._manager.get_or_create()
    return SessionResponse(
        session_id=session.id,
        created_at=session.created_at.isoformat(),
    )


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename)[1] if file.filename else ".bin"
    filename = f"{uuid.uuid4()}{ext}"
    path = os.path.join(UPLOAD_DIR, filename)
    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)
    return {"file_path": path, "filename": file.filename}


@app.post("/sleep")
async def trigger_sleep():
    try:
        from agent.sleep import run_async as sleep_run_async
        await sleep_run_async()
        from agent.config.prompts import get_labels
        L = get_labels("context.labels", _state._config.get("language", "en"))
        return {"status": "ok", "message": L["memory_done"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/task", response_model=TaskResponse)
async def run_task_endpoint(req: TaskRequest):
    from agent.task_agent import run_task_async
    session = _state._manager.get_or_create("__task__")
    result = await run_task_async(
        task=req.task,
        config=_state._manager.config,
        registry=session.tool_registry,
        max_steps=req.max_steps,
    )
    return TaskResponse(**result)


@app.get("/health")
async def health_check():
    db_ok = False
    llm_ok = False
    try:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            db_ok = True
        finally:
            conn.close()
    except Exception as e:
        logger.warning("Health check: DB unreachable: %s", e)

    if _state._config:
        api_base = _state._config.get("llm", {}).get("api_base", "")
        if api_base:
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    resp = await client.head(api_base)
                    llm_ok = resp.status_code < 500
            except Exception as e:
                logger.warning("Health check: LLM unreachable: %s", e)
        else:
            llm_ok = True

    if db_ok and llm_ok:
        status = "ok"
    elif db_ok or llm_ok:
        status = "degraded"
    else:
        status = "error"

    code = 200 if status == "ok" else 503
    return JSONResponse(
        status_code=code,
        content={"status": status, "db": db_ok, "llm": llm_ok},
    )


@app.get("/profile", response_model=list[ProfileEntry])
async def get_profile():
    profile = load_current_profile()
    return [
        ProfileEntry(category=p["category"], field=p["field"], value=p["value"])
        for p in profile
    ]


@app.get("/hypotheses", response_model=list[HypothesisEntry])
async def get_hypotheses():
    profile = load_full_current_profile()
    return [
        HypothesisEntry(
            id=p["id"], category=p["category"], subject=p["subject"],
            claim=p["value"], confidence=0.5, status=p.get("layer", "suspected"),
        )
        for p in profile
    ]


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket, session_id: str | None = None):
    await websocket.accept()
    session = _state._manager.get_or_create(session_id)
    _state._ws_connections.setdefault(session.id, []).append(websocket)
    await websocket.send_json({
        "type": "session_created",
        "session_id": session.id,
    })

    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "cancel":
                continue

            if data.get("type") == "outsource_confirm":
                task_id = data.get("task_id", "")
                if task_id:
                    from agent.storage.outsource import get_task
                    from agent.tools.dispatch_task import DispatchTaskTool
                    record = get_task(task_id)
                    if (record
                            and record.get("status") == "pending"
                            and record.get("session_id") == session.id):
                        _cfg = dict(session.full_config)
                        _cfg["_session_id"] = session.id
                        tool = DispatchTaskTool(_cfg)
                        result = tool.execute({"action": "start", "task_id": task_id})
                        await websocket.send_json({
                            "type": "outsource_started",
                            "task_id": task_id,
                            "task_id_short": task_id[:8],
                            "message": result.data if result.success else result.error,
                        })
                continue

            if data.get("type") == "outsource_cancel":
                task_id = data.get("task_id", "")
                if task_id:
                    from agent.storage.outsource import get_task, update_task
                    record = get_task(task_id)
                    if record and record.get("session_id") == session.id:
                        from agent.config.prompts import get_labels as _gl
                        _lang = session.full_config.get("language", "en")
                        _cancel_msg = _gl("context.labels", _lang).get("outsource_cancel_result", "Cancelled by user")
                        update_task(task_id, status="cancelled", result=_cancel_msg)
                        await websocket.send_json({
                            "type": "outsource_cancelled",
                            "task_id": task_id,
                            "task_id_short": task_id[:8],
                        })
                continue

            if data.get("type") == "task_answer":
                task_id = data.get("task_id", "")
                answer = data.get("answer", "")
                if task_id and task_id in _state._task_questions:
                    event, holder = _state._task_questions[task_id]
                    holder["answer"] = answer
                    event.set()
                    try:
                        from agent.storage.outsource import update_task as _ot_upd
                        _ot_upd(task_id, pending_question=None)
                    except Exception:
                        pass
                else:
                    try:
                        await websocket.send_json({
                            "type": "error",
                            "detail": f"Task {task_id[:8]} 已不在等待回复状态（可能已超时或重启）",
                        })
                    except Exception:
                        pass
                continue

            message = data.get("message", "")
            if not message:
                continue

            client_time = data.get("client_time")
            if client_time:
                try:
                    set_current_time(datetime.fromisoformat(client_time))
                except (ValueError, TypeError):
                    pass

            process_task = asyncio.create_task(run_cycle_async(message, session))
            cancelled = False

            while not process_task.done():
                recv_task = asyncio.create_task(websocket.receive_json())
                done, _ = await asyncio.wait(
                    {process_task, recv_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if recv_task in done:
                    try:
                        incoming = recv_task.result()
                        if incoming.get("type") == "cancel":
                            process_task.cancel()
                            cancelled = True
                            break
                    except Exception:
                        pass
                else:
                    recv_task.cancel()
                    try:
                        await recv_task
                    except (asyncio.CancelledError, Exception):
                        pass

            if cancelled:
                try:
                    await process_task
                except (asyncio.CancelledError, Exception):
                    pass
                try:
                    await websocket.send_json({"type": "cancelled"})
                except Exception:
                    pass
            else:
                try:
                    result = process_task.result()
                    await websocket.send_json({
                        "type": "response",
                        "response": result["response"],
                        "category": result["perception"].get("category", "chat"),
                        "intent": result["perception"].get("intent", ""),
                    })
                except (WebSocketDisconnect, RuntimeError):
                    pass
                except Exception as e:
                    try:
                        await websocket.send_json({
                            "type": "error",
                            "detail": str(e),
                        })
                    except Exception:
                        pass
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        conns = _state._ws_connections.get(session.id, [])
        try:
            conns.remove(websocket)
        except ValueError:
            pass
        if not conns:
            _state._ws_connections.pop(session.id, None)
