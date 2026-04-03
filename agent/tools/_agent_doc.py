"""AGENT.md scan and update functions for system_manage."""

import os
import yaml

_SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "settings.yaml")
_SKILLS_DIR = os.environ.get("SKILLS_DIR", os.path.join(os.path.dirname(__file__), "..", "skills"))
_AGENT_CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "config")
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
        from agent.tools import BaseTool, ToolRegistry
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
