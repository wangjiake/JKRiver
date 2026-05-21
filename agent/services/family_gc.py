"""Background GC for family auth tables.

Runs daily inside the FastAPI lifespan. Cleans up:
  * access_tokens: hard-DELETE rows revoked more than RETAIN_DAYS days ago
  * family_invites: DELETE rows expired more than INVITE_RETAIN_DAYS days ago
  * family_audit: cap log size at AUDIT_MAX_ROWS, oldest pruned

All of these are non-business data so safe to GC.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from agent.storage._db import get_db_connection

logger = logging.getLogger(__name__)

RETAIN_DAYS = 90              # revoked tokens kept this long for audit
INVITE_RETAIN_DAYS = 7        # expired/used invites kept this long
AUDIT_MAX_ROWS = 5000         # roughly 1-2 years for a small family
GC_INTERVAL_SECONDS = 24 * 3600   # daily


def gc_once() -> dict[str, int]:
    """Run one GC pass; returns counts of rows deleted per table."""
    out = {"tokens_deleted": 0, "invites_deleted": 0, "audit_pruned": 0}
    try:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM access_tokens "
                    "WHERE revoked_at IS NOT NULL "
                    "  AND revoked_at < NOW() - INTERVAL '%s days'" % RETAIN_DAYS
                )
                out["tokens_deleted"] = cur.rowcount

                cur.execute(
                    "DELETE FROM family_invites "
                    "WHERE (used_at IS NOT NULL OR expires_at < NOW()) "
                    "  AND created_at < NOW() - INTERVAL '%s days'" % INVITE_RETAIN_DAYS
                )
                out["invites_deleted"] = cur.rowcount

                cur.execute("SELECT COUNT(*) FROM family_audit")
                count = cur.fetchone()[0]
                if count > AUDIT_MAX_ROWS:
                    excess = count - AUDIT_MAX_ROWS
                    cur.execute(
                        "DELETE FROM family_audit WHERE id IN ("
                        "  SELECT id FROM family_audit ORDER BY at ASC LIMIT %s)",
                        (excess,),
                    )
                    out["audit_pruned"] = cur.rowcount
            conn.commit()
        finally:
            conn.close()
        if any(out.values()):
            logger.info("family GC: %s", out)
    except Exception:
        logger.warning("family GC failed", exc_info=True)
    return out


async def gc_loop():
    """Run gc_once forever at GC_INTERVAL_SECONDS cadence."""
    # Slight initial delay so it doesn't compete with app startup.
    await asyncio.sleep(60)
    while True:
        try:
            await asyncio.to_thread(gc_once)
        except Exception:
            logger.warning("family GC loop iteration failed", exc_info=True)
        await asyncio.sleep(GC_INTERVAL_SECONDS)
