"""Session management endpoints."""
from fastapi import APIRouter, Request
from agent.storage import get_db_connection
from agent.core.identity import DEFAULT_OWNER_ID

router = APIRouter(tags=["sessions"])


def _owner_id(request: Request) -> int:
    return getattr(request.state, "owner_id", DEFAULT_OWNER_ID)

_SESSION_META_SELECT = (
    "SELECT r.session_id, COUNT(*) as turns, "
    "  MIN(r.user_input_at) as started_at, "
    "  MAX(r.user_input_at) as last_at, "
    "  COALESCE("
    "    m.custom_name,"
    "    (SELECT summary FROM session_tags WHERE session_id = r.session_id ORDER BY created_at DESC LIMIT 1),"
    "    (SELECT user_input FROM raw_conversations WHERE session_id = r.session_id ORDER BY user_input_at ASC LIMIT 1)"
    "  ) as preview, "
    "  COALESCE(m.custom_name, '') as custom_name, "
    "  COALESCE(m.pinned, false) as pinned "
    "FROM raw_conversations r "
    "LEFT JOIN session_meta m ON m.session_id = r.session_id "
    "WHERE m.deleted_at IS NULL AND r.owner_id = %s "
)


def _row_to_session(row):
    return {
        "session_id": row[0],
        "turns": row[1],
        "started_at": row[2].isoformat() if row[2] else None,
        "last_at": row[3].isoformat() if row[3] else None,
        "preview": (row[4] or "")[:80],
        "custom_name": row[5] or "",
        "pinned": row[6],
    }


@router.get("/sessions")
async def list_sessions(request: Request, limit: int = 30, offset: int = 0):
    owner_id = _owner_id(request)
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                _SESSION_META_SELECT +
                "GROUP BY r.session_id, m.custom_name, m.pinned "
                "HAVING COALESCE(m.pinned, false) = false "
                "ORDER BY MIN(r.user_input_at) DESC LIMIT %s OFFSET %s",
                (owner_id, limit, offset),
            )
            rows = cur.fetchall()
        return [_row_to_session(r) for r in rows]
    finally:
        conn.close()


@router.get("/sessions/pinned")
async def list_pinned_sessions(request: Request):
    owner_id = _owner_id(request)
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                _SESSION_META_SELECT +
                "GROUP BY r.session_id, m.custom_name, m.pinned, m.pinned_at "
                "HAVING COALESCE(m.pinned, false) = true "
                "ORDER BY MAX(m.pinned_at) DESC",
                (owner_id,),
            )
            rows = cur.fetchall()
        return [_row_to_session(r) for r in rows]
    finally:
        conn.close()


def _session_belongs_to_owner(cur, session_id: str, owner_id: int) -> bool:
    cur.execute(
        "SELECT 1 FROM raw_conversations WHERE session_id = %s AND owner_id = %s LIMIT 1",
        (session_id, owner_id),
    )
    return cur.fetchone() is not None


@router.post("/sessions/{session_id}/pin")
async def toggle_pin_session(request: Request, session_id: str):
    owner_id = _owner_id(request)
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            if not _session_belongs_to_owner(cur, session_id, owner_id):
                return {"ok": False, "error": "not found"}
            cur.execute(
                "INSERT INTO session_meta (session_id, owner_id, pinned, pinned_at) "
                "VALUES (%s, %s, true, NOW()) "
                "ON CONFLICT (session_id) DO UPDATE SET "
                "  pinned = NOT session_meta.pinned, "
                "  pinned_at = CASE WHEN NOT session_meta.pinned THEN NOW() ELSE session_meta.pinned_at END",
                (session_id, owner_id),
            )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@router.patch("/sessions/{session_id}/rename")
async def rename_session(request: Request, session_id: str, body: dict):
    owner_id = _owner_id(request)
    name = (body.get("name") or "").strip()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            if not _session_belongs_to_owner(cur, session_id, owner_id):
                return {"ok": False, "error": "not found"}
            cur.execute(
                "INSERT INTO session_meta (session_id, owner_id, custom_name) VALUES (%s, %s, %s) "
                "ON CONFLICT (session_id) DO UPDATE SET custom_name = %s",
                (session_id, owner_id, name or None, name or None),
            )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@router.delete("/sessions/{session_id}")
async def delete_session(request: Request, session_id: str):
    owner_id = _owner_id(request)
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            if not _session_belongs_to_owner(cur, session_id, owner_id):
                return {"ok": False, "error": "not found"}
            cur.execute(
                "INSERT INTO session_meta (session_id, owner_id, deleted_at) VALUES (%s, %s, NOW()) "
                "ON CONFLICT (session_id) DO UPDATE SET deleted_at = NOW()",
                (session_id, owner_id),
            )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@router.get("/sessions/search")
async def search_sessions(request: Request, q: str = "", limit: int = 50):
    if not q.strip():
        return []
    owner_id = _owner_id(request)
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT r.session_id, "
                "  COUNT(*) as turns, "
                "  MAX(r.user_input_at) as last_at, "
                "  COALESCE(m.custom_name, "
                "    (SELECT user_input FROM raw_conversations "
                "     WHERE session_id = r.session_id ORDER BY user_input_at ASC LIMIT 1)) as preview, "
                "  SUM(CASE WHEN r.user_input ILIKE %s OR r.assistant_reply ILIKE %s THEN 1 ELSE 0 END) as matches, "
                "  COALESCE(m.custom_name, '') as custom_name, "
                "  COALESCE(m.pinned, false) as pinned "
                "FROM raw_conversations r "
                "LEFT JOIN session_meta m ON m.session_id = r.session_id "
                "WHERE m.deleted_at IS NULL AND r.owner_id = %s "
                "GROUP BY r.session_id, m.custom_name, m.pinned "
                "HAVING SUM(CASE WHEN r.user_input ILIKE %s OR r.assistant_reply ILIKE %s THEN 1 ELSE 0 END) > 0 "
                "ORDER BY MIN(r.user_input_at) DESC LIMIT %s",
                (f"%{q}%", f"%{q}%", owner_id, f"%{q}%", f"%{q}%", limit),
            )
            rows = cur.fetchall()
        return [
            {
                "session_id": row[0],
                "turns": row[1],
                "last_at": row[2].isoformat() if row[2] else None,
                "preview": (row[3] or "")[:80],
                "matches": row[4],
                "custom_name": row[5] or "",
                "pinned": row[6],
            }
            for row in rows
        ]
    finally:
        conn.close()


@router.get("/session/{session_id}/history")
async def session_history(request: Request, session_id: str, limit: int = 100):
    owner_id = _owner_id(request)
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT user_input, assistant_reply, user_input_at "
                "FROM raw_conversations "
                "WHERE session_id = %s AND owner_id = %s "
                "ORDER BY user_input_at ASC LIMIT %s",
                (session_id, owner_id, limit),
            )
            rows = cur.fetchall()
        return [
            {"user": r[0], "agent": r[1], "at": r[2].isoformat() if r[2] else None}
            for r in rows
        ]
    finally:
        conn.close()
