"""system_manage — AI tool for managing tools, skills, agents, and config."""

import os
import yaml

from agent.tools import BaseTool, ToolManifest, ToolResult

_SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "settings.yaml")
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
                if value in ("true", "false"):
                    yaml_val = value
                else:
                    try:
                        float(value)
                        yaml_val = value
                    except ValueError:
                        yaml_val = f'"{value}"'
                lines[i] = " " * indent + f'{expected_key}: {yaml_val}\n'
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


_AGENT_MD_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "AGENT.md"))


def _replace_section(content: str, section: str, new_body: str) -> str:
    """Replace content between AUTO-GENERATED markers, preserving everything else."""
    start_tag = f"<!-- AUTO-GENERATED: {section} -->"
    end_tag = f"<!-- END AUTO-GENERATED: {section} -->"
    start = content.find(start_tag)
    end = content.find(end_tag)
    if start == -1 or end == -1:
        return content
    return content[:start] + start_tag + "\n" + new_body.strip() + "\n" + end_tag + content[end + len(end_tag):]


def _scan_tools(config: dict) -> str:
    """Scan all registered tools and return markdown summary."""
    try:
        import importlib
        from agent.tools import BaseTool, ToolManifest, ToolRegistry
        tool_names = ToolRegistry.list_registered_tool_names()
    except Exception:
        return ""
    if not tool_names:
        return ""

    # Scan config: inject placeholders so context-dependent tools report correctly
    scan_config = dict(config)
    scan_config.setdefault("_session_id", "__scan__")
    scan_config.setdefault("_task_id", "__scan__")
    scan_config.setdefault("_main_loop", True)
    # Populate cloud_llm_configs so web_search (openai_responses) reports correctly
    if not scan_config.get("cloud_llm_configs"):
        providers = scan_config.get("cloud_llm", {}).get("providers", [])
        scan_config["cloud_llm_configs"] = [p for p in providers if p.get("search")]

    entries = []
    for name in tool_names:
        try:
            mod = importlib.import_module(f"agent.tools.{name}")
        except Exception:
            continue
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if not (isinstance(attr, type) and issubclass(attr, BaseTool) and attr is not BaseTool):
                continue
            try:
                inst = attr(scan_config)
                manifest = inst.manifest()
                # For availability: use settings-based check (enabled flag),
                # not runtime checks (missing API keys, session context, etc.)
                cfg_available = inst.is_available()
                entries.append((manifest, cfg_available))
            except Exception:
                pass
            break  # only first matching class per module

    if not entries:
        return ""

    lines = ["## Available Tools\n"]
    for m, available in sorted(entries, key=lambda x: x[0].name):
        status = "enabled" if available else "disabled"
        lines.append(f"### `{m.name}` ({status})")
        lines.append(m.description.strip())
        if m.parameters:
            lines.append("\nParameters:")
            for k, v in m.parameters.items():
                type_hint = m.parameter_types.get(k)
                type_str = f" `({type_hint})`" if type_hint else ""
                lines.append(f"- `{k}`{type_str}: {v}")
        lines.append("")
    return "\n".join(lines)


def _scan_agents(config: dict) -> str:
    """Scan agent config files and return markdown summary."""
    lang = config.get("language", "en")
    candidates = [f"agents_{lang}.yaml", "agents_en.yaml", "agents_zh.yaml"]
    data = None
    for fname in candidates:
        path = os.path.join(_AGENT_CONFIG_DIR, fname)
        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            break
        except FileNotFoundError:
            continue
    if not data:
        return ""
    agents = data.get("agents", [])
    if not agents:
        return ""
    lines = ["## Available Agents\n"]
    lines.append("Switch agents via `system_manage` with `action=\"toggle_agent\"`.\n")
    for a in agents:
        name = a.get("name", "")
        desc = a.get("description", "").strip()
        enabled = a.get("enabled", True)
        status = "enabled" if enabled else "disabled"
        examples = a.get("examples", [])
        lines.append(f"### `{name}` ({status})")
        if desc:
            lines.append(desc)
        if examples:
            lines.append("\nExample triggers: " + " / ".join(f'"{e}"' for e in examples[:3]))
        lines.append("")
    return "\n".join(lines)


def _scan_skills(config: dict) -> str:
    """Scan built-in and user skills and return markdown summary."""
    lang = config.get("language", "en")
    all_skills = []

    # Built-in skills
    for fname in [f"skills_{lang}.yaml", "skills_en.yaml", "skills_zh.yaml"]:
        path = os.path.join(os.path.dirname(__file__), "..", "skills", fname)
        try:
            with open(os.path.normpath(path), encoding="utf-8") as f:
                data = yaml.safe_load(f)
            skills = data.get("skills", []) if data else []
            for s in skills:
                s["_source"] = "built-in"
            all_skills.extend(skills)
            break
        except FileNotFoundError:
            continue

    # User custom skills — only read language-matched skills_*.yaml + custom skill dirs
    skills_dir = os.environ.get("SKILLS_DIR", os.path.join(os.path.dirname(__file__), "..", "skills"))
    if os.path.isdir(skills_dir):
        lang_file = os.path.join(skills_dir, f"skills_{lang}.yaml")
        if os.path.isfile(lang_file):
            try:
                with open(lang_file, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                skills = data.get("skills", []) if data else []
                for s in skills:
                    s["_source"] = "user"
                all_skills.extend(skills)
            except Exception:
                pass
        # Custom skill subdirs (each with a SKILL.md)
        for entry in os.listdir(skills_dir):
            dpath = os.path.join(skills_dir, entry)
            if os.path.isdir(dpath) and os.path.isfile(os.path.join(dpath, "SKILL.md")):
                for fname in os.listdir(dpath):
                    if not fname.endswith(".yaml"):
                        continue
                    try:
                        with open(os.path.join(dpath, fname), encoding="utf-8") as f:
                            data = yaml.safe_load(f)
                        skills = data.get("skills", []) if data else []
                        for s in skills:
                            s["_source"] = "user"
                        all_skills.extend(skills)
                    except Exception:
                        continue

    if not all_skills:
        return ""

    # Deduplicate: user skill with same name+description as built-in is redundant
    seen = {}  # name -> skill
    deduped = []
    for s in all_skills:
        key = s.get("name", "")
        if key not in seen:
            seen[key] = s
            deduped.append(s)
        elif s.get("_source") == "user" and seen[key].get("_source") == "built-in":
            pass  # skip user duplicate of built-in
    all_skills = deduped

    lines = ["## Available Skills\n"]
    lines.append("Skills are auto-detected by the AI based on trigger keywords or schedules.\n")
    for s in all_skills:
        name = s.get("name", "")
        desc = s.get("description", "").strip()
        enabled = s.get("enabled", True)
        source = s.get("_source", "built-in")
        trigger = s.get("trigger", {})
        trigger_type = trigger.get("type", "")
        status = "enabled" if enabled else "disabled"
        lines.append(f"### `{name}` ({status}, {source})")
        if desc:
            lines.append(desc)
        if trigger_type == "keyword":
            kws = trigger.get("keywords", [])
            lines.append(f"Trigger keywords: {', '.join(kws[:5])}")
        elif trigger_type == "schedule":
            lines.append(f"Schedule: `{trigger.get('cron', '')}`")
        lines.append("")
    return "\n".join(lines)


def _scan_system_overview(config: dict) -> str:
    """Read current settings and return a system overview."""
    try:
        with open(_SETTINGS_PATH, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
    except Exception:
        cfg = config or {}
    if not cfg:
        return ""

    def yn(val):
        return "✅ enabled" if val else "❌ disabled"

    lines = ["## System Overview (Current State)\n"]
    lines.append(f"- **Language**: {cfg.get('language', '?')}")
    lines.append(f"- **Timezone**: {cfg.get('timezone', '?')}")
    lines.append(f"- **LLM Provider**: {cfg.get('llm_provider', '?')}")

    if cfg.get("llm_provider") == "openai":
        openai_cfg = cfg.get("openai", {})
        lines.append(f"- **Model**: {openai_cfg.get('model', '?')} @ {openai_cfg.get('api_base', '?')}")
    else:
        local_cfg = cfg.get("local", {})
        lines.append(f"- **Model**: {local_cfg.get('model', '?')} (local Ollama)")

    cloud = cfg.get("cloud_llm", {})
    lines.append(f"- **Remote Fallback (远端兜底)**: {yn(cloud.get('enabled', False))}")

    tools_cfg = cfg.get("tools", {}) or {}
    lines.append(f"\n**Tools status:**")
    tool_names = ["web_search", "dispatch_task", "shell_exec", "file_read",
                  "finance_query", "health_query", "image_describe", "voice_transcribe", "tts"]
    for t in tool_names:
        tcfg = tools_cfg.get(t, {}) or {}
        enabled = tcfg.get("enabled", True)
        extra = ""
        if t == "web_search":
            extra = f" (backend: {tcfg.get('backend', 'duckduckgo')})"
        elif t == "dispatch_task":
            mode = "strict" if tcfg.get("strict_mode", True) else "loose"
            extra = f" (mode: {mode})"
        lines.append(f"- `{t}`: {yn(enabled)}{extra}")

    lines.append(f"\n**Bots:**")
    lines.append(f"- Telegram: {yn(cfg.get('telegram', {}).get('enabled', False))}")
    lines.append(f"- Discord: {yn(cfg.get('discord', {}).get('enabled', False))}")

    lines.append(f"\n**Other features:**")
    lines.append(f"- Proactive messaging: {yn(cfg.get('proactive', {}).get('enabled', False))}")
    lines.append(f"- Embedding/vector search: {yn(cfg.get('embedding', {}).get('enabled', False))}")
    lines.append(f"- Skills: {yn(cfg.get('skills', {}).get('enabled', True))}")
    lines.append(f"- MCP servers: {yn(cfg.get('mcp', {}).get('enabled', False))}")

    return "\n".join(lines)


def _update_agent_doc(config: dict) -> str:
    """Scan all tools/agents/skills/settings and update auto-generated sections in AGENT.md."""
    # Find AGENT.md — check multiple locations
    candidates = [
        _AGENT_MD_PATH,
        "/src/AGENT.md",
        os.path.join(os.path.dirname(__file__), "..", "..", "AGENT.md"),
    ]
    agent_md_path = None
    for c in candidates:
        if os.path.isfile(os.path.normpath(c)):
            agent_md_path = os.path.normpath(c)
            break
    if not agent_md_path:
        return "Error: AGENT.md not found."

    with open(agent_md_path, encoding="utf-8") as f:
        content = f.read()

    content = _replace_section(content, "system_overview", _scan_system_overview(config))
    content = _replace_section(content, "tools", _scan_tools(config))
    content = _replace_section(content, "agents", _scan_agents(config))
    content = _replace_section(content, "skills", _scan_skills(config))

    with open(agent_md_path, "w", encoding="utf-8") as f:
        f.write(content)

    return f"AGENT.md updated: system_overview, tools, agents, skills sections refreshed."


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
