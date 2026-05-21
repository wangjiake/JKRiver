"""System skill management endpoints — toggle, install, delete skills."""
import os
import shutil

from fastapi import APIRouter, Depends, HTTPException, Request

from agent.routers import _state
from agent.routers._auth import require_admin
from agent.services.settings_writer import (
    _SKILLS_DIR,
    _set_yaml_enabled,
    _set_skill_file_enabled, _set_skill_md_enabled,
)

router = APIRouter(tags=["system"], dependencies=[Depends(require_admin)])


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
