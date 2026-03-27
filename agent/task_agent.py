
import json
import logging
import re

from agent.utils.llm_client import call_llm_async, is_llm_error

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT_BASE = """You are a task execution agent. You have access to tools to read files, write files, list directories, search code, and execute shell commands.

Complete the given task autonomously. For each step, respond with JSON in one of these formats:

To use a tool:
{"action": "tool", "tool": "<tool_name>", "params": {...}, "reasoning": "<why>"}

When the task is complete:
{"action": "done", "result": "<summary of what was done>", "files_changed": ["list of files"]}

If you cannot complete the task:
{"action": "error", "reason": "<explanation>"}

IMPORTANT: The only valid values for "action" are: "tool", "done", "error".
NEVER use a tool name (like "file_list", "shell_exec") as the action value.
Always use: {"action": "tool", "tool": "<tool_name>", "params": {...}, "reasoning": "..."}

Guidelines:
- Always read a file before modifying it.
- After writing or modifying files, use shell_exec to verify: run syntax checks (python3 -m py_compile), tests (python3 -m pytest), or re-read the file to confirm correctness.
- Only return "done" after verifying the result is correct.
- Be concise in reasoning — focus on what you are doing and why.
- For counting lines, file sizes, or statistics: prefer shell_exec (e.g. wc -l, find, du) over reading files one by one.
- For searching or listing files across directories: ALWAYS use shell_exec with find (e.g. find /app_work -name "*.py") — NEVER use file_list repeatedly directory by directory.
- The "result" field in the "done" action MUST contain the actual output/data the user asked for (numbers, lists, findings), not just a description of what you did."""


def _build_system_prompt() -> str:
    import os
    cwd = os.getcwd()
    prefix = (
        f"You are a task execution agent. The local project directory is: {cwd}\n"
        "All file operations MUST use local paths. Do NOT access GitHub, URLs, or remote resources "
        "unless the task explicitly requires it.\n\n"
    )
    return prefix + _SYSTEM_PROMPT_BASE[_SYSTEM_PROMPT_BASE.index("You have access"):]

_STRICT_SUFFIX = """
Mode: STRICT — You may only read files, search code, run syntax checks and tests.
Do NOT attempt to install packages, modify system files, or run commands outside the whitelist.
If a step requires installing a package or elevated permissions:
  1. Use the ask_user tool to ask the user for permission first. Be specific: name the exact package and command.
  2. If the user says yes/allow/ok: proceed with the installation using shell_exec.
  3. If the user says no/deny: explain what they need to do manually, then use action="error".
  4. Only use action="error" directly if the ask_user tool is unavailable."""

_LOOSE_SUFFIX = """
Mode: LOOSE — You may install packages, run any whitelisted commands, and write files freely.
Always verify after installing or modifying files. Prefer the least invasive approach."""


def _build_tools_description(registry) -> str:
    manifests = registry.list_available()
    if not manifests:
        return "No tools available."
    lines = ["Available tools:"]
    for m in manifests:
        params_str = ", ".join(
            f"{k}: {v}" for k, v in (m.parameters or {}).items()
        )
        lines.append(f"  - {m.name}: {m.description}")
        if params_str:
            lines.append(f"    Parameters: {params_str}")
    return "\n".join(lines)


def _extract_json(text: str) -> dict | None:
    """Try to parse JSON from the LLM response. Handles fenced code blocks."""
    text = text.strip()

    def _loads(s):
        """Try json.loads; fall back to strict=False to handle bare control chars."""
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            try:
                return json.loads(s, strict=False)
            except json.JSONDecodeError:
                return None

    # Try direct parse first
    result = _loads(text)
    if result is not None:
        return result

    # Try to extract from ```json ... ``` or ``` ... ``` blocks
    for pattern in (r"```json\s*([\s\S]+?)\s*```", r"```\s*([\s\S]+?)\s*```"):
        m = re.search(pattern, text)
        if m:
            result = _loads(m.group(1))
            if result is not None:
                return result

    # Find balanced JSON object using bracket counting (handles } inside strings)
    start = text.find('{')
    if start != -1:
        depth = 0
        in_string = False
        escape_next = False
        for i, ch in enumerate(text[start:], start):
            if escape_next:
                escape_next = False
                continue
            if ch == '\\' and in_string:
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    result = _loads(text[start:i + 1])
                    if result is not None:
                        return result
                    break

    return None


def _llm_cfg(config: dict) -> dict:
    """Extract the flat LLM config that call_llm_async expects."""
    return config.get("llm", config)


async def plan_task_async(task: str, config: dict) -> list[dict]:
    """Ask LLM to generate a plan for the task. Returns list of {step, description}."""
    import os
    cwd = os.getcwd()
    lang = config.get("language", "en")
    _lang_instruction = {
        "zh": "用中文描述每个步骤。",
        "ja": "各ステップを日本語で説明してください。",
        "en": "Describe each step in English.",
    }.get(lang, "Describe each step in English.")
    messages = [
        {"role": "system", "content": (
            "You are a task planning agent. Given a task, output a JSON array of planned steps. "
            f"Each step: {{\"step\": N, \"description\": \"what will be done\"}}. "
            f"Be specific and concise. Maximum 8 steps. Output ONLY the JSON array, no explanation. "
            f"{_lang_instruction}\n\n"
            f"IMPORTANT: This is a LOCAL project. The working directory is: {cwd}\n"
            "All file operations should be done on local files, NOT via GitHub or any remote URL.\n"
            "For counting lines/files/statistics: plan to use shell commands (wc -l, find, du, grep -c) — NOT reading files one by one.\n"
            "Keep steps high-level and practical. Do NOT include steps like 'clean up variables' or 'close files'."
        )},
        {"role": "user", "content": f"Task: {task}"}
    ]
    response = await call_llm_async(messages, _llm_cfg(config))
    if is_llm_error(response):
        return [{"step": 1, "description": task}]
    plan = _extract_json(response)
    if isinstance(plan, list):
        return plan
    return [{"step": 1, "description": task}]


async def run_task_async(
    task: str, config: dict, registry, max_steps: int = 100, strict_mode: bool = True,
    progress_callback=None,  # async callable(step_data: dict)
    cancel_event=None,  # threading.Event — set it to cancel the task
) -> dict:
    """Run a task autonomously using a ReAct loop and return results when done.

    Returns a dict with keys:
        success (bool), result (str), steps (list), files_changed (list)
    """
    llm_config = _llm_cfg(config)
    tools_description = _build_tools_description(registry)
    mode_suffix = _STRICT_SUFFIX if strict_mode else _LOOSE_SUFFIX
    tmp_dir = config.get("_tmp_dir", "")
    tmp_hint = f"\n\nIMPORTANT: If you need to create any temporary scripts or files during this task, you MUST place them in the designated temp directory: {tmp_dir}\nDo NOT create files in the project root or any other location. The temp directory will be automatically cleaned up after the task completes." if tmp_dir else ""
    system_message = _build_system_prompt() + mode_suffix + tmp_hint + "\n\n" + tools_description

    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": f"Task: {task}"},
    ]

    steps = []
    files_changed = []
    # Loop detection: track consecutive identical (tool, params) calls
    _last_call: dict = {}
    _repeat_count = 0

    for step_num in range(1, max_steps + 1):
        # Check for cancellation
        if cancel_event and cancel_event.is_set():
            return {
                "success": False,
                "cancelled": True,
                "result": "Task cancelled by user.",
                "steps": steps,
                "files_changed": list(dict.fromkeys(files_changed)),
            }
        logger.debug("Task agent step %d/%d", step_num, max_steps)

        # Trim history: keep system message + last 40 messages to avoid token overflow
        if len(messages) > 41:
            messages = [messages[0]] + messages[-40:]

        response_text = await call_llm_async(messages, llm_config)

        if is_llm_error(response_text):
            return {
                "success": False,
                "result": f"LLM error at step {step_num}: {response_text}",
                "steps": steps,
                "files_changed": files_changed,
            }

        parsed = _extract_json(response_text)
        if parsed is None:
            # Non-JSON response — record it and ask the LLM to try again
            steps.append({
                "step": step_num,
                "reasoning": "Could not parse LLM response as JSON",
                "tool": None,
                "params": {},
                "result": response_text[:500],
            })
            messages.append({"role": "assistant", "content": response_text})
            messages.append({
                "role": "user",
                "content": (
                    "Your response was not valid JSON. Please reply with a JSON object "
                    "in exactly one of the formats described in the system prompt."
                ),
            })
            continue

        action = parsed.get("action", "")

        if action == "done":
            result_summary = parsed.get("result", "Task completed.")
            changed = parsed.get("files_changed", [])
            if isinstance(changed, list):
                files_changed.extend(changed)
            return {
                "success": True,
                "result": result_summary,
                "steps": steps,
                "files_changed": list(dict.fromkeys(files_changed)),
            }

        if action == "error":
            reason = parsed.get("reason", "Unknown error")
            return {
                "success": False,
                "result": reason,
                "steps": steps,
                "files_changed": files_changed,
            }

        if action == "tool":
            tool_name = parsed.get("tool", "")
            tool_params = parsed.get("params", {})
            reasoning = parsed.get("reasoning", "")

            # Loop detection: same tool + same params repeated = stuck
            call_key = {"tool": tool_name, "params": tool_params}
            if call_key == _last_call:
                _repeat_count += 1
                if _repeat_count >= 3:
                    return {
                        "success": False,
                        "result": f"Task aborted: stuck in a loop calling '{tool_name}' with the same parameters {_repeat_count} times.",
                        "steps": steps,
                        "files_changed": list(dict.fromkeys(files_changed)),
                    }
                elif _repeat_count == 2:
                    # Hint before aborting: inject warning and skip re-executing
                    messages.append({"role": "assistant", "content": response_text})
                    messages.append({"role": "user", "content": (
                        f"WARNING: You called '{tool_name}' with the exact same parameters again. "
                        "Do NOT repeat this call. You already have the results from this tool. "
                        "Analyze what you have and proceed to the next step, use a different approach, "
                        "or call action='done' if the task is already complete."
                    )})
                    continue
            else:
                _last_call = call_key
                _repeat_count = 1

            tool_result = registry.execute(tool_name, tool_params)
            observation = tool_result.data if tool_result.success else f"Error: {tool_result.error}"

            steps.append({
                "step": step_num,
                "reasoning": reasoning,
                "tool": tool_name,
                "params": tool_params,
                "result": observation[:1000],
            })

            # Track file writes
            if tool_name == "file_write":
                fp = tool_params.get("path", "")
                if fp and tool_result.success:
                    files_changed.append(fp)

            if progress_callback:
                await progress_callback(steps[-1])

            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "user", "content": f"Tool result:\n{observation}"})
            continue

        # Unknown action — let the LLM correct itself
        steps.append({
            "step": step_num,
            "reasoning": f"Unknown action: {action}",
            "tool": None,
            "params": {},
            "result": str(parsed)[:500],
        })
        messages.append({"role": "assistant", "content": response_text})
        # Check if LLM used tool name as action (common GPT-4o mistake)
        available_tools = [m.name for m in registry.list_available()]
        if action in available_tools:
            correction = (
                f"Format error: '{action}' is a tool name, not an action. "
                f"Use: {{\"action\": \"tool\", \"tool\": \"{action}\", \"params\": {{...}}, \"reasoning\": \"...\"}}. "
                "The valid action values are only: tool, done, error."
            )
        else:
            correction = f"Unknown action '{action}'. Valid actions are: tool, done, error."
        messages.append({"role": "user", "content": correction})

    # Reached max steps
    return {
        "success": False,
        "result": f"Task did not complete within {max_steps} steps.",
        "steps": steps,
        "files_changed": list(dict.fromkeys(files_changed)),
    }
