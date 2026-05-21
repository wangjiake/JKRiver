import json
from datetime import datetime, timedelta
from decimal import Decimal
from psycopg2.extras import RealDictCursor
from agent.utils.time_context import get_now
from ._db import get_db_connection

_health_tables_ensured = False

def _ensure_health_tables():
    global _health_tables_ensured
    if _health_tables_ensured:
        return
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS withings_tokens (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL UNIQUE,
                    access_token TEXT NOT NULL,
                    refresh_token TEXT NOT NULL,
                    expires_at TIMESTAMPTZ NOT NULL,
                    scope TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS withings_measures (
                    id SERIAL PRIMARY KEY,
                    withings_grpid BIGINT NOT NULL,
                    measured_at TIMESTAMPTZ NOT NULL,
                    measure_type INTEGER NOT NULL,
                    value NUMERIC(12, 4) NOT NULL,
                    unit TEXT,
                    source INTEGER,
                    metadata JSONB DEFAULT '{}',
                    synced_at TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE(withings_grpid, measure_type)
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_wm_type_date
                    ON withings_measures(measure_type, measured_at DESC)
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS withings_activity (
                    id SERIAL PRIMARY KEY,
                    activity_date DATE NOT NULL UNIQUE,
                    steps INTEGER,
                    distance NUMERIC(10,2),
                    calories NUMERIC(10,2),
                    active_calories NUMERIC(10,2),
                    soft_activity_duration INTEGER,
                    moderate_activity_duration INTEGER,
                    intense_activity_duration INTEGER,
                    metadata JSONB DEFAULT '{}',
                    synced_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_wa_date
                    ON withings_activity(activity_date DESC)
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS withings_sleep (
                    id SERIAL PRIMARY KEY,
                    sleep_date DATE NOT NULL UNIQUE,
                    start_time TIMESTAMPTZ,
                    end_time TIMESTAMPTZ,
                    duration_seconds INTEGER,
                    deep_sleep_seconds INTEGER,
                    light_sleep_seconds INTEGER,
                    rem_sleep_seconds INTEGER,
                    awake_seconds INTEGER,
                    wakeup_count INTEGER,
                    sleep_score INTEGER,
                    hr_average INTEGER,
                    hr_min INTEGER,
                    rr_average INTEGER,
                    metadata JSONB DEFAULT '{}',
                    synced_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_ws_date
                    ON withings_sleep(sleep_date DESC)
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS withings_sync_log (
                    id SERIAL PRIMARY KEY,
                    data_type TEXT NOT NULL,
                    last_sync_at TIMESTAMPTZ NOT NULL,
                    records_synced INTEGER DEFAULT 0,
                    error TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_wsl_type
                    ON withings_sync_log(data_type, created_at DESC)
            """)
        conn.commit()
        _health_tables_ensured = True
    finally:
        conn.close()

def save_withings_tokens(user_id: str, access_token: str,
                         refresh_token: str, expires_in: int,
                         scope: str = ""):
    _ensure_health_tables()
    now = get_now()
    expires_at = now + timedelta(seconds=expires_in)
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO withings_tokens "
                "(user_id, access_token, refresh_token, expires_at, scope, "
                " created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (user_id) DO UPDATE SET "
                "access_token = EXCLUDED.access_token, "
                "refresh_token = EXCLUDED.refresh_token, "
                "expires_at = EXCLUDED.expires_at, "
                "scope = EXCLUDED.scope, "
                "updated_at = EXCLUDED.updated_at",
                (user_id, access_token, refresh_token, expires_at,
                 scope, now, now),
            )
        conn.commit()
    finally:
        conn.close()

def load_withings_tokens(owner_id: int | None = None) -> dict | None:
    _ensure_health_tables()
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if owner_id is not None:
                cur.execute(
                    "SELECT user_id, access_token, refresh_token, expires_at, scope "
                    "FROM withings_tokens WHERE owner_id = %s "
                    "ORDER BY updated_at DESC LIMIT 1",
                    (owner_id,),
                )
            else:
                cur.execute(
                    "SELECT user_id, access_token, refresh_token, expires_at, scope "
                    "FROM withings_tokens ORDER BY updated_at DESC LIMIT 1"
                )
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()

def save_withings_measure(grpid: int, measured_at, measure_type: int,
                          value: float, unit: str = None,
                          source: int = None):
    _ensure_health_tables()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO withings_measures "
                "(withings_grpid, measured_at, measure_type, value, unit, "
                " source, synced_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (withings_grpid, measure_type) DO NOTHING",
                (grpid, measured_at, measure_type, value, unit,
                 source, get_now()),
            )
        conn.commit()
    finally:
        conn.close()

def load_withings_measures(measure_type: int = None,
                           days: int = 90,
                           owner_id: int | None = None) -> list[dict]:
    _ensure_health_tables()
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            conditions = []
            params = []
            if owner_id is not None:
                conditions.append("owner_id = %s")
                params.append(owner_id)
            if measure_type is not None:
                conditions.append("measure_type = %s")
                params.append(measure_type)
            if days:
                conditions.append("measured_at >= %s")
                params.append(get_now() - timedelta(days=days))
            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            cur.execute(
                f"SELECT id, withings_grpid, measured_at, measure_type, "
                f"value, unit, source, synced_at "
                f"FROM withings_measures {where} "
                f"ORDER BY measured_at DESC",
                params,
            )
            return list(cur.fetchall())
    finally:
        conn.close()

def save_withings_activity(activity_date, steps=None, distance=None,
                           calories=None, active_calories=None,
                           soft_duration=None, moderate_duration=None,
                           intense_duration=None, metadata=None):
    _ensure_health_tables()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO withings_activity "
                "(activity_date, steps, distance, calories, active_calories, "
                " soft_activity_duration, moderate_activity_duration, "
                " intense_activity_duration, metadata, synced_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (activity_date) DO UPDATE SET "
                "steps = EXCLUDED.steps, distance = EXCLUDED.distance, "
                "calories = EXCLUDED.calories, "
                "active_calories = EXCLUDED.active_calories, "
                "soft_activity_duration = EXCLUDED.soft_activity_duration, "
                "moderate_activity_duration = EXCLUDED.moderate_activity_duration, "
                "intense_activity_duration = EXCLUDED.intense_activity_duration, "
                "metadata = EXCLUDED.metadata, synced_at = EXCLUDED.synced_at",
                (activity_date, steps, distance, calories, active_calories,
                 soft_duration, moderate_duration, intense_duration,
                 json.dumps(metadata or {}, ensure_ascii=False), get_now()),
            )
        conn.commit()
    finally:
        conn.close()

def load_withings_activity(days: int = 90, owner_id: int | None = None) -> list[dict]:
    _ensure_health_tables()
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            conditions = []
            params = []
            if owner_id is not None:
                conditions.append("owner_id = %s")
                params.append(owner_id)
            if days:
                conditions.append("activity_date >= %s")
                params.append((get_now() - timedelta(days=days)).date())
            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            cur.execute(
                f"SELECT id, activity_date, steps, distance, calories, "
                f"active_calories, soft_activity_duration, "
                f"moderate_activity_duration, intense_activity_duration, "
                f"synced_at "
                f"FROM withings_activity {where} "
                f"ORDER BY activity_date DESC",
                params,
            )
            return list(cur.fetchall())
    finally:
        conn.close()

def save_withings_sleep(sleep_date, start_time=None, end_time=None,
                        duration_seconds=None,
                        deep_sleep_seconds=None, light_sleep_seconds=None,
                        rem_sleep_seconds=None, awake_seconds=None,
                        wakeup_count=None, sleep_score=None,
                        hr_average=None, hr_min=None, rr_average=None,
                        metadata=None):
    _ensure_health_tables()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO withings_sleep "
                "(sleep_date, start_time, end_time, duration_seconds, "
                " deep_sleep_seconds, light_sleep_seconds, rem_sleep_seconds, "
                " awake_seconds, wakeup_count, sleep_score, "
                " hr_average, hr_min, rr_average, metadata, synced_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (sleep_date) DO UPDATE SET "
                "start_time = EXCLUDED.start_time, end_time = EXCLUDED.end_time, "
                "duration_seconds = EXCLUDED.duration_seconds, "
                "deep_sleep_seconds = EXCLUDED.deep_sleep_seconds, "
                "light_sleep_seconds = EXCLUDED.light_sleep_seconds, "
                "rem_sleep_seconds = EXCLUDED.rem_sleep_seconds, "
                "awake_seconds = EXCLUDED.awake_seconds, "
                "wakeup_count = EXCLUDED.wakeup_count, "
                "sleep_score = EXCLUDED.sleep_score, "
                "hr_average = EXCLUDED.hr_average, hr_min = EXCLUDED.hr_min, "
                "rr_average = EXCLUDED.rr_average, "
                "metadata = EXCLUDED.metadata, synced_at = EXCLUDED.synced_at",
                (sleep_date, start_time, end_time, duration_seconds,
                 deep_sleep_seconds, light_sleep_seconds, rem_sleep_seconds,
                 awake_seconds, wakeup_count, sleep_score,
                 hr_average, hr_min, rr_average,
                 json.dumps(metadata or {}, ensure_ascii=False), get_now()),
            )
        conn.commit()
    finally:
        conn.close()

def load_withings_sleep(days: int = 90, owner_id: int | None = None) -> list[dict]:
    _ensure_health_tables()
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            conditions = []
            params = []
            if owner_id is not None:
                conditions.append("owner_id = %s")
                params.append(owner_id)
            if days:
                conditions.append("sleep_date >= %s")
                params.append((get_now() - timedelta(days=days)).date())
            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            cur.execute(
                f"SELECT id, sleep_date, start_time, end_time, "
                f"duration_seconds, deep_sleep_seconds, light_sleep_seconds, "
                f"rem_sleep_seconds, awake_seconds, wakeup_count, "
                f"sleep_score, hr_average, hr_min, rr_average, synced_at "
                f"FROM withings_sleep {where} "
                f"ORDER BY sleep_date DESC",
                params,
            )
            return list(cur.fetchall())
    finally:
        conn.close()

def get_last_sync_time(data_type: str):
    _ensure_health_tables()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT last_sync_at FROM withings_sync_log "
                "WHERE data_type = %s AND error IS NULL "
                "ORDER BY created_at DESC LIMIT 1",
                (data_type,),
            )
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        conn.close()

def save_sync_log(data_type: str, records_synced: int = 0,
                  error: str = None):
    _ensure_health_tables()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO withings_sync_log "
                "(data_type, last_sync_at, records_synced, error) "
                "VALUES (%s, %s, %s, %s)",
                (data_type, get_now(), records_synced, error),
            )
        conn.commit()
    finally:
        conn.close()

def get_health_overview(owner_id: int | None = None) -> dict:
    _ensure_health_tables()
    owner_clause = " WHERE owner_id = %s" if owner_id is not None else ""
    owner_clause_and = " AND owner_id = %s" if owner_id is not None else ""
    owner_param: tuple = (owner_id,) if owner_id is not None else ()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM withings_measures{owner_clause}", owner_param)
            total_measures = cur.fetchone()[0]

            cur.execute(
                f"SELECT value FROM withings_measures "
                f"WHERE measure_type = 1{owner_clause_and} "
                f"ORDER BY measured_at DESC LIMIT 1",
                owner_param,
            )
            row = cur.fetchone()
            latest_weight = float(row[0]) if row else None

            cur.execute(f"SELECT COUNT(*) FROM withings_activity{owner_clause}", owner_param)
            activity_days = cur.fetchone()[0]

            cur.execute(f"SELECT COUNT(*) FROM withings_sleep{owner_clause}", owner_param)
            sleep_days = cur.fetchone()[0]

            cur.execute(
                f"SELECT COALESCE(AVG(steps), 0) FROM withings_activity "
                f"WHERE activity_date >= %s{owner_clause_and}",
                ((get_now() - timedelta(days=30)).date(), *owner_param),
            )
            avg_steps_30d = round(float(cur.fetchone()[0]))

            cur.execute(
                f"SELECT COALESCE(AVG(sleep_score), 0) FROM withings_sleep "
                f"WHERE sleep_date >= %s AND sleep_score IS NOT NULL{owner_clause_and}",
                ((get_now() - timedelta(days=30)).date(), *owner_param),
            )
            avg_sleep_score_30d = round(float(cur.fetchone()[0]))

            cur.execute(
                f"SELECT expires_at FROM withings_tokens"
                f"{owner_clause} "
                f"ORDER BY updated_at DESC LIMIT 1",
                owner_param,
            )
            token_row = cur.fetchone()
            token_connected = token_row is not None
            token_expires_at = token_row[0].isoformat() if token_row else None

            return {
                "total_measures": total_measures,
                "latest_weight": latest_weight,
                "activity_days": activity_days,
                "sleep_days": sleep_days,
                "avg_steps_30d": avg_steps_30d,
                "avg_sleep_score_30d": avg_sleep_score_30d,
                "token_connected": token_connected,
                "token_expires_at": token_expires_at,
            }
    finally:
        conn.close()
