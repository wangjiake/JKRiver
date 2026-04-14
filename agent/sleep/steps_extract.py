
import logging
from agent.utils.profile_filter import prepare_profile
from agent.storage import (
    save_event, save_session_tag, save_session_summary,
    save_observation,
    load_full_current_profile, load_trajectory_summary,
    save_or_update_relationship,
)
from agent.sleep._pipeline_state import _PipelineState
from agent.sleep.extractors import extract_observations_and_tags, extract_events

logger = logging.getLogger(__name__)

_SKIP_EXTRACT_PREFIXES = ("outsource:", "dispatch_task:", "task_agent:")


def _step_load_initial(state: _PipelineState):
    """Load existing profile and trajectory."""
    state.existing_profile = load_full_current_profile(exclude_superseded=True)
    state.trajectory = load_trajectory_summary()
    if not (state.trajectory and state.trajectory.get("life_phase")):
        state.trajectory = None


def _step_extract_sessions(state: _PipelineState):
    """Extract observations, tags, events from each session."""
    total_session_count = len(state.session_convs)
    for session_idx, (session_id, convs) in enumerate(state.session_convs.items(), 1):
        msg_ids = [c["id"] for c in convs]
        state.all_msg_ids.extend(msg_ids)
        state.all_convs.extend(convs)

        # Skip deep analysis for outsource/tool sessions — no personal info to extract
        session_intents = [c.get("intent", "") or "" for c in convs]
        if any(i.startswith(_SKIP_EXTRACT_PREFIXES) for i in session_intents):
            continue

        extract_profile, _ = prepare_profile(
            state.existing_profile, max_entries=25, language=state.language,
        )
        result = extract_observations_and_tags(
            convs, state.config, existing_profile=extract_profile,
        )
        observations_raw = result.get("observations", [])
        tags = result.get("tags", [])
        relationships = result.get("relationships", [])

        observations = []
        third_party_obs = []
        for o in observations_raw:
            about = o.get("about", "user")
            if about == "user" or about == "" or about is None or about == "null":
                observations.append(o)
            else:
                third_party_obs.append(o)

        conv_times = [c["user_input_at"] for c in convs if c.get("user_input_at")]
        session_time = min(conv_times) if conv_times else None
        for o in observations:
            o["_session_order"] = session_idx
            o["_session_total"] = total_session_count
            o["_conv_time"] = session_time

        for o in observations:
            save_observation(
                session_id=session_id,
                observation_type=o["type"],
                content=o["content"],
                subject=o.get("subject"),
                context=o.get("context"),
            )

        for o in third_party_obs:
            save_observation(
                session_id=session_id,
                observation_type=o["type"],
                content=o["content"],
                subject=o.get("subject"),
                context=f"about:{o.get('about', '?')}",
            )

        state.all_observations.extend(observations)

        for r in relationships:
            name = r.get("name")
            relation = r.get("relation", "")
            details = r.get("details", {})
            if relation:
                save_or_update_relationship(name, relation, details)

        for t in tags:
            save_session_tag(session_id, t["tag"], t.get("summary", ""))

        intent_parts = [c.get("intent", "") for c in convs if c.get("intent")]
        if intent_parts:
            intent_summary = " | ".join(intent_parts)
            save_session_summary(session_id, intent_summary)

        events = extract_events(convs, state.config)
        for e in events:
            decay_days = e.get("decay_days")
            importance = e.get("importance")
            save_event(e["category"], e["summary"], session_id,
                       importance=importance, decay_days=decay_days,
                       reference_time=session_time)

    # Reload profile after extraction mutations
    state.current_profile = load_full_current_profile(exclude_superseded=True)


def _obs_query(state: _PipelineState) -> str:
    return " ".join(o.get("subject", "") for o in state.all_observations if o.get("subject"))
