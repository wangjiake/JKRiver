
import logging
import os
import shutil
import yaml

logger = logging.getLogger(__name__)

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "settings.yaml")
_DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "settings.yaml.default")

def load_config(path: str = None) -> dict:
    path = path or _CONFIG_PATH
    if not os.path.exists(path) and os.path.exists(_DEFAULT_PATH):
        shutil.copy2(_DEFAULT_PATH, path)
    with open(path, "r", encoding="utf-8") as f:
        try:
            raw = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Failed to parse {path}: {e}") from e

    provider = raw.get("llm_provider", "local")
    llm_config = raw.get(provider, raw.get("local", {}))
    raw["llm"] = llm_config

    cloud_cfg = raw.get("cloud_llm", {})
    if cloud_cfg.get("enabled") and cloud_cfg.get("providers"):
        providers = sorted(cloud_cfg["providers"], key=lambda p: p.get("priority", 99))
        raw["cloud_llm_configs"] = [
            {
                "name": p.get("name", p["model"]),
                "model": p["model"],
                "api_base": p["api_base"],
                "api_key": p.get("api_key", ""),
                "temperature": p.get("temperature", 0.7),
                "max_tokens": p.get("max_tokens", 2048),
                "search": p.get("search", False),
            }
            for p in providers
        ]
    else:
        raw["cloud_llm_configs"] = []

    if "tools" not in raw:
        raw["tools"] = {"enabled": True}

    if "embedding" not in raw:
        raw["embedding"] = {"enabled": False}
    emb = raw["embedding"]
    emb.setdefault("model", "")
    emb.setdefault("api_base", "")
    emb.setdefault("search", {})
    emb["search"].setdefault("top_k", 5)
    emb["search"].setdefault("min_score", 0.40)
    emb.setdefault("clustering", {})
    emb["clustering"].setdefault("enabled", False)
    emb["clustering"].setdefault("show_themes", False)

    if "skills" not in raw:
        raw["skills"] = {"enabled": True}

    raw.setdefault("language", "en")

    _validate_config(raw)

    return raw


def _validate_config(raw: dict):
    db = raw.get("database", {})
    if not db.get("name"):
        raise ValueError("database.name must not be empty")
    if not db.get("user"):
        raise ValueError("database.user must not be empty")

    lang = raw.get("language", "")
    if lang not in ("zh", "en", "ja"):
        logger.warning("Unsupported language '%s', defaulting to 'en'", lang)
        raw["language"] = "en"

    provider = raw.get("llm_provider", "")
    if provider and provider not in ("openai", "local"):
        logger.warning("Unknown llm_provider '%s'", provider)

    llm = raw.get("llm", {})
    temp = llm.get("temperature")
    if temp is not None and not (0 <= temp <= 2):
        logger.warning("temperature %.2f outside [0, 2]", temp)

    max_tokens = llm.get("max_tokens")
    if max_tokens is not None and max_tokens <= 0:
        logger.warning("max_tokens %d is not positive", max_tokens)

    if provider == "openai" and not llm.get("api_key"):
        logger.warning("llm_provider is 'openai' but no api_key configured")

    tg = raw.get("telegram", {})
    if tg.get("enabled") and not tg.get("token"):
        logger.warning("telegram.enabled is true but no token configured")

    dc = raw.get("discord", {})
    if dc.get("enabled") and not dc.get("token"):
        logger.warning("discord.enabled is true but no token configured")
