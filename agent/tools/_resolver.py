
import json
from agent.config.prompts import get_prompt, get_labels
from agent.utils.llm_client import call_llm, call_llm_async

def _needs_resolution(perception: dict, input_metadata: dict | None) -> bool:
    if input_metadata and input_metadata.get("type") != "text":
        return True
    if perception.get("need_online"):
        return True
    if perception.get("need_tools"):
        return True
    return False

def resolve_tools(user_input: str, perception: dict,
                  registry, llm_config: dict,
                  input_metadata: dict | None = None,
                  language: str = "zh",
                  profile: list[dict] | None = None) -> list[dict]:
    if not _needs_resolution(perception, input_metadata):
        return []

    available = registry.list_available()
    if not available:
        return []

    L = get_labels("context.labels", language)

    tool_list = []
    for m in available:
        tool_info = f"- {m.name}: {m.description}"
        if m.parameters:
            params_str = ", ".join(f"{k}={v}" for k, v in m.parameters.items())
            tool_info += f"  {L['params']}: {params_str}"
        if m.examples:
            tool_info += f"  {L['examples']}: {'; '.join(m.examples[:3])}"
        tool_list.append(tool_info)

    tools_text = "\n".join(tool_list)

    meta_desc = ""
    if input_metadata:
        input_type = input_metadata.get("type", "text")
        if input_type != "text":
            meta_desc = f"\n{L['input_type']}: {input_type}"
            if input_metadata.get("file_path"):
                meta_desc += f"\n{L['attachment_path']}: {input_metadata['file_path']}"

    profile_hint = ""
    if profile:
        profile_lines = [f"  {p['category']}: {p['value']}" for p in profile]
        profile_hint = f"\n{L.get('user_profile_hint', '用户信息')}:\n" + "\n".join(profile_lines)

    messages = [
        {"role": "system", "content": get_prompt("tools.resolver_system", language, tools_text=tools_text)},
        {"role": "user", "content": (
            f"[{L['current_time']}: {__import__('agent.utils.time_context', fromlist=['get_now']).get_now().strftime('%Y-%m-%dT%H:%M')}]\n"
            f"{L['user_input_resolver']}: {user_input}{meta_desc}{profile_hint}"
        )},
    ]

    raw = call_llm(messages, llm_config).strip()

    tool_calls = _parse_resolver_output(raw)
    if not tool_calls:
        return []

    results = []
    for tc in tool_calls:
        tool_name = tc.get("tool", "")
        params = tc.get("params", {})

        if tool_name in ("image_describe", "voice_transcribe") and input_metadata:
            if not params.get("file_path") and input_metadata.get("file_path"):
                params["file_path"] = input_metadata["file_path"]
        result = registry.execute(tool_name, params)
        if result.success:
            pass
        else:
            pass
        results.append({"tool": tool_name, "params": params, "result": result})

    return results

def _parse_resolver_output(raw: str) -> list[dict]:
    text = raw.strip()

    if text.upper() == "NONE":
        return []

    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    start = text.find("[")
    end = text.rfind("]") + 1
    if start >= 0 and end > start:
        text = text[start:end]

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict) and "tool" in item]
        if isinstance(parsed, dict) and "tool" in parsed:
            return [parsed]
    except (json.JSONDecodeError, ValueError):
        pass

    return []

# ── Async version ──

async def resolve_tools_async(user_input: str, perception: dict,
                  registry, llm_config: dict,
                  input_metadata: dict | None = None,
                  language: str = "zh",
                  profile: list[dict] | None = None) -> list[dict]:
    if not _needs_resolution(perception, input_metadata):
        return []

    available = registry.list_available()
    if not available:
        return []

    L = get_labels("context.labels", language)

    tool_list = []
    for m in available:
        tool_info = f"- {m.name}: {m.description}"
        if m.parameters:
            params_str = ", ".join(f"{k}={v}" for k, v in m.parameters.items())
            tool_info += f"  {L['params']}: {params_str}"
        if m.examples:
            tool_info += f"  {L['examples']}: {'; '.join(m.examples[:3])}"
        tool_list.append(tool_info)

    tools_text = "\n".join(tool_list)

    meta_desc = ""
    if input_metadata:
        input_type = input_metadata.get("type", "text")
        if input_type != "text":
            meta_desc = f"\n{L['input_type']}: {input_type}"
            if input_metadata.get("file_path"):
                meta_desc += f"\n{L['attachment_path']}: {input_metadata['file_path']}"

    profile_hint = ""
    if profile:
        profile_lines = [f"  {p['category']}: {p['value']}" for p in profile]
        profile_hint = f"\n{L.get('user_profile_hint', '用户信息')}:\n" + "\n".join(profile_lines)

    messages = [
        {"role": "system", "content": get_prompt("tools.resolver_system", language, tools_text=tools_text)},
        {"role": "user", "content": (
            f"[{L['current_time']}: {__import__('agent.utils.time_context', fromlist=['get_now']).get_now().strftime('%Y-%m-%dT%H:%M')}]\n"
            f"{L['user_input_resolver']}: {user_input}{meta_desc}{profile_hint}"
        )},
    ]

    raw = (await call_llm_async(messages, llm_config)).strip()

    tool_calls = _parse_resolver_output(raw)
    if not tool_calls:
        return []

    results = []
    for tc in tool_calls:
        tool_name = tc.get("tool", "")
        params = tc.get("params", {})

        if tool_name in ("image_describe", "voice_transcribe") and input_metadata:
            if not params.get("file_path") and input_metadata.get("file_path"):
                params["file_path"] = input_metadata["file_path"]
        result = registry.execute(tool_name, params)
        results.append({"tool": tool_name, "params": params, "result": result})

    return results
