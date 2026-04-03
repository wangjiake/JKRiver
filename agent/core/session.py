import uuid
import logging

from agent.cognition import CognitionEngine
from agent.utils.time_context import get_now
from agent.storage import get_db_connection
from agent.tools import ToolRegistry
from agent.skills import SkillRegistry

logger = logging.getLogger(__name__)


def _load_resolver_profile() -> list[dict]:
    """Load confirmed-only profile sorted by recency, for use in tool resolver."""
    try:
        conn = get_db_connection()
        try:
            from psycopg2.extras import RealDictCursor
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT category, subject, value FROM user_profile "
                    "WHERE layer = 'confirmed' AND end_time IS NULL "
                    "AND rejected = false AND human_end_time IS NULL "
                    "ORDER BY updated_at DESC"
                )
                return list(cur.fetchall())
        finally:
            conn.close()
    except Exception:
        return []


class Session:
    def __init__(self, config: dict, session_id: str | None = None):
        self.id = session_id or str(uuid.uuid4())
        self.created_at = get_now()
        self.full_config = config
        self.cognition = CognitionEngine(config)
        self.cognition.session_memory.session_id = self.id
        self.executed_strategy_ids: set = set()
        tools_enabled = config.get("tools", {}).get("enabled", True)
        self.tool_registry = ToolRegistry(config, enabled=tools_enabled)
        self.skill_registry = SkillRegistry(config)


class SessionManager:
    def __init__(self, config: dict):
        self.config = config
        self._sessions: dict[str, Session] = {}

    def get_or_create(self, session_id: str | None = None) -> Session:
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]
        session = Session(self.config, session_id)
        self._sessions[session.id] = session
        if session_id:
            self._load_history_into_session(session, session_id)
        return session

    def _load_history_into_session(self, session: Session, session_id: str,
                                   limit: int = 10) -> None:
        """Load the last N turns of an existing session into session memory."""
        try:
            conn = get_db_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT user_input, assistant_reply, user_input_at "
                        "FROM raw_conversations "
                        "WHERE session_id = %s "
                        "ORDER BY user_input_at DESC LIMIT %s",
                        (session_id, limit),
                    )
                    rows = cur.fetchall()
            finally:
                conn.close()

            # Rows are DESC, reverse to get chronological order
            for user_input, assistant_reply, user_input_at in reversed(rows):
                session.cognition.session_memory.add_turn(
                    user_summary=user_input,
                    assistant_summary=assistant_reply,
                    user_input_at=user_input_at,
                )
        except Exception:
            # Non-fatal: session still works, just without history
            logger.warning("Failed to load history for session %s", session_id, exc_info=True)

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def remove(self, session_id: str):
        self._sessions.pop(session_id, None)

    def list_sessions(self) -> list[str]:
        return list(self._sessions.keys())
