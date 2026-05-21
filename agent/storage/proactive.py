from datetime import timedelta

from psycopg2.extras import RealDictCursor
from agent.utils.time_context import get_now
from ._db import get_db_connection


_proactive_table_ensured = False


def _ensure_proactive_table():
    global _proactive_table_ensured
    if _proactive_table_ensured:
        return
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS proactive_log (
                    id SERIAL PRIMARY KEY,
                    chat_id BIGINT NOT NULL,
                    trigger_type VARCHAR(50) NOT NULL,
                    trigger_ref TEXT,
                    message_text TEXT NOT NULL,
                    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_proactive_log_chat_sent
                    ON proactive_log (chat_id, sent_at DESC)
            """)
        conn.commit()
        _proactive_table_ensured = True
    finally:
        conn.close()


def save_proactive_log(chat_id: int, trigger_type: str,
                       trigger_ref: str | None, message_text: str,
                       owner_id: int = 1):
    _ensure_proactive_table()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO proactive_log (owner_id, chat_id, trigger_type, trigger_ref, "
                "message_text, sent_at) VALUES (%s, %s, %s, %s, %s, %s)",
                (owner_id, chat_id, trigger_type, trigger_ref, message_text, get_now()),
            )
        conn.commit()
    finally:
        conn.close()


def load_proactive_log(chat_id: int, since_hours: int = 24,
                       owner_id: int | None = None) -> list[dict]:
    _ensure_proactive_table()
    since = get_now() - timedelta(hours=since_hours)
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if owner_id is not None:
                cur.execute(
                    "SELECT id, chat_id, trigger_type, trigger_ref, message_text, sent_at "
                    "FROM proactive_log "
                    "WHERE chat_id = %s AND sent_at > %s AND owner_id = %s "
                    "ORDER BY sent_at DESC",
                    (chat_id, since, owner_id),
                )
            else:
                cur.execute(
                    "SELECT id, chat_id, trigger_type, trigger_ref, message_text, sent_at "
                    "FROM proactive_log "
                    "WHERE chat_id = %s AND sent_at > %s "
                    "ORDER BY sent_at DESC",
                    (chat_id, since),
                )
            return list(cur.fetchall())
    finally:
        conn.close()


def get_last_interaction_time(session_id: str, owner_id: int | None = None):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            if owner_id is not None:
                cur.execute(
                    "SELECT MAX(user_input_at) FROM conversation_turns "
                    "WHERE session_id = %s AND owner_id = %s",
                    (session_id, owner_id),
                )
            else:
                cur.execute(
                    "SELECT MAX(user_input_at) FROM conversation_turns "
                    "WHERE session_id = %s",
                    (session_id,),
                )
            row = cur.fetchone()
            return row[0] if row and row[0] else None
    finally:
        conn.close()
