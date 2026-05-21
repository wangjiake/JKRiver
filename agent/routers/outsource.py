"""Outsource task endpoints and WebSocket push helpers."""
import asyncio
import copy
import threading

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from agent.core.identity import DEFAULT_OWNER_ID
from agent.routers import _state
from agent.storage.outsource import (
    create_task as _ot_create,
    update_task as _ot_update,
    get_task as _ot_get,
    list_tasks as _ot_list,
    count_active as _ot_count_active,
    delete_task as _ot_delete,
)

router = APIRouter(prefix="/api/outsource/tasks", tags=["outsource"])


def _owner_id(request: Request) -> int:
    return getattr(request.state, "owner_id", DEFAULT_OWNER_ID)


class OutsourceCreateRequest(BaseModel):
    task: str
    strict_mode: bool = True


@router.get("/active_count")
async def api_active_count(request: Request):
    return {"count": _ot_count_active(owner_id=_owner_id(request))}


@router.get("/{task_id}")
async def api_get_task(task_id: str, request: Request):
    task = _ot_get(task_id, owner_id=_owner_id(request))
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    for k in ("created_at", "updated_at"):
        if task.get(k):
            task[k] = task[k].isoformat()
    return task


@router.get("")
async def api_list_tasks(request: Request):
    tasks = _ot_list(owner_id=_owner_id(request))
    for t in tasks:
        for k in ("created_at", "updated_at"):
            if t.get(k):
                t[k] = t[k].isoformat()
    return tasks


@router.post("")
async def api_create_task(req: OutsourceCreateRequest, request: Request):
    from agent.tools import ToolRegistry
    from agent.task_agent import plan_task_async, run_task_async

    owner_id = _owner_id(request)
    task_id = _ot_create(req.task, strict_mode=req.strict_mode, owner_id=owner_id)
    config = _state._manager.config

    _ot_update(task_id, status="planning", owner_id=owner_id)
    plan = await plan_task_async(req.task, config)
    _ot_update(task_id, plan=plan, total_steps=len(plan), status="running", owner_id=owner_id)

    strict_mode = req.strict_mode

    async def _run():
        if strict_mode:
            agent_config = config
        else:
            try:
                from agent.tools.dispatch_task import _LOOSE_SHELL_WHITELIST
                whitelist = _LOOSE_SHELL_WHITELIST
            except ImportError:
                whitelist = []
            agent_config = copy.deepcopy(config)
            agent_config.setdefault("tools", {}).setdefault("shell_exec", {}).update({
                "enabled": True,
                "whitelist": whitelist,
                "timeout": 120,
            })

        registry = ToolRegistry(agent_config)
        executed_steps = []

        async def on_step(step_data: dict):
            executed_steps.append(step_data)
            _ot_update(task_id, steps=executed_steps, current_step=len(executed_steps))

        result = await run_task_async(
            req.task, agent_config, registry,
            strict_mode=strict_mode,
            progress_callback=on_step,
        )
        _ot_update(task_id,
            status="done" if result["success"] else "failed",
            result=result["result"],
            files_changed=result["files_changed"],
            steps=result["steps"],
            current_step=len(result["steps"]),
        )

    def _thread_runner():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_run())
        finally:
            loop.close()

    t = threading.Thread(target=_thread_runner, daemon=True)
    t.start()
    return {"task_id": task_id, "plan": plan}


@router.post("/{task_id}/confirm")
async def api_confirm_task(task_id: str, request: Request):
    record = _ot_get(task_id, owner_id=_owner_id(request))
    if not record:
        raise HTTPException(status_code=404, detail="Task not found")
    if record.get("status") != "pending":
        return {"ok": False, "reason": "Task is not pending"}
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    session_id = body.get("session_id", "")
    from agent.tools.dispatch_task import DispatchTaskTool
    sess = _state._manager.get_or_create(session_id or None)
    cfg = dict(sess.full_config)
    cfg["_session_id"] = sess.id
    tool = DispatchTaskTool(cfg)
    result = tool.execute({"action": "start", "task_id": task_id})
    return {"ok": result.success, "message": result.data if result.success else result.error}


@router.post("/{task_id}/cancel")
async def api_cancel_task(task_id: str, request: Request):
    owner_id = _owner_id(request)
    record = _ot_get(task_id, owner_id=owner_id)
    if not record:
        raise HTTPException(status_code=404, detail="Task not found")
    if record.get("status", "") not in ("pending", "planning", "running", "suspended"):
        return {"ok": False, "reason": "Task is not active"}
    if task_id in _state._cancel_flags:
        _state._cancel_flags[task_id].set()
    _ot_update(task_id, status="cancelled", result="Cancelled by user", owner_id=owner_id)
    return {"ok": True}


@router.post("/{task_id}/answer")
async def api_task_answer(task_id: str, request: Request):
    owner_id = _owner_id(request)
    # Ensure the task belongs to the caller before letting them answer it.
    if not _ot_get(task_id, owner_id=owner_id):
        raise HTTPException(status_code=404, detail="Task not found")
    body = await request.json()
    answer = body.get("answer", "").strip()
    if not answer:
        return {"ok": False, "reason": "Missing 'answer'"}
    if task_id not in _state._task_questions:
        return {"ok": False, "reason": "No pending question for this task"}
    event, holder = _state._task_questions[task_id]
    holder["answer"] = answer
    event.set()
    try:
        from agent.storage.outsource import update_task as _ot_upd
        _ot_upd(task_id, pending_question=None, owner_id=owner_id)
    except Exception:
        pass
    return {"ok": True}


@router.post("/{task_id}/retry")
async def api_retry_task(task_id: str, request: Request):
    record = _ot_get(task_id, owner_id=_owner_id(request))
    if not record:
        raise HTTPException(status_code=404, detail="Task not found")
    if record.get("status") not in ("failed", "cancelled"):
        return {"ok": False, "reason": f"Task is not failed or cancelled (status: {record.get('status')})"}
    cfg = copy.deepcopy(_state._config)
    task_session_id = record.get("session_id", "")
    if task_session_id:
        cfg["_session_id"] = task_session_id
    cfg.setdefault("llm", {})["_owner_id"] = _owner_id(request)
    from agent.tools.dispatch_task import DispatchTaskTool
    tool = DispatchTaskTool(cfg)
    result = tool.execute({"action": "retry", "task_id": task_id})
    if result.success:
        return {"ok": True, "message": result.data}
    return {"ok": False, "reason": result.error}


@router.post("/{task_id}/resume")
async def api_resume_task(task_id: str, request: Request):
    record = _ot_get(task_id, owner_id=_owner_id(request))
    if not record:
        raise HTTPException(status_code=404, detail="Task not found")
    if record.get("status") != "suspended":
        return {"ok": False, "reason": f"Task is not suspended (status: {record.get('status')})"}
    cfg = copy.deepcopy(_state._config)
    task_session_id = record.get("session_id", "")
    if task_session_id:
        cfg["_session_id"] = task_session_id
    cfg.setdefault("llm", {})["_owner_id"] = _owner_id(request)
    from agent.tools.dispatch_task import DispatchTaskTool
    tool = DispatchTaskTool(cfg)
    result = tool.execute({"action": "resume", "task_id": task_id})
    if result.success:
        return {"ok": True, "message": result.data}
    return {"ok": False, "reason": result.error}


@router.delete("/{task_id}")
async def api_delete_task(task_id: str, request: Request):
    owner_id = _owner_id(request)
    record = _ot_get(task_id, owner_id=owner_id)
    if not record:
        raise HTTPException(status_code=404, detail="Task not found")
    if task_id in _state._cancel_flags:
        _state._cancel_flags[task_id].set()
        _state._cancel_flags.pop(task_id, None)
    deleted = _ot_delete(task_id, owner_id=owner_id)
    return {"ok": deleted}


# ── WebSocket push helpers ────────────────────────────────────────────────────

async def push_task_result_to_session(session_id: str, task_id: str, success: bool, result: str,
                                      files_changed: list = None, steps_count: int = 0,
                                      language: str = "zh"):
    """Push outsource task completion to the chat session WebSocket(s) if connected."""
    icon = "✅" if success else "❌"
    _labels = {
        "zh": ("执行完成", "执行失败", "步骤数", "修改文件"),
        "ja": ("完了", "失敗", "ステップ数", "変更ファイル"),
        "en": ("Completed", "Failed", "Steps", "Files changed"),
    }
    _done, _fail, _steps_lbl, _files_lbl = _labels.get(language, _labels["zh"])
    label = _done if success else _fail
    msg = f"{icon} **[Task #{task_id[:8]}] {label}**\n\n{result}"
    if steps_count:
        msg += f"\n\n**{_steps_lbl}**：{steps_count}"
    if files_changed:
        msg += f"\n\n**{_files_lbl}**：\n" + "\n".join(f"- `{f}`" for f in files_changed)

    try:
        from agent.storage.conversation import save_raw_conversation
        from agent.storage._db import get_db_connection
        from agent.utils.time_context import get_now
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT session_created_at, owner_id FROM raw_conversations "
                    "WHERE session_id = %s ORDER BY user_input_at ASC LIMIT 1",
                    (session_id,)
                )
                row = cur.fetchone()
            session_created_at = row[0] if row else get_now()
            owner_id = int(row[1]) if row and row[1] is not None else 1
        finally:
            conn.close()
        now = get_now()
        save_raw_conversation(session_id, session_created_at, "", now, msg, now,
                              owner_id=owner_id)
    except Exception:
        pass

    wss = _state._ws_connections.get(session_id, [])
    if not wss:
        return
    payload = {
        "type": "task_complete",
        "task_id": task_id,
        "task_id_short": task_id[:8],
        "success": success,
        "status": "done" if success else "failed",
        "result": result,
        "files_changed": files_changed or [],
        "steps_count": steps_count,
    }
    for ws in list(wss):
        try:
            await ws.send_json(payload)
        except Exception:
            pass


async def push_task_question_to_session(session_id: str, task_id: str, question: str):
    """Push a mid-task question to the user's chat WebSocket(s)."""
    wss = _state._ws_connections.get(session_id, [])
    if not wss:
        return
    payload = {
        "type": "task_question",
        "task_id": task_id,
        "task_id_short": task_id[:8],
        "question": question,
    }
    for ws in list(wss):
        try:
            await ws.send_json(payload)
        except Exception:
            pass
