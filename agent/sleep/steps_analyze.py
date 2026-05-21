
import logging
from datetime import timedelta
from agent.utils.time_context import get_now
from agent.utils.profile_filter import prepare_profile
from agent.storage import (
    load_full_current_profile, load_timeline,
    save_profile_fact, confirm_profile_fact,
    add_evidence,
    load_suspected_profile,
    load_disputed_facts, resolve_dispute,
    save_strategy,
    delete_fact_edges_for,
)
from agent.sleep._pipeline_state import _PipelineState, _build_fact_lookup, _find_fact_in_profile
from agent.sleep._utils import _safe_int
from agent.sleep.extractors import classify_observations, create_new_facts
from agent.sleep.analysis import (
    generate_strategies, analyze_behavioral_patterns, cross_verify_suspected_facts,
)
from agent.sleep.disputes import resolve_disputes_with_llm
from agent.sleep.steps_extract import _obs_query

logger = logging.getLogger(__name__)

RECENT_PROFILE_LOOKBACK_DAYS = 90


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
    _ = state.owner_id  # behavioral_patterns reads no owner-scoped table directly
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
                    owner_id=state.owner_id,
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
                    owner_id=state.owner_id,
                )
            except Exception:
                state.pipeline_errors += 1
                logger.error("Save clarify strategy failed", exc_info=True)


# ── Sub-functions for _step_classify_and_integrate ────────────


def _integrate_supports(state, supports, _find_fact):
    """Process support classifications: add evidence and touch profile facts."""
    for s in supports:
        fact = _find_fact(s.get("fact_id"))
        if fact:
            _obs_idx = _safe_int(s.get("obs_index"))
            _obs_time = state.all_observations[_obs_idx].get("_conv_time") if _obs_idx is not None and 0 <= _obs_idx < len(state.all_observations) else state.latest_conv_time
            add_evidence(fact["id"], {"reason": s.get("reason", "")},
                         reference_time=_obs_time)
            save_profile_fact(
                category=fact["category"],
                subject=fact["subject"],
                value=fact["value"],
                source_type=fact.get("source_type", "stated"),
                decay_days=fact.get("decay_days"),
                start_time=_obs_time,
                owner_id=state.owner_id,
            )


def _integrate_evidence_against(state, evidence_against_list, _find_fact):
    """Process evidence_against classifications: add counter-evidence."""
    for ea in evidence_against_list:
        fact = _find_fact(ea.get("fact_id"))
        if fact:
            _ea_idx = _safe_int(ea.get("obs_index"))
            _ea_time = state.all_observations[_ea_idx].get("_conv_time") if _ea_idx is not None and 0 <= _ea_idx < len(state.all_observations) else state.latest_conv_time
            add_evidence(fact["id"], {"reason": f"{state.L['counter_evidence_tag']} {ea.get('reason', '')}"},
                         reference_time=_ea_time)


def _integrate_new_facts(state, new_obs_cls, obs_query):
    """Process new observation classifications: create new profile facts."""
    if not new_obs_cls:
        return

    new_obs_data = []
    for c in new_obs_cls:
        idx = _safe_int(c.get("obs_index"))
        if idx is not None and 0 <= idx < len(state.all_observations):
            new_obs_data.append(state.all_observations[idx])

    if not new_obs_data:
        return

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
            owner_id=state.owner_id,
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


def _integrate_contradictions(state, contradictions, _find_fact):
    """Process contradiction classifications: supersede existing facts."""
    if not contradictions:
        return

    for c in contradictions:
        fid = c.get("fact_id")
        fact = _find_fact(fid)
        new_val = c.get("new_value")
        if not fact or not new_val:
            continue
        _obs_idx = _safe_int(c.get("obs_index"))
        _obs_time = state.all_observations[_obs_idx].get("_conv_time") if _obs_idx is not None and 0 <= _obs_idx < len(state.all_observations) else state.latest_conv_time
        if new_val.strip().lower() == (fact.get("value") or "").strip().lower():
            add_evidence(fact["id"], {"reason": c.get("reason", state.L["mention_again_reason"])},
                         reference_time=_obs_time)
            continue
        if new_val.startswith(state.L["dirty_value_prefix"]) or len(new_val) > 40:
            continue
        _obs = state.all_observations[_obs_idx] if _obs_idx is not None and 0 <= _obs_idx < len(state.all_observations) else {}
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
            owner_id=state.owner_id,
        )
        if new_id:
            state.affected_fact_ids.add(new_id)
        state.changed_items.append({
            "change_type": "contradict",
            "category": fact["category"],
            "subject": fact["subject"],
            "claim": f"{fact['value']}→{new_val}",
        })


def _generate_change_strategies(state):
    """Generate strategies for changed items."""
    if not state.changed_items:
        return

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
                                    trajectory=state.trajectory,
                                    owner_id=state.owner_id)
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
                owner_id=state.owner_id,
            )
        except Exception as e:
            state.pipeline_errors += 1
            logger.error("Save strategy failed: %s", e)


# ── Main classify_and_integrate step ──────────────────────────


def _step_classify_and_integrate(state: _PipelineState):
    """Classify observations and integrate into profile: supports, contradictions, new facts, strategies."""
    # Reload profile after behavioral analysis mutations
    state.current_profile = load_full_current_profile(exclude_superseded=True, owner_id=state.owner_id)
    timeline = load_timeline(owner_id=state.owner_id)

    _all_conv_times = [o["_conv_time"] for o in state.all_observations if o.get("_conv_time")]
    if not _all_conv_times:
        _all_conv_times = [c["user_input_at"] for c in state.all_convs if c.get("user_input_at")]
    state.latest_conv_time = max(_all_conv_times) if _all_conv_times else None

    if not state.all_observations:
        return

    obs_query = _obs_query(state)

    def _find_fact(fid) -> dict | None:
        fid = _safe_int(fid)
        if fid is None:
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

    classified_indices = {_safe_int(c.get("obs_index")) for c in classifications if c.get("obs_index") is not None}
    classified_indices.discard(None)
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
        fid = _safe_int(s.get("fact_id"))
        if fid is not None:
            state.affected_fact_ids.add(fid)
    for c in contradictions:
        fid = _safe_int(c.get("fact_id"))
        if fid is not None:
            state.affected_fact_ids.add(fid)
    for ea in evidence_against_list:
        fid = _safe_int(ea.get("fact_id"))
        if fid is not None:
            state.affected_fact_ids.add(fid)

    _integrate_supports(state, supports, _find_fact)
    _integrate_evidence_against(state, evidence_against_list, _find_fact)
    _integrate_new_facts(state, new_obs_cls, obs_query)
    _integrate_contradictions(state, contradictions, _find_fact)
    _generate_change_strategies(state)


def _step_cross_verify(state: _PipelineState):
    """Cross-verify suspected facts."""
    suspected_facts = load_suspected_profile(owner_id=state.owner_id)
    if not suspected_facts:
        return

    judgments = cross_verify_suspected_facts(suspected_facts, state.config,
                                             trajectory=state.trajectory,
                                             owner_id=state.owner_id)
    judgment_map = {_safe_int(j["fact_id"]): j for j in judgments if _safe_int(j.get("fact_id")) is not None}

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
    disputed_pairs = load_disputed_facts(owner_id=state.owner_id)
    if not disputed_pairs:
        return

    # Reload profile after cross-verify mutations
    state.current_profile = load_full_current_profile(exclude_superseded=True, owner_id=state.owner_id)

    judgments = resolve_disputes_with_llm(disputed_pairs, state.config,
                                          trajectory=state.trajectory,
                                          owner_id=state.owner_id)
    for j in judgments:
        old_fid = j["old_fact_id"]
        new_fid = j["new_fact_id"]
        action = j["action"]

        try:
            if action == "accept_new":
                resolve_dispute(old_fid, new_fid, accept_new=True,
                              resolution_time=state.latest_conv_time)
                delete_fact_edges_for(old_fid, owner_id=state.owner_id)
                state.affected_fact_ids.add(new_fid)
                state.dispute_resolved += 1
            elif action == "reject_new":
                resolve_dispute(old_fid, new_fid, accept_new=False,
                              resolution_time=state.latest_conv_time)
                delete_fact_edges_for(new_fid, owner_id=state.owner_id)
                state.affected_fact_ids.add(old_fid)
                state.dispute_resolved += 1
        except Exception:
            state.pipeline_errors += 1
            logger.error("Resolve dispute failed (old=%s, new=%s)", old_fid, new_fid, exc_info=True)
