import logging
import os
import re

from agent.utils.time_context import get_now
from agent.storage import save_raw_conversation, save_conversation_turn, mark_strategy_executed
from agent.config.prompts import get_labels
from agent.skills.creator import detect_skill_request, create_skill_from_chat, delete_skill, extract_skill_name
from agent.skills.executor import execute_skill
from agent.core._outsource import OUTSOURCE_TRIGGER_RE

logger = logging.getLogger(__name__)


def _build_trajectory_block(trajectory: dict, L: dict) -> str:
    """Build trajectory divergence block for memory context."""
    block = L["section_trajectory_divergence"] + "\n"
    block += f"  {L['judgment']}: {trajectory.get('trajectory', '?')} — {trajectory.get('reasoning', '')}\n"
    causes = trajectory.get("possible_causes", [])
    if causes:
        block += f"  {L['possible_causes_label']}: {', '.join(causes)}\n"
    if trajectory.get("real_need"):
        block += f"  {L['real_need_guess']}: {trajectory['real_need']}\n"
    block += f"  {L['immediate_strategy_text']}\n"
    is_temp = trajectory.get("is_temporary", True)
    block += f"  {L['persistence_label']}: {L['persistence_temp'] if is_temp else L['persistence_lasting']}"
    return block


def _inject_tool_context(tool_results: list[dict], memories: dict, llm_input: str,
                         L: dict, log_fn) -> str:
    """Inject tool results into memory context, handle image placeholders. Returns updated llm_input."""
    if not tool_results:
        return llm_input
    _tool_labels = {
        "image_describe": L["tool_label_image"],
        "web_search": L["tool_label_web_search"],
        "voice_transcribe": L["tool_label_voice"],
        "finance_query": L["tool_label_finance"],
        "health_query": L["tool_label_health"],
    }
    tool_context = "\n\n".join(
        f"【{_tool_labels.get(t['tool'], t['tool'])}】\n{t['result'].data}"
        for t in tool_results if t["result"].success
    )
    if tool_context:
        if memories["memory_text"]:
            memories["memory_text"] += "\n\n" + tool_context
        else:
            memories["memory_text"] = tool_context
        if log_fn:
            log_fn("info", f"工具结果已注入上下文 ({len(tool_results)} 个工具)")

    for t in tool_results:
        if t["tool"] == "image_describe" and t["result"].success:
            placeholder = L["image_placeholder"]
            clean_input = llm_input.replace(placeholder + " ", "").replace(placeholder, "").strip()
            llm_input = L["image_recognized_prefix"] + clean_input
    return llm_input


def _try_handle_outsource_skill(skill, processed_text: str, session, memories: dict, log_fn) -> bool:
    """
    If the outsource skill matched, call dispatch_task preview directly instead of
    relying on the LLM. Mutates memories in place. Returns True if handled.
    """
    try:
        dispatch_tool = session.tool_registry.get_tool("dispatch_task")
        if not dispatch_tool:
            return False
        task_desc = OUTSOURCE_TRIGGER_RE.sub('', processed_text).strip()
        preview_result = dispatch_tool.execute({"action": "preview", "task": task_desc})
        if preview_result.success:
            memories["_outsource_preview"] = preview_result.data
            memories["memory_text"] += f"\n\n{preview_result.data}"
            if log_fn:
                log_fn("info", f"外包预览已生成: {task_desc[:60]}")
            return True
    except Exception as _e:
        if log_fn:
            log_fn("info", f"外包直接预览失败，回退到指令注入: {_e}")
    return False


def _handle_skills(processed_text: str, session, memories: dict, L: dict, log_fn):
    """Handle skill creation, deletion, and matching."""
    language = session.full_config.get("language", "en")
    if not session.full_config.get("skills", {}).get("enabled", True):
        return

    skill_action = detect_skill_request(processed_text, language=language)
    if skill_action == "create":
        result = create_skill_from_chat(
            processed_text, session.cognition.config,
            session.tool_registry.list_available(),
            language=language,
        )
        if result["success"]:
            session.skill_registry.reload()
            inject = (f"\n\n{L['skill_created_header']}\n{L['skill_name_label']}: {result['skill_name']}\n"
                      f"{L['skill_desc_label']}: {result['description']}\n{result['message']}")
        else:
            inject = f"\n\n{L['skill_create_failed_header']}\n{result['message']}"
        memories["memory_text"] += inject
        if log_fn:
            log_fn("info", f"技能创建: {result}")
    elif skill_action == "delete":
        skill_name = extract_skill_name(processed_text, language=language)
        if skill_name:
            deleted = delete_skill(skill_name)
            if deleted:
                session.skill_registry.reload()
                inject = f"\n\n{L['skill_deleted_header']}\n{L['skill_deleted_label']}: {skill_name}"
            else:
                inject = f"\n\n{L['skill_delete_failed_header']}\n{L['skill_not_found']}: {skill_name}"
        else:
            inject = f"\n\n{L['skill_delete_failed_header']}\n{L['skill_delete_no_name']}"
        memories["memory_text"] += inject
        if log_fn:
            log_fn("info", f"技能删除: skill_name={skill_name}")

    matched_skills = session.skill_registry.match_keywords(processed_text)
    for skill in matched_skills:
        try:
            if skill.name == "outsource":
                if _try_handle_outsource_skill(skill, processed_text, session, memories, log_fn):
                    continue

            if skill.is_simple:
                inject = f"\n\n{L['skill_guide_header'].format(description=skill.description)}\n{skill.instruction}"
            else:
                result = execute_skill(
                    skill, session.tool_registry,
                    session.cognition.config, session.full_config,
                )
                inject = f"\n\n【{skill.description}】\n{result}"
            memories["memory_text"] += inject
            if log_fn:
                log_fn("info", f"技能匹配: {skill.name}")
        except Exception as e:
            if log_fn:
                log_fn("info", f"技能执行失败 {skill.name}: {e}")


def _save_turn_data(session, perception: dict, think_result: dict,
                    memories: dict, memories_used_at, user_input_at,
                    raw_user_input: str, final_response: str,
                    tool_results: list[dict], input_metadata: dict, L: dict):
    """Save raw conversation + detailed conversation turn to DB."""
    assistant_reply_at = get_now()

    for s in memories.get("strategies", []):
        mark_strategy_executed(s["id"], result=L["strategy_executed_result"])

    save_raw_conversation(
        session_id=session.id,
        session_created_at=session.created_at,
        user_input=raw_user_input,
        user_input_at=user_input_at,
        assistant_reply=final_response,
        assistant_reply_at=assistant_reply_at,
    )

    completed_at = get_now()
    memories_for_db = []
    if memories["profile"]:
        memories_for_db.append({
            "type": "profile",
            "data": [{"category": p["category"], "field": p["field"],
                       "value": p["value"]} for p in memories["profile"]],
        })
    if memories["hypotheses"]:
        memories_for_db.append({
            "type": "profile",
            "data": [{"category": h["category"], "subject": h["subject"],
                       "value": h.get("value") or h.get("claim", ""),
                       "layer": h.get("layer", "suspected")}
                      for h in memories["hypotheses"]],
        })
    if memories["events"]:
        memories_for_db.append({
            "type": "events",
            "data": [{"category": e["category"], "summary": e["summary"]}
                      for e in memories["events"]],
        })

    file_data = None
    file_path = input_metadata.get("file_path", "")
    if file_path and input_metadata.get("type") in ("image", "voice", "file"):
        try:
            if os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    file_data = f.read()
        except Exception:
            logger.warning("Failed to read file attachment: %s", file_path, exc_info=True)

    # If this turn dispatched an outsource task, skip deep memory extraction
    _used_dispatch = tool_results and any(t["tool"] == "dispatch_task" for t in tool_results)
    _need_memory = False if _used_dispatch else perception["need_memory"]
    _memory_type = perception["memory_type"] if _need_memory else "无"

    save_conversation_turn({
        "session_id": session.id,
        "session_created_at": session.created_at,
        "user_input": raw_user_input,
        "user_input_at": user_input_at,
        "assistant_reply": final_response,
        "assistant_reply_at": assistant_reply_at,
        "intent": perception["intent"],
        "need_memory": _need_memory,
        "memory_type": _memory_type,
        "ai_summary": perception["ai_summary"],
        "perception_at": perception["perception_at"],
        "memories_used": memories_for_db,
        "memories_used_at": memories_used_at,
        "raw_response": think_result["raw_response"],
        "raw_response_at": think_result["raw_response_at"],
        "verification_result": think_result["verification_result"],
        "verification_result_at": think_result["verification_result_at"],
        "final_response": think_result["final_response"],
        "final_response_at": think_result["final_response_at"],
        "thinking_notes": think_result["thinking_notes"],
        "thinking_notes_at": think_result["thinking_notes_at"],
        "completed_at": completed_at,
        "input_type": input_metadata.get("type", "text"),
        "file_path": file_path,
        "file_data": file_data,
        "tool_results": [
            {"tool": t["tool"], "params": t["params"],
             "success": t["result"].success,
             "data": t["result"].data[:500] if t["result"].success else "",
             "error": t["result"].error}
            for t in tool_results
        ] if tool_results else [],
    })


def _extract_citations(tool_results: list[dict], language: str = "en") -> str:
    L = get_labels("context.labels", language)
    citation_label = L.get("citation_header", L.get("citation_header_default", "Sources"))
    seen = set()
    lines = []
    for t in tool_results:
        if not t["result"].success:
            continue
        data = t["result"].data
        pattern = re.escape(citation_label) + r":\n(.+?)(?:\n\n|\Z)"
        ref_match = re.search(pattern, data, re.DOTALL)
        if ref_match:
            for line in ref_match.group(1).strip().split("\n"):
                line = line.strip()
                if line and line not in seen:
                    seen.add(line)
                    lines.append(line)
        else:
            for m in re.finditer(r"\[([^\]]+)\]\((https?://[^\)]+)\)", data):
                title, url = m.group(1), m.group(2)
                clean_url = re.sub(r"[?&]utm_source=openai", "", url)
                entry = f"- {title}: {clean_url}"
                if entry not in seen:
                    seen.add(entry)
                    lines.append(entry)
    if lines:
        return f"{citation_label}:\n" + "\n".join(lines)
    return ""


def _finalize_response(think_result: dict, tool_results: list[dict],
                        language: str) -> str:
    """Append citations to final_response if tool results contain references."""
    import re as _re
    final_response = think_result["final_response"]
    if tool_results:
        citations = _extract_citations(tool_results, language=language)
        if citations:
            final_response += "\n\n" + citations
        # If dispatch_task preview ran, embed task_id so frontend can show buttons
        for tr in tool_results:
            if tr.get("tool") == "dispatch_task" and tr.get("result") and tr["result"].success:
                m = _re.search(r"<!--\s*task_id:([a-f0-9\-]+)\s*-->", tr["result"].data or "")
                if m:
                    # Strip any existing task_id comments from LLM output (may be copied from history)
                    final_response = _re.sub(r"\s*<!--\s*task_id:[a-f0-9\-]+\s*-->", "", final_response).rstrip()
                    final_response += f"\n\n<!-- task_id:{m.group(1)} -->"
                    break
        think_result["final_response"] = final_response
    return final_response
