
import json
import asyncio
from agent.config.prompts import get_prompt, get_labels
from agent.utils.llm_client import call_llm
from agent.utils.time_context import get_now
from agent.storage import (
    load_observations, load_trajectory_summary,
    load_active_events, load_fact_edges,
    save_fact_edge, save_trajectory_summary,
)
from agent.sleep._parsing import _parse_json_array, _parse_json_object


def generate_trajectory_summary(current_profile: list[dict],
                                config: dict,
                                new_observations: list[dict] | None = None) -> dict:
    llm_config = config.get("llm", {})
    language = config.get("language", "en")
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

    historical_obs = load_observations(limit=80)
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
            f"  {L['phase']}: {prev_trajectory.get('life_phase', '')}\n"
            f"  {L['characteristics']}: {prev_trajectory.get('phase_characteristics', '')}\n"
            f"  {L['direction']}: {prev_trajectory.get('trajectory_direction', '')}\n"
            f"  {L['stability']}: {prev_trajectory.get('stability_assessment', '')}\n"
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


def extract_fact_edges(affected_fact_ids: set[int], current_profile: list[dict],
                       config: dict) -> list[dict]:
    if not affected_fact_ids:
        return []
    llm_config = config.get("llm", {})
    language = config.get("language", "en")
    L = get_labels("context.labels", language)
    prompt_text = get_prompt("sleep.extract_fact_edges", language)

    profile_map = {p["id"]: p for p in current_profile if p.get("id")}
    valid_ids = set(profile_map.keys())

    affected_facts = [profile_map[fid] for fid in affected_fact_ids if fid in profile_map]
    if not affected_facts:
        return []

    affected_text = "\n".join(
        f"  id={p['id']} [{p['category']}] {p['subject']}: {p['value']}"
        for p in affected_facts
    )

    context_profile = sorted(current_profile, key=lambda p: p.get("updated_at") or "", reverse=True)[:60]
    profile_text = "\n".join(
        f"  id={p['id']} [{p['category']}] {p['subject']}: {p['value']}"
        for p in context_profile if p.get("id")
    )

    existing_edges = load_fact_edges(list(affected_fact_ids))
    edges_text = ""
    if existing_edges:
        edges_text = "\n".join(
            f"  {e['source_fact_id']}({e.get('src_category','')}/{e.get('src_subject','')}) "
            f"--[{e['edge_type']}]--> "
            f"{e['target_fact_id']}({e.get('tgt_category','')}/{e.get('tgt_subject','')}): "
            f"{e.get('description', '')}"
            for e in existing_edges[:20]
        )

    user_content = (
        f"{L['new_changed_facts']}:\n{affected_text}\n\n"
        f"{L['existing_profile_facts']}:\n{profile_text}\n\n"
        f"{L['existing_edges']}:\n{edges_text or '(none)'}\n"
    )

    messages = [
        {"role": "system", "content": prompt_text},
        {"role": "user", "content": user_content},
    ]

    raw = call_llm(messages, llm_config)
    edges = _parse_json_array(raw)

    saved = []
    for e in edges:
        if not isinstance(e, dict):
            continue
        src = e.get("source_id")
        tgt = e.get("target_id")
        etype = e.get("edge_type", "")
        if not src or not tgt or not etype or src == tgt:
            continue
        if src not in valid_ids or tgt not in valid_ids:
            continue
        if etype not in ("causes", "related_to", "contradicts", "temporal_sequence", "supports", "part_of"):
            continue
        desc = e.get("description", "")
        conf = min(1.0, max(0.0, float(e.get("confidence", 0.8))))
        save_fact_edge(src, tgt, etype, desc, conf)
        saved.append(e)
    return saved


# ── Async wrappers ──

async def extract_fact_edges_async(affected_fact_ids: set[int], current_profile: list[dict],
                                    config: dict) -> list[dict]:
    return await asyncio.to_thread(extract_fact_edges, affected_fact_ids, current_profile, config)


async def generate_trajectory_summary_async(current_profile: list[dict],
                                             config: dict,
                                             new_observations: list[dict] | None = None) -> dict:
    return await asyncio.to_thread(generate_trajectory_summary, current_profile, config, new_observations)
