from datetime import timedelta

from psycopg2.extras import RealDictCursor
from agent.utils.time_context import get_now
from ._db import get_db_connection


def save_event(category: str, summary: str, session_id: str | None = None,
               importance: float | None = None, decay_days: int | None = None,
               reference_time=None):
    if importance is None:
        importance = 0.5

    now = reference_time if reference_time else get_now()
    if decay_days and decay_days > 0:
        expires_at = now + timedelta(days=decay_days)
    else:
        expires_at = None

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, summary FROM event_log "
                "WHERE category = %s "
                "AND (expires_at IS NULL OR expires_at > %s) "
                "ORDER BY created_at DESC LIMIT 5",
                (category, now),
            )
            rows = cur.fetchall()

            existing_id = None
            for row_id, row_summary in rows:
                if _is_similar_event(row_summary, summary):
                    existing_id = row_id
                    break

            if existing_id:
                cur.execute(
                    "UPDATE event_log SET expires_at = %s, importance = %s WHERE id = %s",
                    (expires_at, importance, existing_id),
                )
            else:
                cur.execute(
                    "INSERT INTO event_log (category, summary, importance, expires_at, source_session, created_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (category, summary, importance, expires_at, session_id, now),
                )
        conn.commit()
    finally:
        conn.close()

def _is_similar_event(existing: str, new: str) -> bool:
    STOPWORDS = [
        "用户", "的", "是", "了", "在", "很", "比较", "非常",
        "喜欢", "感兴趣", "关注", "。", "，",
        "the", "a", "an", "is", "are", "was", "were", "be",
        "user", "very", "really", "quite", "interested", "in",
        "ユーザー", "の", "は", "が", "を", "に", "で", "と",
        "とても", "非常に", "かなり",
        " ", ".", ",",
    ]
    def clean(s):
        s = s.strip()
        for w in STOPWORDS:
            s = s.replace(w, "")
        return s
    a, b = clean(existing), clean(new)
    if not a or not b:
        return False
    return a == b or a in b or b in a

def load_active_events(top_k: int = 10, category: str | None = None) -> list[dict]:
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            conditions = ["(expires_at IS NULL OR expires_at > %s)"]
            params: list = [get_now()]
            if category:
                conditions.append("category = %s")
                params.append(category)
            where = "WHERE " + " AND ".join(conditions)
            params.append(top_k)
            cur.execute(
                f"SELECT id, category, summary, importance, expires_at, created_at "
                f"FROM event_log {where} "
                f"ORDER BY importance DESC, created_at DESC "
                f"LIMIT %s",
                params,
            )
            return list(cur.fetchall())
    finally:
        conn.close()
