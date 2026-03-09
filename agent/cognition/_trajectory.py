"""Trajectory analysis: detect deviation from known user patterns."""

import json
from agent.utils.time_context import get_now
from agent.config.prompts import get_prompt, get_labels


def build_trajectory_context(
    user_input: str,
    memories: dict,
    language: str,
) -> list[dict] | None:
    """Build trajectory analysis messages. Returns None if insufficient data."""
    from agent.utils.profile_filter import prepare_profile

    profile = memories.get("profile", [])
    hypotheses = memories.get("hypotheses", [])
    user_model_data = memories.get("user_model", [])

    if len(profile) < 3 and len(hypotheses) < 3:
        return None

    known_keywords = set()
    for p in profile:
        known_keywords.update(p.get("value", "").split())
        known_keywords.update(p.get("field", "").split())
        known_keywords.add(p.get("category", ""))
    for h in hypotheses:
        known_keywords.update(h.get("value", "").split())
        known_keywords.update(h.get("subject", "").split())
        known_keywords.add(h.get("category", ""))
    known_keywords = {k for k in known_keywords if len(k) >= 2}

    input_chars = user_input.lower()
    overlap = sum(1 for k in known_keywords if k.lower() in input_chars)
    if overlap >= 2:
        return None

    L = get_labels("context.labels", language)

    top_profile, _ = prepare_profile(
        hypotheses, query_text=user_input, max_entries=15, language=language,
    )

    known_parts = []
    if profile:
        lines = [f"  [{p['category']}] {p['field']}: {p['value']}" for p in profile[:15]]
        known_parts.append(f"{L['confirmed_profile']}：\n" + "\n".join(lines))
    if top_profile:
        trusted = [h for h in top_profile
                   if h.get("layer") in ("confirmed", "suspected")][:10]
        if trusted:
            lines = [f"  [{h['category']}] {h['subject']}: {h.get('value', '')} ({h.get('layer', 'suspected')})"
                     for h in trusted]
            known_parts.append(f"{L['high_prob_hypotheses']}：\n" + "\n".join(lines))
    if user_model_data:
        lines = [f"  {m['dimension']}: {m['assessment']}" for m in user_model_data]
        known_parts.append(f"{L['user_model']}：\n" + "\n".join(lines))

    known_text = "\n\n".join(known_parts)

    return [
        {"role": "system", "content": get_prompt("cognition.trajectory_analysis", language)},
        {"role": "user", "content": f"[system_time: {get_now().strftime('%Y-%m-%dT%H:%M')}]\n\n{L['known_info']}：\n{known_text}\n\n{L['user_input_label']}：{user_input}"},
    ]


def parse_trajectory_result(raw: str) -> dict | None:
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
        return None


def finish_trajectory_result(raw: str) -> dict | None:
    result = parse_trajectory_result(raw)
    if not result:
        return None
    if result.get("trajectory", "no_data") in ("on_track", "no_data"):
        return None
    return result
