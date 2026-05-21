
import os
import json
import logging
from datetime import datetime, date
from decimal import Decimal

from agent.config import load_config as _load_config
from agent.storage import get_db_connection

_config = _load_config()
_db_cfg = _config.get("database", {})
DB_NAME = _db_cfg.get("name", "Riverse")
DB_USER = _db_cfg.get("user", "postgres")
IMG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "img")


def get_conn():
    return get_db_connection()


def _serialize(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    return str(obj)


def _log_review(conn, target_table, target_id, action, old_value, new_value, note, owner_id: int = 1):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO review_log (owner_id, target_table, target_id, action, old_value, new_value, note) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (owner_id, target_table, target_id, action,
             json.dumps(old_value, default=_serialize, ensure_ascii=False) if old_value else None,
             json.dumps(new_value, default=_serialize, ensure_ascii=False) if new_value else None,
             note),
        )


def load_config():
    return _load_config()
