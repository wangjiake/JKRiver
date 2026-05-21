
import logging
import asyncio
from agent.config import load_config
from agent.config.prompts import get_labels
from agent.storage import get_db_connection, transaction
from agent.sleep._parsing import LLMPipelineError
from agent.sleep._data_access import get_unprocessed_conversations, list_owners_with_unprocessed
from agent.sleep._pipeline_state import _PipelineState
from agent.sleep._utils import _safe_int
from agent.sleep.steps_extract import (
    _step_load_initial, _SKIP_EXTRACT_PREFIXES, _step_extract_sessions, _obs_query,
)
from agent.sleep.steps_analyze import (
    RECENT_PROFILE_LOOKBACK_DAYS,
    _step_analyze_behavior,
    _step_classify_and_integrate,
    _step_cross_verify,
    _step_resolve_disputes,
)
from agent.sleep.steps_maintain import (
    _step_extract_edges, _step_expire_facts, _step_maturity_decay,
)
from agent.sleep.steps_output import (
    _step_user_model, _step_trajectory, _step_consolidate,
    _step_snapshot, _step_finalize,
)

logger = logging.getLogger(__name__)

# Re-export all step functions and constants so that existing imports
# like ``from agent.sleep.orchestration import _step_extract_sessions``
# continue to work.
__all__ = [
    "run", "run_async",
    "_safe_int", "RECENT_PROFILE_LOOKBACK_DAYS",
    "_SKIP_EXTRACT_PREFIXES", "_obs_query",
    "_step_load_initial", "_step_extract_sessions",
    "_step_analyze_behavior", "_step_classify_and_integrate",
    "_step_cross_verify", "_step_resolve_disputes",
    "_step_extract_edges", "_step_expire_facts", "_step_maturity_decay",
    "_step_user_model", "_step_trajectory", "_step_consolidate",
    "_step_snapshot", "_step_finalize",
]


def run():
    config = load_config()
    config.setdefault("llm", {})["_source"] = "sleep"
    language = config.get("language", "en")
    L = get_labels("context.labels", language)

    owners = list_owners_with_unprocessed()
    if not owners:
        return

    for owner_id in owners:
        session_convs = get_unprocessed_conversations(owner_id=owner_id)
        if not session_convs:
            continue
        logger.info("Sleep pipeline: starting for owner_id=%s (%d sessions)", owner_id, len(session_convs))
        try:
            _run_sleep_pipeline(session_convs, config, language, L, owner_id=owner_id)
        except Exception:
            logger.error("Sleep pipeline failed for owner_id=%s — skipping to next owner", owner_id, exc_info=True)
            continue

        # Non-critical post-processing (outside transaction). Per-owner.
        try:
            from agent.utils.embedding import embed_all_memories
            embed_all_memories(config, owner_id=owner_id)
        except Exception as e:
            logger.warning("Embedding failed for owner_id=%s (non-critical): %s", owner_id, e)

        try:
            from agent.utils.clustering import cluster_memories
            cluster_memories(config, owner_id=owner_id)
        except Exception:
            logger.warning("Clustering failed for owner_id=%s (non-critical)", owner_id, exc_info=True)


def _run_sleep_pipeline(session_convs, config, language, L, owner_id: int = 1):
    """Core sleep pipeline — all DB writes are atomic via transaction().

    The transaction() context manager makes get_db_connection() return a
    proxy that suppresses per-call commit/close.  If anything raises, the
    entire batch is rolled back so the database stays consistent.

    Idempotency: mark_processed() runs last (_step_finalize).  If the
    pipeline crashes mid-way, the transaction rolls back and the same
    sessions will be re-processed on the next run (at-least-once).  This
    is safe because all steps are pure DB operations with no external
    side effects (no webhooks, no notifications).
    """
    # Attribute LLM token usage of this pipeline run to the owner.
    config.setdefault("llm", {})["_owner_id"] = owner_id
    with transaction():
        _run_sleep_pipeline_inner(session_convs, config, language, L, owner_id=owner_id)


def _run_sleep_pipeline_inner(session_convs, config, language, L, owner_id: int = 1):
    state = _PipelineState(
        session_convs=session_convs, config=config,
        language=language, L=L, owner_id=owner_id,
    )
    steps = [
        ("load_initial", _step_load_initial),
        ("extract_sessions", _step_extract_sessions),
        ("analyze_behavior", _step_analyze_behavior),
        ("classify_and_integrate", _step_classify_and_integrate),
        ("cross_verify", _step_cross_verify),
        ("resolve_disputes", _step_resolve_disputes),
        ("extract_edges", _step_extract_edges),
        ("expire_facts", _step_expire_facts),
        ("maturity_decay", _step_maturity_decay),
        ("user_model", _step_user_model),
        ("trajectory", _step_trajectory),
        ("consolidate", _step_consolidate),
        ("snapshot", _step_snapshot),
        ("finalize", _step_finalize),
    ]
    for step_name, step_fn in steps:
        try:
            step_fn(state)
        except LLMPipelineError:
            logger.error("Sleep pipeline aborted at step '%s': LLM unavailable", step_name)
            raise
        except Exception:
            logger.error("Sleep pipeline failed at step '%s'", step_name, exc_info=True)
            raise


async def run_async():
    """Async entry point — delegates to sync pipeline in a thread for transaction safety.

    Iterates over each owner that has unprocessed conversations and runs the
    pipeline (plus per-owner post-processing) for each in turn.
    """
    config = load_config()
    language = config.get("language", "en")
    L = get_labels("context.labels", language)

    owners = await asyncio.to_thread(list_owners_with_unprocessed)
    if not owners:
        return

    for owner_id in owners:
        session_convs = await asyncio.to_thread(get_unprocessed_conversations, owner_id)
        if not session_convs:
            continue
        logger.info("Sleep pipeline (async): starting for owner_id=%s (%d sessions)", owner_id, len(session_convs))
        try:
            await asyncio.to_thread(
                _run_sleep_pipeline, session_convs, config, language, L, owner_id,
            )
        except Exception:
            logger.error("Sleep pipeline failed for owner_id=%s — skipping", owner_id, exc_info=True)
            continue

        # Non-critical post-processing, per owner.
        try:
            from agent.utils.embedding import embed_all_memories
            await asyncio.to_thread(embed_all_memories, config, owner_id)
        except Exception:
            logger.warning("Embedding failed for owner_id=%s (non-critical, async)", owner_id, exc_info=True)

        try:
            from agent.utils.clustering import cluster_memories
            await asyncio.to_thread(cluster_memories, config, owner_id)
        except Exception:
            logger.warning("Clustering failed for owner_id=%s (non-critical, async)", owner_id, exc_info=True)
