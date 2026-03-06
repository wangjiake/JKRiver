"""Perceive stage: intent classification & input parsing."""

from agent.utils.time_context import get_now
from agent.config.prompts import get_prompt, get_labels
from agent.sleep._parsing import _parse_json_object


def build_perceive_messages(
    user_input: str,
    available_tools,
    chat_history: list[dict],
    language: str,
) -> list[dict]:
    """Build LLM messages for the perceive step."""
    L = get_labels("context.labels", language)

    recent_context = ""
    if chat_history:
        recent = chat_history[-3:]
        for turn in recent:
            recent_context += f"{L['user']}：{turn['user_summary']}\n"
            recent_context += f"{L['assistant']}：{turn['assistant_summary']}\n"

    context_block = ""
    if recent_context:
        context_block = (
            f"{L['recent_context']}：\n{recent_context}\n"
            f"{L['use_context_hint']}\n\n"
        )

    system_content = get_prompt("cognition.perceive_system", language)

    if available_tools:
        tool_lines = [f"- {m.name}: {m.description}" for m in available_tools]
        system_content += f"\n\n{L['available_tools']}：\n" + "\n".join(tool_lines)

    user_content = get_prompt(
        "cognition.perceive_user", language,
        system_time=get_now().strftime('%Y-%m-%dT%H:%M'),
        context_block=context_block,
        user_input=user_input,
    )

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]


def process_perceive_raw(raw: str, user_input: str, language: str) -> dict:
    """Parse LLM perceive output into a structured dict."""
    perception_at = get_now()
    labels = get_labels("cognition.perceive_labels", language)
    result = parse_perceive_output(raw, user_input, labels, language)
    result["perception_at"] = perception_at
    corrected = result.get("corrected_input", user_input)
    result["corrected_input"] = corrected if corrected else user_input
    return result


def _parse_perceive_json(raw: str, user_input: str, language: str) -> dict | None:
    """Try to parse perceive output as JSON. Returns None on failure."""
    CL = get_labels("context.labels", language)
    obj = _parse_json_object(raw)
    if not obj or "category" not in obj:
        return None

    category = obj.get("category", "chat").lower()
    if category not in ("knowledge", "chat", "personal"):
        return None

    # Handle bool vs string for need_online / need_tools
    truthy_values = tuple(CL.get("truthy_values", ["yes", "是", "true"]))

    def _to_bool(val) -> bool:
        if isinstance(val, bool):
            return val
        return str(val).lower() in truthy_values

    # Handle keywords: string vs list
    kw_raw = obj.get("keywords", [])
    if isinstance(kw_raw, str):
        keywords = [k.strip() for k in kw_raw.split(",") if k.strip()]
    elif isinstance(kw_raw, list):
        keywords = [str(k).strip() for k in kw_raw if str(k).strip()]
    else:
        keywords = []

    need_online = _to_bool(obj.get("need_online", False))
    need_tools = _to_bool(obj.get("need_tools", False))
    need_memory = category in ("chat", "personal")
    memory_type = "personal" if category == "personal" else CL.get("memory_type_none", "无")

    result = {
        "intent": obj.get("intent", user_input),
        "category": category,
        "need_memory": need_memory,
        "memory_type": memory_type,
        "need_online": need_online,
        "need_tools": need_tools,
        "ai_summary": obj.get("ai_summary", user_input),
        "topic_keywords": keywords,
        "raw": raw,
    }

    correction = obj.get("correction", "")
    if correction:
        result["corrected_input"] = correction

    return result


def _parse_perceive_string(
    raw: str,
    user_input: str,
    labels: dict | None = None,
    language: str = "en",
) -> dict:
    """Line-by-line parsing of perceive LLM output (legacy string format)."""
    if labels is None:
        labels = get_labels("cognition.perceive_labels", language)
    CL = get_labels("context.labels", language)
    l_correction = labels.get("correction", "纠错")
    l_category = labels.get("category", "分类")
    l_intent = labels.get("intent", "意图")
    l_summary = labels.get("summary", "AI摘要")
    l_keywords = labels.get("keywords", "话题关键词")
    l_need_online = labels.get("need_online", "需要联网")
    l_need_tools = labels.get("need_tools", "需要工具")
    truthy_values = tuple(CL.get("truthy_values", ["yes", "是", "true"]))

    result = {
        "intent": user_input,
        "category": "chat",
        "need_memory": False,
        "memory_type": CL.get("memory_type_none", "无"),
        "need_online": False,
        "need_tools": False,
        "ai_summary": user_input,
        "topic_keywords": [],
        "raw": raw,
    }
    def _extract_value(line: str) -> str:
        """Extract value after the first full-width or ASCII colon."""
        if "：" in line:
            return line.split("：", 1)[1].strip()
        return line.split(":", 1)[1].strip() if ":" in line else line.strip()

    for line in raw.split("\n"):
        line = line.strip()
        if line.startswith(f"{l_correction}：") or line.startswith(f"{l_correction}:"):
            val = _extract_value(line)
            if val:
                result["corrected_input"] = val
        elif line.startswith(f"{l_category}：") or line.startswith(f"{l_category}:"):
            val = _extract_value(line).lower()
            if val in ("knowledge", "chat", "personal"):
                result["category"] = val
        elif line.startswith(f"{l_intent}：") or line.startswith(f"{l_intent}:"):
            result["intent"] = _extract_value(line)
        elif line.startswith(f"{l_summary}：") or line.startswith(f"{l_summary}:"):
            result["ai_summary"] = _extract_value(line)
        elif line.startswith(f"{l_keywords}：") or line.startswith(f"{l_keywords}:"):
            kw_str = _extract_value(line)
            result["topic_keywords"] = [k.strip() for k in kw_str.split(",") if k.strip()]
        elif line.startswith(f"{l_need_online}：") or line.startswith(f"{l_need_online}:"):
            val = _extract_value(line).lower()
            result["need_online"] = val in truthy_values
        elif line.startswith(f"{l_need_tools}：") or line.startswith(f"{l_need_tools}:"):
            val = _extract_value(line).lower()
            result["need_tools"] = val in truthy_values
    result["need_memory"] = result["category"] in ("chat", "personal")
    result["memory_type"] = "personal" if result["category"] == "personal" else CL.get("memory_type_none", "无")
    return result


def parse_perceive_output(
    raw: str,
    user_input: str,
    labels: dict | None = None,
    language: str = "en",
) -> dict:
    """Parse perceive output: try JSON first, fall back to string parser."""
    json_result = _parse_perceive_json(raw, user_input, language)
    if json_result is not None:
        return json_result
    return _parse_perceive_string(raw, user_input, labels, language)
