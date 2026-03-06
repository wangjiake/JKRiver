import threading
from contextlib import contextmanager

import psycopg2

from agent.config import load_config

def _load_db_config():
    db = load_config().get("database", {})
    cfg = {
        "dbname": db.get("name", "Riverse"),
        "user": db.get("user", "postgres"),
        "host": db.get("host", "localhost"),
        "options": "-c client_encoding=UTF8",
    }
    if db.get("password"):
        cfg["password"] = db["password"]
    if db.get("port"):
        cfg["port"] = db["port"]
    return cfg

DB_CONFIG = _load_db_config()

_thread_local = threading.local()


class _TransactionProxy:
    """Wraps a real connection; suppresses commit/rollback/close inside a transaction."""
    __slots__ = ("_conn",)

    def __init__(self, conn):
        object.__setattr__(self, "_conn", conn)

    def cursor(self, *args, **kwargs):
        return self._conn.cursor(*args, **kwargs)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass

    def __getattr__(self, name):
        return getattr(self._conn, name)


def get_db_connection():
    shared = getattr(_thread_local, "conn", None)
    if shared is not None:
        return _TransactionProxy(shared)
    return psycopg2.connect(**DB_CONFIG)


@contextmanager
def transaction():
    """Wrap multiple storage calls in a single atomic transaction.

    All get_db_connection() calls inside this block receive a proxy that
    suppresses individual commit/rollback/close.  The real commit (or
    rollback on exception) happens when the block exits.
    """
    conn = psycopg2.connect(**DB_CONFIG)
    _thread_local.conn = conn
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        _thread_local.conn = None
        conn.close()
