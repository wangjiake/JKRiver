"""Settings file read/write helpers for system_manage."""

import os

_SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "settings.yaml")
_SKILLS_DIR = os.environ.get("SKILLS_DIR", os.path.join(os.path.dirname(__file__), "..", "skills"))


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
