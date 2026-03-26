"""Local development startup script — starts all services based on settings.yaml."""
import subprocess
import sys
import shutil
import yaml

with open("settings.yaml") as f:
    cfg = yaml.safe_load(f)

# Use uvicorn from PATH if current Python doesn't have it as a module
def _uvicorn_cmd():
    try:
        import uvicorn  # noqa: F401
        return [sys.executable, "-m", "uvicorn"]
    except ImportError:
        uv = shutil.which("uvicorn")
        if uv:
            return [uv]
        raise RuntimeError("uvicorn not found. Install it: pip install uvicorn")

procs_def = [
    ("FastAPI  :8400", _uvicorn_cmd() + ["agent.api:app", "--host", "127.0.0.1", "--port", "8400"]),
    ("Flask    :1234", [sys.executable, "web.py", "--port", "1234"]),
]

if cfg.get("telegram", {}).get("enabled") and cfg.get("telegram", {}).get("bot_token"):
    procs_def.append(("Telegram Bot", [sys.executable, "-m", "agent.telegram_bot"]))

if cfg.get("discord", {}).get("enabled") and cfg.get("discord", {}).get("bot_token"):
    procs_def.append(("Discord Bot", [sys.executable, "-m", "agent.discord_bot"]))

children = []
for name, cmd in procs_def:
    print(f"[start] {name}")
    children.append(subprocess.Popen(cmd))

print(f"[start] {len(children)} services running. Ctrl+C to stop.")
try:
    for c in children:
        c.wait()
except KeyboardInterrupt:
    print("\n[stop] Stopping all services...")
    for c in children:
        c.terminate()
