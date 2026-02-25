
import os
import re
from functools import lru_cache

_PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")

_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")

@lru_cache(maxsize=None)
def _load_prompts(language: str) -> dict:
    import yaml
    path = os.path.join(_PROMPTS_DIR, f"{language}.yaml")
    if not os.path.isfile(path):
        path = os.path.join(_PROMPTS_DIR, "zh.yaml")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

class _SafeFormatMap(dict):
    def __missing__(self, key):
        return "{" + key + "}"

def get_prompt(key: str, language: str = "zh", **kwargs) -> str:
    prompts = _load_prompts(language)
    text = prompts.get(key)
    if text is None:
        fallback = _load_prompts("zh")
        text = fallback.get(key, "")
    if not isinstance(text, str):
        return text
    if kwargs:
        def _replace(m):
            name = m.group(1)
            if name in kwargs:
                return str(kwargs[name])
            return m.group(0)
        text = _PLACEHOLDER_RE.sub(_replace, text)
    return text

def get_labels(key: str, language: str = "zh") -> dict:
    prompts = _load_prompts(language)
    labels = prompts.get(key)
    if not isinstance(labels, dict):
        fallback = _load_prompts("zh")
        labels = fallback.get(key, {})
    return labels

def get_failure_keywords(language: str = "zh", overrides: list = None) -> list:
    if overrides:
        return overrides
    prompts = _load_prompts(language)
    keywords = prompts.get("meta.failure_keywords")
    if not isinstance(keywords, list):
        fallback = _load_prompts("zh")
        keywords = fallback.get("meta.failure_keywords", [])
    return keywords
