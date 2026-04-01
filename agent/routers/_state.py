"""Shared mutable state accessible by all routers and api.py."""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.core import SessionManager

_config: dict | None = None
_manager: "SessionManager | None" = None
_pending_restart: bool = False
_revert_ops: list[dict] = []
_ws_connections: dict[str, list] = {}   # session_id -> [WebSocket, ...]
_cancel_flags: dict[str, object] = {}   # task_id -> threading.Event
_task_questions: dict[str, tuple] = {}  # task_id -> (threading.Event, holder dict)
_telegram_proc = None   # subprocess.Popen | None
_discord_proc = None    # subprocess.Popen | None
