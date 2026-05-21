import logging

from psycopg2.extras import RealDictCursor
from agent.utils.time_context import get_now
from ._db import get_db_connection
from ._synonyms import _get_subject_synonyms

logger = logging.getLogger(__name__)

DEFAULT_SUMMARY_LIMIT_BEFORE = 30
DEFAULT_SUMMARY_LIMIT_AFTER = 50


def load_conversation_summaries_around(pivot_time,
                                       limit_before=DEFAULT_SUMMARY_LIMIT_BEFORE,
                                       limit_after=DEFAULT_SUMMARY_LIMIT_AFTER,
                                       owner_id: int | None = None) -> dict:
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            before_conditions = ["user_input_at < %s", "ai_summary IS NOT NULL"]
            before_params: list = [pivot_time]
            if owner_id is not None:
                before_conditions.append("owner_id = %s")
                before_params.append(owner_id)
            before_params.append(limit_before)
            cur.execute(
                f"SELECT ai_summary, intent, user_input_at, session_id "
                f"FROM conversation_turns "
                f"WHERE {' AND '.join(before_conditions)} "
                f"ORDER BY user_input_at DESC LIMIT %s",
                before_params,
            )
            before = list(reversed(cur.fetchall()))

            after_conditions = ["user_input_at >= %s", "ai_summary IS NOT NULL"]
            after_params: list = [pivot_time]
            if owner_id is not None:
                after_conditions.append("owner_id = %s")
                after_params.append(owner_id)
            after_params.append(limit_after)
            cur.execute(
                f"SELECT ai_summary, intent, user_input_at, session_id "
                f"FROM conversation_turns "
                f"WHERE {' AND '.join(after_conditions)} "
                f"ORDER BY user_input_at ASC LIMIT %s",
                after_params,
            )
            after = list(cur.fetchall())

        return {"before": before, "after": after}
    finally:
        conn.close()


def load_summaries_by_observation_subject(subject: str, pivot_time=None,
                                          owner_id: int | None = None) -> dict:
    subject_syns = list(_get_subject_synonyms(subject))

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            obs_conditions = [
                "rejected = false",
                "("
                "   subject = ANY(%s) "
                "   OR subject ILIKE '%%' || %s || '%%' "
                "   OR %s ILIKE '%%' || subject || '%%'"
                ")",
            ]
            obs_params: list = [subject_syns, subject, subject]
            if owner_id is not None:
                obs_conditions.append("owner_id = %s")
                obs_params.append(owner_id)
            cur.execute(
                f"SELECT DISTINCT session_id FROM observations "
                f"WHERE {' AND '.join(obs_conditions)}",
                obs_params,
            )
            session_ids = [r["session_id"] for r in cur.fetchall()]

            if not session_ids:
                return {"before": [], "after": []}

            sum_conditions = ["session_id = ANY(%s)", "ai_summary IS NOT NULL"]
            sum_params: list = [session_ids]
            if owner_id is not None:
                sum_conditions.append("owner_id = %s")
                sum_params.append(owner_id)
            cur.execute(
                f"SELECT ai_summary, intent, user_input_at, session_id "
                f"FROM conversation_turns "
                f"WHERE {' AND '.join(sum_conditions)} "
                f"ORDER BY user_input_at ASC",
                sum_params,
            )
            all_summaries = list(cur.fetchall())
    finally:
        conn.close()

    if not pivot_time:
        return {"before": all_summaries, "after": []}

    before, after = [], []
    for s in all_summaries:
        s_time = s.get("user_input_at")
        if not s_time:
            before.append(s)
            continue
        if s_time < pivot_time:
            before.append(s)
        else:
            after.append(s)
    return {"before": before, "after": after}


def save_memory_snapshot(text: str, profile_count: int = 0, owner_id: int = 1):
    """保存预编译的记忆快照"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "CREATE TABLE IF NOT EXISTS memory_snapshot ("
                "  id SERIAL PRIMARY KEY,"
                "  snapshot_text TEXT NOT NULL,"
                "  profile_count INTEGER DEFAULT 0,"
                "  created_at TIMESTAMPTZ DEFAULT NOW()"
                ")"
            )
            cur.execute(
                "INSERT INTO memory_snapshot (owner_id, snapshot_text, profile_count) "
                "VALUES (%s, %s, %s)",
                (owner_id, text, profile_count),
            )
        conn.commit()
    finally:
        conn.close()


def load_memory_snapshot(owner_id: int | None = None) -> dict | None:
    """加载最新快照，返回 {"snapshot_text": str, "profile_count": int, "created_at": datetime}"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                if owner_id is not None:
                    cur.execute(
                        "SELECT snapshot_text, profile_count, created_at "
                        "FROM memory_snapshot WHERE owner_id = %s "
                        "ORDER BY id DESC LIMIT 1",
                        (owner_id,),
                    )
                else:
                    cur.execute(
                        "SELECT snapshot_text, profile_count, created_at "
                        "FROM memory_snapshot ORDER BY id DESC LIMIT 1"
                    )
            except Exception:
                logger.error("load_memory_snapshot query failed", exc_info=True)
                conn.rollback()
                return None
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def save_fact_edge(source_fact_id: int, target_fact_id: int,
                   edge_type: str, description: str = "",
                   confidence: float = 0.8, owner_id: int = 1) -> int:
    now = get_now()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO fact_edges "
                "(owner_id, source_fact_id, target_fact_id, edge_type, description, confidence, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (source_fact_id, target_fact_id, edge_type) DO UPDATE "
                "SET description = EXCLUDED.description, confidence = EXCLUDED.confidence, "
                "updated_at = EXCLUDED.updated_at "
                "RETURNING id",
                (owner_id, source_fact_id, target_fact_id, edge_type, description, confidence, now, now),
            )
            row = cur.fetchone()
            edge_id = row[0] if row else -1
        conn.commit()
        return edge_id
    except Exception:
        logger.error("save_fact_edge failed (src=%s, tgt=%s)", source_fact_id, target_fact_id, exc_info=True)
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()


def load_fact_edges(fact_ids: list[int] | None = None,
                    owner_id: int | None = None) -> list[dict]:
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                if fact_ids:
                    conditions = ["(fe.source_fact_id = ANY(%s) OR fe.target_fact_id = ANY(%s))"]
                    params: list = [fact_ids, fact_ids]
                    if owner_id is not None:
                        conditions.append("fe.owner_id = %s")
                        params.append(owner_id)
                    cur.execute(
                        "SELECT fe.id, fe.source_fact_id, fe.target_fact_id, "
                        "fe.edge_type, fe.description, fe.confidence, "
                        "src.category AS src_category, src.subject AS src_subject, "
                        "tgt.category AS tgt_category, tgt.subject AS tgt_subject "
                        "FROM fact_edges fe "
                        "JOIN user_profile src ON fe.source_fact_id = src.id "
                        "JOIN user_profile tgt ON fe.target_fact_id = tgt.id "
                        f"WHERE {' AND '.join(conditions)} "
                        "ORDER BY fe.confidence DESC, fe.updated_at DESC",
                        params,
                    )
                else:
                    conditions = []
                    params = []
                    if owner_id is not None:
                        conditions.append("fe.owner_id = %s")
                        params.append(owner_id)
                    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
                    cur.execute(
                        "SELECT fe.id, fe.source_fact_id, fe.target_fact_id, "
                        "fe.edge_type, fe.description, fe.confidence, "
                        "src.category AS src_category, src.subject AS src_subject, "
                        "tgt.category AS tgt_category, tgt.subject AS tgt_subject "
                        "FROM fact_edges fe "
                        "JOIN user_profile src ON fe.source_fact_id = src.id "
                        "JOIN user_profile tgt ON fe.target_fact_id = tgt.id "
                        f"{where} "
                        "ORDER BY fe.confidence DESC, fe.updated_at DESC "
                        "LIMIT 50",
                        params,
                    )
                return [dict(r) for r in cur.fetchall()]
            except Exception:
                logger.error("load_fact_edges query failed", exc_info=True)
                raise
    finally:
        conn.close()


def delete_fact_edges_for(fact_id: int, owner_id: int | None = None):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            try:
                if owner_id is not None:
                    cur.execute(
                        "DELETE FROM fact_edges WHERE (source_fact_id = %s OR target_fact_id = %s) "
                        "AND owner_id = %s",
                        (fact_id, fact_id, owner_id),
                    )
                else:
                    cur.execute(
                        "DELETE FROM fact_edges WHERE source_fact_id = %s OR target_fact_id = %s",
                        (fact_id, fact_id),
                    )
            except Exception:
                logger.error("delete_fact_edges_for failed (fact_id=%s)", fact_id, exc_info=True)
                raise
        conn.commit()
    finally:
        conn.close()
