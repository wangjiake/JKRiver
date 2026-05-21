
import logging
from agent.storage import (
    load_full_current_profile,
    save_strategy,
    close_time_period,
    get_expired_facts, update_fact_decay,
    delete_fact_edges_for,
)
from agent.sleep._maturity import _calculate_maturity_decay
from agent.sleep._pipeline_state import _PipelineState
from agent.sleep.trajectory import extract_fact_edges

logger = logging.getLogger(__name__)


def _step_extract_edges(state: _PipelineState):
    """Extract fact edges for the knowledge network."""
    if not state.affected_fact_ids:
        return
    try:
        edge_profile = load_full_current_profile(owner_id=state.owner_id)
        extract_fact_edges(state.affected_fact_ids, edge_profile, state.config,
                           owner_id=state.owner_id)
    except Exception:
        state.pipeline_errors += 1
        logger.error("Extract fact edges failed", exc_info=True)


def _step_expire_facts(state: _PipelineState):
    """Close expired facts and create verify strategies."""
    expired_facts = get_expired_facts(reference_time=state.latest_conv_time, owner_id=state.owner_id)
    if not expired_facts:
        return

    for f in expired_facts:
        if f.get("superseded_by") or f.get("supersedes"):
            continue

        close_time_period(f["id"], end_time=state.latest_conv_time)
        try:
            delete_fact_edges_for(f["id"], owner_id=state.owner_id)
        except Exception:
            logger.error("Delete edges for expired fact %s failed", f["id"], exc_info=True)
        try:
            save_strategy(
                hypothesis_category=f["category"],
                hypothesis_subject=f["subject"],
                strategy_type="verify",
                description=state.L["strategy_expired_desc"].format(subj=f["subject"]),
                trigger_condition=state.L["strategy_topic_trigger"].format(subj=f["subject"]),
                approach=state.L["strategy_verify_approach"].format(subj=f["subject"]),
                reference_time=state.latest_conv_time,
                owner_id=state.owner_id,
            )
        except Exception:
            state.pipeline_errors += 1
            logger.error("Save expired-fact strategy failed", exc_info=True)


def _step_maturity_decay(state: _PipelineState):
    """Update decay values based on fact maturity."""
    key_anchors = []
    if state.trajectory and state.trajectory.get("key_anchors"):
        key_anchors = [str(a).lower() for a in state.trajectory["key_anchors"]]

    all_living = load_full_current_profile(owner_id=state.owner_id)

    for f in all_living:
        start = f.get("start_time")
        updated = f.get("updated_at")
        if not start or not updated:
            continue
        span_days = (updated - start).days
        ev = f.get("evidence", [])
        evidence_count = len(ev) if isinstance(ev, list) else 0
        current_decay = f.get("decay_days") or 90

        subj_lower = (f.get("subject") or "").lower()
        value_lower = (f.get("value") or "").lower()
        in_anchors = any(subj_lower in a or value_lower in a or a in subj_lower or a in value_lower
                         for a in key_anchors)

        new_decay = _calculate_maturity_decay(span_days, evidence_count, current_decay, in_anchors)
        if new_decay > current_decay:
            update_fact_decay(f["id"], new_decay, reference_time=state.latest_conv_time)
