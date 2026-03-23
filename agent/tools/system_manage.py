"""system_manage — AI tool for managing tools, skills, agents, and config."""

import os
import yaml

from agent.tools import BaseTool, ToolManifest, ToolResult

_SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "settings.yaml")
_SKILLS_DIR = os.environ.get("SKILLS_DIR", os.path.join(os.path.dirname(__file__), "..", "skills"))
_AGENT_CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "config")

_MANIFEST = {
    "name": "system_manage",
    "description": (
        "Manage the AI system: list/toggle tools, install/toggle/delete skills, "
        "toggle agents, read or update any config value. "
        "Use this to configure the system on behalf of the user."
    ),
    "parameters": {
        "action": (
            "list_tools | toggle_tool | "
            "list_skills | create_skill | toggle_skill | delete_skill | "
            "list_agents | toggle_agent | "
            "get_config | set_config"
        ),
        "name": "tool/skill/agent name (for toggle/delete/create actions)",
        "enabled": "true/false (for toggle actions)",
        "content": "YAML content string (for create_skill)",
        "key": "dot-notation config key, e.g. openai.model (for get/set_config)",
        "value": "new value string (for set_config)",
    },
    "examples": [
        "install a skill that greets the user every morning",
        "disable the finance_query tool",
        "list all available skills",
        "change my LLM model to gpt-4o",
        "create a skill that summarizes news",
    ],
}


def _read_settings() -> list[str]:
    try:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
            return f.readlines()
    except FileNotFoundError:
        return []


def _write_settings(lines: list[str]) -> None:
    with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)


def _get_nested(lines: list[str], key_path: list[str]) -> str | None:
    """Read a dot-path value from settings lines."""
    depth = 0
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        expected_key = key_path[depth]
        if stripped.startswith(f"{expected_key}:"):
            if depth == len(key_path) - 1:
                val = stripped[len(expected_key) + 1:].strip().strip('"').strip("'")
                return val
            depth += 1
        elif indent == 0 and depth > 0:
            break
    return None


def _set_nested(lines: list[str], key_path: list[str], value: str) -> bool:
    """Set a dot-path value in settings lines. Returns True if found and set."""
    depth = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        expected_key = key_path[depth]
        if stripped.startswith(f"{expected_key}:"):
            if depth == len(key_path) - 1:
                lines[i] = " " * indent + f'{expected_key}: "{value}"\n'
                return True
            depth += 1
        elif indent == 0 and depth > 0:
            break
    return False


def _get_tool_enabled(tool_name: str) -> bool | None:
    lines = _read_settings()
    in_tools = False
    in_tool = False
    tool_indent = None
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if not in_tools:
            if indent == 0 and stripped.startswith("tools:"):
                in_tools = True
        else:
            if indent == 0:
                break
            if not in_tool:
                if stripped.startswith(f"{tool_name}:"):
                    in_tool = True
                    tool_indent = indent
            else:
                if indent <= tool_indent:
                    break
                if stripped.startswith("enabled:"):
                    val = stripped.split(":", 1)[1].strip().lower()
                    return val != "false"
    return None


def _set_tool_enabled(tool_name: str, enabled: bool) -> bool:
    lines = _read_settings()
    in_tools = False
    in_tool = False
    tool_indent = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if not in_tools:
            if indent == 0 and stripped.startswith("tools:"):
                in_tools = True
        else:
            if indent == 0:
                break
            if not in_tool:
                if stripped.startswith(f"{tool_name}:"):
                    in_tool = True
                    tool_indent = indent
            else:
                if indent <= tool_indent:
                    break
                if stripped.startswith("enabled:"):
                    lines[i] = " " * indent + f'enabled: {"true" if enabled else "false"}\n'
                    _write_settings(lines)
                    return True
    # Create the entry
    _create_tool_section(tool_name, enabled, lines)
    return True


def _create_tool_section(tool_name: str, enabled: bool, lines: list[str]) -> None:
    enabled_str = "true" if enabled else "false"
    tools_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith("tools:") and len(line) - len(line.lstrip()) == 0:
            tools_idx = i
            break
    new_block = [f"    {tool_name}:\n", f"        enabled: {enabled_str}\n"]
    if tools_idx is None:
        lines.append(f"\ntools:\n    {tool_name}:\n        enabled: {enabled_str}\n")
    else:
        insert_at = len(lines)
        for i in range(tools_idx + 1, len(lines)):
            s = lines[i].strip()
            if s and not s.startswith("#") and len(lines[i]) - len(lines[i].lstrip()) == 0:
                insert_at = i
                break
        lines[insert_at:insert_at] = new_block
    _write_settings(lines)


def _set_skill_enabled_in_file(name: str, enabled: bool) -> bool:
    """Toggle enabled in an individual skill YAML file."""
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    filepath = os.path.join(_SKILLS_DIR, f"{safe}.yaml")
    if not os.path.exists(filepath):
        return False
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for i, line in enumerate(lines):
            if line.strip().startswith("enabled:") and len(line) - len(line.lstrip()) == 0:
                lines[i] = f'enabled: {"true" if enabled else "false"}\n'
                with open(filepath, "w", encoding="utf-8") as f:
                    f.writelines(lines)
                return True
    except Exception:
        pass
    return False


class SystemManageTool(BaseTool):

    def __init__(self, config: dict):
        self.config = config

    def is_available(self) -> bool:
        return True  # always available — it's the AI's management interface

    def manifest(self) -> ToolManifest:
        return ToolManifest(
            name=_MANIFEST["name"],
            description=_MANIFEST["description"],
            parameters=_MANIFEST["parameters"],
            examples=_MANIFEST["examples"],
        )

    def execute(self, params: dict) -> ToolResult:
        action = params.get("action", "").strip()
        try:
            result = self._dispatch(action, params)
            return ToolResult(output=result, error=None)
        except Exception as e:
            return ToolResult(output=None, error=str(e))

    def _dispatch(self, action: str, params: dict) -> str:
        # ── Tools ────────────────────────────────────────────
        if action == "list_tools":
            from agent.tools import ToolRegistry
            reg = ToolRegistry(self.config)
            tools = []
            for name, tool in reg._tools.items():
                m = tool.manifest()
                tools.append(f"[ON]  {m.name}: {m.description}")
            return "Active tools:\n" + "\n".join(tools) if tools else "No active tools."

        if action == "toggle_tool":
            name = params.get("name", "")
            enabled = str(params.get("enabled", "true")).lower() not in ("false", "0", "no")
            _set_tool_enabled(name, enabled)
            return f"Tool '{name}' set to {'enabled' if enabled else 'disabled'}. Restart required."

        # ── Skills ───────────────────────────────────────────
        if action == "list_skills":
            from agent.skills import SkillRegistry
            reg = SkillRegistry(self.config)
            skills = reg.list_all()
            if not skills:
                return "No skills found."
            lines = []
            for s in skills:
                src = getattr(s, "_source", "bundled")
                state = "ON" if s.enabled else "OFF"
                lines.append(f"[{state}] {s.name} ({src}): {s.description}")
            return "\n".join(lines)

        if action == "create_skill":
            content = params.get("content", "").strip()
            if not content:
                return "Error: 'content' (YAML or SKILL.md) is required."
            # Detect SKILL.md format
            if content.startswith("---"):
                from agent.skills import _parse_skill_md
                data = _parse_skill_md(content)
                if not data or not data.get("name"):
                    return "Error: Invalid SKILL.md format — missing frontmatter or name."
                name = data["name"]
                safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
                skill_dir = os.path.join(_SKILLS_DIR, safe)
                os.makedirs(skill_dir, exist_ok=True)
                with open(os.path.join(skill_dir, "SKILL.md"), "w", encoding="utf-8") as f:
                    f.write(content)
                return f"Skill '{name}' (SkillHub format) created at agent/skills/{safe}/SKILL.md and activated."
            try:
                data = yaml.safe_load(content)
            except Exception as e:
                return f"Error: Invalid YAML — {e}"
            if not isinstance(data, dict) or not data.get("name"):
                return "Error: Skill must be a YAML dict with a 'name' field."
            name = data["name"]
            safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
            filepath = os.path.join(_SKILLS_DIR, f"{safe}.yaml")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Skill '{name}' created at agent/skills/{safe}.yaml and activated."

        if action == "toggle_skill":
            name = params.get("name", "")
            enabled = str(params.get("enabled", "true")).lower() not in ("false", "0", "no")
            # Try individual YAML file first
            if _set_skill_enabled_in_file(name, enabled):
                return f"Skill '{name}' set to {'enabled' if enabled else 'disabled'}."
            # Try SKILL.md subdirectory (SkillHub)
            from agent.api import _set_skill_md_enabled
            if _set_skill_md_enabled(name, enabled):
                return f"Skill '{name}' set to {'enabled' if enabled else 'disabled'}."
            # Fall back to bundled YAML
            lang = self.config.get("language", "en")
            skill_file = os.path.join(_SKILLS_DIR, f"skills_{lang}.yaml")
            if not os.path.exists(skill_file):
                skill_file = os.path.join(_SKILLS_DIR, "skills_en.yaml")
            from agent.api import _set_yaml_enabled
            if _set_yaml_enabled(skill_file, name, enabled):
                return f"Skill '{name}' set to {'enabled' if enabled else 'disabled'}."
            return f"Skill '{name}' not found."

        if action == "delete_skill":
            import shutil
            name = params.get("name", "")
            safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
            # Try SKILL.md subdirectory first (SkillHub)
            skill_dir = os.path.join(_SKILLS_DIR, safe)
            if os.path.isdir(skill_dir):
                shutil.rmtree(skill_dir)
                return f"Skill '{name}' (SkillHub) deleted."
            # Try individual YAML file
            filepath = os.path.join(_SKILLS_DIR, f"{safe}.yaml")
            if not os.path.exists(filepath):
                return f"Error: Skill '{name}' not found. Bundled skills cannot be deleted."
            os.remove(filepath)
            return f"Skill '{name}' deleted."

        # ── Agents ───────────────────────────────────────────
        if action == "list_agents":
            lang = self.config.get("language", "en")
            agents_path = os.path.join(_AGENT_CONFIG_DIR, f"agents_{lang}.yaml")
            if not os.path.exists(agents_path):
                agents_path = os.path.join(_AGENT_CONFIG_DIR, "agents_en.yaml")
            try:
                with open(agents_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                agents = (data or {}).get("agents", [])
                lines = []
                for a in agents:
                    state = "ON" if a.get("enabled", True) else "OFF"
                    lines.append(f"[{state}] {a.get('name','?')}: {a.get('description','')[:80]}")
                return "\n".join(lines) if lines else "No agents."
            except Exception as e:
                return f"Error reading agents: {e}"

        if action == "toggle_agent":
            name = params.get("name", "")
            enabled = str(params.get("enabled", "true")).lower() not in ("false", "0", "no")
            lang = self.config.get("language", "en")
            agents_path = os.path.join(_AGENT_CONFIG_DIR, f"agents_{lang}.yaml")
            if not os.path.exists(agents_path):
                agents_path = os.path.join(_AGENT_CONFIG_DIR, "agents_en.yaml")
            from agent.api import _set_yaml_enabled
            if _set_yaml_enabled(agents_path, name, enabled):
                return f"Agent '{name}' set to {'enabled' if enabled else 'disabled'}. Restart required."
            return f"Agent '{name}' not found."

        # ── Config ───────────────────────────────────────────
        if action == "get_config":
            key = params.get("key", "")
            if not key:
                return "Error: 'key' is required (e.g. openai.model)"
            lines = _read_settings()
            val = _get_nested(lines, key.split("."))
            if val is None:
                return f"Config key '{key}' not found."
            return f"{key} = {val}"

        if action == "set_config":
            key = params.get("key", "")
            value = str(params.get("value", ""))
            if not key:
                return "Error: 'key' is required (e.g. openai.model)"
            _READONLY_KEYS = {"api_key", "bot_token", "password", "secret", "token"}
            leaf = key.split(".")[-1].lower()
            if any(blocked in leaf for blocked in _READONLY_KEYS):
                return f"Error: '{key}' contains sensitive credentials and cannot be updated via this tool. Edit settings.yaml directly."
            lines = _read_settings()
            if _set_nested(lines, key.split("."), value):
                _write_settings(lines)
                return f"Config updated: {key} = {value}. Restart required for most changes."
            return f"Error: Config key '{key}' not found in settings.yaml."

        return f"Unknown action: '{action}'. Valid actions: list_tools, toggle_tool, list_skills, create_skill, toggle_skill, delete_skill, list_agents, toggle_agent, get_config, set_config"
