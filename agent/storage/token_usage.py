import logging

from ._db import get_db_connection

logger = logging.getLogger(__name__)


def record_usage(model: str, prompt_tokens: int, completion_tokens: int,
                 total_tokens: int, source: str = "chat", owner_id: int = 1):
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO token_usage (owner_id, model, prompt_tokens, completion_tokens, total_tokens, source)"
                " VALUES (%s, %s, %s, %s, %s, %s)",
                (owner_id, model, prompt_tokens, completion_tokens, total_tokens, source),
            )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.debug("token_usage record failed: %s", e)


def get_stats(timezone: str = "UTC", owner_id: int | None = None) -> dict:
    """Return token usage totals for today / this week / this month in the given timezone.

    If owner_id is provided, scope the stats to that owner only.
    """
    def row(r):
        return {"prompt": int(r[0]), "completion": int(r[1]), "total": int(r[2])}

    empty = {"prompt": 0, "completion": 0, "total": 0}
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            tz = timezone.replace("'", "")  # basic sanitize
            owner_clause = " AND owner_id = %s" if owner_id is not None else ""
            extra_params: tuple = (owner_id,) if owner_id is not None else ()
            cur.execute(f"""
                SELECT
                    COALESCE(SUM(CASE WHEN created_at AT TIME ZONE %s >= DATE_TRUNC('day',   NOW() AT TIME ZONE %s) THEN prompt_tokens     ELSE 0 END), 0),
                    COALESCE(SUM(CASE WHEN created_at AT TIME ZONE %s >= DATE_TRUNC('day',   NOW() AT TIME ZONE %s) THEN completion_tokens ELSE 0 END), 0),
                    COALESCE(SUM(CASE WHEN created_at AT TIME ZONE %s >= DATE_TRUNC('day',   NOW() AT TIME ZONE %s) THEN total_tokens      ELSE 0 END), 0),
                    COALESCE(SUM(CASE WHEN created_at AT TIME ZONE %s >= DATE_TRUNC('week',  NOW() AT TIME ZONE %s) THEN prompt_tokens     ELSE 0 END), 0),
                    COALESCE(SUM(CASE WHEN created_at AT TIME ZONE %s >= DATE_TRUNC('week',  NOW() AT TIME ZONE %s) THEN completion_tokens ELSE 0 END), 0),
                    COALESCE(SUM(CASE WHEN created_at AT TIME ZONE %s >= DATE_TRUNC('week',  NOW() AT TIME ZONE %s) THEN total_tokens      ELSE 0 END), 0),
                    COALESCE(SUM(CASE WHEN created_at AT TIME ZONE %s >= DATE_TRUNC('month', NOW() AT TIME ZONE %s) THEN prompt_tokens     ELSE 0 END), 0),
                    COALESCE(SUM(CASE WHEN created_at AT TIME ZONE %s >= DATE_TRUNC('month', NOW() AT TIME ZONE %s) THEN completion_tokens ELSE 0 END), 0),
                    COALESCE(SUM(CASE WHEN created_at AT TIME ZONE %s >= DATE_TRUNC('month', NOW() AT TIME ZONE %s) THEN total_tokens      ELSE 0 END), 0)
                FROM token_usage
                WHERE created_at >= DATE_TRUNC('month', NOW() AT TIME ZONE %s) AT TIME ZONE %s
                {owner_clause}
            """, (tz,) * 20 + extra_params)
            r = cur.fetchone()
        conn.close()
        return {
            "today": row(r[0:3]),
            "week":  row(r[3:6]),
            "month": row(r[6:9]),
        }
    except Exception as e:
        logger.debug("token_usage get_stats failed: %s", e)
        return {"today": empty, "week": empty, "month": empty}
