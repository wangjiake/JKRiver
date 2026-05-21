import json

from psycopg2.extras import RealDictCursor
from agent.utils.time_context import get_now
from ._db import get_db_connection


def save_raw_conversation(session_id: str, session_created_at,
                          user_input: str, user_input_at,
                          assistant_reply: str, assistant_reply_at,
                          owner_id: int = 1):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO raw_conversations "
                "(owner_id, session_id, session_created_at, user_input, user_input_at, "
                " assistant_reply, assistant_reply_at, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (owner_id, session_id, session_created_at,
                 user_input, user_input_at,
                 assistant_reply, assistant_reply_at, get_now()),
            )
        conn.commit()
    finally:
        conn.close()

def save_conversation_turn(turn: dict):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO conversation_turns "
                "(owner_id, session_id, session_created_at, "
                " user_input, user_input_at, assistant_reply, assistant_reply_at, "
                " intent, need_memory, memory_type, ai_summary, perception_at, "
                " memories_used, memories_used_at, "
                " raw_response, raw_response_at, "
                " verification_result, verification_result_at, "
                " final_response, final_response_at, "
                " thinking_notes, thinking_notes_at, "
                " completed_at,"
                " input_type, file_path, file_data, tool_results) "
                "VALUES ("
                " %s, %s, %s, %s, %s, %s, %s, "
                " %s, %s, %s, %s, %s, "
                " %s, %s, "
                " %s, %s, "
                " %s, %s, "
                " %s, %s, "
                " %s, %s, "
                " %s,"
                " %s, %s, %s, %s)",
                (
                    turn.get("owner_id", 1),
                    turn["session_id"], turn["session_created_at"],
                    turn["user_input"], turn["user_input_at"],
                    turn["assistant_reply"], turn["assistant_reply_at"],
                    turn.get("intent"), turn.get("need_memory"),
                    turn.get("memory_type"), turn.get("ai_summary"),
                    turn.get("perception_at"),
                    json.dumps(turn.get("memories_used", []), ensure_ascii=False),
                    turn.get("memories_used_at"),
                    turn.get("raw_response"), turn.get("raw_response_at"),
                    turn.get("verification_result"), turn.get("verification_result_at"),
                    turn.get("final_response"), turn.get("final_response_at"),
                    turn.get("thinking_notes"), turn.get("thinking_notes_at"),
                    turn.get("completed_at"),
                    turn.get("input_type", "text"),
                    turn.get("file_path", ""),
                    turn.get("file_data"),
                    json.dumps(turn.get("tool_results", []), ensure_ascii=False),
                ),
            )
        conn.commit()
    finally:
        conn.close()

def save_session_tag(session_id: str, tag: str, summary: str = "", owner_id: int = 1):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO session_tags (owner_id, session_id, tag, summary, created_at) "
                "VALUES (%s, %s, %s, %s, %s)",
                (owner_id, session_id, tag, summary, get_now()),
            )
        conn.commit()
    finally:
        conn.close()

def load_existing_tags(limit: int = 50, owner_id: int | None = None) -> list[str]:
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            if owner_id is not None:
                cur.execute(
                    "SELECT DISTINCT tag FROM session_tags WHERE owner_id = %s "
                    "ORDER BY tag LIMIT %s",
                    (owner_id, limit),
                )
            else:
                cur.execute(
                    "SELECT DISTINCT tag FROM session_tags "
                    "ORDER BY tag LIMIT %s",
                    (limit,),
                )
            return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()

def save_session_summary(session_id: str, intent_summary: str, owner_id: int = 1):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO session_summaries (owner_id, session_id, intent_summary, created_at) "
                "VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (session_id) DO UPDATE SET intent_summary = EXCLUDED.intent_summary",
                (owner_id, session_id, intent_summary, get_now()),
            )
        conn.commit()
    finally:
        conn.close()

def search_sessions_by_tag(tag_keyword: str, limit: int = 10, owner_id: int | None = None) -> list[dict]:
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            conditions = ["tag LIKE %s"]
            params: list = [f"%{tag_keyword}%"]
            if owner_id is not None:
                conditions.append("owner_id = %s")
                params.append(owner_id)
            params.append(limit)
            cur.execute(
                f"SELECT session_id, tag, summary, created_at "
                f"FROM session_tags "
                f"WHERE {' AND '.join(conditions)} "
                f"ORDER BY created_at DESC LIMIT %s",
                params,
            )
            return list(cur.fetchall())
    finally:
        conn.close()
