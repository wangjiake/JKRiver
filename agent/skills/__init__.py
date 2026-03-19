
import os
import re
import yaml


def _parse_skill_md(content: str) -> dict | None:
    """Parse SkillHub/Anthropic SKILL.md format (YAML frontmatter + markdown body)."""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)", content, re.DOTALL)
    if not match:
        return None
    try:
        frontmatter = yaml.safe_load(match.group(1)) or {}
    except Exception:
        return None
    name = frontmatter.get("name", "")
    if not name:
        return None
    instruction = match.group(2).strip()
    description = frontmatter.get("description", "")
    # Use explicit keywords from frontmatter, or auto-generate from name
    if frontmatter.get("keywords"):
        keywords = list(frontmatter["keywords"])
    else:
        keywords = list({
            name,
            name.replace("-", " ").replace("_", " "),
        })
    result = {
        "name": name,
        "description": description,
        "instruction": instruction,
        "trigger": {"type": "keyword", "keywords": keywords},
        "enabled": frontmatter.get("enabled", True),
    }
    # Support steps and variables defined in frontmatter (JKRiver extension)
    if frontmatter.get("steps"):
        result["steps"] = frontmatter["steps"]
        result["instruction"] = ""  # steps take over, instruction becomes unused
    if frontmatter.get("variables"):
        result["variables"] = frontmatter["variables"]
    return result


class Skill:

    def __init__(self, data: dict):
        self.name: str = data.get("name", "")
        self.description: str = data.get("description", "")
        self.enabled: bool = data.get("enabled", True)
        self.trigger: dict = data.get("trigger", {})
        self.steps: list[dict] = data.get("steps", [])
        self.variables: dict = data.get("variables", {})
        self.instruction: str = data.get("instruction", "")
        self._source: str = "bundled"  # "bundled", filename, or "skillhub:<name>"

    @property
    def trigger_type(self) -> str:
        return self.trigger.get("type", "keyword")

    @property
    def keywords(self) -> list[str]:
        return self.trigger.get("keywords", [])

    @property
    def cron(self) -> str:
        return self.trigger.get("cron", "")

    @property
    def is_simple(self) -> bool:
        return bool(self.instruction) and not self.steps

    def __repr__(self):
        return f"<Skill '{self.name}' type={self.trigger_type} enabled={self.enabled}>"

class SkillRegistry:

    def __init__(self, config: dict):
        self.config = config
        self._skills: list[Skill] = []
        self._discover()

    def _discover(self):
        skills_dir = os.path.join(os.path.dirname(__file__))
        if not os.path.isdir(skills_dir):
            return

        loaded_names: set[str] = set()

        # 1. Individual *.yaml files take priority (user-installed skills override bundled)
        for filename in sorted(os.listdir(skills_dir)):
            if not filename.endswith((".yaml", ".yml")):
                continue
            if filename.startswith("skills_"):
                continue
            filepath = os.path.join(skills_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if not data or not isinstance(data, dict) or not data.get("name"):
                    continue
                skill = Skill(data)
                skill._source = filename
                self._skills.append(skill)
                loaded_names.add(data["name"])
            except Exception:
                pass

        # 2. SKILL.md subdirectories (SkillHub format)
        for entry in sorted(os.listdir(skills_dir)):
            entry_path = os.path.join(skills_dir, entry)
            if not os.path.isdir(entry_path):
                continue
            skill_md = os.path.join(entry_path, "SKILL.md")
            if not os.path.exists(skill_md):
                continue
            try:
                with open(skill_md, "r", encoding="utf-8") as f:
                    raw = f.read()
                data = _parse_skill_md(raw)
                if not data or not data.get("name"):
                    continue
                if data["name"] in loaded_names:
                    continue
                skill = Skill(data)
                skill._source = f"skillhub:{data['name']}"
                self._skills.append(skill)
                loaded_names.add(data["name"])
            except Exception:
                pass

        # 3. Bundled skills_*.yaml (lowest priority — only if not already loaded)
        lang = self.config.get("language", "zh")
        for lang_suffix in [lang, "en", "ja"]:
            bundled_path = os.path.join(skills_dir, f"skills_{lang_suffix}.yaml")
            if not os.path.exists(bundled_path):
                continue
            try:
                with open(bundled_path, "r", encoding="utf-8") as f:
                    bundled = yaml.safe_load(f) or {}
                for item in bundled.get("skills", []):
                    if not isinstance(item, dict) or not item.get("name"):
                        continue
                    if item["name"] in loaded_names:
                        continue
                    skill = Skill(item)
                    skill._source = "bundled"
                    self._skills.append(skill)
                    loaded_names.add(item["name"])
            except Exception:
                pass
            break  # only load one language's bundled file


    def get_keyword_skills(self) -> list[Skill]:
        return [s for s in self._skills if s.trigger_type == "keyword" and s.enabled]

    def get_schedule_skills(self) -> list[Skill]:
        return [s for s in self._skills if s.trigger_type == "schedule" and s.enabled]

    def match_keywords(self, user_input: str) -> list[Skill]:
        if not user_input:
            return []

        input_lower = user_input.lower()
        matched = []
        for skill in self.get_keyword_skills():
            for kw in skill.keywords:
                if kw.lower() in input_lower:
                    matched.append(skill)
                    break
        return matched

    def reload(self):
        self._skills.clear()
        self._discover()

    def list_all(self) -> list[Skill]:
        return list(self._skills)
