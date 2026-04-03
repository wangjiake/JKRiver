"""System configuration endpoints — tools, skills, agents, cloud providers, settings."""
import asyncio
import importlib
import os
import shutil
import subprocess
import sys

from fastapi import APIRouter, HTTPException, Request

from agent.routers import _state
from agent.services.settings_writer import (
    _SETTINGS_PATH, _TOOLS_YAML, _SKILLS_DIR,
    _TOP_LEVEL_TOOL_NAMES, _mask,
    _set_settings_field, _set_settings_list_item_field, _set_settings_allowed_ids,
    _get_settings_tool_enabled, _set_settings_tool_enabled, _create_settings_tool_section,
    _get_top_level_enabled, _set_top_level_enabled,
    _set_yaml_enabled, _delete_yaml_entry, _append_cloud_provider,
    _set_skill_file_enabled, _set_skill_md_enabled,
)

router = APIRouter(tags=["system"])

_net_last: dict = {}


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/api/system/stats")
async def system_stats():
    try:
        import psutil, time
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        disk_free_gb = disk.free / 1024 ** 3
        net = psutil.net_io_counters()
        now = time.monotonic()
        upload_bps = download_bps = 0.0
        if _net_last:
            dt = now - _net_last["time"]
            if dt > 0:
                upload_bps = (net.bytes_sent - _net_last["bytes_sent"]) / dt
                download_bps = (net.bytes_recv - _net_last["bytes_recv"]) / dt
        _net_last.update({"bytes_sent": net.bytes_sent, "bytes_recv": net.bytes_recv, "time": now})
        return {
            "cpu": round(cpu, 1),
            "mem": round(mem.percent, 1),
            "disk_pct": round(disk.percent, 1),
            "disk_free_gb": round(disk_free_gb, 1),
            "upload_bps": round(upload_bps),
            "download_bps": round(download_bps),
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/api/token-usage")
async def token_usage_stats():
    try:
        from agent.storage.token_usage import get_stats
        timezone = _state._config.get("timezone", "UTC") if _state._config else "UTC"
        return get_stats(timezone)
    except Exception as e:
        return {"error": str(e)}


# ── System overview ───────────────────────────────────────────────────────────

@router.get("/system")
async def get_system():
    import yaml as _yaml
    session = _state._manager.get_or_create()
    registry = session.tool_registry

    from agent.tools import ToolRegistry as _TR, BaseTool as _BaseTool
    _BUILTIN_NAMES = set(_TR.list_registered_tool_names())

    def _builtin_enabled(tname: str) -> bool:
        if tname in _TOP_LEVEL_TOOL_NAMES:
            v = _get_top_level_enabled(tname)
            return v if v is not None else True
        v = _get_settings_tool_enabled(tname)
        return v if v is not None else True

    tools = []
    seen_tools: set[str] = set()
    for name, tool in registry._tools.items():
        m = tool.manifest()
        if name.startswith("mcp_"):
            ttype = "mcp"
        elif name in _BUILTIN_NAMES:
            ttype = "builtin"
        else:
            ttype = "agent"
        tools.append({
            "name": m.name,
            "description": m.description,
            "type": ttype,
            "enabled": _builtin_enabled(name) if ttype == "builtin" else True,
            "examples": m.examples,
            "parameters": m.parameters,
        })
        seen_tools.add(name)

    for tname in _BUILTIN_NAMES:
        if tname in seen_tools:
            continue
        desc, examples, parameters = "", [], {}
        try:
            mod = importlib.import_module(f"agent.tools.{tname}")
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if (isinstance(attr, type) and issubclass(attr, _BaseTool) and attr is not _BaseTool):
                    m = attr(_state._config).manifest()
                    desc, examples, parameters = m.description, m.examples, m.parameters
                    break
        except Exception:
            pass
        tools.append({"name": tname, "description": desc, "type": "builtin",
                      "enabled": False, "examples": examples, "parameters": parameters})

    lang = _state._config.get("language", "en")
    config_dir = os.path.join(os.path.dirname(__file__), "..", "config")
    agents_path = os.path.join(config_dir, f"agents_{lang}.yaml")
    if not os.path.exists(agents_path):
        agents_path = os.path.join(config_dir, "agents_en.yaml")
    agents = []
    if os.path.exists(agents_path):
        with open(agents_path, "r", encoding="utf-8") as f:
            agents_data = _yaml.safe_load(f) or {}
        for a in agents_data.get("agents", []):
            agents.append({
                "name": a.get("name", ""),
                "description": a.get("description", ""),
                "type": a.get("type", "http"),
                "enabled": a.get("enabled", True),
                "examples": a.get("examples", []),
                "parameters": a.get("parameters", {}),
            })

    from agent.skills import SkillRegistry
    skills = []
    try:
        skill_reg = SkillRegistry(_state._config)
        for s in skill_reg.list_all():
            skills.append({
                "name": s.name,
                "description": s.description,
                "trigger_type": s.trigger_type,
                "keywords": s.keywords,
                "cron": s.cron,
                "enabled": s.enabled,
                "source": getattr(s, "_source", "bundled"),
            })
    except Exception:
        pass

    mcp_cfg = _state._config.get("mcp", {})
    mcp_servers = [
        {"name": srv.get("name", ""), "command": srv.get("command", ""), "args": srv.get("args", [])}
        for srv in mcp_cfg.get("servers", [])
    ]

    _llm_provider = _state._config.get("llm_provider", "openai")
    llm = _state._config.get(_llm_provider, {})
    cloud_cfg = _state._config.get("cloud_llm", {})

    _ws_backend = _state._config.get("tools", {}).get("web_search", {}).get("backend", "openai_responses")
    _openai_search_supported = (
        cloud_cfg.get("enabled", False) and
        any(p.get("search") and p.get("api_key") for p in cloud_cfg.get("providers", []))
    )
    _web_search_supported = (_ws_backend == "duckduckgo") or \
                            (_ws_backend == "openai_responses" and _openai_search_supported)
    for _t in tools:
        if _t["name"] == "web_search":
            _t["search_supported"] = _web_search_supported
            _t["search_backend"] = _ws_backend

    cloud_providers_full = [
        {
            "index": idx,
            "name": p.get("name", ""),
            "model": p.get("model", ""),
            "api_base": p.get("api_base", ""),
            "api_key_masked": _mask(p.get("api_key", "")),
            "priority": str(p.get("priority", idx + 1)),
            "search": p.get("search", False),
            "temperature": str(p.get("temperature", 0.7)),
            "max_tokens": str(p.get("max_tokens", 2048)),
        }
        for idx, p in enumerate(cloud_cfg.get("providers", []))
    ]
    cloud_escalation = cloud_cfg.get("escalation", {})
    provider_cfg = _state._config.get(_llm_provider, {})

    system = {
        "language": _state._config.get("language", "en"),
        "llm_provider": _state._config.get("llm_provider", ""),
        "llm_model": llm.get("model", ""),
        "llm_api_base": llm.get("api_base", ""),
        "llm_api_key_masked": _mask(provider_cfg.get("api_key", "")),
        "openai_model": _state._config.get("openai", {}).get("model", ""),
        "openai_api_base": _state._config.get("openai", {}).get("api_base", ""),
        "openai_api_key_masked": _mask(_state._config.get("openai", {}).get("api_key", "")),
        "openai_temperature": str(_state._config.get("openai", {}).get("temperature", 0.7)),
        "openai_max_tokens": str(_state._config.get("openai", {}).get("max_tokens", 2048)),
        "local_model": _state._config.get("local", {}).get("model", ""),
        "local_api_base": _state._config.get("local", {}).get("api_base", ""),
        "local_temperature": str(_state._config.get("local", {}).get("temperature", 0.7)),
        "local_max_tokens": str(_state._config.get("local", {}).get("max_tokens", 2048)),
        "embedding_enabled": _state._config.get("embedding", {}).get("enabled", False),
        "embedding_model": _state._config.get("embedding", {}).get("model", ""),
        "public_mode": _state._config.get("public_mode", {}).get("enabled", False),
        "cloud_llm_enabled": cloud_cfg.get("enabled", False),
        "cloud_llm_providers": [p.get("model", "") for p in cloud_cfg.get("providers", []) if p.get("api_key")],
        "telegram_enabled": _state._config.get("telegram", {}).get("enabled", False),
        "telegram_token_masked": _mask(_state._config.get("telegram", {}).get("bot_token", "")),
        "discord_enabled": _state._config.get("discord", {}).get("enabled", False),
        "discord_token_masked": _mask(_state._config.get("discord", {}).get("bot_token", "")),
        "tts_enabled": _state._config.get("tts", {}).get("enabled", False),
        "proactive_enabled": _state._config.get("proactive", {}).get("enabled", False),
        "skills_enabled": _state._config.get("skills", {}).get("enabled", False),
        "mcp_enabled": mcp_cfg.get("enabled", False),
        "llm_temperature": str(llm.get("temperature", 0.7)),
        "llm_max_tokens": str(llm.get("max_tokens", 2048)),
        "telegram_temp_dir": _state._config.get("telegram", {}).get("temp_dir", "tmp/telegram"),
        "telegram_allowed_ids": ",".join(str(x) for x in _state._config.get("telegram", {}).get("allowed_user_ids", [])),
        "discord_temp_dir": _state._config.get("discord", {}).get("temp_dir", "tmp/discord"),
        "discord_allowed_ids": ",".join(str(x) for x in _state._config.get("discord", {}).get("allowed_user_ids", [])),
        "tts_voice_zh": _state._config.get("tts", {}).get("voices", {}).get("zh", ""),
        "tts_voice_en": _state._config.get("tts", {}).get("voices", {}).get("en", ""),
        "tts_max_chars": str(_state._config.get("tts", {}).get("max_chars", 500)),
        "tts_temp_dir": _state._config.get("tts", {}).get("temp_dir", "tmp/tts"),
        "embedding_api_base": _state._config.get("embedding", {}).get("api_base", ""),
        "proactive_interval": str(_state._config.get("proactive", {}).get("scan_interval_minutes", 30)),
        "proactive_quiet_start": _state._config.get("proactive", {}).get("quiet_hours", {}).get("start", "23:00"),
        "proactive_quiet_end": _state._config.get("proactive", {}).get("quiet_hours", {}).get("end", "08:00"),
        "proactive_max_per_day": str(_state._config.get("proactive", {}).get("max_messages_per_day", 3)),
        "proactive_min_gap": str(_state._config.get("proactive", {}).get("min_gap_minutes", 120)),
        "public_access_token_masked": _mask(_state._config.get("public_mode", {}).get("access_token", "")),
        "cloud_llm_escalation_auto": cloud_escalation.get("auto", True),
        "cloud_llm_escalation_feedback": cloud_escalation.get("feedback", True),
        "cloud_llm_escalation_min_length": str(cloud_escalation.get("min_response_length", 20)),
        "timezone": _state._config.get("timezone", ""),
        "db_name": _state._config.get("database", {}).get("name", ""),
        "db_user": _state._config.get("database", {}).get("user", ""),
        "db_host": _state._config.get("database", {}).get("host", "localhost"),
        "sm_char_budget": str(_state._config.get("session_memory", {}).get("char_budget", 3000)),
        "sm_keep_recent": str(_state._config.get("session_memory", {}).get("keep_recent", 5)),
        "sm_summary_ratio": str(_state._config.get("session_memory", {}).get("summary_ratio", 0.4)),
        "sm_recall_max": str(_state._config.get("session_memory", {}).get("recall_max", 3)),
        "sm_recall_min_score": str(_state._config.get("session_memory", {}).get("recall_min_score", 0.45)),
        "tools_enabled": _state._config.get("tools", {}).get("enabled", True),
        "voice_model": _state._config.get("tools", {}).get("voice_transcribe", {}).get("model", ""),
        "voice_language": _state._config.get("tools", {}).get("voice_transcribe", {}).get("language", ""),
        "image_provider": _state._config.get("tools", {}).get("image_describe", {}).get("provider", ""),
        "image_model": _state._config.get("tools", {}).get("image_describe", {}).get("model", ""),
        "file_read_max_size": str(_state._config.get("tools", {}).get("file_read", {}).get("max_file_size", 1048576)),
        "shell_timeout": str(_state._config.get("tools", {}).get("shell_exec", {}).get("timeout", 30)),
        "dispatch_strict_mode": bool(_state._config.get("tools", {}).get("dispatch_task", {}).get("strict_mode", True)),
        "agent_doc_scan_enabled": bool(_state._config.get("agent_doc_scan", {}).get("enabled", True)),
        "embedding_top_k": str(_state._config.get("embedding", {}).get("search", {}).get("top_k", 5)),
        "embedding_min_score": str(_state._config.get("embedding", {}).get("search", {}).get("min_score", 0.40)),
        "embedding_clustering": _state._config.get("embedding", {}).get("clustering", {}).get("enabled", False),
        "proactive_followup_enabled": _state._config.get("proactive", {}).get("triggers", {}).get("event_followup", {}).get("enabled", True),
        "proactive_followup_min_importance": str(_state._config.get("proactive", {}).get("triggers", {}).get("event_followup", {}).get("min_importance", 0.6)),
        "proactive_followup_after_hours": str(_state._config.get("proactive", {}).get("triggers", {}).get("event_followup", {}).get("followup_after_hours", 24)),
        "proactive_followup_max_age": str(_state._config.get("proactive", {}).get("triggers", {}).get("event_followup", {}).get("max_age_days", 7)),
        "proactive_strategy_enabled": _state._config.get("proactive", {}).get("triggers", {}).get("strategy", {}).get("enabled", True),
        "proactive_idle_enabled": _state._config.get("proactive", {}).get("triggers", {}).get("idle_checkin", {}).get("enabled", True),
        "proactive_idle_hours": str(_state._config.get("proactive", {}).get("triggers", {}).get("idle_checkin", {}).get("idle_hours", 48)),
    }

    return {
        "system": system,
        "tools": tools,
        "agents": agents,
        "skills": skills,
        "mcp_servers": mcp_servers,
        "cloud_providers": cloud_providers_full,
        "pending_restart": _state._pending_restart,
    }


# ── Config update ─────────────────────────────────────────────────────────────

@router.patch("/system/config")
async def update_config(request: Request):
    body = await request.json()
    path = body.get("path", "")
    value = str(body.get("value", ""))
    path_parts = path.split(".")

    if len(path_parts) == 2 and path_parts[1] == "allowed_user_ids" and path_parts[0] in ("telegram", "discord"):
        success, old_value = _set_settings_allowed_ids(path_parts[0], value)
    elif len(path_parts) == 4 and path_parts[2].isdigit():
        section, list_key, idx_str, field = path_parts
        success, old_value = _set_settings_list_item_field(section, list_key, int(idx_str), field, value)
    else:
        success, old_value = _set_settings_field(path_parts, value)

    if not success:
        raise HTTPException(status_code=404, detail=f"Config field '{path}' not found")
    _state._revert_ops.append({"type": "settings_field", "path": path, "old_value": old_value})
    _state._pending_restart = True
    return {"path": path, "pending_restart": True}


# ── Tools ─────────────────────────────────────────────────────────────────────

@router.patch("/system/tool/{name}")
async def toggle_tool(name: str, request: Request):
    body = await request.json()
    enabled = bool(body.get("enabled", True))

    if name in _TOP_LEVEL_TOOL_NAMES:
        original = _get_top_level_enabled(name)
        _state._revert_ops.append({"file": _SETTINGS_PATH, "name": name, "enabled": original, "type": "top_level"})
        if not _set_top_level_enabled(name, enabled):
            try:
                with open(_SETTINGS_PATH, "a", encoding="utf-8") as f:
                    f.write(f"\n{name}:\n    enabled: {'true' if enabled else 'false'}\n")
            except Exception:
                _state._revert_ops.pop()
                raise HTTPException(status_code=500, detail=f"Failed to update tool '{name}'")
    else:
        original = _get_settings_tool_enabled(name)
        _state._revert_ops.append({"file": _SETTINGS_PATH, "name": name, "enabled": original, "type": "settings_tool"})
        if not _set_settings_tool_enabled(name, enabled):
            _state._revert_ops.pop()
            if not _create_settings_tool_section(name, enabled):
                raise HTTPException(status_code=500, detail=f"Failed to create config for tool '{name}'")

    _state._pending_restart = True
    return {"name": name, "enabled": enabled, "pending_restart": True}


@router.delete("/system/tool/{name}")
async def delete_tool(name: str):
    import yaml as _yaml
    try:
        with open(_TOOLS_YAML, "r", encoding="utf-8") as f:
            data = _yaml.safe_load(f) or {}
        tools_list = [str(t) for t in data.get("tools", []) if t]
        if name not in tools_list:
            raise HTTPException(status_code=404, detail=f"Tool '{name}' not found in registry")
        tools_list.remove(name)
        data["tools"] = tools_list
        with open(_TOOLS_YAML, "w", encoding="utf-8") as f:
            _yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    _state._pending_restart = True
    return {"ok": True, "name": name, "pending_restart": True}


# ── Skills ────────────────────────────────────────────────────────────────────

def _reload_skills():
    try:
        session = _state._manager.get_or_create()
        session.skill_registry.reload()
    except Exception:
        pass


def _parse_skill_md_api(content: str) -> dict | None:
    from agent.skills import _parse_skill_md
    return _parse_skill_md(content)


@router.patch("/system/skill/{name}")
async def toggle_skill(name: str, request: Request):
    body = await request.json()
    enabled = bool(body.get("enabled", True))
    if _set_skill_file_enabled(name, enabled):
        _reload_skills()
        return {"name": name, "enabled": enabled, "pending_restart": False}
    if _set_skill_md_enabled(name, enabled):
        _reload_skills()
        return {"name": name, "enabled": enabled, "pending_restart": False}
    lang = _state._config.get("language", "en")
    skills_dir = os.path.join(os.path.dirname(__file__), "..", "skills")
    skill_file = os.path.join(skills_dir, f"skills_{lang}.yaml")
    if not os.path.exists(skill_file):
        skill_file = os.path.join(skills_dir, "skills_en.yaml")
    if not _set_yaml_enabled(skill_file, name, enabled):
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")
    _reload_skills()
    return {"name": name, "enabled": enabled, "pending_restart": _state._pending_restart}


@router.post("/system/skill/install")
async def install_skill(request: Request):
    import yaml as _yaml
    body = await request.json()
    content = body.get("content", "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="Empty skill content")

    if content.startswith("---"):
        data = _parse_skill_md_api(content)
        if not data:
            raise HTTPException(status_code=400, detail="Invalid SKILL.md format: missing frontmatter or name")
        name = data["name"]
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        skill_dir = os.path.join(_SKILLS_DIR, safe_name)
        os.makedirs(skill_dir, exist_ok=True)
        with open(os.path.join(skill_dir, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write(content)
        _reload_skills()
        return {"ok": True, "name": name, "format": "skillhub", "file": f"{safe_name}/SKILL.md"}

    try:
        data = _yaml.safe_load(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {e}")
    if not isinstance(data, dict) or not data.get("name"):
        raise HTTPException(status_code=400, detail="Skill must be a YAML dict with a 'name' field")
    name = data["name"]
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    filepath = os.path.join(_SKILLS_DIR, f"{safe_name}.yaml")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    _reload_skills()
    return {"ok": True, "name": name, "format": "yaml", "file": f"{safe_name}.yaml"}


@router.post("/system/skill/install-from-hub")
async def install_skill_from_hub(request: Request):
    import httpx
    body = await request.json()
    skill_name = body.get("name", "").strip().lower().replace(" ", "-")
    if not skill_name:
        raise HTTPException(status_code=400, detail="Skill name required")

    urls_to_try = [
        f"https://raw.githubusercontent.com/skill-hub/{skill_name}/main/SKILL.md",
        f"https://raw.githubusercontent.com/skill-hub/skills/main/{skill_name}/SKILL.md",
        f"https://raw.githubusercontent.com/anthropics/anthropic-skills/main/{skill_name}/SKILL.md",
    ]
    content = None
    async with httpx.AsyncClient(timeout=10.0) as client:
        for url in urls_to_try:
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    content = resp.text
                    break
            except Exception:
                continue

    if not content:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found on SkillHub.")

    data = _parse_skill_md_api(content)
    if not data:
        raise HTTPException(status_code=400, detail="Invalid SKILL.md fetched from hub")
    name = data["name"]
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    skill_dir = os.path.join(_SKILLS_DIR, safe_name)
    os.makedirs(skill_dir, exist_ok=True)
    with open(os.path.join(skill_dir, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write(content)
    _reload_skills()
    return {"ok": True, "name": name, "format": "skillhub", "file": f"{safe_name}/SKILL.md"}


@router.delete("/system/skill/{name}")
async def delete_skill(name: str):
    import yaml as _yaml
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    candidates = list(dict.fromkeys([safe_name, name]))

    for cname in candidates:
        skill_dir = os.path.join(_SKILLS_DIR, cname)
        if os.path.isdir(skill_dir) and os.path.exists(os.path.join(skill_dir, "SKILL.md")):
            shutil.rmtree(skill_dir)
            _reload_skills()
            return {"ok": True, "name": name}

    for entry in os.scandir(_SKILLS_DIR):
        if not entry.is_dir():
            continue
        skill_md = os.path.join(entry.path, "SKILL.md")
        if not os.path.exists(skill_md):
            continue
        try:
            with open(skill_md, "r", encoding="utf-8") as f:
                content = f.read()
            data = _parse_skill_md_api(content)
            if data and data.get("name") == name:
                shutil.rmtree(entry.path)
                _reload_skills()
                return {"ok": True, "name": name}
        except Exception:
            continue

    for prefix in ("", "auto_"):
        for cname in candidates:
            filepath = os.path.join(_SKILLS_DIR, f"{prefix}{cname}.yaml")
            if os.path.exists(filepath):
                os.remove(filepath)
                _reload_skills()
                return {"ok": True, "name": name}

    raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")


# ── Agents ────────────────────────────────────────────────────────────────────

@router.patch("/system/agent/{name}")
async def toggle_agent(name: str, request: Request):
    body = await request.json()
    enabled = bool(body.get("enabled", True))
    lang = _state._config.get("language", "en")
    config_dir = os.path.join(os.path.dirname(__file__), "..", "config")
    agents_path = os.path.join(config_dir, f"agents_{lang}.yaml")
    if not os.path.exists(agents_path):
        agents_path = os.path.join(config_dir, "agents_en.yaml")
    _state._revert_ops.append({"file": agents_path, "name": name, "enabled": not enabled})
    if not _set_yaml_enabled(agents_path, name, enabled):
        _state._revert_ops.pop()
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")
    _state._pending_restart = True
    return {"name": name, "enabled": enabled, "pending_restart": True}


@router.delete("/system/agent/{name}")
async def delete_agent(name: str):
    lang = _state._config.get("language", "en")
    config_dir = os.path.join(os.path.dirname(__file__), "..", "config")
    agents_path = os.path.join(config_dir, f"agents_{lang}.yaml")
    if not os.path.exists(agents_path):
        agents_path = os.path.join(config_dir, "agents_en.yaml")
    success, _ = _delete_yaml_entry(agents_path, name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")
    _state._pending_restart = True
    return {"name": name, "deleted": True, "pending_restart": True}


# ── Cloud providers ───────────────────────────────────────────────────────────

@router.post("/system/cloud_provider")
async def add_cloud_provider(request: Request):
    body = await request.json()
    name = body.get("name", "").strip()
    model = body.get("model", "").strip()
    api_base = body.get("api_base", "").strip()
    if not name or not model:
        raise HTTPException(status_code=400, detail="name and model are required")
    existing = [p.get("name") for p in _state._config.get("cloud_llm", {}).get("providers", [])]
    if name in existing:
        raise HTTPException(status_code=400, detail=f"Provider '{name}' already exists")
    priority = len(existing) + 1
    if not _append_cloud_provider(name, model, api_base or "https://api.openai.com", priority):
        raise HTTPException(status_code=500, detail="Failed to write settings.yaml")
    _state._pending_restart = True
    return {"name": name, "pending_restart": True}


@router.delete("/system/cloud_provider/{name}")
async def delete_cloud_provider(name: str):
    success, _ = _delete_yaml_entry(_SETTINGS_PATH, name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Cloud provider '{name}' not found")
    _state._pending_restart = True
    return {"name": name, "deleted": True, "pending_restart": True}


# ── Revert / Restart ──────────────────────────────────────────────────────────

@router.post("/system/revert")
async def revert_changes():
    for op in reversed(_state._revert_ops):
        if op.get("type") == "top_level":
            _set_top_level_enabled(op["name"], op["enabled"])
        elif op.get("type") == "settings_tool":
            _set_settings_tool_enabled(op["name"], op["enabled"])
        elif op.get("type") == "settings_field":
            _set_settings_field(op["path"].split("."), op["old_value"])
        else:
            _set_yaml_enabled(op["file"], op["name"], op["enabled"])
    _state._revert_ops.clear()
    _state._pending_restart = False
    return {"status": "reverted"}


def _start_bot(key: str, module: str):
    """Start a bot subprocess, killing any existing one first."""
    proc_attr = f"_{key}_proc"
    existing = getattr(_state, proc_attr, None)
    if existing and existing.poll() is None:
        existing.terminate()
        try:
            existing.wait(timeout=5)
        except Exception:
            existing.kill()
    cfg = (_state._config or {}).get(key, {})
    if cfg.get("enabled") and cfg.get("bot_token"):
        proc = subprocess.Popen([sys.executable, "-m", module])
        setattr(_state, proc_attr, proc)
        return True
    return False


def _stop_bot(key: str):
    """Stop a bot subprocess if running."""
    proc_attr = f"_{key}_proc"
    existing = getattr(_state, proc_attr, None)
    if existing and existing.poll() is None:
        existing.terminate()
        try:
            existing.wait(timeout=5)
        except Exception:
            existing.kill()
    setattr(_state, proc_attr, None)


def _sync_bots():
    """Start/stop bots based on current config."""
    _start_bot("telegram", "agent.telegram_bot")
    _start_bot("discord", "agent.discord_bot")


@router.post("/system/restart")
async def restart_service():
    async def _do_restart():
        await asyncio.sleep(0.5)
        # Reload config so bot changes take effect immediately
        from agent.config import load_config
        _state._config = load_config()
        _sync_bots()
        os.execv(sys.executable, [sys.executable, "-m", "uvicorn", "agent.api:app",
                                   "--host", "0.0.0.0", "--port", "8400"])
    asyncio.create_task(_do_restart())
    return {"status": "restarting"}
