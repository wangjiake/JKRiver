"""Profile storage — user facts, relationships, trajectory, user model.

All write functions follow the commit/transaction proxy pattern:
each function calls conn.commit() once at the end.  When called inside
a transaction() block, get_db_connection() returns a _TransactionProxy
that makes commit() a no-op, so the real commit happens when the
transaction block exits.  This keeps functions self-contained for
standalone use while allowing batched atomic transactions.
"""

import json
from datetime import datetime, timedelta
from psycopg2.extras import RealDictCursor
from agent.utils.time_context import get_now
from agent.config import load_config
from agent.config.prompts import get_labels
from ._db import get_db_connection

def _lang() -> str:
    return load_config().get("language", "en")
from ._synonyms import _get_category_synonyms, _get_subject_synonyms


def upsert_profile(category: str, field: str, value: str,
                   hypothesis_id: int | None = None):
    now = get_now()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO current_profile (category, field, value, hypothesis_id, confirmed_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (category, field, value) DO UPDATE "
                "SET hypothesis_id = %s, updated_at = %s",
                (category, field, value, hypothesis_id, now, now,
                 hypothesis_id, now),
            )
        conn.commit()
    finally:
        conn.close()

def load_current_profile() -> list[dict]:
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, category, field, value, hypothesis_id, confirmed_at, updated_at "
                "FROM current_profile "
                "ORDER BY category, field"
            )
            return list(cur.fetchall())
    finally:
        conn.close()

def remove_profile(category: str, field: str, value: str | None = None):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            if value:
                cur.execute(
                    "DELETE FROM current_profile WHERE category = %s AND field = %s AND value = %s",
                    (category, field, value),
                )
            else:
                cur.execute(
                    "DELETE FROM current_profile WHERE category = %s AND field = %s",
                    (category, field),
                )
        conn.commit()
    finally:
        conn.close()

def upsert_user_model(dimension: str, assessment: str,
                      evidence_summary: str | None = None):
    now = get_now()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO user_model (dimension, assessment, evidence_summary, updated_at) "
                "VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (dimension) DO UPDATE "
                "SET assessment = %s, evidence_summary = %s, updated_at = %s",
                (dimension, assessment, evidence_summary, now,
                 assessment, evidence_summary, now),
            )
        conn.commit()
    finally:
        conn.close()

def load_user_model() -> list[dict]:
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, dimension, assessment, evidence_summary, updated_at "
                "FROM user_model ORDER BY dimension"
            )
            return list(cur.fetchall())
    finally:
        conn.close()

def save_trajectory_summary(trajectory: dict, session_count: int = 0):
    def _text(val):
        if isinstance(val, (dict, list)):
            return json.dumps(val, ensure_ascii=False)
        return val if val is not None else ""

    now = get_now()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO trajectory_summary "
                "(life_phase, phase_characteristics, trajectory_direction, "
                " stability_assessment, key_anchors, volatile_areas, "
                " recent_momentum, predicted_shifts, full_summary, "
                " session_count, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    _text(trajectory.get("life_phase", "")),
                    _text(trajectory.get("phase_characteristics", "")),
                    _text(trajectory.get("trajectory_direction", "")),
                    _text(trajectory.get("stability_assessment", "")),
                    json.dumps(trajectory.get("key_anchors", []), ensure_ascii=False),
                    json.dumps(trajectory.get("volatile_areas", []), ensure_ascii=False),
                    _text(trajectory.get("recent_momentum", "")),
                    _text(trajectory.get("predicted_shifts", "")),
                    _text(trajectory.get("full_summary", "")),
                    session_count, now, now,
                ),
            )
        conn.commit()
    finally:
        conn.close()

def load_trajectory_summary() -> dict | None:
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM trajectory_summary ORDER BY updated_at DESC LIMIT 1"
            )
            return cur.fetchone()
    finally:
        conn.close()

def save_or_update_relationship(name: str | None, relation: str,
                                 details: dict | None = None) -> int:
    now = get_now()
    details = details or {}
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            if name:
                cur.execute(
                    "SELECT id, details, mention_count FROM relationships "
                    "WHERE name = %s AND relation = %s AND status = 'active' "
                    "ORDER BY id LIMIT 1",
                    (name, relation),
                )
            else:
                cur.execute(
                    "SELECT id, details, mention_count FROM relationships "
                    "WHERE name IS NULL AND relation = %s AND status = 'active' "
                    "ORDER BY id LIMIT 1",
                    (relation,),
                )
            row = cur.fetchone()
            if row:
                rid, old_details_raw, mc = row
                old_details = old_details_raw if isinstance(old_details_raw, dict) else json.loads(old_details_raw or "{}")
                merged = {**old_details, **details}
                cur.execute(
                    "UPDATE relationships SET details = %s, mention_count = %s, "
                    "last_mentioned_at = %s WHERE id = %s",
                    (json.dumps(merged, ensure_ascii=False), mc + 1, now, rid),
                )
            else:
                cur.execute(
                    "INSERT INTO relationships (name, relation, details, "
                    "first_mentioned_at, last_mentioned_at, mention_count) "
                    "VALUES (%s, %s, %s, %s, %s, 1) RETURNING id",
                    (name, relation, json.dumps(details, ensure_ascii=False), now, now),
                )
                rid = cur.fetchone()[0]
        conn.commit()
        return rid
    finally:
        conn.close()

def load_relationships(status: str = "active") -> list[dict]:
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, name, relation, details, mention_count, "
                "first_mentioned_at, last_mentioned_at "
                "FROM relationships WHERE status = %s "
                "ORDER BY last_mentioned_at DESC",
                (status,),
            )
            return list(cur.fetchall())
    finally:
        conn.close()

def save_profile_fact(category: str, subject: str, value: str,
                      source_type: str = 'stated',
                      decay_days: int | None = None,
                      evidence: list | None = None,
                      start_time=None) -> int:
    if not start_time:
        start_time = get_now()
    now = start_time
    if evidence is None:
        evidence = []
    if not decay_days or decay_days <= 0:
        decay_days = 365
    expires_at = now + timedelta(days=decay_days)

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            existing = _find_current_fact_cursor(cur, category, subject)

            if existing:
                if existing["value"].strip().lower() == value.strip().lower():
                    old_evidence = existing["evidence"] if existing["evidence"] else []
                    merged = old_evidence + evidence
                    new_mc = (existing["mention_count"] or 1) + 1
                    new_expires = now + timedelta(days=decay_days)
                    cur.execute(
                        "UPDATE user_profile SET mention_count = %s, evidence = %s, "
                        "updated_at = %s, expires_at = %s "
                        "WHERE id = %s",
                        (new_mc, json.dumps(merged, ensure_ascii=False),
                         now, new_expires, existing["id"]),
                    )
                    result_id = existing["id"]
                elif existing["category"] in (get_labels("context.labels", _lang()).get("interest_category", "interest"),):
                    cur.execute(
                        "SELECT id, evidence, mention_count FROM user_profile "
                        "WHERE category = %s AND subject = %s "
                        "AND LOWER(TRIM(value)) = LOWER(TRIM(%s)) "
                        "AND end_time IS NULL AND human_end_time IS NULL LIMIT 1",
                        (existing["category"], existing["subject"], value),
                    )
                    exact_match = cur.fetchone()
                    if exact_match:
                        old_ev = exact_match["evidence"] if exact_match["evidence"] else []
                        merged_ev = old_ev + evidence
                        new_mc = (exact_match["mention_count"] or 1) + 1
                        new_expires = now + timedelta(days=decay_days)
                        cur.execute(
                            "UPDATE user_profile SET mention_count = %s, evidence = %s, "
                            "updated_at = %s, expires_at = %s WHERE id = %s",
                            (new_mc, json.dumps(merged_ev, ensure_ascii=False),
                             now, new_expires, exact_match["id"]),
                        )
                        result_id = exact_match["id"]
                    else:
                        cur.execute(
                            "INSERT INTO user_profile "
                            "(category, subject, value, layer, source_type, "
                            " start_time, decay_days, expires_at, evidence, "
                            " mention_count, created_at, updated_at) "
                            "VALUES (%s, %s, %s, 'suspected', %s, %s, %s, %s, %s, "
                            "1, %s, %s) "
                            "RETURNING id",
                            (category, subject, value, source_type,
                             start_time, decay_days, expires_at,
                             json.dumps(evidence, ensure_ascii=False),
                             now, now),
                        )
                        result_id = cur.fetchone()["id"]
                else:
                    cur.execute(
                        "INSERT INTO user_profile "
                        "(category, subject, value, layer, source_type, "
                        " start_time, decay_days, expires_at, evidence, "
                        " mention_count, created_at, updated_at, "
                        " supersedes) "
                        "VALUES (%s, %s, %s, 'suspected', %s, %s, %s, %s, %s, "
                        "1, %s, %s, %s) "
                        "RETURNING id",
                        (category, subject, value, source_type,
                         start_time, decay_days, expires_at,
                         json.dumps(evidence, ensure_ascii=False),
                         now, now, existing["id"]),
                    )
                    result_id = cur.fetchone()["id"]
                    cur.execute(
                        "UPDATE user_profile SET superseded_by = %s WHERE id = %s",
                        (result_id, existing["id"]),
                    )
            else:
                cur.execute(
                    "INSERT INTO user_profile "
                    "(category, subject, value, layer, source_type, "
                    " start_time, decay_days, expires_at, evidence, "
                    " mention_count, created_at, updated_at) "
                    "VALUES (%s, %s, %s, 'suspected', %s, %s, %s, %s, %s, "
                    "1, %s, %s) "
                    "RETURNING id",
                    (category, subject, value, source_type,
                     start_time, decay_days, expires_at,
                     json.dumps(evidence, ensure_ascii=False),
                     now, now),
                )
                result_id = cur.fetchone()["id"]
        conn.commit()
        return result_id
    finally:
        conn.close()

def close_time_period(fact_id: int, end_time=None, superseded_by: int | None = None):
    now = get_now()
    if not end_time:
        end_time = now
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT human_end_time FROM user_profile WHERE id = %s", (fact_id,))
            row = cur.fetchone()
            if row and row[0] is not None:
                return

            if superseded_by:
                cur.execute(
                    "UPDATE user_profile SET end_time = %s, updated_at = %s, "
                    "superseded_by = %s WHERE id = %s",
                    (end_time, now, superseded_by, fact_id),
                )
            else:
                cur.execute(
                    "UPDATE user_profile SET end_time = %s, updated_at = %s "
                    "WHERE id = %s",
                    (end_time, now, fact_id),
                )
        conn.commit()
    finally:
        conn.close()

def confirm_profile_fact(fact_id: int, reference_time=None):
    now = reference_time if reference_time else get_now()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE user_profile SET layer = 'confirmed', "
                "confirmed_at = %s, updated_at = %s WHERE id = %s",
                (now, now, fact_id),
            )
        conn.commit()
    finally:
        conn.close()

def add_evidence(fact_id: int, evidence_entry: dict, reference_time=None):
    now = reference_time if reference_time else get_now()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT evidence FROM user_profile WHERE id = %s",
                (fact_id,),
            )
            row = cur.fetchone()
            if not row:
                return
            MAX_EVIDENCE = 10
            cur_evidence = row[0] if row[0] else []
            cur_evidence.append(evidence_entry)
            if len(cur_evidence) > MAX_EVIDENCE:
                cur_evidence = cur_evidence[-MAX_EVIDENCE:]
            cur.execute(
                "UPDATE user_profile SET evidence = %s, updated_at = %s "
                "WHERE id = %s",
                (json.dumps(cur_evidence, ensure_ascii=False), now, fact_id),
            )
        conn.commit()
    finally:
        conn.close()

def _find_current_fact_cursor(cur, category: str, subject: str):
    _FIELDS = ("id, category, subject, value, layer, source_type, "
               "start_time, end_time, decay_days, expires_at, evidence, "
               "mention_count, created_at, updated_at, confirmed_at, "
               "superseded_by, supersedes")
    _ORDER = "ORDER BY (superseded_by IS NULL) DESC, created_at DESC LIMIT 1"

    cur.execute(
        f"SELECT {_FIELDS} FROM user_profile "
        f"WHERE category = %s AND subject = %s AND end_time IS NULL "
        f"AND rejected = false AND human_end_time IS NULL "
        f"{_ORDER}",
        (category, subject),
    )
    row = cur.fetchone()
    if row:
        return row

    cat_syns = list(_get_category_synonyms(category))
    subj_syns = list(_get_subject_synonyms(subject))
    if len(cat_syns) > 1 or len(subj_syns) > 1:
        cur.execute(
            f"SELECT {_FIELDS} FROM user_profile "
            f"WHERE category = ANY(%s) AND subject = ANY(%s) AND end_time IS NULL "
            f"AND rejected = false AND human_end_time IS NULL "
            f"{_ORDER}",
            (cat_syns, subj_syns),
        )
        row = cur.fetchone()
        if row:
            return row

    cur.execute(
        f"SELECT {_FIELDS} FROM user_profile "
        f"WHERE category = ANY(%s) AND end_time IS NULL "
        f"AND rejected = false AND human_end_time IS NULL "
        f"AND (subject ILIKE '%%' || %s || '%%' OR %s ILIKE '%%' || subject || '%%') "
        f"{_ORDER}",
        (cat_syns, subject, subject),
    )
    row = cur.fetchone()
    if row:
        return row
    return None

def find_current_fact(category: str, subject: str) -> dict | None:
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            return _find_current_fact_cursor(cur, category, subject)
    finally:
        conn.close()

def load_suspected_profile() -> list[dict]:
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, category, subject, value, layer, source_type, "
                "start_time, decay_days, expires_at, evidence, mention_count, "
                "created_at, updated_at, supersedes "
                "FROM user_profile "
                "WHERE layer = 'suspected' AND end_time IS NULL "
                "AND rejected = false AND human_end_time IS NULL "
                "ORDER BY category, subject"
            )
            return list(cur.fetchall())
    finally:
        conn.close()

def load_confirmed_profile() -> list[dict]:
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, category, subject, value, layer, source_type, "
                "start_time, decay_days, expires_at, evidence, mention_count, "
                "created_at, updated_at, confirmed_at, supersedes "
                "FROM user_profile "
                "WHERE layer = 'confirmed' AND end_time IS NULL "
                "AND rejected = false AND human_end_time IS NULL "
                "ORDER BY category, subject"
            )
            return list(cur.fetchall())
    finally:
        conn.close()

def load_full_current_profile(exclude_superseded: bool = False) -> list[dict]:
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            where = "WHERE end_time IS NULL AND rejected = false AND human_end_time IS NULL"
            if exclude_superseded:
                where += " AND superseded_by IS NULL"
            cur.execute(
                f"SELECT id, category, subject, value, layer, source_type, "
                f"start_time, decay_days, expires_at, evidence, mention_count, "
                f"created_at, updated_at, confirmed_at, superseded_by, supersedes "
                f"FROM user_profile "
                f"{where} "
                f"ORDER BY CASE layer WHEN 'confirmed' THEN 1 WHEN 'suspected' THEN 2 END, "
                f"category, subject"
            )
            return list(cur.fetchall())
    finally:
        conn.close()

def load_timeline(category: str | None = None,
                  subject: str | None = None,
                  include_rejected: bool = False) -> list[dict]:
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            conditions = []
            params: list = []
            if not include_rejected:
                conditions.append("rejected = FALSE")
            if category:
                conditions.append("category = %s")
                params.append(category)
            if subject:
                conditions.append("subject = %s")
                params.append(subject)
            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            cur.execute(
                f"SELECT id, category, subject, value, layer, source_type, "
                f"start_time, end_time, decay_days, expires_at, evidence, "
                f"mention_count, created_at, updated_at, confirmed_at, "
                f"superseded_by, supersedes, rejected, human_end_time "
                f"FROM user_profile {where} "
                f"ORDER BY category, subject, start_time",
                params,
            )
            return list(cur.fetchall())
    finally:
        conn.close()

def get_expired_facts(reference_time=None) -> list[dict]:
    ref = reference_time if reference_time else get_now()
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, category, subject, value, layer, source_type, "
                "start_time, decay_days, expires_at, evidence, mention_count, "
                "created_at, updated_at, superseded_by, supersedes "
                "FROM user_profile "
                "WHERE expires_at IS NOT NULL AND expires_at < %s "
                "AND end_time IS NULL AND rejected = false AND human_end_time IS NULL "
                "ORDER BY expires_at ASC",
                (ref,)
            )
            return list(cur.fetchall())
    finally:
        conn.close()

def load_disputed_facts() -> list[dict]:
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, category, subject, value, layer, source_type, "
                "start_time, decay_days, expires_at, evidence, mention_count, "
                "created_at, updated_at, confirmed_at, superseded_by "
                "FROM user_profile "
                "WHERE superseded_by IS NOT NULL AND end_time IS NULL "
                "AND rejected = false AND human_end_time IS NULL "
                "ORDER BY category, subject"
            )
            old_records = list(cur.fetchall())

            pairs = []
            for old in old_records:
                new_id = old["superseded_by"]
                cur.execute(
                    "SELECT id, category, subject, value, layer, source_type, "
                    "start_time, decay_days, expires_at, evidence, mention_count, "
                    "created_at, updated_at, supersedes "
                    "FROM user_profile WHERE id = %s AND end_time IS NULL "
                    "AND human_end_time IS NULL",
                    (new_id,),
                )
                new = cur.fetchone()
                if new:
                    pairs.append({"old": dict(old), "new": dict(new)})
            return pairs
    finally:
        conn.close()

def resolve_dispute(old_fact_id: int, new_fact_id: int, accept_new: bool,
                    resolution_time=None):
    now = resolution_time or get_now()
    end_time = now
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            if accept_new:
                cur.execute(
                    "UPDATE user_profile SET end_time = %s, updated_at = %s "
                    "WHERE id = %s",
                    (end_time, now, old_fact_id),
                )
                cur.execute(
                    "UPDATE user_profile SET supersedes = NULL, updated_at = %s "
                    "WHERE id = %s",
                    (now, new_fact_id),
                )
            else:
                cur.execute(
                    "UPDATE user_profile SET end_time = %s, updated_at = %s "
                    "WHERE id = %s",
                    (end_time, now, new_fact_id),
                )
                cur.execute(
                    "UPDATE user_profile SET superseded_by = NULL, updated_at = %s "
                    "WHERE id = %s",
                    (now, old_fact_id),
                )
        conn.commit()
    finally:
        conn.close()

def update_fact_decay(fact_id: int, new_decay_days: int, reference_time=None):
    now = reference_time if reference_time else get_now()
    new_expires = now + timedelta(days=new_decay_days)
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE user_profile SET decay_days = %s, expires_at = %s, "
                "updated_at = %s WHERE id = %s",
                (new_decay_days, new_expires, now, fact_id),
            )
        conn.commit()
    finally:
        conn.close()
