
import asyncio
import logging
import os
import uuid
from datetime import datetime
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

UPLOAD_DIR = "/tmp/jkriver_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

from agent.config import load_config
from agent.core import SessionManager, run_cycle_async
from agent.core.identity import DEFAULT_OWNER_ID, resolve_owner_id
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

    # Family GC: daily prune of stale tokens / invites / audit rows.
    try:
        from agent.services.family_gc import gc_loop
        asyncio.create_task(gc_loop())
    except Exception as e:
        logger.warning("Family GC not started: %s", e)
    yield


app = FastAPI(title="Riverse Agent API", version="2.4.0", lifespan=lifespan)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)
    token = request.headers.get("X-Device-Token", "") or request.query_params.get("token", "")
    pm = _state._config.get("public_mode", {}) if _state._config else {}
    if not pm.get("enabled", False):
        # public_mode disabled: single-user dev mode.
        request.state.owner_id = DEFAULT_OWNER_ID
        request.state.access_token = token
        return await call_next(request)
    ua = request.headers.get("User-Agent")
    ip = request.client.host if request.client else None
    owner_id = resolve_owner_id(token, user_agent=ua, ip=ip)
    if owner_id is None:
        return JSONResponse(status_code=401, content={"detail": "unauthorized"})
    request.state.owner_id = owner_id
    request.state.access_token = token
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
from agent.routers import system_tools, system_skills, system_agents
from agent.routers import stats as stats_router
from agent.routers import chat as chat_router
from agent.routers import family as family_router
app.include_router(outsource.router)
app.include_router(sessions.router)
app.include_router(system_router.router)
app.include_router(system_tools.router)
app.include_router(system_skills.router)
app.include_router(system_agents.router)
app.include_router(stats_router.router)
app.include_router(chat_router.router)
app.include_router(family_router.router)


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
async def chat(req: ChatRequest, request: Request):
    if req.client_time:
        try:
            set_current_time(datetime.fromisoformat(req.client_time))
        except (ValueError, TypeError):
            pass
    owner_id = getattr(request.state, "owner_id", DEFAULT_OWNER_ID)
    session = _state._manager.get_or_create(req.session_id, owner_id=owner_id)
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
async def new_session(request: Request):
    owner_id = getattr(request.state, "owner_id", DEFAULT_OWNER_ID)
    session = _state._manager.get_or_create(owner_id=owner_id)
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
async def get_profile(request: Request):
    owner_id = getattr(request.state, "owner_id", DEFAULT_OWNER_ID)
    profile = load_current_profile(owner_id=owner_id)
    return [
        ProfileEntry(category=p["category"], field=p["field"], value=p["value"])
        for p in profile
    ]


@app.get("/hypotheses", response_model=list[HypothesisEntry])
async def get_hypotheses(request: Request):
    owner_id = getattr(request.state, "owner_id", DEFAULT_OWNER_ID)
    profile = load_full_current_profile(owner_id=owner_id)
    return [
        HypothesisEntry(
            id=p["id"], category=p["category"], subject=p["subject"],
            claim=p["value"], confidence=0.5, status=p.get("layer", "suspected"),
        )
        for p in profile
    ]

