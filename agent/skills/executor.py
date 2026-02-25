
import re
from agent.storage import load_full_current_profile
from agent.config.prompts import get_prompt, get_labels
from agent.utils.llm_client import call_llm

def resolve_variables(skill, config: dict) -> dict:
    variables = dict(skill.variables)
    resolved = {}

    profile_cache = None

    for name, value in variables.items():
        if isinstance(value, str) and value.startswith("$profile."):
            subject = value[len("$profile."):]
            if profile_cache is None:
                profile_cache = load_full_current_profile()
            found = None
            for p in profile_cache:
                if p.get("subject") == subject:
                    found = p.get("value", "")
                    break
            resolved[name] = found or value
        else:
            resolved[name] = value

    return resolved

def interpolate(template: str, variables: dict) -> str:
    result = template
    for name, value in variables.items():
        result = result.replace(f"{{{name}}}", str(value))
    return result

def execute_skill(skill, tool_registry, llm_config: dict,
                  config: dict) -> str:
    variables = resolve_variables(skill, config)
    language = config.get("language", "zh")
    L = get_labels("context.labels", language)

    results = []
    for step in skill.steps:
        if "tool" in step:
            tool_name = step["tool"]
            raw_params = step.get("params", {})
            params = {}
            for k, v in raw_params.items():
                if isinstance(v, str):
                    params[k] = interpolate(v, variables)
                else:
                    params[k] = v

            result = tool_registry.execute(tool_name, params)
            result_text = result.data if result.success else f"[{L['tool_error']}: {result.error}]"

            save_as = step.get("save_as")
            if save_as:
                variables[save_as] = result_text

            results.append(result_text)

        elif "respond" in step:
            prompt_template = step["respond"]
            prompt = interpolate(prompt_template, variables)

            language = config.get("language", "zh")
            messages = [
                {"role": "system", "content": get_prompt("skills.executor_respond_system", language)},
                {"role": "user", "content": prompt},
            ]
            try:
                response = call_llm(messages, llm_config)
                return response
            except Exception as e:
                return L["skill_exec_failed"].format(error=e)

    if results:
        return "\n".join(results)
    return L["skill_no_output"]
