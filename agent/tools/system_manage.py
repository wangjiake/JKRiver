"""system_manage — AI tool for managing tools, skills, agents, and config."""

import os
import yaml

from agent.tools import BaseTool, ToolManifest, ToolResult
from agent.tools._system_settings import (
    _read_settings, _write_settings,
    _get_nested, _set_nested,
    _set_tool_enabled, _set_skill_enabled_in_file,
)
from agent.tools._agent_doc import _update_agent_doc

_SKILLS_DIR = os.environ.get("SKILLS_DIR", os.path.join(os.path.dirname(__file__), "..", "skills"))
_AGENT_CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "config")

_MANIFEST = {
    "en": {
        "description": (
            "Manage the AI system: list/toggle tools, install/toggle/delete skills, "
            "toggle agents, read or update any config value. "
            "Use this to configure the system on behalf of the user.\n\n"
            "Actions and required parameters:\n"
            "  list_tools       — no extra params. Returns all tools and their enabled status.\n"
            "  toggle_tool      — name: tool name e.g. 'web_search'; enabled: 'true'/'false'.\n"
            "  list_skills      — no extra params.\n"
            "  create_skill     — name: skill name; content: YAML skill definition.\n"
            "  toggle_skill     — name: skill name; enabled: 'true'/'false'.\n"
            "  delete_skill     — name: skill name.\n"
            "  list_agents      — no extra params.\n"
            "  toggle_agent     — name: agent name; enabled: 'true'/'false'.\n"
            "  get_config       — key: dot-notation path, e.g. 'tools.web_search.backend'.\n"
            "  set_config       — key: dot-notation path; value: new value.\n"
            "                     Cannot set: api_key, bot_token, password, secret, token.\n"
            "  restart          — no extra params. Restarts service to apply config changes.\n"
            "                     Always call after set_config or file_write on settings.yaml.\n"
            "  update_agent_doc — no extra params. Scans all tools/agents/skills and updates\n"
            "                     AGENT.md so the AI has up-to-date knowledge of the system."
        ),
        "parameters": {
            "action": "list_tools | toggle_tool | list_skills | create_skill | toggle_skill | delete_skill | list_agents | toggle_agent | get_config | set_config | restart | update_agent_doc",
            "name": "tool/skill/agent name (for toggle/delete/create actions)",
            "enabled": "'true' or 'false' (for toggle actions)",
            "content": "YAML content string (for create_skill)",
            "key": "dot-notation config key, e.g. 'tools.web_search.backend' (for get/set_config)",
            "value": "new value string (for set_config)",
        },
        "examples": [
            "enable web_search: action=toggle_tool, name=web_search, enabled=true",
            "switch web_search to cloud: action=set_config, key=tools.web_search.backend, value=openai_responses",
            "change LLM model: action=set_config, key=openai.model, value=gpt-4o",
            "restart after config change: action=restart",
            "refresh system knowledge: action=update_agent_doc",
        ],
    },
    "zh": {
        "description": (
            "管理 AI 系统：查看/开关工具，安装/开关/删除技能，切换智能体，读写配置。\n\n"
            "可用操作及参数：\n"
            "  list_tools       — 无需参数。返回所有工具及其启用状态。\n"
            "  toggle_tool      — name: 工具名如 'web_search'; enabled: 'true'/'false'。\n"
            "  list_skills      — 无需参数。\n"
            "  create_skill     — name: 技能名; content: YAML 技能定义。\n"
            "  toggle_skill     — name: 技能名; enabled: 'true'/'false'。\n"
            "  delete_skill     — name: 技能名。\n"
            "  list_agents      — 无需参数。\n"
            "  toggle_agent     — name: 智能体名; enabled: 'true'/'false'。\n"
            "  get_config       — key: 点分路径，如 'tools.web_search.backend'。\n"
            "  set_config       — key: 点分路径; value: 新值。\n"
            "                     不可设置: api_key, bot_token, password, secret, token。\n"
            "  restart          — 无需参数。重启服务使配置生效。\n"
            "                     修改 settings.yaml 后必须调用此操作。\n"
            "  update_agent_doc — 无需参数。扫描所有工具/智能体/技能，更新 AGENT.md，\n"
            "                     让 AI 获得最新的系统能力说明。"
        ),
        "parameters": {
            "action": "list_tools | toggle_tool | list_skills | create_skill | toggle_skill | delete_skill | list_agents | toggle_agent | get_config | set_config | restart | update_agent_doc",
            "name": "工具/技能/智能体名称（toggle/delete/create 时必填）",
            "enabled": "'true' 或 'false'（toggle 操作时必填）",
            "content": "YAML 格式的技能定义（create_skill 时必填）",
            "key": "点分路径配置键，如 'tools.web_search.backend'（get/set_config 时必填）",
            "value": "新的配置值（set_config 时必填）",
        },
        "examples": [
            "开启 web_search：action=toggle_tool, name=web_search, enabled=true",
            "切换搜索到云端：action=set_config, key=tools.web_search.backend, value=openai_responses",
            "修改 LLM 模型：action=set_config, key=openai.model, value=gpt-4o",
            "修改配置后重启：action=restart",
            "刷新系统说明书：action=update_agent_doc",
        ],
    },
    "ja": {
        "description": (
            "AIシステムを管理：ツールの確認/切替、スキルのインストール/切替/削除、エージェント切替、設定の読み書き。\n\n"
            "利用可能なアクションとパラメータ：\n"
            "  list_tools       — 追加パラメータ不要。全ツールと有効状態を返す。\n"
            "  toggle_tool      — name: ツール名 例 'web_search'; enabled: 'true'/'false'。\n"
            "  list_skills      — 追加パラメータ不要。\n"
            "  create_skill     — name: スキル名; content: YAMLスキル定義。\n"
            "  toggle_skill     — name: スキル名; enabled: 'true'/'false'。\n"
            "  delete_skill     — name: スキル名。\n"
            "  list_agents      — 追加パラメータ不要。\n"
            "  toggle_agent     — name: エージェント名; enabled: 'true'/'false'。\n"
            "  get_config       — key: ドット記法パス 例 'tools.web_search.backend'。\n"
            "  set_config       — key: ドット記法パス; value: 新しい値。\n"
            "                     設定不可: api_key, bot_token, password, secret, token。\n"
            "  restart          — 追加パラメータ不要。設定変更を反映するためサービスを再起動。\n"
            "                     settings.yaml 変更後は必ず呼び出すこと。\n"
            "  update_agent_doc — 追加パラメータ不要。全ツール/エージェント/スキルをスキャンし\n"
            "                     AGENT.md を更新してAIのシステム理解を最新化する。"
        ),
        "parameters": {
            "action": "list_tools | toggle_tool | list_skills | create_skill | toggle_skill | delete_skill | list_agents | toggle_agent | get_config | set_config | restart | update_agent_doc",
            "name": "ツール/スキル/エージェント名（toggle/delete/create時必須）",
            "enabled": "'true' または 'false'（toggle操作時必須）",
            "content": "YAMLスキル定義文字列（create_skill時必須）",
            "key": "ドット記法の設定キー 例 'tools.web_search.backend'（get/set_config時必須）",
            "value": "新しい設定値（set_config時必須）",
        },
        "examples": [
            "web_searchを有効化：action=toggle_tool, name=web_search, enabled=true",
            "検索をクラウドに切替：action=set_config, key=tools.web_search.backend, value=openai_responses",
            "LLMモデル変更：action=set_config, key=openai.model, value=gpt-4o",
            "設定変更後に再起動：action=restart",
            "システム説明書を更新：action=update_agent_doc",
        ],
    },
}


class SystemManageTool(BaseTool):

    def __init__(self, config: dict):
        self.config = config

    def is_available(self) -> bool:
        return True  # always available — it's the AI's management interface

    def manifest(self) -> ToolManifest:
        lang = self.config.get("language", "en")
        m = _MANIFEST.get(lang) or _MANIFEST["en"]
        return ToolManifest(
            name="system_manage",
            description=m["description"],
            parameters=m["parameters"],
            examples=m["examples"],
            parameter_types={
                "action": "string",
                "name": "string",
                "enabled": "bool",
                "content": "string",
                "key": "string",
                "value": "bool|int|float|string",
            },
        )

    def execute(self, params: dict) -> ToolResult:
        action = params.get("action", "").strip()
        try:
            result = self._dispatch(action, params)
            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, data="", error=str(e))

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
            from agent.services.settings_writer import _set_skill_md_enabled
            if _set_skill_md_enabled(name, enabled):
                return f"Skill '{name}' set to {'enabled' if enabled else 'disabled'}."
            # Fall back to bundled YAML
            lang = self.config.get("language", "en")
            skill_file = os.path.join(_SKILLS_DIR, f"skills_{lang}.yaml")
            if not os.path.exists(skill_file):
                skill_file = os.path.join(_SKILLS_DIR, "skills_en.yaml")
            from agent.services.settings_writer import _set_yaml_enabled
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
            from agent.services.settings_writer import _set_yaml_enabled
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
            # Key not found — append new section to end of file
            parts = key.split(".")
            if len(parts) == 2:
                lines.append(f"\n{parts[0]}:\n  {parts[1]}: {value}\n")
                _write_settings(lines)
                return f"Config added: {key} = {value}. Restart required for most changes."
            return f"Error: Config field '{key}' not found in settings.yaml."

        if action == "restart":
            import urllib.request
            try:
                token = (self.config.get("public_mode", {}) or {}).get("access_token", "")
                headers = {"Content-Type": "application/json"}
                if token:
                    headers["X-Device-Token"] = token
                req = urllib.request.Request(
                    "http://localhost:8400/system/restart",
                    method="POST",
                    headers=headers,
                    data=b"{}",
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    resp.read()
                return "Service is restarting. Config changes will take effect in a few seconds."
            except Exception as e:
                return f"Restart request failed: {e}"

        if action == "update_agent_doc":
            return _update_agent_doc(self.config)

        return f"Unknown action: '{action}'. Valid actions: list_tools, toggle_tool, list_skills, create_skill, toggle_skill, delete_skill, list_agents, toggle_agent, get_config, set_config, restart, update_agent_doc"
