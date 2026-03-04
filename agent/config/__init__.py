
import os
import yaml

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "settings.yaml")

def load_config(path: str = None) -> dict:
    path = path or _CONFIG_PATH
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

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

    raw.setdefault("language", "zh")

    return raw
