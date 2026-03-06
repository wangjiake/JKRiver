
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
    add_evidence, find_current_fact,
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

    MAX_SESSIONS_PER_RUN = 20
    session_convs = get_unprocessed_conversations()
    if not session_convs:
        return
    if len(session_convs) > MAX_SESSIONS_PER_RUN:
        session_convs = dict(list(session_convs.items())[:MAX_SESSIONS_PER_RUN])

    total_msgs = sum(len(msgs) for msgs in session_convs.values())

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
    """
    with transaction():
        _run_sleep_pipeline_inner(session_convs, config, language, L)


def _run_sleep_pipeline_inner(session_convs, config, language, L):
    _pipeline_errors = 0
    all_msg_ids = []
    all_convs = []
    all_observations = []

    existing_profile = load_full_current_profile(exclude_superseded=True)

    trajectory = load_trajectory_summary()
    if not (trajectory and trajectory.get("life_phase")):
        trajectory = None

    total_session_count = len(session_convs)
    for session_idx, (session_id, convs) in enumerate(session_convs.items(), 1):
        msg_ids = [c["id"] for c in convs]
        all_msg_ids.extend(msg_ids)
        all_convs.extend(convs)

        extract_profile, _ = prepare_profile(existing_profile, max_entries=25, language=language)
        result = extract_observations_and_tags(convs, config,
                                               existing_profile=extract_profile)
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

        user_count = len(observations)
        tp_count = len(third_party_obs)

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

        all_observations.extend(observations)

        for r in relationships:
            name = r.get("name")
            relation = r.get("relation", "")
            details = r.get("details", {})
            if relation:
                save_or_update_relationship(name, relation, details)
                detail_str = ", ".join(f"{k}:{v}" for k, v in details.items()) if details else ""

        for t in tags:
            save_session_tag(session_id, t["tag"], t.get("summary", ""))

        intent_parts = [c.get("intent", "") for c in convs if c.get("intent")]
        if intent_parts:
            intent_summary = " | ".join(intent_parts)
            save_session_summary(session_id, intent_summary)

        events = extract_events(convs, config)
        for e in events:
            decay_days = e.get("decay_days")
            importance = e.get("importance")
            save_event(e["category"], e["summary"], session_id,
                       importance=importance, decay_days=decay_days,
                       reference_time=session_time)
            status = f", 状态:{e['status']}" if e.get("status") else ""

    obs_query = " ".join(o.get("subject", "") for o in all_observations if o.get("subject"))

    behavioral_signals = []
    if all_observations and len(all_observations) >= 1:
        current_profile = load_full_current_profile(exclude_superseded=True)
        behavioral_profile, _ = prepare_profile(
            current_profile, query_text=obs_query, max_entries=20, language=language,
        )
        behavioral_signals = analyze_behavioral_patterns(
            all_observations, behavioral_profile, trajectory, config
        )
        if behavioral_signals:
            _obs_times = [o.get("_conv_time") for o in all_observations if o.get("_conv_time")]
            _earliest_time = min(_obs_times) if _obs_times else None

            for bs in behavioral_signals:
                pattern_type = bs.get('pattern_type', '?')
                cat = bs.get('category', '')
                subj = bs.get('subject', '')
                inferred = bs.get('inferred_value', '')
                conf = bs.get('confidence', 0)
                ev_count = bs.get("evidence_count", 0)

                if cat and subj and inferred:
                    existing = find_current_fact(cat, subj)
                    if not (existing and existing.get("value", "").strip().lower() == inferred.strip().lower()):
                        fact_id = save_profile_fact(
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
                            description=L["strategy_behavioral_desc"].format(subj=subj, inferred=inferred),
                            trigger_condition=L["strategy_topic_trigger"].format(subj=subj),
                            approach=L["strategy_clarify_approach"].format(inferred=inferred),
                            reference_time=_earliest_time,
                        )
                    except Exception:
                        _pipeline_errors += 1
                        logger.error("Save clarify strategy failed", exc_info=True)

    current_profile = load_full_current_profile(exclude_superseded=True)
    timeline = load_timeline()

    def _find_fact(fid) -> dict | None:
        if not fid:
            return None
        for p in current_profile:
            if p.get("id") == fid:
                return p
        return None

    _all_conv_times = [o["_conv_time"] for o in all_observations if o.get("_conv_time")]
    if not _all_conv_times:
        _all_conv_times = [c["user_input_at"] for c in all_convs if c.get("user_input_at")]
    latest_conv_time = max(_all_conv_times) if _all_conv_times else None

    changed_items = []
    new_fact_count = 0
    affected_fact_ids = set()  # 增量 cross_verify / resolve_disputes 用

    if all_observations:
        # Dynamic range for classify_observations
        obs_subjects = set(o.get("subject", "") for o in all_observations if o.get("subject"))
        obs_categories = set(o.get("_category", "") or "" for o in all_observations)
        has_contradictions = any(o.get("type") == "contradiction" for o in all_observations)

        if has_contradictions:
            classify_profile = current_profile
        elif len(obs_subjects) <= 3:
            three_months_ago = get_now() - timedelta(days=RECENT_PROFILE_LOOKBACK_DAYS)
            classify_profile = [
                p for p in current_profile
                if p.get("subject") in obs_subjects
                or p.get("category") in obs_categories
                or (p.get("updated_at") and p["updated_at"].replace(tzinfo=None) >= three_months_ago)
            ]
        else:
            classify_profile, _ = prepare_profile(
                current_profile, query_text=obs_query, config=config, max_entries=80,
                language=language,
            )

        classifications = classify_observations(
            all_observations, classify_profile, config, timeline,
            trajectory=trajectory
        )

        classified_indices = {c.get("obs_index") for c in classifications if c.get("obs_index") is not None}
        all_indices = set(range(len(all_observations)))
        missing_indices = all_indices - classified_indices
        if missing_indices:
            for idx in missing_indices:
                obs = all_observations[idx]
                if obs.get("type") in ("statement", "contradiction"):
                    classifications.append({"obs_index": idx, "action": "new",
                                            "reason": L["auto_classify_reason"]})

        supports = [c for c in classifications if c.get("action") == "support"]
        contradictions = [c for c in classifications if c.get("action") == "contradict"]
        evidence_against_list = [c for c in classifications if c.get("action") == "evidence_against"]
        new_obs_cls = [c for c in classifications if c.get("action") == "new"]
        irrelevant_cls = [c for c in classifications if c.get("action") == "irrelevant"]

        # 收集本轮受影响的 fact_id（供增量 cross_verify / resolve_disputes）
        for s in supports:
            fid = s.get("fact_id")
            if fid:
                affected_fact_ids.add(fid)
        for c in contradictions:
            fid = c.get("fact_id")
            if fid:
                affected_fact_ids.add(fid)
        for ea in evidence_against_list:
            fid = ea.get("fact_id")
            if fid:
                affected_fact_ids.add(fid)

        for s in supports:
            fact = _find_fact(s.get("fact_id"))
            if fact:
                _obs_idx = s.get("obs_index")
                _obs_time = all_observations[_obs_idx].get("_conv_time") if isinstance(_obs_idx, int) and 0 <= _obs_idx < len(all_observations) else latest_conv_time
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
                _ea_time = all_observations[_ea_idx].get("_conv_time") if isinstance(_ea_idx, int) and 0 <= _ea_idx < len(all_observations) else latest_conv_time
                add_evidence(fact["id"], {"reason": f"{L['counter_evidence_tag']} {ea.get('reason', '')}"},
                             reference_time=_ea_time)

        new_fact_count = 0
        if new_obs_cls:
            new_obs_data = []
            for c in new_obs_cls:
                idx = c.get("obs_index")
                if isinstance(idx, int) and 0 <= idx < len(all_observations):
                    new_obs_data.append(all_observations[idx])

            if new_obs_data:
                _new_obs_times = [o.get("_conv_time") for o in new_obs_data if o.get("_conv_time")]
                _new_batch_time = max(_new_obs_times) if _new_obs_times else None
                create_profile, _ = prepare_profile(
                    current_profile, query_text=obs_query, max_entries=15,
                    language=language,
                )
                new_facts = create_new_facts(
                    new_obs_data, create_profile, config, behavioral_signals,
                    trajectory=trajectory
                )
                for nf in new_facts:
                    value = nf.get("value") or nf.get("claim")
                    if not nf.get("category") or not nf.get("subject") or not value:
                        continue
                    if value.startswith(L["dirty_value_prefix"]) or len(value) > 80:
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
                    new_fact_count += 1
                    if fact_id:
                        affected_fact_ids.add(fact_id)
                    decay_str = f", 过期:{decay}天" if decay else ""
                    changed_items.append({
                        "change_type": "new",
                        "category": nf["category"],
                        "subject": nf["subject"],
                        "claim": value,
                        "source_type": nf.get("source_type", "stated"),
                    })

        contradict_count = 0
        if contradictions:
            for c in contradictions:
                fid = c.get("fact_id")
                fact = _find_fact(fid)
                new_val = c.get("new_value")
                if not fact or not new_val:
                    continue
                _obs_idx = c.get("obs_index")
                _obs_time = all_observations[_obs_idx].get("_conv_time") if isinstance(_obs_idx, int) and 0 <= _obs_idx < len(all_observations) else latest_conv_time
                if new_val.strip().lower() == (fact.get("value") or "").strip().lower():
                    add_evidence(fact["id"], {"reason": c.get("reason", L["mention_again_reason"])},
                                 reference_time=_obs_time)
                    continue
                if new_val.startswith(L["dirty_value_prefix"]) or len(new_val) > 40:
                    continue
                _obs = all_observations[_obs_idx] if isinstance(_obs_idx, int) and 0 <= _obs_idx < len(all_observations) else {}
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
                contradict_count += 1
                if new_id:
                    affected_fact_ids.add(new_id)
                changed_items.append({
                    "change_type": "contradict",
                    "category": fact["category"],
                    "subject": fact["subject"],
                    "claim": f"{fact['value']}→{new_val}",
                })

        strategy_count = 0
        if changed_items:
            strategy_query = " ".join(
                f"{item.get('category', '')} {item.get('subject', '')}"
                for item in changed_items
            )
            strategy_profile, _ = prepare_profile(
                current_profile, query_text=strategy_query, max_entries=15,
                language=language,
            )
            strategies = generate_strategies(changed_items, config,
                                            current_profile=strategy_profile,
                                            trajectory=trajectory)
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
                        reference_time=latest_conv_time,
                    )
                    strategy_count += 1
                except Exception as e:
                    _pipeline_errors += 1
                    logger.error("Save strategy failed: %s", e)


    # cross-verify suspected facts
    suspected_facts = load_suspected_profile()
    confirmed_count = 0

    if suspected_facts:
        judgments = cross_verify_suspected_facts(suspected_facts, config, trajectory=trajectory)
        judgment_map = {j["fact_id"]: j for j in judgments}

        for f in suspected_facts:
            j = judgment_map.get(f["id"])
            if not j:
                continue

            action = j["action"]
            reason = j.get("reason", "")

            if action == "confirm":
                confirm_profile_fact(f["id"], reference_time=latest_conv_time)
                affected_fact_ids.add(f["id"])
                confirmed_count += 1

    # resolve disputes
    disputed_pairs = load_disputed_facts()
    dispute_resolved = 0
    if disputed_pairs:
        judgments = resolve_disputes_with_llm(disputed_pairs, config, trajectory=trajectory)
        for j in judgments:
            old_fid = j["old_fact_id"]
            new_fid = j["new_fact_id"]
            action = j["action"]
            reason = j.get("reason", "")

            if action == "accept_new":
                resolve_dispute(old_fid, new_fid, accept_new=True, resolution_time=latest_conv_time)
                delete_fact_edges_for(old_fid)
                affected_fact_ids.add(new_fid)
                dispute_resolved += 1
            elif action == "reject_new":
                resolve_dispute(old_fid, new_fid, accept_new=False, resolution_time=latest_conv_time)
                delete_fact_edges_for(new_fid)
                affected_fact_ids.add(old_fid)
                dispute_resolved += 1

    # Extract fact edges (knowledge network)
    if affected_fact_ids:
        try:
            edge_profile = load_full_current_profile()
            extract_fact_edges(affected_fact_ids, edge_profile, config)
        except Exception:
            _pipeline_errors += 1
            logger.error("Extract fact edges failed", exc_info=True)

    expired_facts = get_expired_facts(reference_time=latest_conv_time)
    stale_count = 0
    if expired_facts:
        for f in expired_facts:
            fact_id = f["id"]
            cat = f["category"]
            subj = f["subject"]

            if f.get("superseded_by") or f.get("supersedes"):
                continue

            close_time_period(fact_id, end_time=latest_conv_time)
            delete_fact_edges_for(fact_id)
            try:
                save_strategy(
                    hypothesis_category=cat,
                    hypothesis_subject=subj,
                    strategy_type="verify",
                    description=L["strategy_expired_desc"].format(subj=subj),
                    trigger_condition=L["strategy_topic_trigger"].format(subj=subj),
                    approach=L["strategy_verify_approach"].format(subj=subj),
                    reference_time=latest_conv_time,
                )
            except Exception:
                _pipeline_errors += 1
                logger.error("Save expired-fact strategy failed", exc_info=True)
            stale_count += 1

    key_anchors = []
    if trajectory and trajectory.get("key_anchors"):
        key_anchors = [str(a).lower() for a in trajectory["key_anchors"]]

    all_living = load_full_current_profile()

    maturity_count = 0
    for f in all_living:
        start = f.get("start_time")
        updated = f.get("updated_at")
        if not start or not updated:
            continue
        f_naive = start.replace(tzinfo=None) if hasattr(start, 'tzinfo') and start.tzinfo else start
        l_naive = updated.replace(tzinfo=None) if hasattr(updated, 'tzinfo') and updated.tzinfo else updated
        span_days = (l_naive - f_naive).days
        ev = f.get("evidence", [])
        evidence_count = len(ev) if isinstance(ev, list) else 0
        current_decay = f.get("decay_days") or 90

        subj_lower = (f.get("subject") or "").lower()
        value_lower = (f.get("value") or "").lower()
        in_anchors = any(subj_lower in a or value_lower in a or a in subj_lower or a in value_lower
                         for a in key_anchors)

        new_decay = _calculate_maturity_decay(span_days, evidence_count, current_decay, in_anchors)
        if new_decay > current_decay:
            update_fact_decay(f["id"], new_decay, reference_time=latest_conv_time)
            maturity_count += 1
            anchor_tag = " [锚点加速]" if in_anchors else ""

    if all_convs:
        current_profile_for_model = load_full_current_profile(exclude_superseded=True)
        model_profile, _ = prepare_profile(
            current_profile_for_model, query_text=obs_query, max_entries=20,
            language=language,
        )
        model_convs = all_convs[-50:] if len(all_convs) > 50 else all_convs
        model_results = analyze_user_model(model_convs, config,
                                           current_profile=model_profile)
        for m in model_results:
            upsert_user_model(
                dimension=m["dimension"],
                assessment=m["assessment"],
                evidence_summary=m.get("evidence", ""),
            )

    should_update_trajectory = False
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(DISTINCT session_id) FROM raw_conversations WHERE processed = TRUE")
            total_sessions = cur.fetchone()[0] + len(session_convs)
    finally:
        conn.close()

    prev_session_count = trajectory.get("session_count", 0) if trajectory else 0
    sessions_since_update = total_sessions - prev_session_count

    has_significant_change = (
        confirmed_count > 0
        or dispute_resolved > 0
        or any(o.get("type") == "contradiction" for o in all_observations)
        or any(
            is_significant_category(item.get("category", ""))
            for item in changed_items
        )
    )

    if has_significant_change and sessions_since_update >= 2:
        should_update_trajectory = True
    elif sessions_since_update >= 10:
        should_update_trajectory = True

    if not trajectory:
        current_profile = load_full_current_profile(exclude_superseded=True)
        if current_profile:
            should_update_trajectory = True

    if should_update_trajectory:
        current_profile = load_full_current_profile(exclude_superseded=True)
        if current_profile:
            trajectory_result = generate_trajectory_summary(
                current_profile, config, new_observations=all_observations
            )
            if trajectory_result and trajectory_result.get("life_phase"):
                try:
                    save_trajectory_summary(trajectory_result, session_count=total_sessions)
                except Exception as e:
                    _pipeline_errors += 1
                    logger.error("Save trajectory failed: %s", e)

    # Profile dedup consolidation (only when new facts created or disputes resolved)
    if new_fact_count > 0 or dispute_resolved > 0:
        _consolidate_profile()

    # Generate memory snapshot
    try:
        final_profile = load_full_current_profile(exclude_superseded=True)
        snapshot_text = format_profile_text(
            final_profile, max_entries=40, detail="full", language=language,
        )

        user_model = load_user_model()
        if user_model:
            model_lines = [f"  {m['dimension']}: {m['assessment']}" for m in user_model]
            snapshot_text += f"\n\n{L['section_user_traits']}\n" + "\n".join(model_lines)

        snapshot_events = load_active_events(top_k=5)
        if snapshot_events:
            event_lines = [f"  [{e['category']}] {e['summary']}" for e in snapshot_events]
            snapshot_text += f"\n\n{L['section_events']}\n" + "\n".join(event_lines)

        snapshot_relationships = load_relationships()
        if snapshot_relationships:
            rel_lines = [f"  {r['relation']}: {r.get('name', '?')}" for r in snapshot_relationships[:10]]
            snapshot_text += f"\n\n{L['section_relationships']}\n" + "\n".join(rel_lines)

        snapshot_edges = load_fact_edges(
            [p["id"] for p in final_profile if p.get("id")]
        ) if final_profile else []
        if snapshot_edges:
            edge_lines = [
                f"  [{e.get('src_category','')}/{e.get('src_subject','')}] "
                f"--[{e['edge_type']}]--> "
                f"[{e.get('tgt_category','')}/{e.get('tgt_subject','')}]: "
                f"{e.get('description', '')}"
                for e in snapshot_edges[:15]
            ]
            snapshot_text += f"\n\n{L['section_knowledge_network']}\n" + "\n".join(edge_lines)

        save_memory_snapshot(snapshot_text, profile_count=len(final_profile))
    except Exception:
        _pipeline_errors += 1
        logger.error("Save memory snapshot failed", exc_info=True)

    if _pipeline_errors:
        logger.warning("Sleep pipeline completed with %d error(s)", _pipeline_errors)

    mark_processed(all_msg_ids)


async def run_async():
    """Async entry point — delegates to sync pipeline in a thread for transaction safety."""
    config = load_config()
    language = config.get("language", "en")
    L = get_labels("context.labels", language)

    MAX_SESSIONS_PER_RUN = 20
    session_convs = await asyncio.to_thread(get_unprocessed_conversations)
    if not session_convs:
        return
    if len(session_convs) > MAX_SESSIONS_PER_RUN:
        session_convs = dict(list(session_convs.items())[:MAX_SESSIONS_PER_RUN])

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

