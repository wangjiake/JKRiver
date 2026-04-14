"""System agent & cloud provider management endpoints."""
import os

from fastapi import APIRouter, HTTPException, Request

from agent.routers import _state
from agent.services.settings_writer import (
    _SETTINGS_PATH,
    _set_yaml_enabled, _delete_yaml_entry, _append_cloud_provider,
)

router = APIRouter(tags=["system"])


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
