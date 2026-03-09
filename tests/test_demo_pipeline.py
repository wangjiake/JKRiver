"""Integration test: end-to-end pipeline — feed demo JSON → perceive → save → sleep.

Usage:
    python tests/test_demo_pipeline.py [demo.json path] [--sessions N]
    python tests/test_demo_pipeline.py --clean

Examples:
    # Run all sessions from demo2.json (52 sessions, English)
    python tests/test_demo_pipeline.py

    # Run first 3 sessions only (quick smoke test)
    python tests/test_demo_pipeline.py --sessions 3

    # Run with demo.json (50 sessions, Chinese)
    python tests/test_demo_pipeline.py tests/data/demo.json

    # Clean up all test data from the database
    python tests/test_demo_pipeline.py --clean

Notes:
    - Requires a running PostgreSQL with the JKRiver schema created
    - Requires LLM access (configured in settings.yaml)
    - Will INSERT data into the database — use --clean to remove test data afterwards
    - Sleep may need multiple runs to process all conversations
"""

import argparse
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.config import load_config
from agent.cognition import CognitionEngine
from agent.storage import save_raw_conversation, save_conversation_turn
from agent.storage._db import get_db_connection

logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s: %(message)s")


TABLES_TO_CLEAN = [
    "trajectory_summary", "user_model", "strategies", "relationships",
    "event_log", "user_profile", "observations", "fact_edges",
    "memory_snapshot", "memory_embeddings", "memory_clusters",
    "conversation_turns", "raw_conversations", "proactive_log",
]


def clean_db():
    """Truncate all data tables, preserving schema."""
    conn = get_db_connection()
    cleaned = []
    skipped = []
    try:
        with conn.cursor() as cur:
            for table in TABLES_TO_CLEAN:
                try:
                    cur.execute(f"TRUNCATE TABLE {table} CASCADE")
                    conn.commit()
                    cleaned.append(table)
                except Exception:
                    conn.rollback()
                    skipped.append(table)
    finally:
        conn.close()

    print(f"Cleaned {len(cleaned)} tables: {', '.join(cleaned)}")
    if skipped:
        print(f"Skipped {len(skipped)} (not found): {', '.join(skipped)}")
    print("Database is clean.")


def count_table(table):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT count(*) FROM {table}")
            return cur.fetchone()[0]
    finally:
        conn.close()


def run_pipeline(demo_path, max_sessions=None):
    with open(demo_path, "r", encoding="utf-8") as f:
        sessions = json.load(f)

    if max_sessions:
        sessions = sessions[:max_sessions]

    config = load_config()
    engine = CognitionEngine(config)

    print(f"LLM: {config['llm'].get('model', '?')}")
    print(f"Sessions: {len(sessions)}")

    total_turns = sum(len(s["messages"]) for s in sessions)
    turn_idx = 0
    perceive_ok = 0
    perceive_fail = 0

    for si, session in enumerate(sessions, 1):
        date_str = session.get("date", "2025-01-01")
        session_time = datetime.strptime(date_str, "%Y-%m-%d").replace(
            hour=20, minute=0, tzinfo=timezone.utc)
        session_id = f"test-{str(uuid.uuid4())[:8]}"
        messages = session["messages"]

        print(f"\n{'='*60}")
        print(f"Session {si}/{len(sessions)}: {date_str} ({len(messages)} turns)")
        print(f"{'='*60}")

        for mi, msg in enumerate(messages):
            turn_idx += 1
            user_input = msg["user"]
            assistant_reply = msg["assistant"]
            ts = session_time + timedelta(minutes=mi * 5)

            print(f"  [{turn_idx}/{total_turns}] {user_input[:50]}{'...' if len(user_input)>50 else ''}")

            try:
                perception = engine.perceive(user_input)
                perceive_ok += 1
            except Exception as e:
                print(f"    perceive error: {e}")
                perception = {
                    "intent": user_input,
                    "category": "personal",
                    "need_memory": True,
                    "memory_type": "personal",
                    "ai_summary": user_input,
                    "perception_at": ts,
                }
                perceive_fail += 1
            print(f"    category={perception.get('category')} intent={perception.get('intent','')[:40]}")

            engine.session_memory.add_turn(user_input[:100], assistant_reply[:100])

            save_raw_conversation(
                session_id=session_id,
                session_created_at=session_time,
                user_input=user_input,
                user_input_at=ts,
                assistant_reply=assistant_reply,
                assistant_reply_at=ts,
            )

            save_conversation_turn({
                "session_id": session_id,
                "session_created_at": session_time,
                "user_input": user_input,
                "user_input_at": ts,
                "assistant_reply": assistant_reply,
                "assistant_reply_at": ts,
                "intent": perception.get("intent", ""),
                "need_memory": perception.get("need_memory", True),
                "memory_type": perception.get("memory_type", "personal"),
                "ai_summary": perception.get("ai_summary", user_input),
                "perception_at": perception.get("perception_at", ts),
                "memories_used": [],
                "memories_used_at": None,
                "completed_at": ts,
                "has_new_info": perception.get("category") == "personal",
            })

    return total_turns, perceive_ok, perceive_fail


def run_sleep():
    """Run sleep processing. May need multiple calls to process all data."""
    from agent.sleep.orchestration import run

    max_rounds = 5
    for i in range(max_rounds):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM raw_conversations WHERE processed = FALSE")
                unprocessed = cur.fetchone()[0]
        finally:
            conn.close()

        if unprocessed == 0:
            break

        print(f"\nSleep round {i+1}: {unprocessed} unprocessed conversations...")
        run()

    return unprocessed


def print_results():
    tables = [
        "raw_conversations", "conversation_turns", "observations",
        "user_profile", "event_log", "relationships", "strategies",
        "user_model", "trajectory_summary",
    ]
    print(f"\n{'='*60}")
    print("Results:")
    print(f"{'='*60}")
    for t in tables:
        print(f"  {t}: {count_table(t)}")

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM raw_conversations WHERE processed = FALSE")
            unprocessed = cur.fetchone()[0]
            print(f"  unprocessed: {unprocessed}")

            cur.execute("SELECT category, subject, value, layer FROM user_profile WHERE superseded_by IS NULL ORDER BY layer DESC, category")
            rows = cur.fetchall()
            if rows:
                print(f"\nProfile ({len(rows)} active entries):")
                for r in rows:
                    print(f"  [{r[3]}] {r[0]} / {r[1]}: {r[2]}")

            cur.execute("SELECT name, relation FROM relationships")
            rows = cur.fetchall()
            if rows:
                print(f"\nRelationships ({len(rows)}):")
                for r in rows:
                    print(f"  {r[0]} ({r[1]})")

            cur.execute("SELECT life_phase FROM trajectory_summary ORDER BY created_at")
            rows = cur.fetchall()
            if rows:
                print(f"\nTrajectory phases: {[r[0] for r in rows]}")
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="JKRiver end-to-end pipeline test")
    default_demo = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "demo2.json")
    parser.add_argument("demo_path", nargs="?", default=default_demo,
                        help="Path to demo JSON file (default: tests/data/demo2.json)")
    parser.add_argument("--sessions", type=int, default=None,
                        help="Max sessions to process (default: all)")
    parser.add_argument("--skip-sleep", action="store_true",
                        help="Skip sleep processing (only run perceive + save)")
    parser.add_argument("--clean", action="store_true",
                        help="Clean all test data from database and exit")
    args = parser.parse_args()

    if args.clean:
        clean_db()
        return

    print(f"Demo file: {args.demo_path}")
    total, ok, fail = run_pipeline(args.demo_path, args.sessions)
    print(f"\nPerceive: {ok}/{total} ok, {fail} failed")

    if not args.skip_sleep:
        print(f"\n{'='*60}")
        print("Running sleep processing...")
        print(f"{'='*60}")
        remaining = run_sleep()
        if remaining:
            print(f"\nWARNING: {remaining} conversations still unprocessed after sleep")

    print_results()
    print("\nDone!")


if __name__ == "__main__":
    main()
