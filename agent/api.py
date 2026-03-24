
import asyncio
import logging
import os
import secrets
import sys
import uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, File, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

UPLOAD_DIR = "/tmp/jkriver_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

from agent.config import load_config
from agent.core import SessionManager, run_cycle_async
from agent.storage import get_db_connection, load_current_profile, load_full_current_profile
from agent.utils.time_context import set_current_time

logger = logging.getLogger(__name__)

_config = None
_manager = None
_pending_restart = False
_revert_ops: list[dict] = []   # [{"file", "name", "enabled"(original)}]

_SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "..", "settings.yaml")

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _config, _manager
    _config = load_config()
    _manager = SessionManager(_config)
    yield


def _api_token_valid(token: str) -> bool:
    pm = _config.get("public_mode", {}) if _config else {}
    if not pm.get("enabled", False):
        return True
    expected = pm.get("access_token", "")
    if not expected:
        return True
    try:
        return secrets.compare_digest(token.encode(), expected.encode())
    except Exception:
        return False

app = FastAPI(title="Riverse Agent API", version="2.2.0", lifespan=lifespan)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # Always allow health check without auth
    if request.url.path == "/health":
        return await call_next(request)
    token = request.headers.get("X-Device-Token", "") or request.query_params.get("token", "")
    if not _api_token_valid(token):
        return JSONResponse(status_code=401, content={"detail": "unauthorized"})
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str = ""
    session_id: str | None = None
    input_type: str = "text"
    file_path: str | None = None
    client_time: str | None = None

class ChatResponse(BaseModel):
    response: str
    session_id: str
    category: str
    intent: str

class SessionResponse(BaseModel):
    session_id: str
    created_at: str

class ProfileEntry(BaseModel):
    category: str
    field: str
    value: str

class HypothesisEntry(BaseModel):
    id: int
    category: str
    subject: str
    claim: str
    confidence: float
    status: str

_TOOL_FOR_INPUT = {"image": "image_describe", "voice": "voice_transcribe"}

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if req.client_time:
        try:
            set_current_time(datetime.fromisoformat(req.client_time))
        except (ValueError, TypeError):
            pass
    session = _manager.get_or_create(req.session_id)
    try:
        # Check tool availability before processing media input
        required_tool = _TOOL_FOR_INPUT.get(req.input_type)
        if required_tool and required_tool not in session.tool_registry._tools:
            from agent.config.prompts import get_labels
            L = get_labels("context.labels", _config.get("language", "en"))
            return ChatResponse(
                response=L.get(f"{req.input_type}_not_supported",
                               f"{req.input_type} input is not supported: {required_tool} tool is not configured."),
                session_id=session.id,
                category="error",
                intent="",
            )

        if req.input_type == "text" and not req.file_path:
            user_input = req.message
        else:
            user_input = {
                "type": req.input_type,
                "text": req.message,
                "file_path": req.file_path or "",
            }

        result = await run_cycle_async(user_input, session)
        return ChatResponse(
            response=result["response"],
            session_id=session.id,
            category=result["perception"].get("category", "chat"),
            intent=result["perception"].get("intent", ""),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/capabilities")
async def get_capabilities():
    """Return which media input tools are configured and available."""
    session = _manager.get_or_create()
    tools = session.tool_registry._tools
    return {
        "image": "image_describe" in tools,
        "voice": "voice_transcribe" in tools,
    }

@app.post("/session/new", response_model=SessionResponse)
async def new_session():
    session = _manager.get_or_create()
    return SessionResponse(
        session_id=session.id,
        created_at=session.created_at.isoformat(),
    )

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename)[1] if file.filename else ".bin"
    filename = f"{uuid.uuid4()}{ext}"
    path = os.path.join(UPLOAD_DIR, filename)
    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)
    return {"file_path": path, "filename": file.filename}


@app.post("/sleep")
async def trigger_sleep():
    try:
        from agent.sleep import run_async as sleep_run_async
        await sleep_run_async()
        from agent.config.prompts import get_labels
        L = get_labels("context.labels", _config.get("language", "en"))
        return {"status": "ok", "message": L["memory_done"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Check DB connectivity and LLM API reachability."""
    db_ok = False
    llm_ok = False

    # DB check
    try:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            db_ok = True
        finally:
            conn.close()
    except Exception as e:
        logger.warning("Health check: DB unreachable: %s", e)

    # LLM check (HEAD request to api_base)
    if _config:
        api_base = _config.get("llm", {}).get("api_base", "")
        if api_base:
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    resp = await client.head(api_base)
                    llm_ok = resp.status_code < 500
            except Exception as e:
                logger.warning("Health check: LLM unreachable: %s", e)
        else:
            llm_ok = True  # no LLM configured = not applicable

    if db_ok and llm_ok:
        status = "ok"
    elif db_ok or llm_ok:
        status = "degraded"
    else:
        status = "error"

    code = 200 if status == "ok" else 503
    return JSONResponse(
        status_code=code,
        content={"status": status, "db": db_ok, "llm": llm_ok},
    )


@app.get("/profile", response_model=list[ProfileEntry])
async def get_profile():
    profile = load_current_profile()
    return [
        ProfileEntry(category=p["category"], field=p["field"], value=p["value"])
        for p in profile
    ]

@app.get("/hypotheses", response_model=list[HypothesisEntry])
async def get_hypotheses():
    profile = load_full_current_profile()
    return [
        HypothesisEntry(
            id=p["id"], category=p["category"], subject=p["subject"],
            claim=p["value"], confidence=0.5, status=p.get("layer", "suspected"),
        )
        for p in profile
    ]

@app.get("/system")
async def get_system():
    """Return full system overview: tools, agents, skills, MCP, config."""
    import yaml as _yaml

    session = _manager.get_or_create()
    registry = session.tool_registry

    # ── Tools — read from tools.yaml registry ──
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

    # ── Disabled builtin tools (listed in tools.yaml but not loaded) ──
    import importlib
    for tname in _BUILTIN_NAMES:
        if tname in seen_tools:
            continue
        desc, examples, parameters = "", [], {}
        try:
            mod = importlib.import_module(f"agent.tools.{tname}")
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if (isinstance(attr, type) and issubclass(attr, _BaseTool)
                        and attr is not _BaseTool):
                    m = attr(_config).manifest()
                    desc = m.description
                    examples = m.examples
                    parameters = m.parameters
                    break
        except Exception:
            pass
        tools.append({"name": tname, "description": desc, "type": "builtin",
                      "enabled": False, "examples": examples, "parameters": parameters})

    # ── Agents from agents_xx.yaml (all, including disabled) ──
    lang = _config.get("language", "en")
    config_dir = os.path.join(os.path.dirname(__file__), "config")
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

    # ── Skills ──
    from agent.skills import SkillRegistry
    skills = []
    try:
        skill_reg = SkillRegistry(_config)
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

    # ── MCP servers ──
    mcp_cfg = _config.get("mcp", {})
    mcp_servers = [
        {"name": srv.get("name", ""), "command": srv.get("command", ""),
         "args": srv.get("args", [])}
        for srv in mcp_cfg.get("servers", [])
    ]

    # ── System config summary ──
    _llm_provider = _config.get("llm_provider", "openai")
    llm = _config.get(_llm_provider, {})
    cloud_cfg = _config.get("cloud_llm", {})

    # Mark web_search tool with whether a search-capable provider is configured
    _web_search_supported = (
        cloud_cfg.get("enabled", False) and
        any(p.get("search") and p.get("api_key") for p in cloud_cfg.get("providers", []))
    )
    for _t in tools:
        if _t["name"] == "web_search":
            _t["search_supported"] = _web_search_supported
    cloud_providers = [
        p.get("model", "") for p in cloud_cfg.get("providers", [])
        if p.get("api_key")
    ]
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
    provider = _config.get("llm_provider", "openai")
    provider_cfg = _config.get(provider, {})
    system = {
        "language": _config.get("language", "en"),
        "llm_provider": _config.get("llm_provider", ""),
        "llm_model": llm.get("model", ""),
        "llm_api_base": llm.get("api_base", ""),
        "llm_api_key_masked": _mask(provider_cfg.get("api_key", "")),
        # openai section (always present)
        "openai_model": _config.get("openai", {}).get("model", ""),
        "openai_api_base": _config.get("openai", {}).get("api_base", ""),
        "openai_api_key_masked": _mask(_config.get("openai", {}).get("api_key", "")),
        "openai_temperature": str(_config.get("openai", {}).get("temperature", 0.7)),
        "openai_max_tokens": str(_config.get("openai", {}).get("max_tokens", 2048)),
        # local section (always present)
        "local_model": _config.get("local", {}).get("model", ""),
        "local_api_base": _config.get("local", {}).get("api_base", ""),
        "local_temperature": str(_config.get("local", {}).get("temperature", 0.7)),
        "local_max_tokens": str(_config.get("local", {}).get("max_tokens", 2048)),
        "embedding_enabled": _config.get("embedding", {}).get("enabled", False),
        "embedding_model": _config.get("embedding", {}).get("model", ""),
        "public_mode": _config.get("public_mode", {}).get("enabled", False),
        "cloud_llm_enabled": _config.get("cloud_llm", {}).get("enabled", False),
        "cloud_llm_providers": cloud_providers,
        "telegram_enabled": _config.get("telegram", {}).get("enabled", False),
        "telegram_token_masked": _mask(_config.get("telegram", {}).get("bot_token", "")),
        "discord_enabled": _config.get("discord", {}).get("enabled", False),
        "discord_token_masked": _mask(_config.get("discord", {}).get("bot_token", "")),
        "tts_enabled": _config.get("tts", {}).get("enabled", False),
        "proactive_enabled": _config.get("proactive", {}).get("enabled", False),
        "skills_enabled": _config.get("skills", {}).get("enabled", False),
        "mcp_enabled": mcp_cfg.get("enabled", False),
        # LLM extra fields
        "llm_temperature": str(llm.get("temperature", 0.7)),
        "llm_max_tokens": str(llm.get("max_tokens", 2048)),
        # Telegram
        "telegram_temp_dir": _config.get("telegram", {}).get("temp_dir", "tmp/telegram"),
        "telegram_allowed_ids": ",".join(str(x) for x in _config.get("telegram", {}).get("allowed_user_ids", [])),
        # Discord
        "discord_temp_dir": _config.get("discord", {}).get("temp_dir", "tmp/discord"),
        "discord_allowed_ids": ",".join(str(x) for x in _config.get("discord", {}).get("allowed_user_ids", [])),
        # TTS
        "tts_voice_zh": _config.get("tts", {}).get("voices", {}).get("zh", ""),
        "tts_voice_en": _config.get("tts", {}).get("voices", {}).get("en", ""),
        "tts_max_chars": str(_config.get("tts", {}).get("max_chars", 500)),
        "tts_temp_dir": _config.get("tts", {}).get("temp_dir", "tmp/tts"),
        # Embedding
        "embedding_api_base": _config.get("embedding", {}).get("api_base", ""),
        # Proactive
        "proactive_interval": str(_config.get("proactive", {}).get("scan_interval_minutes", 30)),
        "proactive_quiet_start": _config.get("proactive", {}).get("quiet_hours", {}).get("start", "23:00"),
        "proactive_quiet_end": _config.get("proactive", {}).get("quiet_hours", {}).get("end", "08:00"),
        "proactive_max_per_day": str(_config.get("proactive", {}).get("max_messages_per_day", 3)),
        "proactive_min_gap": str(_config.get("proactive", {}).get("min_gap_minutes", 120)),
        # Public mode
        "public_access_token_masked": _mask(_config.get("public_mode", {}).get("access_token", "")),
        # Cloud LLM escalation
        "cloud_llm_escalation_auto": cloud_escalation.get("auto", True),
        "cloud_llm_escalation_feedback": cloud_escalation.get("feedback", True),
        "cloud_llm_escalation_min_length": str(cloud_escalation.get("min_response_length", 20)),
        # Timezone
        "timezone": _config.get("timezone", ""),
        # Database (read-only)
        "db_name": _config.get("database", {}).get("name", ""),
        "db_user": _config.get("database", {}).get("user", ""),
        "db_host": _config.get("database", {}).get("host", "localhost"),
        # Session memory
        "sm_char_budget": str(_config.get("session_memory", {}).get("char_budget", 3000)),
        "sm_keep_recent": str(_config.get("session_memory", {}).get("keep_recent", 5)),
        "sm_summary_ratio": str(_config.get("session_memory", {}).get("summary_ratio", 0.4)),
        "sm_recall_max": str(_config.get("session_memory", {}).get("recall_max", 3)),
        "sm_recall_min_score": str(_config.get("session_memory", {}).get("recall_min_score", 0.45)),
        # Tools sub-config
        "tools_enabled": _config.get("tools", {}).get("enabled", True),
        "voice_model": _config.get("tools", {}).get("voice_transcribe", {}).get("model", ""),
        "voice_language": _config.get("tools", {}).get("voice_transcribe", {}).get("language", ""),
        "image_provider": _config.get("tools", {}).get("image_describe", {}).get("provider", ""),
        "image_model": _config.get("tools", {}).get("image_describe", {}).get("model", ""),
        "file_read_max_size": str(_config.get("tools", {}).get("file_read", {}).get("max_file_size", 1048576)),
        "shell_timeout": str(_config.get("tools", {}).get("shell_exec", {}).get("timeout", 30)),
        # Embedding extra
        "embedding_top_k": str(_config.get("embedding", {}).get("search", {}).get("top_k", 5)),
        "embedding_min_score": str(_config.get("embedding", {}).get("search", {}).get("min_score", 0.40)),
        "embedding_clustering": _config.get("embedding", {}).get("clustering", {}).get("enabled", False),
        # Proactive triggers
        "proactive_followup_enabled": _config.get("proactive", {}).get("triggers", {}).get("event_followup", {}).get("enabled", True),
        "proactive_followup_min_importance": str(_config.get("proactive", {}).get("triggers", {}).get("event_followup", {}).get("min_importance", 0.6)),
        "proactive_followup_after_hours": str(_config.get("proactive", {}).get("triggers", {}).get("event_followup", {}).get("followup_after_hours", 24)),
        "proactive_followup_max_age": str(_config.get("proactive", {}).get("triggers", {}).get("event_followup", {}).get("max_age_days", 7)),
        "proactive_strategy_enabled": _config.get("proactive", {}).get("triggers", {}).get("strategy", {}).get("enabled", True),
        "proactive_idle_enabled": _config.get("proactive", {}).get("triggers", {}).get("idle_checkin", {}).get("enabled", True),
        "proactive_idle_hours": str(_config.get("proactive", {}).get("triggers", {}).get("idle_checkin", {}).get("idle_hours", 48)),
    }

    return {
        "system": system,
        "tools": tools,
        "agents": agents,
        "skills": skills,
        "mcp_servers": mcp_servers,
        "cloud_providers": cloud_providers_full,
        "pending_restart": _pending_restart,
    }


def _delete_yaml_entry(filepath: str, name: str) -> tuple[bool, str]:
    """Remove a named list entry from a YAML file. Returns (success, removed_block)."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return False, ""

    name_idx = None
    name_indent = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped in (f'name: {name}', f'name: "{name}"',
                        f'- name: {name}', f'- name: "{name}"'):
            if stripped.startswith('- '):
                name_indent = len(line) - len(line.lstrip())
                name_idx = i
            else:
                for j in range(i, -1, -1):
                    if lines[j].lstrip().startswith('- '):
                        name_indent = len(lines[j]) - len(lines[j].lstrip())
                        name_idx = j
                        break
            break

    if name_idx is None:
        return False, ""

    end_idx = len(lines)
    for i in range(name_idx + 1, len(lines)):
        stripped = lines[i].strip()
        indent = len(lines[i]) - len(lines[i].lstrip())
        if stripped and indent <= name_indent and stripped.startswith('- '):
            end_idx = i
            break

    removed = ''.join(lines[name_idx:end_idx])
    new_lines = lines[:name_idx] + lines[end_idx:]
    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    return True, removed


def _set_settings_list_item_field(section: str, list_key: str, index: int, field: str, value: str) -> tuple[bool, str]:
    """Update a field within the Nth item of a list in settings.yaml.
    e.g. section='cloud_llm', list_key='providers', index=0, field='api_key'
    If the field does not exist in the target item, it is inserted.
    """
    import re as _re
    try:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return False, ""

    if value in ("true", "false"):
        new_val = value
    else:
        try:
            float(value)
            new_val = value
        except ValueError:
            new_val = f'"{value}"'

    in_section = False
    in_list = False
    list_key_indent = 0
    item_indent = None
    current_item = -1
    in_target = False
    target_last_line = None  # last non-empty/non-comment line seen while in_target

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())

        if not in_section:
            if indent == 0 and stripped.startswith(f"{section}:"):
                in_section = True
        elif not in_list:
            if indent == 0:
                return False, ""
            if stripped.startswith(f"{list_key}:"):
                in_list = True
                list_key_indent = indent
        else:
            if indent == 0 or (indent <= list_key_indent and not stripped.startswith("- ")):
                break  # exited the list
            if stripped.startswith("- "):
                if item_indent is None:
                    item_indent = indent
                if indent == item_indent:
                    if in_target:
                        break  # next item started; field was not found in target
                    current_item += 1
                    in_target = (current_item == index)
            if in_target:
                target_last_line = i
                if stripped.startswith(f"{field}:"):
                    rest = stripped[len(field) + 1:].strip()
                    m = _re.match(r'^"(.*)"$', rest) or _re.match(r"^'(.*)'$", rest)
                    old_value = m.group(1) if m else rest
                    comment_match = _re.search(r'\s+(#.*)$', line[line.index(':') + 1:])
                    comment = "  " + comment_match.group(1) if comment_match else ""
                    lines[i] = " " * indent + f'{field}: {new_val}{comment}\n'
                    with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
                        f.writelines(lines)
                    return True, old_value

    # Field not found in target item — insert it after the last field of that item
    if in_target and target_last_line is not None:
        field_indent = (item_indent or 0) + 2
        new_line = " " * field_indent + f'{field}: {new_val}\n'
        lines.insert(target_last_line + 1, new_line)
        with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
            f.writelines(lines)
        return True, ""

    return False, ""


def _set_yaml_enabled(filepath: str, name: str, enabled: bool) -> bool:
    """Toggle the `enabled` field for a named entry in a YAML list file, preserving all comments."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return False

    name_idx = None
    name_indent = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped in (f'name: {name}', f'name: "{name}"',
                        f'- name: {name}', f'- name: "{name}"'):
            name_indent = len(line) - len(line.lstrip())
            name_idx = i
            break

    if name_idx is None:
        return False

    for i in range(name_idx + 1, len(lines)):
        line = lines[i]
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if indent <= name_indent and stripped.startswith("- "):
            break
        if stripped.startswith("enabled:"):
            lines[i] = " " * indent + f'enabled: {"true" if enabled else "false"}\n'
            with open(filepath, "w", encoding="utf-8") as f:
                f.writelines(lines)
            return True

    return False


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "••••"
    return value[:6] + "••••" + value[-4:]


def _set_settings_field(path_parts: list[str], value: str) -> tuple[bool, str]:
    """Update a field in settings.yaml at arbitrary depth, preserving comments.
    Returns (success, old_value).
    """
    import re as _re
    try:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return False, ""

    depth = 0          # which part of path_parts we're looking for next
    parent_indent = -1 # indent of the last section header we entered

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())

        # Exited the current section without finding the target
        if depth > 0 and indent <= parent_indent:
            return False, ""

        # Top-level keys must be at indent 0
        if depth == 0 and indent != 0:
            continue

        target = path_parts[depth]
        if not stripped.startswith(f"{target}:"):
            continue

        if depth == len(path_parts) - 1:
            # Found the final field — update it
            rest = stripped[len(target) + 1:].strip()
            m = _re.match(r'^"(.*)"$', rest) or _re.match(r"^'(.*)'$", rest)
            old_value = m.group(1) if m else rest
            comment_match = _re.search(r'\s+(#.*)$', line[line.index(':') + 1:])
            comment = "  " + comment_match.group(1) if comment_match else ""
            if value in ("true", "false"):
                new_val = value
            else:
                try:
                    float(value)
                    new_val = value  # numeric — no quotes
                except ValueError:
                    new_val = f'"{value}"'
            lines[i] = " " * indent + f'{target}: {new_val}{comment}\n'
            with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
                f.writelines(lines)
            return True, old_value
        else:
            # Enter this section, descend one level
            parent_indent = indent
            depth += 1

    return False, ""


def _set_settings_allowed_ids(section: str, value: str) -> tuple[bool, str]:
    """Write allowed_user_ids as a YAML list in the given section of settings.yaml."""
    import re as _re
    try:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return False, ""

    # Parse comma-separated IDs into a list
    raw_ids = [x.strip() for x in value.split(",") if x.strip()]
    if raw_ids:
        list_str = "[" + ", ".join(raw_ids) + "]"
    else:
        list_str = "[]"

    in_section = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if not in_section:
            if indent == 0 and stripped.startswith(f"{section}:"):
                in_section = True
        else:
            if indent == 0 and stripped and not stripped.startswith("#"):
                break
            if stripped.startswith("allowed_user_ids:"):
                rest = stripped[len("allowed_user_ids:"):].strip()
                old_value = rest
                lines[i] = " " * indent + f'allowed_user_ids: {list_str}\n'
                with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
                    f.writelines(lines)
                return True, old_value
    return False, ""


@app.patch("/system/config")
async def update_config(request: Request):
    global _pending_restart, _revert_ops
    body = await request.json()
    path = body.get("path", "")          # e.g. "openai.api_key"
    value = str(body.get("value", ""))
    path_parts = path.split(".")

    _READONLY_KEYS = {"api_key", "bot_token", "password", "secret", "token"}
    if any(blocked in path_parts[-1].lower() for blocked in _READONLY_KEYS):
        raise HTTPException(status_code=403, detail=f"'{path}' contains sensitive credentials and cannot be updated via API. Edit settings.yaml directly.")

    # Special handling for allowed_user_ids (comma-separated string -> YAML list)
    if len(path_parts) == 2 and path_parts[1] == "allowed_user_ids" and path_parts[0] in ("telegram", "discord"):
        success, old_value = _set_settings_allowed_ids(path_parts[0], value)
    # Special handling for list-item paths: section.list_key.index.field
    elif len(path_parts) == 4 and path_parts[2].isdigit():
        section, list_key, idx_str, field = path_parts
        success, old_value = _set_settings_list_item_field(section, list_key, int(idx_str), field, value)
    else:
        success, old_value = _set_settings_field(path_parts, value)

    if not success:
        raise HTTPException(status_code=404, detail=f"Config field '{path}' not found")
    _revert_ops.append({"type": "settings_field", "path": path, "old_value": old_value})
    _pending_restart = True
    return {"path": path, "pending_restart": True}


def _get_settings_tool_enabled(tool_name: str) -> bool | None:
    """Read current enabled value for a tool from settings.yaml."""
    try:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return None
    in_tools = False
    in_tool_block = False
    tool_indent = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("tools:"):
            in_tools = True
            continue
        if not in_tools:
            continue
        indent = len(line) - len(line.lstrip())
        if indent == 0 and stripped and not stripped.startswith("#"):
            break
        if not in_tool_block:
            if stripped.startswith(f"{tool_name}:"):
                in_tool_block = True
                tool_indent = indent
        else:
            if indent <= tool_indent and stripped and not stripped.startswith("#"):
                break
            if stripped.startswith("enabled:"):
                val = stripped.split(":", 1)[1].strip().lower()
                return val != "false"
    return None


def _set_settings_tool_enabled(tool_name: str, enabled: bool) -> bool:
    """Toggle enabled for a tool block in settings.yaml, preserving comments."""
    try:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return False
    in_tools = False
    in_tool_block = False
    tool_indent = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("tools:"):
            in_tools = True
            continue
        if not in_tools:
            continue
        indent = len(line) - len(line.lstrip())
        if indent == 0 and stripped and not stripped.startswith("#"):
            break
        if not in_tool_block:
            if stripped.startswith(f"{tool_name}:"):
                in_tool_block = True
                tool_indent = indent
        else:
            if indent <= tool_indent and stripped and not stripped.startswith("#"):
                break
            if stripped.startswith("enabled:"):
                lines[i] = " " * indent + f'enabled: {"true" if enabled else "false"}\n'
                with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
                    f.writelines(lines)
                return True
    return False


def _set_skill_file_enabled(name: str, enabled: bool) -> bool:
    """Toggle enabled in an individual YAML skill file."""
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    # Try both safe_name and original name (for files with Unicode/Chinese names)
    candidates = list(dict.fromkeys([safe_name, name]))
    for prefix in ("", "auto_"):
        for cname in candidates:
            filepath = os.path.join(_SKILLS_DIR, f"{prefix}{cname}.yaml")
            if os.path.exists(filepath):
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    # Update existing enabled field
                    for i, line in enumerate(lines):
                        if line.strip().startswith("enabled:") and len(line) - len(line.lstrip()) == 0:
                            lines[i] = f'enabled: {"true" if enabled else "false"}\n'
                            with open(filepath, "w", encoding="utf-8") as f:
                                f.writelines(lines)
                            return True
                    # No enabled field found — insert after name: line
                    for i, line in enumerate(lines):
                        if line.strip().startswith("name:"):
                            lines.insert(i + 1, f'enabled: {"true" if enabled else "false"}\n')
                            with open(filepath, "w", encoding="utf-8") as f:
                                f.writelines(lines)
                            return True
                    # Fallback: prepend
                    lines.insert(0, f'enabled: {"true" if enabled else "false"}\n')
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.writelines(lines)
                    return True
                except Exception:
                    pass
    return False


def _set_skill_md_enabled(name: str, enabled: bool) -> bool:
    """Toggle enabled in a SKILL.md subdirectory skill's frontmatter."""
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    skill_md = os.path.join(_SKILLS_DIR, safe_name, "SKILL.md")
    if not os.path.exists(skill_md):
        return False
    try:
        with open(skill_md, "r", encoding="utf-8") as f:
            content = f.read()
        import re as _re
        # Update or insert enabled in frontmatter
        def replace_enabled(m):
            fm = m.group(1)
            body = m.group(2)
            if _re.search(r'^enabled:', fm, _re.MULTILINE):
                fm = _re.sub(r'^enabled:.*$', f'enabled: {"true" if enabled else "false"}', fm, flags=_re.MULTILINE)
            else:
                fm = fm.rstrip() + f'\nenabled: {"true" if enabled else "false"}\n'
            return f"---\n{fm}\n---\n{body}"
        new_content = _re.sub(r'^---\s*\n(.*?)\n---\s*\n?(.*)', replace_enabled, content, flags=_re.DOTALL)
        with open(skill_md, "w", encoding="utf-8") as f:
            f.write(new_content)
        return True
    except Exception:
        return False


@app.patch("/system/skill/{name}")
async def toggle_skill(name: str, request: Request):
    global _pending_restart
    body = await request.json()
    enabled = bool(body.get("enabled", True))
    # Try individual YAML file first
    if _set_skill_file_enabled(name, enabled):
        _reload_skills()
        return {"name": name, "enabled": enabled, "pending_restart": False}
    # Try SKILL.md subdirectory (SkillHub)
    if _set_skill_md_enabled(name, enabled):
        _reload_skills()
        return {"name": name, "enabled": enabled, "pending_restart": False}
    # Fall back to bundled YAML
    lang = _config.get("language", "en")
    skills_dir = os.path.join(os.path.dirname(__file__), "skills")
    skill_file = os.path.join(skills_dir, f"skills_{lang}.yaml")
    if not os.path.exists(skill_file):
        skill_file = os.path.join(skills_dir, "skills_en.yaml")
    if not _set_yaml_enabled(skill_file, name, enabled):
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")
    _reload_skills()
    return {"name": name, "enabled": enabled, "pending_restart": _pending_restart}


@app.patch("/system/agent/{name}")
async def toggle_agent(name: str, request: Request):
    global _pending_restart, _revert_ops
    body = await request.json()
    enabled = bool(body.get("enabled", True))
    lang = _config.get("language", "en")
    config_dir = os.path.join(os.path.dirname(__file__), "config")
    agents_path = os.path.join(config_dir, f"agents_{lang}.yaml")
    if not os.path.exists(agents_path):
        agents_path = os.path.join(config_dir, "agents_en.yaml")
    _revert_ops.append({"file": agents_path, "name": name, "enabled": not enabled})
    if not _set_yaml_enabled(agents_path, name, enabled):
        _revert_ops.pop()
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")
    _pending_restart = True
    return {"name": name, "enabled": enabled, "pending_restart": True}


def _get_top_level_enabled(section: str) -> bool | None:
    """Read enabled from a top-level section in settings.yaml (e.g. tts.enabled)."""
    try:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return None
    in_section = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{section}:"):
            in_section = True
            continue
        if not in_section:
            continue
        indent = len(line) - len(line.lstrip())
        if indent == 0 and stripped and not stripped.startswith("#"):
            break
        if stripped.startswith("enabled:"):
            return stripped.split(":", 1)[1].strip().lower() != "false"
    return None


def _set_top_level_enabled(section: str, enabled: bool) -> bool:
    """Set enabled under a top-level section in settings.yaml."""
    try:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return False
    in_section = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(f"{section}:"):
            in_section = True
            continue
        if not in_section:
            continue
        indent = len(line) - len(line.lstrip())
        if indent == 0 and stripped and not stripped.startswith("#"):
            break
        if stripped.startswith("enabled:"):
            lines[i] = " " * indent + f'enabled: {"true" if enabled else "false"}\n'
            with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
                f.writelines(lines)
            return True
    return False


# Tools that live under {name}.enabled (top-level section, not under tools:)
_TOP_LEVEL_TOOL_NAMES = {"tts"}


def _create_settings_tool_section(tool_name: str, enabled: bool) -> bool:
    """Add tools.{tool_name}.enabled to settings.yaml, creating the section if missing."""
    try:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return False

    enabled_str = "true" if enabled else "false"
    new_block = [f"    {tool_name}:\n", f"        enabled: {enabled_str}\n"]

    # Find tools: at indent 0
    tools_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("tools:") and len(line) - len(line.lstrip()) == 0:
            tools_idx = i
            break

    if tools_idx is None:
        lines.append(f"\ntools:\n    {tool_name}:\n        enabled: {enabled_str}\n")
    else:
        # Insert before the next top-level key
        insert_at = len(lines)
        for i in range(tools_idx + 1, len(lines)):
            s = lines[i].strip()
            if s and not s.startswith("#") and len(lines[i]) - len(lines[i].lstrip()) == 0:
                insert_at = i
                break
        lines[insert_at:insert_at] = new_block

    with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)
    return True


@app.patch("/system/tool/{name}")
async def toggle_tool(name: str, request: Request):
    global _pending_restart, _revert_ops
    body = await request.json()
    enabled = bool(body.get("enabled", True))

    if name in _TOP_LEVEL_TOOL_NAMES:
        original = _get_top_level_enabled(name)
        _revert_ops.append({"file": _SETTINGS_PATH, "name": name, "enabled": original, "type": "top_level"})
        if not _set_top_level_enabled(name, enabled):
            # Section doesn't exist yet — append it at top level
            try:
                with open(_SETTINGS_PATH, "a", encoding="utf-8") as f:
                    f.write(f"\n{name}:\n    enabled: {'true' if enabled else 'false'}\n")
            except Exception:
                _revert_ops.pop()
                raise HTTPException(status_code=500, detail=f"Failed to update tool '{name}'")
    else:
        original = _get_settings_tool_enabled(name)
        _revert_ops.append({"file": _SETTINGS_PATH, "name": name, "enabled": original, "type": "settings_tool"})
        if not _set_settings_tool_enabled(name, enabled):
            _revert_ops.pop()
            # Auto-create the section
            if not _create_settings_tool_section(name, enabled):
                raise HTTPException(status_code=500, detail=f"Failed to create config for tool '{name}'")

    _pending_restart = True
    return {"name": name, "enabled": enabled, "pending_restart": True}


_TOOLS_YAML = os.path.join(os.path.dirname(__file__), "tools", "tools.yaml")

@app.delete("/system/tool/{name}")
async def delete_tool(name: str):
    """Remove a tool from tools.yaml registry."""
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
    global _pending_restart
    _pending_restart = True
    return {"ok": True, "name": name, "pending_restart": True}


_SKILLS_DIR = os.environ.get("SKILLS_DIR", os.path.join(os.path.dirname(__file__), "skills"))


def _parse_skill_md_api(content: str) -> dict | None:
    """Parse SkillHub SKILL.md format — delegates to the canonical parser in skills/__init__.py."""
    from agent.skills import _parse_skill_md
    return _parse_skill_md(content)


def _reload_skills():
    try:
        session = _manager.get_or_create()
        session.skill_registry.reload()
    except Exception:
        pass


@app.post("/system/skill/install")
async def install_skill(request: Request):
    """Install a skill from YAML or SKILL.md content."""
    body = await request.json()
    content = body.get("content", "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="Empty skill content")

    import yaml as _yaml

    # Detect SKILL.md format (starts with ---)
    if content.startswith("---"):
        data = _parse_skill_md_api(content)
        if not data:
            raise HTTPException(status_code=400, detail="Invalid SKILL.md format: missing frontmatter or name")
        name = data["name"]
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        # Save as SKILL.md in a subdirectory
        skill_dir = os.path.join(_SKILLS_DIR, safe_name)
        os.makedirs(skill_dir, exist_ok=True)
        with open(os.path.join(skill_dir, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write(content)
        _reload_skills()
        return {"ok": True, "name": name, "format": "skillhub", "file": f"{safe_name}/SKILL.md"}

    # Regular YAML format
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


@app.post("/system/skill/install-from-hub")
async def install_skill_from_hub(request: Request):
    """Fetch and install a skill from SkillHub by name (fetches SKILL.md from GitHub)."""
    body = await request.json()
    skill_name = body.get("name", "").strip().lower().replace(" ", "-")
    if not skill_name:
        raise HTTPException(status_code=400, detail="Skill name required")

    # SkillHub skills are hosted on GitHub under the skill-hub org
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
        raise HTTPException(
            status_code=404,
            detail=f"Skill '{skill_name}' not found on SkillHub. Try pasting SKILL.md content directly."
        )

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


@app.delete("/system/skill/{name}")
async def delete_skill(name: str):
    """Delete an individually-installed skill file (YAML or SKILL.md subdirectory)."""
    import shutil
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    candidates = list(dict.fromkeys([safe_name, name]))

    # Try subdirectory (SKILL.md) — by directory name first, then scan all for matching frontmatter name
    for cname in candidates:
        skill_dir = os.path.join(_SKILLS_DIR, cname)
        if os.path.isdir(skill_dir) and os.path.exists(os.path.join(skill_dir, "SKILL.md")):
            shutil.rmtree(skill_dir)
            _reload_skills()
            return {"ok": True, "name": name}
    # Scan all subdirectories for a SKILL.md whose frontmatter name matches
    import yaml as _yaml
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

    # Try individual YAML file (with and without auto_ prefix)
    for prefix in ("", "auto_"):
        for cname in candidates:
            filepath = os.path.join(_SKILLS_DIR, f"{prefix}{cname}.yaml")
            if os.path.exists(filepath):
                os.remove(filepath)
                _reload_skills()
                return {"ok": True, "name": name}

    raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")


def _append_cloud_provider(name: str, model: str, api_base: str, priority: int) -> bool:
    """Append a new provider entry to cloud_llm.providers in settings.yaml."""
    try:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return False

    in_cloud = False
    in_providers = False
    providers_indent = 0
    item_indent = None
    insert_before = None

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if not in_cloud:
            if indent == 0 and stripped.startswith("cloud_llm:"):
                in_cloud = True
        elif not in_providers:
            if indent == 0:
                break
            if stripped.startswith("providers:"):
                in_providers = True
                providers_indent = indent
        else:
            if stripped.startswith("- ") and (item_indent is None or indent == item_indent):
                item_indent = indent
            # End of providers list: back to same indent as providers with a different key
            if indent <= providers_indent and not stripped.startswith("- "):
                insert_before = i
                break

    if insert_before is None:
        insert_before = len(lines)

    ind = " " * (item_indent or (providers_indent + 4))
    sub = " " * ((item_indent or (providers_indent + 4)) + 2)
    new_item = [
        f'{ind}- name: "{name}"\n',
        f'{sub}model: "{model}"\n',
        f'{sub}api_base: "{api_base}"\n',
        f'{sub}api_key: ""\n',
        f'{sub}temperature: 0.7\n',
        f'{sub}max_tokens: 2048\n',
        f'{sub}priority: {priority}\n',
    ]
    lines[insert_before:insert_before] = new_item
    with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)
    return True


@app.delete("/system/cloud_provider/{name}")
async def delete_cloud_provider(name: str):
    global _pending_restart
    success, _ = _delete_yaml_entry(_SETTINGS_PATH, name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Cloud provider '{name}' not found")
    _pending_restart = True
    return {"name": name, "deleted": True, "pending_restart": True}


@app.post("/system/cloud_provider")
async def add_cloud_provider(request: Request):
    global _pending_restart
    body = await request.json()
    name = body.get("name", "").strip()
    model = body.get("model", "").strip()
    api_base = body.get("api_base", "").strip()
    if not name or not model:
        raise HTTPException(status_code=400, detail="name and model are required")
    existing = [p.get("name") for p in _config.get("cloud_llm", {}).get("providers", [])]
    if name in existing:
        raise HTTPException(status_code=400, detail=f"Provider '{name}' already exists")
    priority = len(existing) + 1
    if not _append_cloud_provider(name, model, api_base or "https://api.openai.com", priority):
        raise HTTPException(status_code=500, detail="Failed to write settings.yaml")
    _pending_restart = True
    return {"name": name, "pending_restart": True}


@app.delete("/system/agent/{name}")
async def delete_agent(name: str):
    global _pending_restart
    lang = _config.get("language", "en")
    config_dir = os.path.join(os.path.dirname(__file__), "config")
    agents_path = os.path.join(config_dir, f"agents_{lang}.yaml")
    if not os.path.exists(agents_path):
        agents_path = os.path.join(config_dir, "agents_en.yaml")
    success, _ = _delete_yaml_entry(agents_path, name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")
    _pending_restart = True
    return {"name": name, "deleted": True, "pending_restart": True}


@app.post("/system/revert")
async def revert_changes():
    global _pending_restart, _revert_ops
    for op in reversed(_revert_ops):
        if op.get("type") == "top_level":
            _set_top_level_enabled(op["name"], op["enabled"])
        elif op.get("type") == "settings_tool":
            _set_settings_tool_enabled(op["name"], op["enabled"])
        elif op.get("type") == "settings_field":
            _set_settings_field(op["path"].split("."), op["old_value"])
        else:
            _set_yaml_enabled(op["file"], op["name"], op["enabled"])
    _revert_ops.clear()
    _pending_restart = False
    return {"status": "reverted"}


@app.post("/system/restart")
async def restart_service():
    import sys
    async def _do_restart():
        await asyncio.sleep(0.5)
        os.execv(sys.executable, [sys.executable, "-m", "uvicorn", "agent.api:app",
                                   "--host", "0.0.0.0", "--port", "8400"])
    asyncio.create_task(_do_restart())
    return {"status": "restarting"}


_SESSION_META_SELECT = (
    "SELECT r.session_id, COUNT(*) as turns, "
    "  MIN(r.user_input_at) as started_at, "
    "  MAX(r.user_input_at) as last_at, "
    "  COALESCE("
    "    m.custom_name,"
    "    (SELECT summary FROM session_tags WHERE session_id = r.session_id ORDER BY created_at DESC LIMIT 1),"
    "    (SELECT user_input FROM raw_conversations WHERE session_id = r.session_id ORDER BY user_input_at ASC LIMIT 1)"
    "  ) as preview, "
    "  COALESCE(m.custom_name, '') as custom_name, "
    "  COALESCE(m.pinned, false) as pinned "
    "FROM raw_conversations r "
    "LEFT JOIN session_meta m ON m.session_id = r.session_id "
    "WHERE m.deleted_at IS NULL "
)

def _row_to_session(row):
    return {
        "session_id": row[0],
        "turns": row[1],
        "started_at": row[2].isoformat() if row[2] else None,
        "last_at": row[3].isoformat() if row[3] else None,
        "preview": (row[4] or "")[:80],
        "custom_name": row[5] or "",
        "pinned": row[6],
    }

@app.get("/sessions")
async def list_sessions(limit: int = 30, offset: int = 0):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                _SESSION_META_SELECT +
                "GROUP BY r.session_id, m.custom_name, m.pinned "
                "HAVING COALESCE(m.pinned, false) = false "
                "ORDER BY MIN(r.user_input_at) DESC LIMIT %s OFFSET %s",
                (limit, offset),
            )
            rows = cur.fetchall()
        return [_row_to_session(r) for r in rows]
    finally:
        conn.close()

@app.get("/sessions/pinned")
async def list_pinned_sessions():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                _SESSION_META_SELECT +
                "GROUP BY r.session_id, m.custom_name, m.pinned, m.pinned_at "
                "HAVING COALESCE(m.pinned, false) = true "
                "ORDER BY MAX(m.pinned_at) DESC",
            )
            rows = cur.fetchall()
        return [_row_to_session(r) for r in rows]
    finally:
        conn.close()

@app.post("/sessions/{session_id}/pin")
async def toggle_pin_session(session_id: str):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO session_meta (session_id, pinned, pinned_at) VALUES (%s, true, NOW()) "
                "ON CONFLICT (session_id) DO UPDATE SET "
                "  pinned = NOT session_meta.pinned, "
                "  pinned_at = CASE WHEN NOT session_meta.pinned THEN NOW() ELSE session_meta.pinned_at END",
                (session_id,),
            )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

@app.patch("/sessions/{session_id}/rename")
async def rename_session(session_id: str, body: dict):
    name = (body.get("name") or "").strip()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO session_meta (session_id, custom_name) VALUES (%s, %s) "
                "ON CONFLICT (session_id) DO UPDATE SET custom_name = %s",
                (session_id, name or None, name or None),
            )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO session_meta (session_id, deleted_at) VALUES (%s, NOW()) "
                "ON CONFLICT (session_id) DO UPDATE SET deleted_at = NOW()",
                (session_id,),
            )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

@app.get("/sessions/search")
async def search_sessions(q: str = "", limit: int = 50):
    if not q.strip():
        return []
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT r.session_id, "
                "  COUNT(*) as turns, "
                "  MAX(r.user_input_at) as last_at, "
                "  COALESCE(m.custom_name, "
                "    (SELECT user_input FROM raw_conversations "
                "     WHERE session_id = r.session_id ORDER BY user_input_at ASC LIMIT 1)) as preview, "
                "  SUM(CASE WHEN r.user_input ILIKE %s OR r.assistant_reply ILIKE %s THEN 1 ELSE 0 END) as matches, "
                "  COALESCE(m.custom_name, '') as custom_name, "
                "  COALESCE(m.pinned, false) as pinned "
                "FROM raw_conversations r "
                "LEFT JOIN session_meta m ON m.session_id = r.session_id "
                "WHERE m.deleted_at IS NULL "
                "GROUP BY r.session_id, m.custom_name, m.pinned "
                "HAVING SUM(CASE WHEN r.user_input ILIKE %s OR r.assistant_reply ILIKE %s THEN 1 ELSE 0 END) > 0 "
                "ORDER BY MIN(r.user_input_at) DESC LIMIT %s",
                (f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%", limit),
            )
            rows = cur.fetchall()
        return [
            {
                "session_id": row[0],
                "turns": row[1],
                "last_at": row[2].isoformat() if row[2] else None,
                "preview": (row[3] or "")[:80],
                "matches": row[4],
                "custom_name": row[5] or "",
                "pinned": row[6],
            }
            for row in rows
        ]
    finally:
        conn.close()

@app.get("/session/{session_id}/history")
async def session_history(session_id: str, limit: int = 100):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT user_input, assistant_reply, user_input_at "
                "FROM raw_conversations "
                "WHERE session_id = %s "
                "ORDER BY user_input_at ASC LIMIT %s",
                (session_id, limit),
            )
            rows = cur.fetchall()
        return [
            {"user": r[0], "agent": r[1], "at": r[2].isoformat() if r[2] else None}
            for r in rows
        ]
    finally:
        conn.close()


@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket, session_id: str | None = None):
    await websocket.accept()
    session = _manager.get_or_create(session_id)
    await websocket.send_json({
        "type": "session_created",
        "session_id": session.id,
    })

    try:
        while True:
            data = await websocket.receive_json()
            message = data.get("message", "")
            if not message:
                continue

            client_time = data.get("client_time")
            if client_time:
                try:
                    set_current_time(datetime.fromisoformat(client_time))
                except (ValueError, TypeError):
                    pass

            try:
                result = await run_cycle_async(message, session)
                await websocket.send_json({
                    "type": "response",
                    "response": result["response"],
                    "category": result["perception"].get("category", "chat"),
                    "intent": result["perception"].get("intent", ""),
                })
            except Exception as e:
                await websocket.send_json({
                    "type": "error",
                    "detail": str(e),
                })
    except WebSocketDisconnect:
        pass
