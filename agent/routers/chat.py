"""WebSocket chat endpoint."""

import asyncio
import logging
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from agent.core import run_cycle_async
from agent.routers import _state
from agent.utils.time_context import set_current_time

logger = logging.getLogger(__name__)

router = APIRouter()


async def _handle_outsource_confirm(websocket: WebSocket, data: dict, session) -> None:
    task_id = data.get("task_id", "")
    if not task_id:
        return
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


async def _handle_outsource_cancel(websocket: WebSocket, data: dict, session) -> None:
    task_id = data.get("task_id", "")
    if not task_id:
        return
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


async def _handle_task_answer(websocket: WebSocket, data: dict) -> None:
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


@router.websocket("/ws/chat")
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
                await _handle_outsource_confirm(websocket, data, session)
                continue

            if data.get("type") == "outsource_cancel":
                await _handle_outsource_cancel(websocket, data, session)
                continue

            if data.get("type") == "task_answer":
                await _handle_task_answer(websocket, data)
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
