
from collections import defaultdict
from datetime import datetime, timezone
from agent.storage import (
    get_db_connection,
    load_full_current_profile,
    add_evidence, close_time_period,
    delete_fact_edges_for,
)


def list_owners_with_unprocessed() -> list[int]:
    """Return distinct owner_ids with processed = FALSE conversations."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT owner_id FROM raw_conversations "
                "WHERE processed = FALSE AND owner_id IS NOT NULL "
                "ORDER BY owner_id"
            )
            return [int(row[0]) for row in cur.fetchall()]
    finally:
        conn.close()


def get_unprocessed_conversations(owner_id: int | None = None) -> dict[str, list[dict]]:
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            if owner_id is not None:
                cur.execute(
                    "SELECT r.id, r.session_id, r.user_input, r.assistant_reply, "
                    "       ct.ai_summary, r.user_input_at, ct.intent "
                    "FROM raw_conversations r "
                    "LEFT JOIN conversation_turns ct "
                    "  ON r.session_id = ct.session_id "
                    "  AND r.user_input_at = ct.user_input_at "
                    "  AND ct.owner_id = r.owner_id "
                    "WHERE r.processed = FALSE AND r.owner_id = %s "
                    "ORDER BY r.id",
                    (owner_id,),
                )
            else:
                cur.execute(
                    "SELECT r.id, r.session_id, r.user_input, r.assistant_reply, "
                    "       ct.ai_summary, r.user_input_at, ct.intent "
                    "FROM raw_conversations r "
                    "LEFT JOIN conversation_turns ct "
                    "  ON r.session_id = ct.session_id "
                    "  AND r.user_input_at = ct.user_input_at "
                    "  AND ct.owner_id = r.owner_id "
                    "WHERE r.processed = FALSE "
                    "ORDER BY r.id"
                )
            sessions: dict[str, list[dict]] = {}
            for id_, sid, user_input, assistant_reply, ai_summary, user_input_at, intent in cur.fetchall():
                if sid not in sessions:
                    sessions[sid] = []
                sessions[sid].append({
                    "id": id_,
                    "user_input": user_input,
                    "assistant_reply": assistant_reply,
                    "ai_summary": ai_summary or user_input,
                    "user_input_at": user_input_at,
                    "intent": intent or "",
                })
            return sessions
    finally:
        conn.close()


def mark_processed(message_ids: list[int], owner_id: int | None = None):
    """Mark raw_conversations rows as processed.

    owner_id is optional but recommended — when provided, the UPDATE is
    scoped to that owner as defence in depth.
    """
    if not message_ids:
        return
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            if owner_id is not None:
                cur.execute(
                    "UPDATE raw_conversations SET processed = TRUE "
                    "WHERE id = ANY(%s) AND owner_id = %s",
                    (message_ids, owner_id),
                )
            else:
                cur.execute(
                    "UPDATE raw_conversations SET processed = TRUE WHERE id = ANY(%s)",
                    (message_ids,),
                )
        conn.commit()
    finally:
        conn.close()


def _consolidate_profile(owner_id: int | None = None):
    """合并同 category+subject 的冗余条目，保留最新的"""
    all_profile = load_full_current_profile(owner_id=owner_id)
    groups = defaultdict(list)
    for p in all_profile:
        groups[(p["category"], p["subject"])].append(p)

    for (cat, subj), entries in groups.items():
        if len(entries) <= 1:
            continue
        entries.sort(key=lambda x: x.get("updated_at") or x.get("created_at") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        keeper = entries[0]
        for old in entries[1:]:
            if old["id"] == keeper["id"]:
                continue
            if old.get("superseded_by") or old.get("end_time"):
                continue
            if old.get("value", "").strip().lower() != keeper.get("value", "").strip().lower():
                continue
            old_evidence = old.get("evidence", [])
            if old_evidence and isinstance(old_evidence, list):
                add_evidence(keeper["id"], {"merged_from": old["id"]})
            close_time_period(old["id"])
            delete_fact_edges_for(old["id"], owner_id=owner_id)
