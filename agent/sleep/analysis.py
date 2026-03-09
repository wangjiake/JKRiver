
import json
import asyncio
from datetime import datetime, timedelta
from agent.config.prompts import get_prompt, get_labels
from agent.utils.llm_client import call_llm
from agent.utils.time_context import get_now
from agent.storage import (
    load_full_current_profile, load_timeline,
    load_summaries_by_observation_subject,
    load_user_model,
)
from agent.sleep._parsing import _parse_json_array
from agent.sleep._formatting import _format_trajectory_block, _format_profile_for_llm


def generate_strategies(changed_items: list[dict], config: dict,
                        current_profile: list[dict] | None = None,
                        trajectory: dict | None = None) -> list[dict]:
    llm_config = config.get("llm", {})
    language = config.get("language", "en")
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
    language = config.get("language", "en")
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
    language = config.get("language", "en")
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
    language = config.get("language", "en")
    L = get_labels("context.labels", language)
    if not suspected_facts:
        return []

    # ── 规则预处理：source_type=stated + mention_count>=2 → 直接确认 ──
    rule_results = []
    llm_candidates = []
    for f in suspected_facts:
        mc = f.get("mention_count") or 1
        if f.get("source_type") == "stated" and mc >= 2:
            rule_results.append({"fact_id": f["id"], "action": "confirm",
                                 "reason": "规则：stated+mention>=2直接确认"})
        else:
            llm_candidates.append(f)

    if not llm_candidates:
        return rule_results

    # 按 mention_count 降序，限制最多 80 条发给 LLM
    llm_candidates.sort(key=lambda f: -(f.get("mention_count") or 1))
    llm_candidates = llm_candidates[:80]

    all_current = load_full_current_profile()
    all_facts_map = {p["id"]: p for p in all_current}

    items_text = ""
    seen_subjects = set()
    for f in llm_candidates:
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

    # 按 subject 分类加载相关对话摘要（限最近 3 个月）
    obs_context = ""
    three_months_ago = get_now() - timedelta(days=90)
    for cat, subj in seen_subjects:
        if not subj:
            continue
        subj_summaries = load_summaries_by_observation_subject(subject=subj)
        all_subj = subj_summaries.get("before", [])
        all_subj = [s for s in all_subj
                     if s.get('user_input_at') and s['user_input_at'] >= three_months_ago]
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
    raw = call_llm(messages, llm_config)
    llm_results = _parse_json_array(raw)
    llm_results = [r for r in llm_results if isinstance(r, dict) and r.get("fact_id") and r.get("action")]
    return rule_results + llm_results


# ── Async wrappers ──

async def generate_strategies_async(changed_items: list[dict], config: dict,
                                     current_profile: list[dict] | None = None,
                                     trajectory: dict | None = None) -> list[dict]:
    return await asyncio.to_thread(generate_strategies, changed_items, config, current_profile, trajectory)


async def analyze_user_model_async(conversations: list[dict], config: dict,
                                    current_profile: list[dict] | None = None) -> list[dict]:
    return await asyncio.to_thread(analyze_user_model, conversations, config, current_profile)


async def analyze_behavioral_patterns_async(observations: list[dict],
                                              current_profile: list[dict],
                                              trajectory: dict | None,
                                              config: dict) -> list[dict]:
    return await asyncio.to_thread(analyze_behavioral_patterns, observations, current_profile,
                                   trajectory, config)


async def cross_verify_suspected_facts_async(suspected_facts: list[dict], config: dict,
                                              trajectory: dict | None = None) -> list[dict]:
    return await asyncio.to_thread(cross_verify_suspected_facts, suspected_facts, config, trajectory)
