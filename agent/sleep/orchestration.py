
import logging
import asyncio
from datetime import timedelta
from agent.config import load_config
from agent.config.prompts import get_labels
from agent.utils.time_context import get_now
from agent.utils.profile_filter import prepare_profile, format_profile_text
from agent.storage import (
    get_db_connection, transaction, save_event, save_session_tag, save_session_summary,
    save_observation,
    save_profile_fact, close_time_period, confirm_profile_fact,
    add_evidence,
    load_full_current_profile, load_timeline,
    get_expired_facts, update_fact_decay,
    load_suspected_profile,
    load_disputed_facts, resolve_dispute,
    upsert_user_model, load_user_model,
    save_strategy,
    save_trajectory_summary, load_trajectory_summary,
    load_active_events,
    save_or_update_relationship, load_relationships,
    save_memory_snapshot,
    load_fact_edges, delete_fact_edges_for,
)
from agent.storage._synonyms import is_significant_category
from agent.sleep._maturity import _calculate_maturity_decay
from agent.sleep._data_access import (
    get_unprocessed_conversations, mark_processed, _consolidate_profile,
)
from agent.sleep._pipeline_state import _PipelineState, _build_fact_lookup, _find_fact_in_profile
from agent.sleep.extractors import (
    extract_observations_and_tags, extract_events,
    classify_observations, create_new_facts,
)
from agent.sleep.analysis import (
    generate_strategies, analyze_user_model,
    analyze_behavioral_patterns, cross_verify_suspected_facts,
)
from agent.sleep.disputes import resolve_disputes_with_llm
from agent.sleep.trajectory import generate_trajectory_summary, extract_fact_edges

logger = logging.getLogger(__name__)

RECENT_PROFILE_LOOKBACK_DAYS = 90


def run():
    config = load_config()
    language = config.get("language", "en")
    L = get_labels("context.labels", language)

    session_convs = get_unprocessed_conversations()
    if not session_convs:
        return

    _run_sleep_pipeline(session_convs, config, language, L)

    # Non-critical post-processing (outside transaction)
    try:
        from agent.utils.embedding import embed_all_memories
        embed_all_memories(config)
    except Exception as e:
        logger.warning("Embedding failed (non-critical): %s", e)

    try:
        from agent.utils.clustering import cluster_memories
        cluster_memories(config)
    except Exception:
        logger.warning("Clustering failed (non-critical)", exc_info=True)


def _run_sleep_pipeline(session_convs, config, language, L):
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
    with transaction():
        _run_sleep_pipeline_inner(session_convs, config, language, L)


def _run_sleep_pipeline_inner(session_convs, config, language, L):
    state = _PipelineState(
        session_convs=session_convs, config=config,
        language=language, L=L,
    )
    _step_load_initial(state)
    _step_extract_sessions(state)
    _step_analyze_behavior(state)
    _step_classify_and_integrate(state)
    _step_cross_verify(state)
    _step_resolve_disputes(state)
    _step_extract_edges(state)
    _step_expire_facts(state)
    _step_maturity_decay(state)
    _step_user_model(state)
    _step_trajectory(state)
    _step_consolidate(state)
    _step_snapshot(state)
    _step_finalize(state)


# ── Step functions ─────────────────────────────────────────


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


def _step_analyze_behavior(state: _PipelineState):
    """Analyze behavioral patterns with in-memory fact lookup (N+1 fix)."""
    if not state.all_observations:
        return

    obs_query = _obs_query(state)
    behavioral_profile, _ = prepare_profile(
        state.current_profile, query_text=obs_query, max_entries=20,
        language=state.language,
    )
    state.behavioral_signals = analyze_behavioral_patterns(
        state.all_observations, behavioral_profile, state.trajectory, state.config,
    )
    if not state.behavioral_signals:
        return

    _obs_times = [o.get("_conv_time") for o in state.all_observations if o.get("_conv_time")]
    _earliest_time = min(_obs_times) if _obs_times else None

    # Build in-memory lookup to avoid N+1 DB queries
    fact_lookup = _build_fact_lookup(state.current_profile)

    for bs in state.behavioral_signals:
        cat = bs.get('category', '')
        subj = bs.get('subject', '')
        inferred = bs.get('inferred_value', '')
        ev_count = bs.get("evidence_count", 0)

        if cat and subj and inferred:
            existing = _find_fact_in_profile(fact_lookup, cat, subj)
            if not (existing and existing.get("value", "").strip().lower() == inferred.strip().lower()):
                save_profile_fact(
                    category=cat,
                    subject=subj,
                    value=inferred,
                    source_type="inferred",
                    start_time=_earliest_time,
                )

        if ev_count >= 3:
            try:
                save_strategy(
                    hypothesis_category=cat,
                    hypothesis_subject=subj,
                    strategy_type="clarify",
                    description=state.L["strategy_behavioral_desc"].format(subj=subj, inferred=inferred),
                    trigger_condition=state.L["strategy_topic_trigger"].format(subj=subj),
                    approach=state.L["strategy_clarify_approach"].format(inferred=inferred),
                    reference_time=_earliest_time,
                )
            except Exception:
                state.pipeline_errors += 1
                logger.error("Save clarify strategy failed", exc_info=True)


def _step_classify_and_integrate(state: _PipelineState):
    """Classify observations and integrate into profile: supports, contradictions, new facts, strategies."""
    # Reload profile after behavioral analysis mutations
    state.current_profile = load_full_current_profile(exclude_superseded=True)
    timeline = load_timeline()

    _all_conv_times = [o["_conv_time"] for o in state.all_observations if o.get("_conv_time")]
    if not _all_conv_times:
        _all_conv_times = [c["user_input_at"] for c in state.all_convs if c.get("user_input_at")]
    state.latest_conv_time = max(_all_conv_times) if _all_conv_times else None

    if not state.all_observations:
        return

    obs_query = _obs_query(state)

    def _find_fact(fid) -> dict | None:
        if not fid:
            return None
        for p in state.current_profile:
            if p.get("id") == fid:
                return p
        return None

    # Dynamic range for classify_observations
    obs_subjects = set(o.get("subject", "") for o in state.all_observations if o.get("subject"))
    obs_categories = set(o.get("_category", "") or "" for o in state.all_observations)
    has_contradictions = any(o.get("type") == "contradiction" for o in state.all_observations)

    if has_contradictions:
        classify_profile = state.current_profile
    elif len(obs_subjects) <= 3:
        three_months_ago = get_now() - timedelta(days=RECENT_PROFILE_LOOKBACK_DAYS)
        classify_profile = [
            p for p in state.current_profile
            if p.get("subject") in obs_subjects
            or p.get("category") in obs_categories
            or (p.get("updated_at") and p["updated_at"] >= three_months_ago)
        ]
    else:
        classify_profile, _ = prepare_profile(
            state.current_profile, query_text=obs_query, config=state.config,
            max_entries=80, language=state.language,
        )

    classifications = classify_observations(
        state.all_observations, classify_profile, state.config, timeline,
        trajectory=state.trajectory,
    )

    classified_indices = {c.get("obs_index") for c in classifications if c.get("obs_index") is not None}
    all_indices = set(range(len(state.all_observations)))
    missing_indices = all_indices - classified_indices
    if missing_indices:
        for idx in missing_indices:
            obs = state.all_observations[idx]
            if obs.get("type") in ("statement", "contradiction"):
                classifications.append({"obs_index": idx, "action": "new",
                                        "reason": state.L["auto_classify_reason"]})

    supports = [c for c in classifications if c.get("action") == "support"]
    contradictions = [c for c in classifications if c.get("action") == "contradict"]
    evidence_against_list = [c for c in classifications if c.get("action") == "evidence_against"]
    new_obs_cls = [c for c in classifications if c.get("action") == "new"]

    # Collect affected fact_ids for incremental cross_verify / resolve_disputes
    for s in supports:
        fid = s.get("fact_id")
        if fid:
            state.affected_fact_ids.add(fid)
    for c in contradictions:
        fid = c.get("fact_id")
        if fid:
            state.affected_fact_ids.add(fid)
    for ea in evidence_against_list:
        fid = ea.get("fact_id")
        if fid:
            state.affected_fact_ids.add(fid)

    for s in supports:
        fact = _find_fact(s.get("fact_id"))
        if fact:
            _obs_idx = s.get("obs_index")
            _obs_time = state.all_observations[_obs_idx].get("_conv_time") if isinstance(_obs_idx, int) and 0 <= _obs_idx < len(state.all_observations) else state.latest_conv_time
            add_evidence(fact["id"], {"reason": s.get("reason", "")},
                         reference_time=_obs_time)
            save_profile_fact(
                category=fact["category"],
                subject=fact["subject"],
                value=fact["value"],
                source_type=fact.get("source_type", "stated"),
                decay_days=fact.get("decay_days"),
                start_time=_obs_time,
            )

    for ea in evidence_against_list:
        fact = _find_fact(ea.get("fact_id"))
        if fact:
            _ea_idx = ea.get("obs_index")
            _ea_time = state.all_observations[_ea_idx].get("_conv_time") if isinstance(_ea_idx, int) and 0 <= _ea_idx < len(state.all_observations) else state.latest_conv_time
            add_evidence(fact["id"], {"reason": f"{state.L['counter_evidence_tag']} {ea.get('reason', '')}"},
                         reference_time=_ea_time)

    if new_obs_cls:
        new_obs_data = []
        for c in new_obs_cls:
            idx = c.get("obs_index")
            if isinstance(idx, int) and 0 <= idx < len(state.all_observations):
                new_obs_data.append(state.all_observations[idx])

        if new_obs_data:
            _new_obs_times = [o.get("_conv_time") for o in new_obs_data if o.get("_conv_time")]
            _new_batch_time = max(_new_obs_times) if _new_obs_times else None
            create_profile, _ = prepare_profile(
                state.current_profile, query_text=obs_query, max_entries=15,
                language=state.language,
            )
            new_facts = create_new_facts(
                new_obs_data, create_profile, state.config, state.behavioral_signals,
                trajectory=state.trajectory,
            )
            for nf in new_facts:
                value = nf.get("value") or nf.get("claim")
                if not nf.get("category") or not nf.get("subject") or not value:
                    continue
                if value.startswith(state.L["dirty_value_prefix"]) or len(value) > 80:
                    continue
                decay = nf.get("decay_days")
                _src_obs = ""
                for _o in new_obs_data:
                    _cnt = _o.get("content") or ""
                    if _cnt and (value in _cnt or _cnt in value):
                        _src_obs = _cnt
                        break
                _evidence = [{"observation": _src_obs}] if _src_obs else None
                fact_id = save_profile_fact(
                    category=nf["category"],
                    subject=nf["subject"],
                    value=value,
                    source_type=nf.get("source_type", "stated"),
                    decay_days=decay,
                    evidence=_evidence,
                    start_time=_new_batch_time,
                )
                state.new_fact_count += 1
                if fact_id:
                    state.affected_fact_ids.add(fact_id)
                state.changed_items.append({
                    "change_type": "new",
                    "category": nf["category"],
                    "subject": nf["subject"],
                    "claim": value,
                    "source_type": nf.get("source_type", "stated"),
                })

    if contradictions:
        for c in contradictions:
            fid = c.get("fact_id")
            fact = _find_fact(fid)
            new_val = c.get("new_value")
            if not fact or not new_val:
                continue
            _obs_idx = c.get("obs_index")
            _obs_time = state.all_observations[_obs_idx].get("_conv_time") if isinstance(_obs_idx, int) and 0 <= _obs_idx < len(state.all_observations) else state.latest_conv_time
            if new_val.strip().lower() == (fact.get("value") or "").strip().lower():
                add_evidence(fact["id"], {"reason": c.get("reason", state.L["mention_again_reason"])},
                             reference_time=_obs_time)
                continue
            if new_val.startswith(state.L["dirty_value_prefix"]) or len(new_val) > 40:
                continue
            _obs = state.all_observations[_obs_idx] if isinstance(_obs_idx, int) and 0 <= _obs_idx < len(state.all_observations) else {}
            _evidence_entry = {"reason": c.get("reason", "")}
            if _obs.get("content"):
                _evidence_entry["observation"] = _obs["content"]
            new_id = save_profile_fact(
                category=fact["category"],
                subject=fact["subject"],
                value=new_val,
                source_type="stated",
                decay_days=fact.get("decay_days"),
                evidence=[_evidence_entry],
                start_time=_obs_time,
            )
            if new_id:
                state.affected_fact_ids.add(new_id)
            state.changed_items.append({
                "change_type": "contradict",
                "category": fact["category"],
                "subject": fact["subject"],
                "claim": f"{fact['value']}→{new_val}",
            })

    if state.changed_items:
        strategy_query = " ".join(
            f"{item.get('category', '')} {item.get('subject', '')}"
            for item in state.changed_items
        )
        strategy_profile, _ = prepare_profile(
            state.current_profile, query_text=strategy_query, max_entries=15,
            language=state.language,
        )
        strategies = generate_strategies(state.changed_items, state.config,
                                        current_profile=strategy_profile,
                                        trajectory=state.trajectory)
        for s in strategies:
            cat = s.get("category")
            subj = s.get("subject")
            if not cat or not subj:
                continue
            try:
                save_strategy(
                    hypothesis_category=cat,
                    hypothesis_subject=subj,
                    strategy_type=s.get("type", "probe"),
                    description=s.get("description", ""),
                    trigger_condition=s.get("trigger", ""),
                    approach=s.get("approach", ""),
                    reference_time=state.latest_conv_time,
                )
            except Exception as e:
                state.pipeline_errors += 1
                logger.error("Save strategy failed: %s", e)


def _step_cross_verify(state: _PipelineState):
    """Cross-verify suspected facts."""
    suspected_facts = load_suspected_profile()
    if not suspected_facts:
        return

    judgments = cross_verify_suspected_facts(suspected_facts, state.config,
                                             trajectory=state.trajectory)
    judgment_map = {j["fact_id"]: j for j in judgments}

    for f in suspected_facts:
        j = judgment_map.get(f["id"])
        if not j:
            continue
        if j["action"] == "confirm":
            confirm_profile_fact(f["id"], reference_time=state.latest_conv_time)
            state.affected_fact_ids.add(f["id"])
            state.confirmed_count += 1


def _step_resolve_disputes(state: _PipelineState):
    """Resolve disputed facts."""
    disputed_pairs = load_disputed_facts()
    if not disputed_pairs:
        return

    # Reload profile after cross-verify mutations
    state.current_profile = load_full_current_profile(exclude_superseded=True)

    judgments = resolve_disputes_with_llm(disputed_pairs, state.config,
                                          trajectory=state.trajectory)
    for j in judgments:
        old_fid = j["old_fact_id"]
        new_fid = j["new_fact_id"]
        action = j["action"]

        try:
            if action == "accept_new":
                resolve_dispute(old_fid, new_fid, accept_new=True,
                              resolution_time=state.latest_conv_time)
                delete_fact_edges_for(old_fid)
                state.affected_fact_ids.add(new_fid)
                state.dispute_resolved += 1
            elif action == "reject_new":
                resolve_dispute(old_fid, new_fid, accept_new=False,
                              resolution_time=state.latest_conv_time)
                delete_fact_edges_for(new_fid)
                state.affected_fact_ids.add(old_fid)
                state.dispute_resolved += 1
        except Exception:
            state.pipeline_errors += 1
            logger.error("Resolve dispute failed (old=%s, new=%s)", old_fid, new_fid, exc_info=True)


def _step_extract_edges(state: _PipelineState):
    """Extract fact edges for the knowledge network."""
    if not state.affected_fact_ids:
        return
    try:
        edge_profile = load_full_current_profile()
        extract_fact_edges(state.affected_fact_ids, edge_profile, state.config)
    except Exception:
        state.pipeline_errors += 1
        logger.error("Extract fact edges failed", exc_info=True)


def _step_expire_facts(state: _PipelineState):
    """Close expired facts and create verify strategies."""
    expired_facts = get_expired_facts(reference_time=state.latest_conv_time)
    if not expired_facts:
        return

    for f in expired_facts:
        if f.get("superseded_by") or f.get("supersedes"):
            continue

        close_time_period(f["id"], end_time=state.latest_conv_time)
        try:
            delete_fact_edges_for(f["id"])
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
            )
        except Exception:
            state.pipeline_errors += 1
            logger.error("Save expired-fact strategy failed", exc_info=True)


def _step_maturity_decay(state: _PipelineState):
    """Update decay values based on fact maturity."""
    key_anchors = []
    if state.trajectory and state.trajectory.get("key_anchors"):
        key_anchors = [str(a).lower() for a in state.trajectory["key_anchors"]]

    all_living = load_full_current_profile()

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
                                       current_profile=model_profile)
    for m in model_results:
        upsert_user_model(
            dimension=m["dimension"],
            assessment=m["assessment"],
            evidence_summary=m.get("evidence", ""),
        )


def _step_trajectory(state: _PipelineState):
    """Update trajectory summary when appropriate."""
    should_update_trajectory = False
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(DISTINCT session_id) FROM raw_conversations WHERE processed = TRUE")
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
        )
        if trajectory_result and trajectory_result.get("life_phase"):
            try:
                save_trajectory_summary(trajectory_result, session_count=total_sessions)
            except Exception as e:
                state.pipeline_errors += 1
                logger.error("Save trajectory failed: %s", e)


def _step_consolidate(state: _PipelineState):
    """Dedup profile when new facts were created or disputes resolved."""
    if state.new_fact_count > 0 or state.dispute_resolved > 0:
        _consolidate_profile()


def _step_snapshot(state: _PipelineState):
    """Generate memory snapshot."""
    try:
        final_profile = load_full_current_profile(exclude_superseded=True)
        snapshot_text = format_profile_text(
            final_profile, max_entries=40, detail="full", language=state.language,
        )

        user_model = load_user_model()
        if user_model:
            model_lines = [f"  {m['dimension']}: {m['assessment']}" for m in user_model]
            snapshot_text += f"\n\n{state.L['section_user_traits']}\n" + "\n".join(model_lines)

        snapshot_events = load_active_events(top_k=5)
        if snapshot_events:
            event_lines = [f"  [{e['category']}] {e['summary']}" for e in snapshot_events]
            snapshot_text += f"\n\n{state.L['section_events']}\n" + "\n".join(event_lines)

        snapshot_relationships = load_relationships()
        if snapshot_relationships:
            rel_lines = [f"  {r['relation']}: {r.get('name', '?')}" for r in snapshot_relationships[:10]]
            snapshot_text += f"\n\n{state.L['section_relationships']}\n" + "\n".join(rel_lines)

        try:
            snapshot_edges = load_fact_edges(
                [p["id"] for p in final_profile if p.get("id")]
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

        save_memory_snapshot(snapshot_text, profile_count=len(final_profile))
    except Exception:
        state.pipeline_errors += 1
        logger.error("Save memory snapshot failed", exc_info=True)


def _step_finalize(state: _PipelineState):
    """Mark processed and log errors."""
    if state.pipeline_errors:
        logger.warning("Sleep pipeline completed with %d error(s)", state.pipeline_errors)
    mark_processed(state.all_msg_ids)


async def run_async():
    """Async entry point — delegates to sync pipeline in a thread for transaction safety."""
    config = load_config()
    language = config.get("language", "en")
    L = get_labels("context.labels", language)

    session_convs = await asyncio.to_thread(get_unprocessed_conversations)
    if not session_convs:
        return

    # Run the transactional pipeline on a thread (keeps all DB ops on one thread)
    await asyncio.to_thread(_run_sleep_pipeline, session_convs, config, language, L)

    # Non-critical post-processing
    try:
        from agent.utils.embedding import embed_all_memories
        await asyncio.to_thread(embed_all_memories, config)
    except Exception:
        logger.warning("Embedding failed (non-critical, async)", exc_info=True)

    try:
        from agent.utils.clustering import cluster_memories
        await asyncio.to_thread(cluster_memories, config)
    except Exception:
        logger.warning("Clustering failed (non-critical, async)", exc_info=True)
