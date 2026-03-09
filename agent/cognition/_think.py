"""Think stage: response generation, verification, and post-processing."""

from agent.utils.time_context import get_now
from agent.config.prompts import get_prompt, get_labels


def build_think_messages(
    user_input: str,
    perception: dict,
    memories: dict,
    session_context: str,
    language: str,
) -> list[dict]:
    """Build LLM messages for the think step."""
    messages = [{"role": "system", "content": get_prompt("cognition.system_prompt", language)}]

    memory_text = memories.get("memory_text", "")
    if memory_text:
        messages.append({
            "role": "system",
            "content": memory_text,
        })

    if session_context:
        messages.append({
            "role": "system",
            "content": session_context,
        })

    messages.append({"role": "user", "content": f"[system_time: {get_now().strftime('%Y-%m-%dT%H:%M')}]\n{user_input}"})
    return messages


def build_verify_messages(
    user_input: str,
    perception: dict,
    memory_text: str,
    response: str,
    session_context: str,
    language: str,
) -> list[dict]:
    """Build LLM messages for the verification step."""
    L = get_labels("context.labels", language)
    verify_memory = strip_internal_sections(memory_text, language=language)

    return [
        {"role": "system", "content": get_prompt("cognition.verify_system", language)},
        {"role": "user", "content": (
            f"[system_time: {get_now().strftime('%Y-%m-%dT%H:%M')}]\n"
            f"{L['memory']}：\n{verify_memory}\n"
            f"{session_context if session_context else L['current_session'] + '：' + chr(10) + L['none']}\n"
            f"{L['user_asks']}：{user_input}\n"
            f"{L['ai_reply']}：{response}\n\n"
            f"{L['output']}："
        )},
    ]


def parse_verify_raw(raw: str) -> str:
    if raw.startswith("FAIL:") or raw.startswith("FAIL："):
        return raw
    return "PASS"


def strip_internal_sections(memory_text: str, language: str = "en") -> str:
    L = get_labels("context.labels", language)
    none_fallback = L.get("none_fallback", "无")
    if not memory_text:
        return none_fallback
    lines = memory_text.split("\n")
    result_lines = []
    skip = False
    markers = L.get("strip_markers", ["【高概率推测", "【待验证信息", "【本轮策略提示", "【轨迹偏离分析"])
    for line in lines:
        if any(marker in line for marker in markers):
            skip = True
            continue
        if skip and (line.startswith("【") or line.startswith("[")):
            skip = False
        if not skip:
            result_lines.append(line)
    result = "\n".join(result_lines).strip()
    return result if result else none_fallback


def summarize_response(response: str, max_len: int = 120) -> str:
    text = response.strip().replace("\n", " ")
    for sep in ["。", "！", "？", ".", "!", "?"]:
        pos = text.find(sep)
        if 0 < pos < max_len:
            return text[:pos + 1]
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


def make_thinking_notes(
    perception: dict,
    memory_text: str,
    raw_response: str,
    verification_result: str,
    final_response: str,
    language: str,
) -> str:
    L = get_labels("context.labels", language)
    notes = []
    category = perception.get("category", "chat")
    if category == "knowledge":
        notes.append(L.get("note_knowledge_skip", "纯知识问答，跳过记忆"))
    elif memory_text:
        notes.append(L.get("note_memory_loaded", "记忆已加载"))
    else:
        notes.append(L.get("note_memory_not_found", "需要记忆但未找到"))

    if verification_result == "PASS":
        notes.append(L.get("note_verification_pass", "验证通过"))
    elif verification_result != "SKIP":
        notes.append(L.get("note_verification_blocked", "验证拦截：{result}").format(result=verification_result))

    return "；".join(notes)


def finish_think_result(
    raw_response,
    raw_response_at,
    user_input,
    perception,
    memory_text,
    verification_result,
    verification_at,
    final_response,
    final_response_at,
    language: str,
) -> dict:
    """Build final think result dict."""
    thinking_notes = make_thinking_notes(
        perception, memory_text, raw_response, verification_result, final_response, language
    )
    thinking_notes_at = get_now()

    return {
        "raw_response": raw_response,
        "raw_response_at": raw_response_at,
        "verification_result": verification_result,
        "verification_result_at": verification_at,
        "final_response": final_response,
        "final_response_at": final_response_at,
        "thinking_notes": thinking_notes,
        "thinking_notes_at": thinking_notes_at,
    }
