
import json
import asyncio
from agent.config.prompts import get_prompt, get_labels
from agent.utils.llm_client import call_llm, call_llm_async
from agent.utils.time_context import get_now
from agent.storage import (
    load_conversation_summaries_around,
    load_summaries_by_observation_subject,
)
from agent.sleep._parsing import _parse_json_array, _parse_json_object


def _preprocess_disputes(disputed_pairs: list[dict], language: str = "en") -> tuple[list[dict], list[dict]]:
    """Shared rule-based preprocessing for dispute resolution.
    Returns (rule_results, llm_candidates)."""
    L = get_labels("context.labels", language)
    rule_results = []
    llm_candidates = []
    now = get_now()
    for pair in disputed_pairs:
        old = pair["old"]
        new = pair["new"]
        new_mc = new.get("mention_count") or 1
        old_mc = old.get("mention_count") or 1
        new_start = new.get("start_time")
        old_start = old.get("start_time")

        if new_mc >= 2 and new_start and old_start and new_start > old_start:
            rule_results.append({
                "old_fact_id": old["id"], "new_fact_id": new["id"],
                "action": "accept_new",
                "reason": "规则：新值mention>=2且时间更新"
            })
            continue

        dispute_age = (now - new_start).days if new_start else 0
        if dispute_age > 90:
            if new_mc > old_mc:
                rule_results.append({
                    "old_fact_id": old["id"], "new_fact_id": new["id"],
                    "action": "accept_new",
                    "reason": f"规则：争议{dispute_age}天，新值mention更高"
                })
            else:
                rule_results.append({
                    "old_fact_id": old["id"], "new_fact_id": new["id"],
                    "action": "reject_new",
                    "reason": f"规则：争议{dispute_age}天，旧值mention更高"
                })
            continue

        llm_candidates.append(pair)

    return rule_results, llm_candidates


def _build_dispute_messages(pair: dict, traj_context: str, language: str = "en") -> list[dict]:
    """Build LLM messages for a single dispute pair."""
    L = get_labels("context.labels", language)
    now = get_now()
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
    return [
        {"role": "system", "content": get_prompt("sleep.resolve_dispute", language)},
        {"role": "user", "content": user_content},
    ]


def _parse_dispute_result(raw: str, old_id: int, new_id: int) -> dict | None:
    """Parse LLM response for a single dispute."""
    result = _parse_json_object(raw)
    if not result:
        arr = _parse_json_array(raw)
        result = arr[0] if arr else None
    if result and isinstance(result, dict):
        if not result.get("old_fact_id"):
            result["old_fact_id"] = old_id
        if not result.get("new_fact_id"):
            result["new_fact_id"] = new_id
        if result.get("action") in ("accept_new", "reject_new", "keep"):
            return result
    return None


def _build_traj_context(trajectory: dict | None, language: str = "en") -> str:
    """Build trajectory context string for dispute resolution."""
    if not trajectory or not trajectory.get("life_phase"):
        return ""
    L = get_labels("context.labels", language)
    return (
        f"\n{L['trajectory_ref_label']}：\n"
        f"  {L['anchors_stable']}: {json.dumps(trajectory.get('key_anchors', []), ensure_ascii=False)}\n"
        f"  {L['volatile_areas']}: {json.dumps(trajectory.get('volatile_areas', []), ensure_ascii=False)}\n"
    )


def resolve_disputes_with_llm(disputed_pairs: list[dict], config: dict,
                              trajectory: dict | None = None) -> list[dict]:
    llm_config = config.get("llm", {})
    language = config.get("language", "en")
    if not disputed_pairs:
        return []

    rule_results, llm_candidates = _preprocess_disputes(disputed_pairs, language)
    if not llm_candidates:
        return rule_results

    traj_context = _build_traj_context(trajectory, language)
    all_results = []

    for pair in llm_candidates:
        messages = _build_dispute_messages(pair, traj_context, language)
        raw = call_llm(messages, llm_config)
        result = _parse_dispute_result(raw, pair["old"]["id"], pair["new"]["id"])
        if result:
            all_results.append(result)

    return rule_results + all_results


async def resolve_disputes_with_llm_async(disputed_pairs: list[dict], config: dict,
                                           trajectory: dict | None = None) -> list[dict]:
    llm_config = config.get("llm", {})
    language = config.get("language", "en")
    if not disputed_pairs:
        return []

    rule_results, llm_candidates = _preprocess_disputes(disputed_pairs, language)
    if not llm_candidates:
        return rule_results

    traj_context = _build_traj_context(trajectory, language)

    async def _resolve_one(pair: dict) -> dict | None:
        messages = _build_dispute_messages(pair, traj_context, language)
        raw = await call_llm_async(messages, llm_config)
        return _parse_dispute_result(raw, pair["old"]["id"], pair["new"]["id"])

    tasks = [_resolve_one(pair) for pair in llm_candidates]
    results = await asyncio.gather(*tasks)
    return rule_results + [r for r in results if r is not None]
