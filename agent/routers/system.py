"""System configuration endpoints — overview, config update, revert, restart."""
import asyncio
import importlib
import os
import subprocess
import sys

from fastapi import APIRouter, HTTPException, Request

from agent.routers import _state
from agent.services.settings_writer import (
    _TOP_LEVEL_TOOL_NAMES, _mask,
    _set_settings_field, _set_settings_list_item_field, _set_settings_allowed_ids,
    _get_settings_tool_enabled,
    _get_top_level_enabled, _set_top_level_enabled,
    _set_settings_tool_enabled,
    _set_yaml_enabled,
)

router = APIRouter(tags=["system"])


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
    """Start a bot subprocess, killing any existing one first.

    Uses pgrep to find and kill ALL running instances of the module
    (including orphaned ones from before os.execv), not just the
    tracked _state proc which is lost after process replacement.
    """
    import os as _os, signal as _signal, time as _time

    # Kill all existing instances by module name (catches post-execv orphans)
    own_pid = _os.getpid()
    try:
        result = subprocess.run(["pgrep", "-f", module], capture_output=True, text=True)
        pids = [int(p) for p in result.stdout.strip().split() if p.strip().isdigit()]
        for pid in pids:
            if pid != own_pid:
                try:
                    _os.kill(pid, _signal.SIGTERM)
                except ProcessLookupError:
                    pass
        if pids:
            _time.sleep(0.5)
    except Exception:
        pass

    # Also clean up the tracked subprocess reference
    proc_attr = f"_{key}_proc"
    existing = getattr(_state, proc_attr, None)
    if existing and existing.poll() is None:
        existing.terminate()
        try:
            existing.wait(timeout=3)
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
