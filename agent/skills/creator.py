
import os
import re
import yaml
from agent.config.prompts import get_prompt, get_labels
from agent.utils.llm_client import call_llm

_CREATE_ACTION = []
_CREATE_TRIGGER = []
_DELETE_KEYWORDS = []

def detect_skill_request(text: str, language: str = "zh") -> str | None:
    if not text:
        return None

    kw = get_labels("skills.detect_keywords", language)
    delete_keywords = kw.get("delete", _DELETE_KEYWORDS)
    create_action = kw.get("create_action", _CREATE_ACTION)
    create_trigger = kw.get("create_trigger", _CREATE_TRIGGER)
    create_short = kw.get("create_short", [])

    for k in delete_keywords:
        if k in text:
            return "delete"

    for k in create_action:
        if k in text:
            return "create"

    has_action = any(w in text for w in create_short)
    has_trigger = any(w in text for w in create_trigger)
    if has_action and has_trigger:
        return "create"

    return None

def generate_skill_yaml(user_request: str, llm_config: dict,
                        available_tools: list, language: str = "zh") -> dict:
    L = get_labels("context.labels", language)

    tools_list = "\n".join(
        f"- {t.name}: {t.description}" for t in available_tools
    ) if available_tools else L["no_tools_available"]

    prompt = get_prompt("skills.generator_prompt", language,
                        tools_list=tools_list,
                        user_request=user_request)

    messages = [
        {"role": "system", "content": get_prompt("skills.generator_system", language)},
        {"role": "user", "content": prompt},
    ]
    raw = call_llm(messages, llm_config)

    yaml_match = re.search(r"```ya?ml\s*\n(.*?)```", raw, re.DOTALL)
    yaml_text = yaml_match.group(1).strip() if yaml_match else raw.strip()

    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:
        EL = get_labels("errors.llm", language)
        raise ValueError(EL["yaml_parse_failed"].format(error=e))

    EL = get_labels("errors.llm", language)
    if not isinstance(data, dict):
        raise ValueError(EL["yaml_not_dict"])
    if not data.get("name"):
        raise ValueError(EL["skill_missing_name"])

    data.setdefault("enabled", True)
    data.setdefault("trigger", {})
    if "type" not in data["trigger"]:
        data["trigger"]["type"] = "keyword"

    return data

def _skills_dir() -> str:
    return os.path.dirname(__file__)

def save_skill(skill_data: dict) -> str:
    name = skill_data["name"]
    filename = f"auto_{name}.yaml"
    filepath = os.path.join(_skills_dir(), filename)

    with open(filepath, "w", encoding="utf-8") as f:
        yaml.dump(skill_data, f, allow_unicode=True, default_flow_style=False,
                  sort_keys=False)

    return filepath

def delete_skill(skill_name: str) -> bool:
    skills_dir = _skills_dir()
    candidates = [
        f"auto_{skill_name}.yaml",
        f"auto_{skill_name}.yml",
        f"{skill_name}.yaml",
        f"{skill_name}.yml",
    ]
    for filename in candidates:
        filepath = os.path.join(skills_dir, filename)
        if os.path.isfile(filepath):
            os.remove(filepath)
            return True
    return False

def extract_skill_name(text: str, language: str = "zh") -> str:
    kw = get_labels("skills.detect_keywords", language)
    delete_keywords = kw.get("delete", _DELETE_KEYWORDS)
    clean = text
    for k in delete_keywords:
        clean = clean.replace(k, "")
    clean = clean.strip().strip("：:").strip()
    return clean

def create_skill_from_chat(user_text: str, llm_config: dict,
                           available_tools: list,
                           language: str = "zh") -> dict:
    try:
        L = get_labels("context.labels", language)
        skill_data = generate_skill_yaml(user_text, llm_config, available_tools, language=language)
        filepath = save_skill(skill_data)
        return {
            "success": True,
            "skill_name": skill_data["name"],
            "description": skill_data.get("description", ""),
            "message": L["skill_saved_msg"].format(filename=os.path.basename(filepath)),
        }
    except Exception as e:
        return {
            "success": False,
            "skill_name": "",
            "description": "",
            "message": str(e),
        }
