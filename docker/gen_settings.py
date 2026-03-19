"""Generate settings.yaml from environment variables for Docker deployment.
Only runs if settings.yaml does not already exist (mounted volume takes priority).
"""
import os
import shutil
import yaml

SETTINGS_PATH = "settings.yaml"
DEFAULT_PATH = "settings.yaml.default"

if os.path.exists(SETTINGS_PATH):
    print("[gen_settings] settings.yaml already exists, skipping")
    exit(0)

if not os.path.exists(DEFAULT_PATH):
    print("[gen_settings] ERROR: settings.yaml.default not found")
    exit(1)

with open(DEFAULT_PATH, "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

def env(key, default=None):
    return os.environ.get(key, default)

# Language / timezone
if env("LANGUAGE"):
    cfg["language"] = env("LANGUAGE")
if env("TIMEZONE"):
    cfg["timezone"] = env("TIMEZONE")

# Database
cfg.setdefault("database", {})
cfg["database"]["name"] = env("DB_NAME", "Riverse")
cfg["database"]["user"] = env("DB_USER", "postgres")
cfg["database"]["host"] = env("DB_HOST", "postgres")
if env("DB_PASSWORD"):
    cfg["database"]["password"] = env("DB_PASSWORD")

# LLM provider
if env("LLM_PROVIDER"):
    cfg["llm_provider"] = env("LLM_PROVIDER")

# Remote API (openai-compatible)
cfg.setdefault("openai", {})
if env("OPENAI_API_KEY"):
    cfg["openai"]["api_key"] = env("OPENAI_API_KEY")
if env("OPENAI_API_BASE"):
    cfg["openai"]["api_base"] = env("OPENAI_API_BASE")
if env("OPENAI_MODEL"):
    cfg["openai"]["model"] = env("OPENAI_MODEL")

# Local Ollama
cfg.setdefault("local", {})
if env("OLLAMA_MODEL"):
    cfg["local"]["model"] = env("OLLAMA_MODEL")
if env("OLLAMA_API_BASE"):
    cfg["local"]["api_base"] = env("OLLAMA_API_BASE")

# Public mode / access token
import secrets as _secrets
_public_mode = env("PUBLIC_MODE", "false").lower() in ("1", "true", "yes")
cfg.setdefault("public_mode", {})
cfg["public_mode"]["enabled"] = _public_mode
if _public_mode:
    _token = env("ACCESS_TOKEN") or _secrets.token_urlsafe(32)
    cfg["public_mode"]["access_token"] = _token
    if not env("ACCESS_TOKEN"):
        print("=" * 60)
        print("[gen_settings] Access token generated (save this!):")
        print(f"  ACCESS_TOKEN={_token}")
        print("=" * 60)

# Telegram
if env("TELEGRAM_BOT_TOKEN"):
    cfg.setdefault("telegram", {})
    cfg["telegram"]["enabled"] = True
    cfg["telegram"]["bot_token"] = env("TELEGRAM_BOT_TOKEN")
    raw_ids = env("TELEGRAM_ALLOWED_USERS", "")
    if raw_ids.strip():
        try:
            cfg["telegram"]["allowed_user_ids"] = [
                int(x.strip()) for x in raw_ids.split(",") if x.strip()
            ]
        except ValueError:
            pass

# Discord
if env("DISCORD_BOT_TOKEN"):
    cfg.setdefault("discord", {})
    cfg["discord"]["enabled"] = True
    cfg["discord"]["bot_token"] = env("DISCORD_BOT_TOKEN")

# Sleep mode
if env("SLEEP_MODE"):
    cfg.setdefault("sleep_mode", {})
    cfg["sleep_mode"]["mode"] = env("SLEEP_MODE")
if env("SLEEP_CRON_HOUR"):
    cfg.setdefault("sleep_mode", {})
    try:
        cfg["sleep_mode"]["cron_hour"] = int(env("SLEEP_CRON_HOUR"))
    except ValueError:
        pass

with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
    yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

print("[gen_settings] settings.yaml generated from environment variables")
