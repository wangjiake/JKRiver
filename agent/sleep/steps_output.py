
import logging
from agent.utils.profile_filter import prepare_profile, format_profile_text
from agent.storage import (
    get_db_connection,
    load_full_current_profile,
    upsert_user_model, load_user_model,
    save_trajectory_summary, load_active_events,
    load_relationships,
    save_memory_snapshot,
    load_fact_edges,
)
from agent.storage._synonyms import is_significant_category
from agent.sleep._pipeline_state import _PipelineState
from agent.sleep._data_access import mark_processed, _consolidate_profile
from agent.sleep.analysis import analyze_user_model
from agent.sleep.trajectory import generate_trajectory_summary
from agent.sleep.steps_extract import _obs_query

logger = logging.getLogger(__name__)


def _step_user_model(state: _PipelineState):
    """Analyze communication style and update user model."""
    if not state.all_convs:
        return

    obs_query = _obs_query(state)
    model_profile, _ = prepare_profile(
        state.current_profile, query_text=obs_query, max_entries=20,
        language=state.language,
    )
    model_convs = state.all_convs[-50:] if len(state.all_convs) > 50 else state.all_convs
    model_results = analyze_user_model(model_convs, state.config,
                                       current_profile=model_profile,
                                       owner_id=state.owner_id)
    for m in model_results:
        upsert_user_model(
            dimension=m["dimension"],
            assessment=m["assessment"],
            evidence_summary=m.get("evidence", ""),
            owner_id=state.owner_id,
        )


def _step_trajectory(state: _PipelineState):
    """Update trajectory summary when appropriate."""
    should_update_trajectory = False
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(DISTINCT session_id) FROM raw_conversations "
            "WHERE processed = TRUE AND owner_id = %s",
            (state.owner_id,),
        )
        total_sessions = cur.fetchone()[0] + len(state.session_convs)

    prev_session_count = state.trajectory.get("session_count", 0) if state.trajectory else 0
    sessions_since_update = total_sessions - prev_session_count

    has_significant_change = (
        state.confirmed_count > 0
        or state.dispute_resolved > 0
        or any(o.get("type") == "contradiction" for o in state.all_observations)
        or any(
            is_significant_category(item.get("category", ""))
            for item in state.changed_items
        )
    )

    if has_significant_change and sessions_since_update >= 2:
        should_update_trajectory = True
    elif sessions_since_update >= 10:
        should_update_trajectory = True

    if not state.trajectory and state.current_profile:
        should_update_trajectory = True

    if should_update_trajectory and state.current_profile:
        trajectory_result = generate_trajectory_summary(
            state.current_profile, state.config,
            new_observations=state.all_observations,
            owner_id=state.owner_id,
        )
        if trajectory_result and trajectory_result.get("life_phase"):
            try:
                save_trajectory_summary(trajectory_result, session_count=total_sessions,
                                        owner_id=state.owner_id)
            except Exception as e:
                state.pipeline_errors += 1
                logger.error("Save trajectory failed: %s", e)


def _step_consolidate(state: _PipelineState):
    """Dedup profile when new facts were created or disputes resolved."""
    if state.new_fact_count > 0 or state.dispute_resolved > 0:
        _consolidate_profile(owner_id=state.owner_id)


def _step_snapshot(state: _PipelineState):
    """Generate memory snapshot."""
    try:
        final_profile = load_full_current_profile(exclude_superseded=True, owner_id=state.owner_id)
        snapshot_text = format_profile_text(
            final_profile, max_entries=40, detail="full", language=state.language,
        )

        user_model = load_user_model(owner_id=state.owner_id)
        if user_model:
            model_lines = [f"  {m['dimension']}: {m['assessment']}" for m in user_model]
            snapshot_text += f"\n\n{state.L['section_user_traits']}\n" + "\n".join(model_lines)

        snapshot_events = load_active_events(top_k=5, owner_id=state.owner_id)
        if snapshot_events:
            event_lines = [f"  [{e['category']}] {e['summary']}" for e in snapshot_events]
            snapshot_text += f"\n\n{state.L['section_events']}\n" + "\n".join(event_lines)

        snapshot_relationships = load_relationships(owner_id=state.owner_id)
        if snapshot_relationships:
            rel_lines = [f"  {r['relation']}: {r.get('name', '?')}" for r in snapshot_relationships[:10]]
            snapshot_text += f"\n\n{state.L['section_relationships']}\n" + "\n".join(rel_lines)

        try:
            snapshot_edges = load_fact_edges(
                [p["id"] for p in final_profile if p.get("id")],
                owner_id=state.owner_id,
            ) if final_profile else []
        except Exception:
            logger.error("Load fact edges for snapshot failed", exc_info=True)
            snapshot_edges = []
        if snapshot_edges:
            edge_lines = [
                f"  [{e.get('src_category','')}/{e.get('src_subject','')}] "
                f"--[{e['edge_type']}]--> "
                f"[{e.get('tgt_category','')}/{e.get('tgt_subject','')}]: "
                f"{e.get('description', '')}"
                for e in snapshot_edges[:15]
            ]
            snapshot_text += f"\n\n{state.L['section_knowledge_network']}\n" + "\n".join(edge_lines)

        save_memory_snapshot(snapshot_text, profile_count=len(final_profile), owner_id=state.owner_id)
    except Exception:
        state.pipeline_errors += 1
        logger.error("Save memory snapshot failed", exc_info=True)


def _step_finalize(state: _PipelineState):
    """Mark processed and log errors."""
    if state.pipeline_errors:
        logger.warning("Sleep pipeline completed with %d error(s)", state.pipeline_errors)
    mark_processed(state.all_msg_ids, owner_id=state.owner_id)
