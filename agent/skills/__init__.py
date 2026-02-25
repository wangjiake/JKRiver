
import os
import yaml

class Skill:

    def __init__(self, data: dict):
        self.name: str = data.get("name", "")
        self.description: str = data.get("description", "")
        self.enabled: bool = data.get("enabled", True)
        self.trigger: dict = data.get("trigger", {})
        self.steps: list[dict] = data.get("steps", [])
        self.variables: dict = data.get("variables", {})
        self.instruction: str = data.get("instruction", "")

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

        for filename in sorted(os.listdir(skills_dir)):
            if not filename.endswith((".yaml", ".yml")):
                continue

            filepath = os.path.join(skills_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if not data or not isinstance(data, dict):
                    continue
                if not data.get("name"):
                    continue

                skill = Skill(data)
                if skill.enabled:
                    self._skills.append(skill)
            except Exception as e:
                pass

    def get_keyword_skills(self) -> list[Skill]:
        return [s for s in self._skills if s.trigger_type == "keyword"]

    def get_schedule_skills(self) -> list[Skill]:
        return [s for s in self._skills if s.trigger_type == "schedule"]

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
