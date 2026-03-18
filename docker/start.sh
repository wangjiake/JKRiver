#!/bin/bash
set -e

cd /app

echo "[start] Generating settings.yaml..."
python3 docker/gen_settings.py

echo "[start] Waiting for PostgreSQL..."
until python3 - <<'EOF'
import psycopg2, os, sys
try:
    psycopg2.connect(
        dbname=os.environ.get("DB_NAME", "Riverse"),
        user=os.environ.get("DB_USER", "postgres"),
        host=os.environ.get("DB_HOST", "postgres"),
        connect_timeout=3,
    )
    sys.exit(0)
except Exception as e:
    print(f"  not ready: {e}")
    sys.exit(1)
EOF
do
    sleep 2
done
echo "[start] PostgreSQL ready."

echo "[start] Initializing database schema..."
python3 - <<'EOF'
import psycopg2, os

conn = psycopg2.connect(
    dbname=os.environ.get("DB_NAME", "Riverse"),
    user=os.environ.get("DB_USER", "postgres"),
    host=os.environ.get("DB_HOST", "postgres"),
)
conn.autocommit = True

with open("agent/schema.sql", "r") as f:
    schema_sql = f.read()

with conn.cursor() as cur:
    cur.execute(schema_sql)

conn.close()
print("[start] Schema applied.")
EOF

echo "[start] Running migrations..."
python3 -c "from agent.storage.migrations import migrate; migrate()"
echo "[start] Migrations done."

echo "[start] Starting FastAPI on :8400..."
uvicorn agent.api:app --host 0.0.0.0 --port 8400 &

echo "[start] Starting Flask UI on :1234..."
python3 web.py --host 0.0.0.0 --port 1234 &

# Start bots if enabled in settings.yaml
python3 - <<'EOF'
import yaml, subprocess, sys
with open("settings.yaml") as f:
    cfg = yaml.safe_load(f)
if cfg.get("telegram", {}).get("enabled") and cfg.get("telegram", {}).get("bot_token"):
    print("[start] Starting Telegram Bot...")
    subprocess.Popen([sys.executable, "-m", "agent.telegram_bot"])
if cfg.get("discord", {}).get("enabled") and cfg.get("discord", {}).get("bot_token"):
    print("[start] Starting Discord Bot...")
    subprocess.Popen([sys.executable, "-m", "agent.discord_bot"])
EOF

echo "[start] All services running. Ctrl+C to stop."
wait -n
exit $?
