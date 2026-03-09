
import json
import asyncio
from agent.config.prompts import get_prompt, get_labels
from agent.utils.llm_client import call_llm
from agent.utils.time_context import get_now
from agent.storage import load_existing_tags
from agent.sleep._parsing import _parse_json_array, _parse_json_object
from agent.sleep._formatting import _format_profile_for_llm


def extract_observations_and_tags(conversations: list[dict], config: dict,
                                   existing_profile: list[dict] | None = None) -> dict:
    llm_config = config.get("llm", {})
    language = config.get("language", "en")
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
    language = config.get("language", "en")
    L = get_labels("context.labels", language)

    dialogue = ""
    for msg in conversations:
        dialogue += f"{L['user']}：{msg['user_input']}\n"
        dialogue += f"{L['assistant']}：{msg.get('assistant_reply') or ''}\n\n"

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
    language = config.get("language", "en")
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
    cleaned = []
    for r in results:
        if not isinstance(r, dict):
            continue
        if not r.get("action"):
            r["action"] = "new"
            r.setdefault("reason", "LLM未返回action，自动补为new")
        cleaned.append(r)
    return cleaned


def create_new_facts(new_observations: list[dict],
                     existing_profile: list[dict],
                     config: dict,
                     behavioral_signals: list | None = None,
                     trajectory: dict | None = None) -> list[dict]:
    llm_config = config.get("llm", {})
    language = config.get("language", "en")
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


# ── Async wrappers ──

async def extract_observations_and_tags_async(conversations: list[dict], config: dict,
                                               existing_profile: list[dict] | None = None) -> dict:
    return await asyncio.to_thread(extract_observations_and_tags, conversations, config, existing_profile)


async def extract_events_async(conversations: list[dict], config: dict) -> list[dict]:
    return await asyncio.to_thread(extract_events, conversations, config)


async def classify_observations_async(observations: list[dict],
                                       existing_profile: list[dict],
                                       config: dict,
                                       timeline: list[dict] | None = None,
                                       trajectory: dict | None = None) -> list[dict]:
    return await asyncio.to_thread(classify_observations, observations, existing_profile, config,
                                   timeline, trajectory)


async def create_new_facts_async(observations: list[dict],
                                  existing_profile: list[dict],
                                  config: dict,
                                  behavioral_signals: list[dict] | None = None,
                                  trajectory: dict | None = None) -> list[dict]:
    return await asyncio.to_thread(create_new_facts, observations, existing_profile, config,
                                   behavioral_signals, trajectory)
