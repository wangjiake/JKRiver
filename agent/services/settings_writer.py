"""YAML settings read/write helpers — all functions that touch settings.yaml or agent YAML files."""
import os
import re

_SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "settings.yaml")
_TOOLS_YAML = os.path.join(os.path.dirname(__file__), "..", "tools", "tools.yaml")
_SKILLS_DIR = os.environ.get("SKILLS_DIR", os.path.join(os.path.dirname(__file__), "..", "skills"))

_ALWAYS_STRING_FIELDS = {
    "api_key", "api_base", "model", "token", "bot_token", "access_token",
    "name", "host", "user", "password", "language",
}
_TOP_LEVEL_TOOL_NAMES = {"tts"}


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "••••"
    return value[:6] + "••••" + value[-4:]


def _yaml_value(field: str, value: str) -> str:
    """Format a value for YAML output, quoting strings where needed."""
    if value in ("true", "false"):
        return value
    if field in _ALWAYS_STRING_FIELDS:
        return f'"{value.replace(chr(92), chr(92)*2).replace(chr(34), chr(92)+chr(34))}"'
    try:
        float(value)
        return value
    except ValueError:
        return f'"{value.replace(chr(92), chr(92)*2).replace(chr(34), chr(92)+chr(34))}"'


# ── settings.yaml field read/write ───────────────────────────────────────────

def _set_settings_field(path_parts: list[str], value: str) -> tuple[bool, str]:
    """Update a scalar field at arbitrary depth in settings.yaml, preserving comments."""
    try:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return False, ""

    depth = 0
    parent_indent = -1

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())

        if depth > 0 and indent <= parent_indent:
            return False, ""
        if depth == 0 and indent != 0:
            continue

        target = path_parts[depth]
        if not stripped.startswith(f"{target}:"):
            continue

        if depth == len(path_parts) - 1:
            rest = stripped[len(target) + 1:].strip()
            rest_value = re.sub(r'\s+#.*$', '', rest).strip()
            m = re.match(r'^"(.*)"$', rest_value) or re.match(r"^'(.*)'$", rest_value)
            old_value = m.group(1) if m else rest_value
            comment_match = re.search(r'\s+(#.*)$', line[line.index(':') + 1:])
            comment = "  " + comment_match.group(1) if comment_match else ""
            new_val = _yaml_value(path_parts[-1], value)
            lines[i] = " " * indent + f'{target}: {new_val}{comment}\n'
            with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
                f.writelines(lines)
            return True, old_value
        else:
            parent_indent = indent
            depth += 1

    # Key not found — append new section if path is 2 levels deep.
    # Guard: only append if parent key does not already exist anywhere in the file,
    # to avoid creating duplicate top-level sections.
    if len(path_parts) == 2:
        parent_key = path_parts[0]
        parent_exists = any(
            line.strip() and not line.strip().startswith("#")
            and re.match(rf"^{re.escape(parent_key)}\s*:", line)
            for line in lines
        )
        new_val = _yaml_value(path_parts[-1], value)
        if parent_exists:
            # Parent section exists but child key was not found — append child under parent
            for i in range(len(lines) - 1, -1, -1):
                if re.match(rf"^{re.escape(parent_key)}\s*:", lines[i].strip() and lines[i]):
                    lines.insert(i + 1, f"  {path_parts[1]}: {new_val}\n")
                    break
        else:
            lines.append(f"\n{parent_key}:\n  {path_parts[1]}: {new_val}\n")
        with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
            f.writelines(lines)
        return True, ""

    return False, ""


def _set_settings_list_item_field(section: str, list_key: str, index: int, field: str, value: str) -> tuple[bool, str]:
    """Update a field within the Nth item of a list in settings.yaml."""
    try:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return False, ""

    new_val = _yaml_value(field, value)

    in_section = False
    in_list = False
    list_key_indent = 0
    item_indent = None
    current_item = -1
    in_target = False
    target_last_line = None

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
                break
            if stripped.startswith("- "):
                if item_indent is None:
                    item_indent = indent
                if indent == item_indent:
                    if in_target:
                        break
                    current_item += 1
                    in_target = (current_item == index)
            if in_target:
                target_last_line = i
                if stripped.startswith(f"{field}:"):
                    rest = stripped[len(field) + 1:].strip()
                    m = re.match(r'^"(.*)"$', rest) or re.match(r"^'(.*)'$", rest)
                    old_value = m.group(1) if m else rest
                    comment_match = re.search(r'\s+(#.*)$', line[line.index(':') + 1:])
                    comment = "  " + comment_match.group(1) if comment_match else ""
                    lines[i] = " " * indent + f'{field}: {new_val}{comment}\n'
                    with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
                        f.writelines(lines)
                    return True, old_value

    if in_target and target_last_line is not None:
        field_indent = (item_indent or 0) + 2
        new_line = " " * field_indent + f'{field}: {new_val}\n'
        lines.insert(target_last_line + 1, new_line)
        with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
            f.writelines(lines)
        return True, ""

    return False, ""


def _set_settings_allowed_ids(section: str, value: str) -> tuple[bool, str]:
    """Write allowed_user_ids as a YAML list in the given section."""
    try:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return False, ""

    raw_ids = [x.strip() for x in value.split(",") if x.strip()]
    list_str = "[" + ", ".join(raw_ids) + "]" if raw_ids else "[]"

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
                old_value = stripped[len("allowed_user_ids:"):].strip()
                lines[i] = " " * indent + f'allowed_user_ids: {list_str}\n'
                with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
                    f.writelines(lines)
                return True, old_value
    return False, ""


# ── tools section ─────────────────────────────────────────────────────────────

def _get_settings_tool_enabled(tool_name: str) -> bool | None:
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
                return stripped.split(":", 1)[1].strip().lower() != "false"
    return None


def _set_settings_tool_enabled(tool_name: str, enabled: bool) -> bool:
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


def _create_settings_tool_section(tool_name: str, enabled: bool) -> bool:
    """Add tools.{tool_name}.enabled to settings.yaml, creating the section if missing."""
    try:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return False

    enabled_str = "true" if enabled else "false"
    new_block = [f"    {tool_name}:\n", f"        enabled: {enabled_str}\n"]

    tools_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("tools:") and len(line) - len(line.lstrip()) == 0:
            tools_idx = i
            break

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

    with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)
    return True


# ── top-level section enabled ─────────────────────────────────────────────────

def _get_top_level_enabled(section: str) -> bool | None:
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


# ── named YAML list entries ───────────────────────────────────────────────────

def _set_yaml_enabled(filepath: str, name: str, enabled: bool) -> bool:
    """Toggle the `enabled` field for a named entry in a YAML list file."""
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


def _delete_yaml_entry(filepath: str, name: str) -> tuple[bool, str]:
    """Remove a named list entry from a YAML file."""
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


# ── cloud provider ────────────────────────────────────────────────────────────

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


# ── skills ────────────────────────────────────────────────────────────────────

def _set_skill_file_enabled(name: str, enabled: bool) -> bool:
    """Toggle enabled in an individual YAML skill file."""
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    candidates = list(dict.fromkeys([safe_name, name]))
    for prefix in ("", "auto_"):
        for cname in candidates:
            filepath = os.path.join(_SKILLS_DIR, f"{prefix}{cname}.yaml")
            if os.path.exists(filepath):
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    for i, line in enumerate(lines):
                        if line.strip().startswith("enabled:") and len(line) - len(line.lstrip()) == 0:
                            lines[i] = f'enabled: {"true" if enabled else "false"}\n'
                            with open(filepath, "w", encoding="utf-8") as f:
                                f.writelines(lines)
                            return True
                    for i, line in enumerate(lines):
                        if line.strip().startswith("name:"):
                            lines.insert(i + 1, f'enabled: {"true" if enabled else "false"}\n')
                            with open(filepath, "w", encoding="utf-8") as f:
                                f.writelines(lines)
                            return True
                    lines.insert(0, f'enabled: {"true" if enabled else "false"}\n')
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.writelines(lines)
                    return True
                except Exception:
                    pass
    return False


def _set_skill_md_enabled(name: str, enabled: bool) -> bool:
    """Toggle enabled in a SKILL.md subdirectory skill's frontmatter."""
    import re as _re
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    skill_md = os.path.join(_SKILLS_DIR, safe_name, "SKILL.md")
    if not os.path.exists(skill_md):
        return False
    try:
        with open(skill_md, "r", encoding="utf-8") as f:
            content = f.read()

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
