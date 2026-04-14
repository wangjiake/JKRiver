"""System tool management endpoints — toggle and delete tools."""
from fastapi import APIRouter, HTTPException, Request

from agent.routers import _state
from agent.services.settings_writer import (
    _SETTINGS_PATH, _TOOLS_YAML,
    _TOP_LEVEL_TOOL_NAMES,
    _get_settings_tool_enabled, _set_settings_tool_enabled, _create_settings_tool_section,
    _get_top_level_enabled, _set_top_level_enabled,
)

router = APIRouter(tags=["system"])


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
