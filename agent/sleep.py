
import json
import re
from datetime import datetime, timedelta
from agent.config import load_config
from agent.config.prompts import get_prompt, get_labels
from agent.utils.llm_client import call_llm
from agent.utils.time_context import get_now
from psycopg2.extras import RealDictCursor
from agent.storage import (
    get_db_connection, save_event, save_session_tag, save_session_summary,
    load_existing_tags,
    save_observation, load_observations,
    load_observations_by_time_range,
    load_conversation_summaries_around,
    load_summaries_by_observation_subject,
    save_profile_fact, close_time_period, confirm_profile_fact,
    add_evidence, find_current_fact,
    load_suspected_profile, load_confirmed_profile,
    load_full_current_profile, load_timeline,
    get_expired_facts, update_fact_decay,
    load_disputed_facts, resolve_dispute,
    upsert_user_model, load_user_model,
    save_strategy,
    save_trajectory_summary, load_trajectory_summary,
    load_active_events,
    save_or_update_relationship, load_relationships,
)

def _format_trajectory_block(trajectory: dict | None, language: str = "zh") -> str:
    L = get_labels("context.labels", language)
    if not trajectory or not trajectory.get("life_phase"):
        return f"\n{L['trajectory_summary']}：{L['trajectory_none']}\n"
    return (
        f"\n{L['trajectory_summary']}：\n"
        f"  {L['phase']}: {trajectory.get('life_phase', '?')}\n"
        f"  {L['characteristics']}: {trajectory.get('phase_characteristics', '?')}\n"
        f"  {L['direction']}: {trajectory.get('trajectory_direction', '?')}\n"
        f"  {L['stability']}: {trajectory.get('stability_assessment', '?')}\n"
        f"  {L['anchors']}: {json.dumps(trajectory.get('key_anchors', []), ensure_ascii=False)}\n"
        f"  {L['volatile_areas']}: {json.dumps(trajectory.get('volatile_areas', []), ensure_ascii=False)}\n"
        f"  {L['recent_momentum']}: {trajectory.get('recent_momentum', '?')}\n"
        f"  {L['summary']}: {trajectory.get('full_summary', '?')}\n"
    )

def _format_profile_for_llm(profile: list[dict], timeline: list[dict] | None = None, language: str = "zh") -> str:
    L = get_labels("context.labels", language)
    if not profile:
        return L["no_profile"] + "\n"
    text = ""
    for p in profile:
        ev = p.get("evidence", [])
        layer = p.get("layer", "suspected")
        mention_count = p.get("mention_count", 1) or 1
        start = p["start_time"].strftime("%m-%d") if p.get("start_time") else "?"
        updated = p["updated_at"].strftime("%m-%d") if p.get("updated_at") else "?"
        fact_id = p.get("id", "?")
        if p.get("superseded_by"):
            layer_tag = L["layer_disputed"]
        elif layer == "confirmed":
            layer_tag = L["layer_core"]
        else:
            layer_tag = L["layer_suspected"]

        line = (
            f"#{fact_id} {layer_tag} [{p['category']}] {p['subject']}: {p['value']} "
            f"({L['mentions']}{mention_count}, source={p.get('source_type', 'stated')}, "
            f"{L['start']}={start}, {L['updated']}={updated}, {L['evidence']}{len(ev)}"
        )
        if p.get("superseded_by"):
            line += f", {L['challenged_by'].format(p['superseded_by'])}"
        if p.get("supersedes"):
            line += f", {L['challenges'].format(p['supersedes'])}"
        line += ")\n"
        text += line

    if timeline:
        closed = [t for t in timeline if t.get("end_time") or t.get("human_end_time") or t.get("rejected")]
        if closed:
            text += f"\n{L['closed_timeline']}：\n"
            for t in closed:
                start = t["start_time"].strftime("%Y-%m-%d") if t.get("start_time") else "?"
                if t.get("rejected"):
                    text += (
                        f"  [{t['category']}] {t['subject']}: {t['value']} "
                        f"({start}, {L['marked_error']})\n"
                    )
                else:
                    eff_end = t.get("human_end_time") or t.get("end_time")
                    end = eff_end.strftime("%Y-%m-%d") if eff_end else "?"
                    text += (
                        f"  [{t['category']}] {t['subject']}: {t['value']} "
                        f"({start} ~ {end})\n"
                    )
    return text

_MATURITY_TIERS = [
    (730, 10, 730),
    (365, 6, 365),
    (90, 3, 180),
]

def _calculate_maturity_decay(span_days: int, evidence_count: int,
                               current_decay: int, in_key_anchors: bool = False) -> int:
    boost = 0.6 if in_key_anchors else 1.0
    for min_span, min_ev, target in _MATURITY_TIERS:
        if (span_days >= min_span * boost
                and evidence_count >= max(1, int(min_ev * boost))
                and target > current_decay):
            return target
    return current_decay

def extract_observations_and_tags(conversations: list[dict], config: dict,
                                   existing_profile: list[dict] | None = None) -> dict:
    llm_config = config.get("llm", {})
    language = config.get("language", "zh")
    L = get_labels("context.labels", language)

    text = ""
    msg_index = 0
    for msg in conversations:
        ts = msg.get("user_input_at")
        time_str = ts.strftime("%Y-%m-%d %H:%M") if hasattr(ts, 'strftime') else ""
        prefix = f"[{time_str}] " if time_str else ""
        intent = msg.get('intent', '')
        intent_tag = f" [{L['intent']}: {intent}]" if intent else ""
        msg_index += 1
        text += f"{prefix}[msg-{msg_index}] {L['user']}：{msg.get('ai_summary') or msg['user_input']}{intent_tag}\n"
        reply = msg.get('assistant_reply', '')
        if reply:
            if len(reply) > 200:
                reply = reply[:200] + "..."
            text += f"{prefix}{L['assistant']}：{reply}\n"
        text += "\n"
    total_user_msgs = msg_index

    if not text.strip():
        return {"observations": [], "tags": []}

    known_lines = []
    if existing_profile:
        for p in existing_profile:
            layer = p.get("layer", "suspected")
            layer_tag = L["layer_core"] if layer == "confirmed" else L["layer_suspected"]
            known_lines.append(
                f"  {layer_tag} [{p['category']}] {p['subject']}: {p['value']}"
            )

    if known_lines:
        known_block = f"{L['known_info_header']}：\n" + "\n".join(known_lines)
    else:
        known_block = L["known_info_none"]

    if existing_profile:
        categories = sorted(set(p["category"] for p in existing_profile if p.get("category")))
        category_hint = "、".join(categories) if categories else L["none"]
    else:
        category_hint = L["none"]

    existing = load_existing_tags()
    tag_hint = "、".join(existing) if existing else L["none"]

    prompt = get_prompt("sleep.extract_observations", language,
                        known_info_block=known_block,
                        existing_tags=tag_hint,
                        category_list=category_hint)

    now = get_now()
    date_prefix = (
        f"[system_time: {now.strftime('%Y-%m-%dT%H:%M')}]\n"
        f"{L['birth_year_note'].format(year=now.year, result=now.year - 25)}\n\n"
    )
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": date_prefix + text},
    ]
    raw = call_llm(messages, llm_config)
    result = _parse_json_object(raw)

    obs = [o for o in result.get("observations", []) if isinstance(o, dict) and o.get("type") and o.get("content")]
    tags = [t for t in result.get("tags", []) if isinstance(t, dict) and t.get("tag")]
    rels = [r for r in result.get("relationships", []) if isinstance(r, dict) and r.get("relation")]

    if total_user_msgs > 0 and len(obs) < total_user_msgs:
        pass

    return {"observations": obs, "tags": tags, "relationships": rels}

def extract_events(conversations: list[dict], config: dict) -> list[dict]:
    llm_config = config.get("llm", {})
    language = config.get("language", "zh")
    L = get_labels("context.labels", language)

    dialogue = ""
    for msg in conversations:
        dialogue += f"{L['user']}：{msg['user_input']}\n"
        dialogue += f"{L['assistant']}：{msg['assistant_reply']}\n\n"

    if not dialogue.strip():
        return []

    now = get_now()
    messages = [
        {"role": "system", "content": get_prompt("sleep.extract_event", language)},
        {"role": "user", "content": f"[system_time: {now.strftime('%Y-%m-%dT%H:%M')}]\n\n{dialogue}"},
    ]
    raw = call_llm(messages, llm_config)
    events = _parse_json_array(raw)
    return [e for e in events if isinstance(e, dict) and e.get("category") and e.get("summary")]

def classify_observations(observations: list[dict],
                           current_profile: list[dict],
                           config: dict,
                           timeline: list[dict] | None = None,
                           trajectory: dict | None = None) -> list[dict]:
    llm_config = config.get("llm", {})
    language = config.get("language", "zh")
    L = get_labels("context.labels", language)
    if not observations:
        return []

    obs_text = ""
    grouped: dict[int, list[tuple[int, dict]]] = {}
    for i, o in enumerate(observations):
        order = o.get("_session_order", 0)
        if order not in grouped:
            grouped[order] = []
        grouped[order].append((i, o))

    if grouped:
        total = max(grouped.keys()) if grouped else 1
        for order in sorted(grouped.keys()):
            first_obs = grouped[order][0][1] if grouped[order] else None
            time_str = ""
            if first_obs and first_obs.get("_conv_time"):
                time_str = f" {first_obs['_conv_time'].strftime('%Y-%m-%d')}"
            label = f"[{L['session']} {order}/{total}{time_str}"
            if order == total:
                label += f" — {L['latest']}"
            label += "]"
            obs_text += f"{label}\n"
            for i, o in grouped[order]:
                subj = o.get('subject', '')
                subj_tag = f" [subject:{subj}]" if subj else ""
                obs_text += f"  [{i}] [{o['type']}]{subj_tag} {o['content']}\n"
    else:
        for i, o in enumerate(observations):
            subj = o.get('subject', '')
            subj_tag = f" [subject:{subj}]" if subj else ""
            obs_text += f"[{i}] [{o['type']}]{subj_tag} {o['content']}\n"

    profile_text = _format_profile_for_llm(current_profile, timeline, language=language)

    traj_context = ""
    if trajectory and trajectory.get("life_phase"):
        traj_context = (
            f"\n{L['trajectory_ref']}：\n"
            f"  {L['current_phase']}: {trajectory.get('life_phase', '?')}\n"
            f"  {L['anchors_stable']}: {json.dumps(trajectory.get('key_anchors', []), ensure_ascii=False)}\n"
            f"  {L['volatile_areas']}: {json.dumps(trajectory.get('volatile_areas', []), ensure_ascii=False)}\n"
        )

    now = get_now()
    user_content = (
        f"[system_time: {now.strftime('%Y-%m-%dT%H:%M')}]\n\n"
        f"{L['current_profile']}：\n{profile_text}\n"
        f"{L['new_observations']}：\n{obs_text}"
        f"{traj_context}"
    )
    messages = [
        {"role": "system", "content": get_prompt("sleep.classify_observations", language)},
        {"role": "user", "content": user_content},
    ]
    raw = call_llm(messages, llm_config)
    results = _parse_json_array(raw)
    return [r for r in results if isinstance(r, dict) and r.get("action")]

def create_new_facts(new_observations: list[dict],
                     existing_profile: list[dict],
                     config: dict,
                     behavioral_signals: list | None = None,
                     trajectory: dict | None = None) -> list[dict]:
    llm_config = config.get("llm", {})
    language = config.get("language", "zh")
    L = get_labels("context.labels", language)
    if not new_observations:
        return []

    obs_text = ""
    for o in new_observations:
        time_str = ""
        if o.get("_conv_time"):
            time_str = f" ({o['_conv_time'].strftime('%Y-%m-%d')})"
        subj_str = f" (subject: {o['subject']})" if o.get('subject') else ""
        obs_text += f"[{o['type']}] {o['content']}{subj_str}{time_str}\n"

    existing_cats = set()
    for p in existing_profile:
        existing_cats.add(f"  {p['category']}: {p['subject']}")
    default_cats = L["default_categories"]
    if existing_cats:
        cat_block = (f"{L['existing_naming']}：\n"
                     + "\n".join(sorted(existing_cats))
                     + f"\n{L['reference']}：" + default_cats)
    else:
        cat_block = default_cats

    categorization_history = []
    for p in existing_profile:
        ev = p.get("evidence") or []
        for e in ev:
            obs_text_ev = e.get("observation", "")
            if obs_text_ev:
                categorization_history.append(
                    f"  \"{obs_text_ev}\" → [{p['category']}] {p['subject']} = {p['value']}"
                )
                break
    if categorization_history:
        history_block = (f"{L['categorization_precedents']}\n"
                         + "\n".join(categorization_history))
    else:
        history_block = ""

    signal_block = ""
    if behavioral_signals:
        signal_block = f"\n{L['signal_hint']}：\n"
        for s in behavioral_signals:
            signal_block += (
                f"  [{s.get('category', '?')}] {s.get('subject', '?')}: "
                f"{L['maybe_is'].format(value=s.get('inferred_value', '?'))}\n"
            )

    traj_context = ""
    if trajectory and trajectory.get("life_phase"):
        traj_context = (
            f"\n{L['background_ref']}：\n"
            f"  {L['current_phase']}: {trajectory.get('life_phase', '?')}\n"
            f"  {L['anchors_permanent']}: {json.dumps(trajectory.get('key_anchors', []), ensure_ascii=False)}\n"
            f"  {L['volatile_areas']}: {json.dumps(trajectory.get('volatile_areas', []), ensure_ascii=False)}\n"
        )

    now = get_now()
    prompt = get_prompt("sleep.create_hypotheses", language,
                        existing_categories=cat_block,
                        categorization_history=history_block,
                        birth_year=str(now.year))

    user_content = (
        f"[system_time: {now.strftime('%Y-%m-%dT%H:%M')}]\n"
        f"{L['birth_year_note'].format(year=now.year, result=now.year - 25)}\n\n"
        f"{L['new_obs']}：\n{obs_text}"
        f"{signal_block}"
        f"{traj_context}"
    )
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": user_content},
    ]
    if signal_block:
        pass
    raw = call_llm(messages, llm_config)
    return _parse_json_array(raw)

def cross_validate_contradictions(contradictions: list[dict],
                                  observations: list[dict],
                                  current_profile: list[dict],
                                  config: dict,
                                  trajectory: dict | None = None) -> list[dict]:
    llm_config = config.get("llm", {})
    language = config.get("language", "zh")
    L = get_labels("context.labels", language)
    if not contradictions:
        return []

    profile_map = {p["id"]: p for p in current_profile}

    relevant_keywords = set()
    for c in contradictions:
        fid = c.get("fact_id")
        if fid and fid in profile_map:
            p = profile_map[fid]
            relevant_keywords.add(p.get("subject", ""))
            relevant_keywords.add(p.get("value", ""))
            relevant_keywords.add(p.get("category", ""))
        new_val = c.get("new_value", "")
        if new_val:
            relevant_keywords.add(new_val)
    relevant_keywords = {k for k in relevant_keywords if k and len(k) >= 2}

    items_text = ""
    now = get_now()
    for c in contradictions:
        obs_idx = c.get("obs_index", "?")
        obs = observations[obs_idx] if isinstance(obs_idx, int) and obs_idx < len(observations) else {}
        fid = c.get("fact_id")
        fact = profile_map.get(fid, {})
        obs_time = obs.get('_conv_time') or now
        obs_time_str = obs_time.strftime('%Y-%m-%d')
        fact_start = fact['start_time'].strftime('%Y-%m-%d') if fact.get('start_time') else '?'
        fact_updated = fact['updated_at'].strftime('%Y-%m-%d') if fact.get('updated_at') else '?'
        fact_mentions = fact.get('mention_count', 1)

        items_text += (
            f"[{L['contradiction']}{obs_idx}] [{fact.get('category', '?')}] {fact.get('subject', '?')}\n"
            f"  {L['old_value']}: \"{fact.get('value', '?')}\" (从 {fact_start} 到 {obs_time_str}, {L['mentions']}{fact_mentions})\n"
            f"  {L['new_statement']}: \"{c.get('new_value', '?')}\" (开始于 {obs_time_str})\n"
            f"  {L['original_text']}: {obs.get('content', '?')}\n"
            f"  {L['classify_reason']}: {c.get('reason', '')}\n"
        )
        if fact.get("category") and fact.get("subject"):
            tl = load_timeline(category=fact["category"], subject=fact["subject"])
            closed = [t for t in tl if t.get("end_time") or t.get("human_end_time") or t.get("rejected")]
            if closed:
                items_text += f"  {L['historical_timeline']}:\n"
                for t in closed:
                    t_start = t["start_time"].strftime('%Y-%m-%d') if t.get("start_time") else "?"
                    eff_end = t.get("human_end_time") or t.get("end_time")
                    t_end = eff_end.strftime('%Y-%m-%d') if eff_end else "?"
                    items_text += f"    \"{t.get('value', '?')}\" ({t_start} ~ {t_end})\n"
        items_text += "\n"

    historical_obs = load_observations(limit=100)
    hist_text = ""
    if historical_obs and relevant_keywords:
        filtered = [ho for ho in historical_obs
                    if any(kw in (ho.get("content", "") + " " + (ho.get("subject", "") or ""))
                           for kw in relevant_keywords)]
        if filtered:
            for ho in filtered[:30]:
                time_str = ho['created_at'].strftime('%Y-%m-%d') if ho.get('created_at') else '?'
                hist_text += f"  [{time_str}] [{ho['observation_type']}] {ho['content']}"
                if ho.get("subject"):
                    hist_text += f" (subject: {ho['subject']})"
                hist_text += "\n"
        else:
            hist_text = f"{L['no_related_obs']}\n"
    else:
        hist_text = f"{L['no_historical_obs']}\n"

    traj_block = ""
    if trajectory and trajectory.get("life_phase"):
        traj_block = (
            f"\n{L['trajectory_ref_label']}：\n"
            f"  {L['anchors_stable']}: {json.dumps(trajectory.get('key_anchors', []), ensure_ascii=False)}\n"
            f"  {L['volatile_areas']}: {json.dumps(trajectory.get('volatile_areas', []), ensure_ascii=False)}\n"
        )

    user_content = (
        f"[system_time: {now.strftime('%Y-%m-%dT%H:%M')}]\n\n"
        f"{L['contradiction_details']}：\n{items_text}"
        f"{L['related_historical_obs']}：\n{hist_text}"
        f"{traj_block}"
    )
    messages = [
        {"role": "system", "content": get_prompt("sleep.cross_validate", language)},
        {"role": "user", "content": user_content},
    ]
    raw = call_llm(messages, llm_config)
    return _parse_json_array(raw)

def generate_strategies(changed_items: list[dict], config: dict,
                        current_profile: list[dict] | None = None,
                        trajectory: dict | None = None) -> list[dict]:
    llm_config = config.get("llm", {})
    language = config.get("language", "zh")
    L = get_labels("context.labels", language)
    if not changed_items:
        return []

    items_text = ""
    for item in changed_items:
        items_text += (
            f"[{item.get('change_type', '?')}] [{item.get('category', '?')}] "
            f"{item.get('subject', '?')}: {item.get('claim', '?')}"
        )
        if item.get("source_type"):
            items_text += f" (source={item['source_type']})"
        items_text += "\n"

    profile_context = ""
    if current_profile:
        profile_lines = []
        for p in current_profile:
            layer_tag = L["layer_core"] if p.get("layer") == "confirmed" else L["layer_suspected"]
            profile_lines.append(f"  {layer_tag} [{p['category']}] {p['subject']}: {p['value']}")
        profile_context = f"\n{L['user_profile_ref']}：\n" + "\n".join(profile_lines) + "\n"

    traj_context = ""
    if trajectory and trajectory.get("life_phase"):
        traj_context = (
            f"\n{L['trajectory_ref_strategy']}：\n"
            f"  {L['phase']}: {trajectory.get('life_phase', '?')}\n"
            f"  {L['direction']}: {trajectory.get('trajectory_direction', '?')}\n"
            f"  {L['volatile_areas']}: {json.dumps(trajectory.get('volatile_areas', []), ensure_ascii=False)}\n"
        )

    user_model = load_user_model()
    model_context = ""
    if user_model:
        model_lines = [f"  {m['dimension']}: {m['assessment']}" for m in user_model]
        model_context = f"\n{L['user_comm_style']}：\n" + "\n".join(model_lines) + "\n"

    now = get_now()
    user_content = (
        f"[system_time: {now.strftime('%Y-%m-%dT%H:%M')}]\n\n"
        f"{L['changed_items']}：\n{items_text}"
        f"{profile_context}"
        f"{traj_context}"
        f"{model_context}"
    )
    messages = [
        {"role": "system", "content": get_prompt("sleep.generate_strategies", language)},
        {"role": "user", "content": user_content},
    ]
    raw = call_llm(messages, llm_config)
    return _parse_json_array(raw)

def analyze_user_model(conversations: list[dict], config: dict,
                       current_profile: list[dict] | None = None) -> list[dict]:
    llm_config = config.get("llm", {})
    language = config.get("language", "zh")
    L = get_labels("context.labels", language)

    dialogue = ""
    for msg in conversations:
        dialogue += f"{L['user']}：{msg['user_input']}\n"
        dialogue += f"{L['assistant']}：{msg['assistant_reply']}\n\n"

    if not dialogue.strip():
        return []

    existing_model = load_user_model()
    if existing_model:
        model_lines = []
        for m in existing_model:
            model_lines.append(f"  {m['dimension']}: {m['assessment']}")
        existing_block = f"{L['existing_model']}：\n" + "\n".join(model_lines)
    else:
        existing_block = f"{L['existing_model']}：{L['first_analysis']}"

    profile_block = ""
    if current_profile:
        profile_lines = []
        for p in current_profile:
            layer_tag = L["layer_core"] if p.get("layer") == "confirmed" else L["layer_suspected"]
            profile_lines.append(f"  {layer_tag} [{p['category']}] {p['subject']}: {p['value']}")
        profile_block = f"\n{L['user_profile_background']}：\n" + "\n".join(profile_lines) + "\n"

    prompt = get_prompt("sleep.analyze_user_model", language, existing_model_block=existing_block)

    now = get_now()
    user_content = f"[system_time: {now.strftime('%Y-%m-%dT%H:%M')}]\n\n{dialogue}{profile_block}"
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": user_content},
    ]
    raw = call_llm(messages, llm_config)
    results = _parse_json_array(raw)
    return [r for r in results if isinstance(r, dict) and r.get("dimension") and r.get("assessment")]

def analyze_behavioral_patterns(observations: list[dict],
                                 current_profile: list[dict],
                                 trajectory: dict | None,
                                 config: dict) -> list[dict]:
    llm_config = config.get("llm", {})
    language = config.get("language", "zh")
    L = get_labels("context.labels", language)
    if not observations or len(observations) < 1:
        return []

    profile_text = ""
    if current_profile:
        for p in current_profile:
            layer_tag = L["layer_core"] if p.get("layer") == "confirmed" else L["layer_suspected"]
            profile_text += f"  {layer_tag} [{p['category']}] {p['subject']}: {p['value']}\n"
    else:
        profile_text = f"{L['no_profile']}\n"

    obs_text = ""
    for o in observations:
        obs_text += f"[{o['type']}] {o['content']}"
        if o.get("subject"):
            obs_text += f" (subject: {o['subject']})"
        obs_text += "\n"

    trajectory_block = _format_trajectory_block(trajectory, language=language)

    user_content = (
        f"[system_time: {get_now().strftime('%Y-%m-%dT%H:%M')}]\n\n"
        f"{L['current_profile_label']}：\n{profile_text}\n"
        f"{L['recent_obs']}：\n{obs_text}\n"
        f"{trajectory_block}"
        f"\n{L['output_json_array']}"
    )
    messages = [
        {"role": "system", "content": get_prompt("sleep.behavioral_pattern", language)},
        {"role": "user", "content": user_content},
    ]
    raw = call_llm(messages, llm_config)
    results = _parse_json_array(raw)
    return [r for r in results
            if isinstance(r, dict) and r.get("category") and r.get("inferred_value")]

def cross_verify_suspected_facts(suspected_facts: list[dict], config: dict,
                                  trajectory: dict | None = None) -> list[dict]:
    llm_config = config.get("llm", {})
    language = config.get("language", "zh")
    L = get_labels("context.labels", language)
    if not suspected_facts:
        return []

    all_current = load_full_current_profile()
    all_facts_map = {p["id"]: p for p in all_current}

    items_text = ""
    seen_subjects = set()
    for f in suspected_facts:
        ev = f.get("evidence", [])
        mention_count = f.get("mention_count", 1) or 1
        start = f["start_time"].strftime("%Y-%m-%d") if f.get("start_time") else "?"
        updated = f["updated_at"].strftime("%Y-%m-%d") if f.get("updated_at") else "?"

        items_text += (
            f"{L['fact_id']}={f['id']}:\n"
            f"  [{f['category']}] {f['subject']}: {f['value']}\n"
            f"  {L['mentions']}{mention_count}, source={f.get('source_type', 'stated')}, "
            f"{L['start']}={start}, {L['updated']}={updated}, {L['evidence']}{len(ev)}\n"
        )
        if ev:
            items_text += f"  {L['evidence']}: {json.dumps(ev, ensure_ascii=False)}\n"
        if f.get("supersedes"):
            old_fact = all_facts_map.get(f["supersedes"])
            if old_fact:
                old_layer = old_fact.get("layer", "suspected")
                old_start = old_fact["start_time"].strftime("%Y-%m-%d") if old_fact.get("start_time") else "?"
                old_mc = old_fact.get("mention_count", 1) or 1
                items_text += (
                    f"  {L['supersedes']}{f['supersedes']}: "
                    f"{old_fact['value']} ({L['layer_equals']}{old_layer}, {L['mentions']}{old_mc}, {L['start']}={old_start})\n"
                )
            else:
                items_text += f"  {L['supersedes']}{f['supersedes']}\n"
        items_text += "\n"
        seen_subjects.add((f.get("category", ""), f.get("subject", "")))

    timeline_context = ""
    for cat, subj in seen_subjects:
        if cat and subj:
            subj_timeline = load_timeline(category=cat, subject=subj)
            if subj_timeline:
                timeline_context += f"\n[{cat}] {subj} {L['full_timeline']}：\n"
                for t in subj_timeline:
                    t_start = t["start_time"].strftime("%Y-%m-%d") if t.get("start_time") else "?"
                    eff_end = t.get("human_end_time") or t.get("end_time")
                    if t.get("rejected"):
                        timeline_context += f"  {t['value']} ({t_start}) {L['rejected']}\n"
                    elif eff_end:
                        t_end = eff_end.strftime("%Y-%m-%d")
                        timeline_context += f"  {t['value']} ({t_start} ~ {t_end}) {L['closed']}\n"
                    else:
                        layer = t.get("layer", "suspected")
                        tag = L["layer_disputed"] if t.get("superseded_by") else f"[{layer}]"
                        timeline_context += f"  {t['value']} ({t_start} ~ {L['until_now']}) {tag}\n"

    obs_context = ""
    for cat, subj in seen_subjects:
        if not subj:
            continue
        subj_summaries = load_summaries_by_observation_subject(subject=subj)
        all_subj = subj_summaries.get("before", [])
        if all_subj:
            obs_context += f"\n[{cat}] {subj} {L['related_summaries']}：\n"
            for s in all_subj[-30:]:
                time_str = s['user_input_at'].strftime('%Y-%m-%d') if s.get('user_input_at') else '?'
                obs_context += f"  [{time_str}] {s.get('ai_summary', '')}\n"

    traj_context = ""
    if trajectory and trajectory.get("life_phase"):
        traj_context = (
            f"\n{L['trajectory_ref_label']}：\n"
            f"  {L['anchors_stable']}: {json.dumps(trajectory.get('key_anchors', []), ensure_ascii=False)}\n"
            f"  {L['volatile_areas']}: {json.dumps(trajectory.get('volatile_areas', []), ensure_ascii=False)}\n"
        )

    now = get_now()
    user_content = (
        f"[system_time: {now.strftime('%Y-%m-%dT%H:%M')}]\n\n"
        f"{L['suspected_to_verify']}：\n{items_text}"
        f"{timeline_context}"
        f"{obs_context}"
        f"{traj_context}"
        f"\n{L['output_json']}"
    )
    messages = [
        {"role": "system", "content": get_prompt("sleep.cross_verify_suspected", language)},
        {"role": "user", "content": user_content},
    ]
    if timeline_context:
        pass
    if obs_context:
        pass
    raw = call_llm(messages, llm_config)
    results = _parse_json_array(raw)
    return [r for r in results if isinstance(r, dict) and r.get("fact_id") and r.get("action")]

def resolve_disputes_with_llm(disputed_pairs: list[dict], config: dict,
                              trajectory: dict | None = None) -> list[dict]:
    llm_config = config.get("llm", {})
    language = config.get("language", "zh")
    L = get_labels("context.labels", language)
    if not disputed_pairs:
        return []

    traj_context = ""
    if trajectory and trajectory.get("life_phase"):
        traj_context = (
            f"\n{L['trajectory_ref_label']}：\n"
            f"  {L['anchors_stable']}: {json.dumps(trajectory.get('key_anchors', []), ensure_ascii=False)}\n"
            f"  {L['volatile_areas']}: {json.dumps(trajectory.get('volatile_areas', []), ensure_ascii=False)}\n"
        )

    now = get_now()
    all_results = []

    for i, pair in enumerate(disputed_pairs):
        old = pair["old"]
        new = pair["new"]

        old_start = old["start_time"].strftime("%Y-%m-%d") if old.get("start_time") else "?"
        old_mention = old.get("mention_count", 1) or 1
        old_layer = old.get("layer", "suspected")
        old_layer_tag = L["core_profile"] if old_layer == "confirmed" else L["suspected_profile"]

        new_start = new["start_time"].strftime("%Y-%m-%d") if new.get("start_time") else "?"
        new_mention = new.get("mention_count", 1) or 1

        pivot_time = new.get("start_time") or new.get("created_at")
        pivot_str = pivot_time.strftime("%Y-%m-%d") if pivot_time else "?"

        trigger_text = ""
        new_evidence = new.get("evidence") or []
        for ev in new_evidence:
            if ev.get("observation"):
                trigger_text = ev["observation"]
                break
        trigger_line = f"{L['trigger_text']}: \"{trigger_text}\"\n" if trigger_text else ""

        item_text = (
            f"{L['old_val']}: \"{old['value']}\" ({old_layer_tag}, {L['from_date_onwards'].format(date=old_start)}, {L['mentions']}{old_mention})\n"
            f"{L['new_val']}: \"{new['value']}\" ({L['suspected_profile']}, {L['from_date_onwards'].format(date=new_start)}, {L['mentions']}{new_mention})\n"
            f"{trigger_line}"
            f"{L['contradiction_created']}: {pivot_str}\n"
        )

        subject_key = old.get("subject", "") or new.get("subject", "")
        if pivot_time and subject_key:
            summary_groups = load_summaries_by_observation_subject(
                subject=subject_key,
                pivot_time=pivot_time,
            )
        elif pivot_time:
            summary_groups = load_conversation_summaries_around(
                pivot_time=pivot_time,
                limit_before=30,
                limit_after=50,
            )
        else:
            summary_groups = {"before": [], "after": []}

        before_summaries = summary_groups.get("before", [])
        if before_summaries:
            item_text += f"\n{L['pre_summaries']}:\n"
            session_ids_before = []
            for s in before_summaries:
                sid = s.get("session_id", "")
                if sid and sid not in session_ids_before:
                    session_ids_before.append(sid)
            for s in before_summaries[-20:]:
                time_str = s['user_input_at'].strftime('%Y-%m-%d') if s.get('user_input_at') else '?'
                sid = s.get("session_id", "")
                sess_num = session_ids_before.index(sid) + 1 if sid in session_ids_before else "?"
                item_text += f"  [{time_str} {L['session']}{sess_num}] {s.get('ai_summary', '')}\n"
        else:
            item_text += f"\n{L['pre_summaries_none']}\n"

        after_summaries = summary_groups.get("after", [])
        if after_summaries:
            item_text += f"\n{L['post_summaries']}:\n"
            session_ids_after = []
            for s in after_summaries:
                sid = s.get("session_id", "")
                if sid and sid not in session_ids_after:
                    session_ids_after.append(sid)
            base_num = len(session_ids_before) if before_summaries else 0
            for s in after_summaries[:30]:
                time_str = s['user_input_at'].strftime('%Y-%m-%d') if s.get('user_input_at') else '?'
                sid = s.get("session_id", "")
                sess_num = base_num + (session_ids_after.index(sid) + 1) if sid in session_ids_after else "?"
                item_text += f"  [{time_str} {L['session']}{sess_num}] {s.get('ai_summary', '')}\n"
        else:
            item_text += f"\n{L['post_summaries_none']}\n"

        user_content = (
            f"[system_time: {now.strftime('%Y-%m-%dT%H:%M')}]\n\n"
            f"{L['contradiction']}: [{old.get('category', '?')}] {old.get('subject', '?')}\n"
            f"{item_text}"
            f"{traj_context}\n"
            f"old_fact_id={old['id']}, new_fact_id={new['id']}\n\n"
            f"{L['output_json_object']}\n"
            f"{{\"old_fact_id\": {old['id']}, \"new_fact_id\": {new['id']}, \"action\": \"{L['dispute_action_hint']}\", \"reason\": \"{L['dispute_reason_hint']}\"}}"
        )
        messages = [
            {"role": "system", "content": get_prompt("sleep.resolve_dispute", language)},
            {"role": "user", "content": user_content},
        ]

        category = old.get('category', '?')
        subject = old.get('subject', '?')
        raw = call_llm(messages, llm_config)

        result = _parse_json_object(raw)
        if not result:
            arr = _parse_json_array(raw)
            result = arr[0] if arr else None

        if result and isinstance(result, dict):
            if not result.get("old_fact_id"):
                result["old_fact_id"] = old["id"]
            if not result.get("new_fact_id"):
                result["new_fact_id"] = new["id"]
            if result.get("action") in ("accept_new", "reject_new", "keep"):
                all_results.append(result)
            else:
                pass
        else:
            pass

    return all_results

def generate_trajectory_summary(current_profile: list[dict],
                                config: dict,
                                new_observations: list[dict] | None = None) -> dict:
    llm_config = config.get("llm", {})
    language = config.get("language", "zh")
    L = get_labels("context.labels", language)

    profile_text = ""
    if current_profile:
        for p in current_profile:
            layer_tag = L["layer_core"] if p.get("layer") == "confirmed" else L["layer_suspected"]
            profile_text += f"  {layer_tag} [{p['category']}] {p['subject']}: {p['value']}\n"
    else:
        profile_text = f"{L['no_profile']}\n"

    new_obs_text = ""
    if new_observations:
        for o in new_observations:
            obs_type = o.get("type") or o.get("observation_type", "?")
            content = o.get("content", "")
            new_obs_text += f"  [{obs_type}] {content}\n"
    else:
        new_obs_text = f"{L['no_new_obs']}\n"

    historical_obs = load_observations(limit=200)
    hist_obs_text = ""
    if historical_obs:
        for o in historical_obs:
            time_str = o['created_at'].strftime('%Y-%m-%d') if o.get('created_at') else '?'
            hist_obs_text += f"  [{time_str}] [{o['observation_type']}] {o['content']}\n"
    else:
        hist_obs_text = f"{L['no_historical']}\n"

    events = load_active_events(top_k=10)
    event_text = ""
    if events:
        for e in events:
            event_text += f"  [{e['category']}] {e['summary']}\n"
    else:
        event_text = f"{L['no_events']}\n"

    prev_trajectory = load_trajectory_summary()
    prev_text = ""
    if prev_trajectory:
        prev_text = (
            f"{L['prev_trajectory']}：\n"
            f"  {L['phase']}: {prev_trajectory['life_phase']}\n"
            f"  {L['characteristics']}: {prev_trajectory['phase_characteristics']}\n"
            f"  {L['direction']}: {prev_trajectory['trajectory_direction']}\n"
            f"  {L['stability']}: {prev_trajectory['stability_assessment']}\n"
            f"  {L['recent_momentum']}: {prev_trajectory.get('recent_momentum', '')}\n"
            f"  {L['summary']}: {prev_trajectory.get('full_summary', '')}\n"
        )
    else:
        prev_text = f"{L['prev_trajectory']}：{L['first_generation']}\n"

    user_content = (
        f"[system_time: {get_now().strftime('%Y-%m-%dT%H:%M')}]\n\n"
        f"{L['active_profile']}：\n{profile_text}\n"
        f"{L['new_observations']}：\n{new_obs_text}\n"
        f"{L['historical_obs']}：\n{hist_obs_text}\n"
        f"{L['recent_events']}：\n{event_text}\n"
        f"{prev_text}"
    )
    messages = [
        {"role": "system", "content": get_prompt("sleep.trajectory_summary", language)},
        {"role": "user", "content": user_content},
    ]
    raw = call_llm(messages, llm_config)
    return _parse_json_object(raw)

def _sweep_uncovered_observations(observations: list[dict], config: dict,
                                   trajectory: dict | None = None):
    llm_config = config.get("llm", {})
    language = config.get("language", "zh")
    L = get_labels("context.labels", language)

    statements = [o for o in observations if o.get("type") in ("statement", "contradiction")]
    if not statements:
        return

    _sweep_times = [o.get("_conv_time") for o in statements if o.get("_conv_time")]
    _sweep_conv_time = max(_sweep_times) if _sweep_times else None

    all_facts = load_full_current_profile()

    obs_text = ""
    for o in statements:
        ts = o.get("_conv_time")
        time_str = f"[{ts.strftime('%Y-%m-%d %H:%M')}] " if ts and hasattr(ts, 'strftime') else ""
        obs_text += f"{time_str}[statement] {o['content']}"
        if o.get("subject"):
            obs_text += f" (subject: {o['subject']})"
        obs_text += "\n"

    fact_text = ""
    if all_facts:
        for f in all_facts:
            start = f["start_time"].strftime("%m-%d") if f.get("start_time") and hasattr(f["start_time"], 'strftime') else "?"
            updated = f["updated_at"].strftime("%m-%d") if f.get("updated_at") and hasattr(f["updated_at"], 'strftime') else "?"
            layer_tag = L["layer_core"] if f.get("layer") == "confirmed" else L["layer_suspected"]
            fact_text += (
                f"[id={f['id']}] {layer_tag} [{f['category']}] {f['subject']}: {f['value']} "
                f"({L['start']}={start}, {L['updated']}={updated})\n"
            )
    else:
        fact_text = f"{L['no_profile']}\n"

    traj_context = ""
    if trajectory and trajectory.get("life_phase"):
        traj_context = (
            f"\n{L['sweep_traj_ref']}：\n"
            f"  {L['sweep_current_phase']}: {trajectory.get('life_phase', '?')}\n"
            f"  {L['sweep_anchors_stable']}: {json.dumps(trajectory.get('key_anchors', []), ensure_ascii=False)}\n"
            f"  {L['volatile_areas']}: {json.dumps(trajectory.get('volatile_areas', []), ensure_ascii=False)}\n"
        )

    now = get_now()
    messages = [
        {"role": "system", "content": get_prompt("sleep.sweep_uncovered", language)},
        {"role": "user", "content": (
            f"[system_time: {now.strftime('%Y-%m-%dT%H:%M')}]\n"
            f"{L['birth_year_note'].format(year=now.year, result=now.year - 25)}\n\n"
            f"{L['statement_obs']}：\n{obs_text}\n"
            f"{L['current_all_profile']}：\n{fact_text}"
            f"{traj_context}"
        )},
    ]
    raw = call_llm(messages, llm_config)
    result = _parse_json_object(raw)
    if result and ("new_facts" in result or "contradictions" in result):
        new_facts_list = result.get("new_facts", [])
        sweep_contradictions = result.get("contradictions", [])
    else:
        new_facts_list = _parse_json_array(raw)
        sweep_contradictions = []

    printed_header = False
    def _sweep_header():
        nonlocal printed_header
        if not printed_header:
            printed_header = True

    if new_facts_list:
        _sweep_header()
        for nf in new_facts_list:
            if not isinstance(nf, dict) or not nf.get("category") or not nf.get("subject") or not nf.get("value"):
                continue
            value = nf["value"]
            if value.startswith(L["dirty_value_prefix"]) or len(value) > 80:
                continue
            decay = nf.get("decay_days")
            fact_id = save_profile_fact(
                category=nf["category"],
                subject=nf["subject"],
                value=nf["value"],
                source_type=nf.get("source_type", "stated"),
                decay_days=decay,
                start_time=_sweep_conv_time,
            )
            decay_str = f", 过期:{decay}天" if decay else ""

    if sweep_contradictions:
        _sweep_header()
        for s in sweep_contradictions:
            new_val = s.get("new_value")
            if not new_val:
                continue
            fid = s.get("fact_id")
            fact = None
            if fid:
                for af in all_facts:
                    if af.get("id") == fid:
                        fact = af
                        break
            if not fact:
                cat = s.get("category")
                subj = s.get("subject")
                if cat and subj:
                    fact = find_current_fact(cat, subj)
            if not fact:
                continue
            if new_val.strip().lower() == (fact.get("value") or "").strip().lower():
                add_evidence(fact["id"], {"reason": s.get("reason", L["mention_again_reason"])},
                             reference_time=_sweep_conv_time)
                continue
            new_id = save_profile_fact(
                category=fact["category"],
                subject=fact["subject"],
                value=new_val,
                source_type="stated",
                decay_days=fact.get("decay_days"),
                start_time=_sweep_conv_time,
            )

def get_unprocessed_conversations() -> dict[str, list[dict]]:
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT r.id, r.session_id, r.user_input, r.assistant_reply, "
                "       ct.ai_summary, r.user_input_at, ct.intent "
                "FROM raw_conversations r "
                "LEFT JOIN conversation_turns ct "
                "  ON r.session_id = ct.session_id "
                "  AND r.user_input_at = ct.user_input_at "
                "WHERE r.processed = FALSE "
                "ORDER BY r.id"
            )
            sessions: dict[str, list[dict]] = {}
            for id_, sid, user_input, assistant_reply, ai_summary, user_input_at, intent in cur.fetchall():
                if sid not in sessions:
                    sessions[sid] = []
                sessions[sid].append({
                    "id": id_,
                    "user_input": user_input,
                    "assistant_reply": assistant_reply,
                    "ai_summary": ai_summary or user_input,
                    "user_input_at": user_input_at,
                    "intent": intent or "",
                })
            return sessions
    finally:
        conn.close()

def mark_processed(message_ids: list[int]):
    if not message_ids:
        return
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE raw_conversations SET processed = TRUE WHERE id = ANY(%s)",
                (message_ids,),
            )
        conn.commit()
    finally:
        conn.close()

def _parse_json_array(raw: str) -> list[dict]:
    text = raw.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    start = text.find("[")
    end = text.rfind("]") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except (json.JSONDecodeError, ValueError):
            pass
    merged = []
    for m in re.finditer(r'\[.*?\]', text, re.DOTALL):
        try:
            arr = json.loads(m.group())
            if isinstance(arr, list):
                merged.extend(arr)
        except (json.JSONDecodeError, ValueError):
            continue
    if merged:
        pass
    return merged

def _parse_json_object(raw: str) -> dict:
    text = raw.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        text = text[start:end]
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return {}

def run():
    config = load_config()
    language = config.get("language", "zh")
    L = get_labels("context.labels", language)

    session_convs = get_unprocessed_conversations()
    if not session_convs:
        return

    total_msgs = sum(len(msgs) for msgs in session_convs.values())

    all_msg_ids = []
    all_convs = []
    all_observations = []

    existing_profile = load_full_current_profile()

    trajectory = load_trajectory_summary()
    if trajectory and trajectory.get("life_phase"):
        pass
    else:
        trajectory = None

    total_session_count = len(session_convs)
    for session_idx, (session_id, convs) in enumerate(session_convs.items(), 1):
        msg_ids = [c["id"] for c in convs]
        all_msg_ids.extend(msg_ids)
        all_convs.extend(convs)

        result = extract_observations_and_tags(convs, config,
                                               existing_profile=existing_profile)
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

    behavioral_signals = []
    if all_observations and len(all_observations) >= 1:
        current_profile = load_full_current_profile()
        behavioral_signals = analyze_behavioral_patterns(
            all_observations, current_profile, trajectory, config
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
                    if existing and existing.get("value", "").strip().lower() == inferred.strip().lower():
                        pass
                    else:
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
                        pass
        else:
            pass

    current_profile = load_full_current_profile()
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

    if all_observations:
        classifications = classify_observations(
            all_observations, current_profile, config, timeline,
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
                else:
                    pass

        supports = [c for c in classifications if c.get("action") == "support"]
        contradictions = [c for c in classifications if c.get("action") == "contradict"]
        evidence_against_list = [c for c in classifications if c.get("action") == "evidence_against"]
        new_obs_cls = [c for c in classifications if c.get("action") == "new"]
        irrelevant_cls = [c for c in classifications if c.get("action") == "irrelevant"]

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
        changed_items = []
        if new_obs_cls:
            new_obs_data = []
            for c in new_obs_cls:
                idx = c.get("obs_index")
                if isinstance(idx, int) and 0 <= idx < len(all_observations):
                    new_obs_data.append(all_observations[idx])

            if new_obs_data:
                _new_obs_times = [o.get("_conv_time") for o in new_obs_data if o.get("_conv_time")]
                _new_batch_time = max(_new_obs_times) if _new_obs_times else None
                new_facts = create_new_facts(
                    new_obs_data, current_profile, config, behavioral_signals,
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
                changed_items.append({
                    "change_type": "contradict",
                    "category": fact["category"],
                    "subject": fact["subject"],
                    "claim": f"{fact['value']}→{new_val}",
                })

        strategy_count = 0
        if changed_items:
            strategies = generate_strategies(changed_items, config,
                                            current_profile=current_profile,
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
                    pass

    else:
        pass

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
                confirmed_count += 1
            else:
                pass

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
                dispute_resolved += 1
            elif action == "reject_new":
                resolve_dispute(old_fid, new_fid, accept_new=False, resolution_time=latest_conv_time)
                dispute_resolved += 1
            else:
                pass

    else:
        pass

    expired_facts = get_expired_facts(reference_time=latest_conv_time)
    stale_count = 0
    if expired_facts:
        for f in expired_facts:
            fact_id = f["id"]
            cat = f["category"]
            subj = f["subject"]

            close_time_period(fact_id, end_time=latest_conv_time)
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
                pass
            stale_count += 1

    else:
        pass

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
        current_profile_for_model = load_full_current_profile()
        model_results = analyze_user_model(all_convs, config,
                                           current_profile=current_profile_for_model)
        for m in model_results:
            upsert_user_model(
                dimension=m["dimension"],
                assessment=m["assessment"],
                evidence_summary=m.get("evidence", ""),
            )
    else:
        pass

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

    if sessions_since_update >= 3:
        should_update_trajectory = True

    if not trajectory:
        current_profile = load_full_current_profile()
        if current_profile:
            should_update_trajectory = True

    if should_update_trajectory:
        current_profile = load_full_current_profile()
        if current_profile:
            trajectory_result = generate_trajectory_summary(
                current_profile, config, new_observations=all_observations
            )
            if trajectory_result and trajectory_result.get("life_phase"):
                try:
                    save_trajectory_summary(trajectory_result, session_count=total_sessions)
                except Exception as e:
                    pass
            else:
                pass
        else:
            pass
    else:
        pass

    mark_processed(all_msg_ids)

    try:
        from agent.utils.embedding import embed_all_memories
        embed_all_memories(config)
    except Exception as e:
        pass

    final_profile = load_full_current_profile()
    if final_profile:
        for p in final_profile:
            layer = p.get("layer", "suspected")
            mc = p.get("mention_count", 1) or 1
            layer_tag = L["layer_core"] if layer == "confirmed" else L["layer_suspected"]

if __name__ == "__main__":
    run()
