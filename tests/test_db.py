"""Integration test: verify database connection and schema.

Requires a running PostgreSQL with the JKRiver schema created.

Usage:
    python -m pytest tests/test_db.py -v
    python tests/test_db.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.storage._db import get_db_connection


EXPECTED_TABLES = [
    "raw_conversations",
    "conversation_turns",
    "observations",
    "user_profile",
    "event_log",
    "relationships",
    "strategies",
    "user_model",
    "trajectory_summary",
    "fact_edges",
    "memory_snapshot",
    "memory_embeddings",
    "memory_clusters",
    "proactive_log",
]


def _get_existing_tables():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            return {r[0] for r in cur.fetchall()}
    finally:
        conn.close()


def test_db_connection():
    conn = get_db_connection()
    assert conn is not None
    cur = conn.cursor()
    cur.execute("SELECT 1")
    assert cur.fetchone()[0] == 1
    conn.close()


def test_required_tables_exist():
    existing = _get_existing_tables()
    missing = [t for t in EXPECTED_TABLES if t not in existing]
    assert not missing, f"Missing tables: {missing}"


def test_table_row_counts():
    """Smoke test: SELECT count(*) should work on all expected tables."""
    conn = get_db_connection()
    existing = _get_existing_tables()
    try:
        with conn.cursor() as cur:
            for table in EXPECTED_TABLES:
                if table not in existing:
                    continue
                cur.execute(f"SELECT count(*) FROM {table}")
                count = cur.fetchone()[0]
                assert count >= 0, f"{table} count returned negative"
    finally:
        conn.close()


def test_user_profile_schema():
    """Verify user_profile has key columns."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'user_profile'
                ORDER BY ordinal_position
            """)
            cols = {r[0] for r in cur.fetchall()}
            for expected in ["id", "category", "subject", "value", "layer",
                             "mention_count", "superseded_by"]:
                assert expected in cols, f"user_profile missing column: {expected}"
    finally:
        conn.close()


def test_raw_conversations_schema():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'raw_conversations'
                ORDER BY ordinal_position
            """)
            cols = {r[0] for r in cur.fetchall()}
            for expected in ["id", "session_id", "user_input", "assistant_reply", "processed"]:
                assert expected in cols, f"raw_conversations missing column: {expected}"
    finally:
        conn.close()


# ── standalone runner ──

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for fn in tests:
        name = fn.__name__
        try:
            fn()
            print(f"  PASS  {name}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {name}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
