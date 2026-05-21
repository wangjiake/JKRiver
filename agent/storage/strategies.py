from datetime import timedelta

from psycopg2.extras import RealDictCursor
from agent.utils.time_context import get_now
from ._db import get_db_connection


def save_strategy(hypothesis_category: str, hypothesis_subject: str,
                  strategy_type: str, description: str,
                  trigger_condition: str, approach: str,
                  priority: float = 0.5, expires_days: int = 30,
                  reference_time=None, owner_id: int = 1):
    now = reference_time if reference_time else get_now()
    expires_at = now + timedelta(days=expires_days) if expires_days > 0 else None
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM strategies "
                "WHERE owner_id = %s AND hypothesis_category = %s AND hypothesis_subject = %s "
                "AND strategy_type = %s AND status = 'pending'",
                (owner_id, hypothesis_category, hypothesis_subject, strategy_type),
            )
            if cur.fetchone():
                return False

            cur.execute(
                "SELECT COUNT(*) FROM strategies WHERE status = 'pending' AND owner_id = %s",
                (owner_id,),
            )
            if cur.fetchone()[0] >= 30:
                return False

            cur.execute(
                "INSERT INTO strategies "
                "(owner_id, hypothesis_category, hypothesis_subject, strategy_type, description, "
                " trigger_condition, approach, priority, status, created_at, expires_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s, %s)",
                (owner_id, hypothesis_category, hypothesis_subject, strategy_type, description,
                 trigger_condition, approach, priority, now, expires_at),
            )
        conn.commit()
        return True
    finally:
        conn.close()


def load_pending_strategies(topic_keywords: list[str] | None = None,
                            owner_id: int | None = None) -> list[dict]:
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            conditions = [
                "status = 'pending'",
                "(expires_at IS NULL OR expires_at > %s)",
            ]
            params: list = [get_now()]

            if owner_id is not None:
                conditions.append("owner_id = %s")
                params.append(owner_id)

            if topic_keywords:
                keyword_conditions = []
                for kw in topic_keywords:
                    keyword_conditions.append("trigger_condition LIKE %s")
                    params.append(f"%{kw}%")
                conditions.append("(" + " OR ".join(keyword_conditions) + ")")

            where = "WHERE " + " AND ".join(conditions)
            cur.execute(
                f"SELECT id, hypothesis_category, hypothesis_subject, strategy_type, "
                f"description, trigger_condition, approach, priority "
                f"FROM strategies {where} "
                f"ORDER BY priority DESC",
                params,
            )
            return list(cur.fetchall())
    finally:
        conn.close()


def mark_strategy_executed(strategy_id: int, result: str):
    now = get_now()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE strategies SET status = 'executed', result = %s, executed_at = %s "
                "WHERE id = %s",
                (result, now, strategy_id),
            )
        conn.commit()
    finally:
        conn.close()
