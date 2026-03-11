import json
import logging
from datetime import datetime, timedelta
from psycopg2.extras import RealDictCursor
from agent.utils.time_context import get_now
from agent.config import load_config
from agent.config.prompts import get_labels
from ._db import get_db_connection

logger = logging.getLogger(__name__)

def _lang() -> str:
    return load_config().get("language", "en")
from ._synonyms import _get_category_synonyms, _get_subject_synonyms


def _find_existing_hypothesis(cur, category: str, subject: str):
    _FIELDS = "id, claim, evidence_for, confidence, status, suspected_value, mention_count"
    _STATUS_SET = "('pending', 'active', 'established', 'suspected', 'dormant', 'confirmed')"
    _ORDER = (
        "ORDER BY CASE status "
        "  WHEN 'established' THEN 1 WHEN 'active' THEN 2 WHEN 'pending' THEN 3 "
        "  WHEN 'suspected' THEN 4 WHEN 'dormant' THEN 5 WHEN 'confirmed' THEN 6 "
        "END LIMIT 1"
    )
    cur.execute(
        f"SELECT {_FIELDS} FROM hypotheses "
        f"WHERE category = %s AND subject = %s "
        f"AND status IN {_STATUS_SET} "
        f"{_ORDER}",
        (category, subject),
    )
    row = cur.fetchone()
    if row:
        return row
    cat_syns = _get_category_synonyms(category)
    subj_syns = _get_subject_synonyms(subject)
    all_cats = list(cat_syns)
    all_subjs = list(subj_syns)
    if len(all_cats) > 1 or len(all_subjs) > 1:
        cur.execute(
            f"SELECT {_FIELDS} FROM hypotheses "
            f"WHERE category = ANY(%s) AND subject = ANY(%s) "
            f"AND status IN {_STATUS_SET} "
            f"{_ORDER}",
            (all_cats, all_subjs),
        )
        row = cur.fetchone()
        if row:
            return row
    cur.execute(
        f"SELECT {_FIELDS} FROM hypotheses "
        f"WHERE category = ANY(%s) AND status IN {_STATUS_SET} "
        f"AND (subject ILIKE '%%' || %s || '%%' OR %s ILIKE '%%' || subject || '%%') "
        f"{_ORDER}",
        (all_cats, subject, subject),
    )
    row = cur.fetchone()
    if row:
        return row
    return None

def save_hypothesis(category: str, subject: str, claim: str,
                    evidence_for: list | None = None,
                    confidence: float = 0.5,
                    source_type: str = 'stated',
                    decay_days: int | None = None,
                    start_time=None) -> int:
    if evidence_for is None:
        evidence_for = []
    now = start_time if start_time else get_now()
    if decay_days is None or decay_days <= 0:
        decay_days = 365
    expires_at = now + timedelta(days=decay_days)
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            row = _find_existing_hypothesis(cur, category, subject)

            if row:
                (existing_id, existing_claim, existing_evidence, existing_conf,
                 existing_status, suspected_value, existing_mention_count) = row
                existing_evidence = existing_evidence if existing_evidence else []
                existing_mention_count = existing_mention_count or 1

                if existing_claim and existing_claim.strip() != claim.strip() and existing_status != 'dormant':
                    if suspected_value:
                        _L = get_labels("context.labels", _lang())
                        evidence_entry = {
                            "reason": _L["new_obs_supports"].format(claim=claim),
                        }
                        cur.execute("SELECT suspected_evidence FROM hypotheses WHERE id = %s", (existing_id,))
                        se_row = cur.fetchone()
                        if se_row:
                            suspected_ev = se_row[0] if se_row[0] else []
                            suspected_ev.append(evidence_entry)
                            cur.execute(
                                "UPDATE hypotheses SET suspected_evidence = %s, "
                                "status = 'suspected', last_updated_at = %s WHERE id = %s",
                                (json.dumps(suspected_ev, ensure_ascii=False), now, existing_id),
                            )
                    else:
                        cur.execute(
                            "UPDATE hypotheses SET suspected_value = %s, "
                            "suspected_since = %s, suspected_evidence = '[]', "
                            "status = 'suspected', last_updated_at = %s "
                            "WHERE id = %s",
                            (claim, now, now, existing_id),
                        )
                    conn.commit()
                    return existing_id

                new_mention_count = existing_mention_count + 1
                merged_evidence = existing_evidence + evidence_for

                new_status = existing_status
                if existing_status == 'dormant':
                    new_status = 'active'

                cur.execute(
                    "UPDATE hypotheses SET claim = %s, evidence_for = %s, "
                    "confidence = %s, mention_count = %s, status = %s, "
                    "last_updated_at = %s, "
                    "decay_days = COALESCE(%s, decay_days), "
                    "expires_at = COALESCE(%s, expires_at) "
                    "WHERE id = %s",
                    (claim, json.dumps(merged_evidence, ensure_ascii=False),
                     confidence, new_mention_count, new_status, now,
                     decay_days, expires_at, existing_id),
                )
                conn.commit()
                return existing_id
            else:
                effective_decay = decay_days
                effective_expires = now + timedelta(days=effective_decay)
                try:
                    cur.execute(
                        "INSERT INTO hypotheses "
                        "(category, subject, claim, evidence_for, confidence, "
                        " mention_count, status, source_type, "
                        " decay_days, expires_at, first_seen_at, last_updated_at) "
                        "VALUES (%s, %s, %s, %s, %s, 1, 'active', %s, %s, %s, %s, %s) "
                        "RETURNING id",
                        (category, subject, claim,
                         json.dumps(evidence_for, ensure_ascii=False),
                         confidence, source_type,
                         effective_decay, effective_expires, now, now),
                    )
                    hyp_id = cur.fetchone()[0]
                    conn.commit()
                    return hyp_id
                except Exception:
                    logger.debug("Hypothesis INSERT conflict, falling back to SELECT", exc_info=True)
                    conn.rollback()
                    cur.execute(
                        "SELECT id FROM hypotheses WHERE category = %s AND subject = %s "
                        "ORDER BY last_updated_at DESC LIMIT 1",
                        (category, subject),
                    )
                    fallback = cur.fetchone()
                    return fallback[0] if fallback else -1
    finally:
        conn.close()

def update_hypothesis_evidence(hypothesis_id: int,
                               evidence_for: dict | None = None,
                               evidence_against: dict | None = None,
                               new_confidence: float | None = None,
                               supports_suspected: bool = False,
                               reference_time=None) -> bool:
    now = reference_time if reference_time else get_now()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT evidence_for, evidence_against, confidence, suspected_value, mention_count "
                "FROM hypotheses WHERE id = %s",
                (hypothesis_id,),
            )
            row = cur.fetchone()
            if not row:
                return False

            cur_for = row[0] if row[0] else []
            cur_against = row[1] if row[1] else []
            has_suspected = bool(row[3])
            cur_mention_count = row[4] if row[4] is not None else 1

            if has_suspected and supports_suspected and evidence_for:
                update_suspected_evidence(hypothesis_id, evidence_for)
                return True

            if evidence_for:
                cur_for.append(evidence_for)
            if evidence_against:
                cur_against.append(evidence_against)

            new_mention_count = cur_mention_count
            if evidence_for:
                new_mention_count = cur_mention_count + 1

            cur.execute("SELECT decay_days FROM hypotheses WHERE id = %s", (hypothesis_id,))
            decay_row = cur.fetchone()
            decay = decay_row[0] if decay_row and decay_row[0] and decay_row[0] > 0 else 365
            refreshed_expires = now + timedelta(days=decay)

            cur.execute(
                "UPDATE hypotheses SET evidence_for = %s, evidence_against = %s, "
                "mention_count = %s, last_updated_at = %s, expires_at = %s "
                "WHERE id = %s",
                (json.dumps(cur_for, ensure_ascii=False),
                 json.dumps(cur_against, ensure_ascii=False),
                 new_mention_count, now, refreshed_expires,
                 hypothesis_id),
            )
        conn.commit()
        return True
    finally:
        conn.close()

def load_active_hypotheses(category: str | None = None,
                           min_confidence: float = 0.0) -> list[dict]:
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            conditions = [
                "status IN ('pending', 'active', 'established', 'suspected', 'confirmed')",
            ]
            params: list = []
            if category:
                conditions.append("category = %s")
                params.append(category)
            where = "WHERE " + " AND ".join(conditions)
            cur.execute(
                f"SELECT id, category, subject, claim, evidence_for, evidence_against, "
                f"confidence, mention_count, status, source_type, decay_days, expires_at, "
                f"first_seen_at, last_updated_at, "
                f"suspected_value, suspected_confidence, suspected_since, suspected_evidence, history "
                f"FROM hypotheses {where} "
                f"ORDER BY CASE status "
                f"  WHEN 'established' THEN 1 WHEN 'active' THEN 2 WHEN 'confirmed' THEN 3 "
                f"  WHEN 'suspected' THEN 4 WHEN 'pending' THEN 5 "
                f"END, mention_count DESC",
                params,
            )
            return list(cur.fetchall())
    finally:
        conn.close()

def get_expired_hypotheses() -> list[dict]:
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, category, subject, claim, confidence, status, "
                "mention_count, decay_days, expires_at, first_seen_at, last_updated_at "
                "FROM hypotheses "
                "WHERE expires_at IS NOT NULL AND expires_at < %s "
                "AND status IN ('pending', 'active', 'established', 'confirmed') "
                "ORDER BY expires_at ASC",
                (get_now(),),
            )
            return list(cur.fetchall())
    finally:
        conn.close()

def get_hypothesis_by_subject(category: str, subject: str) -> dict | None:
    _FIELDS = (
        "id, category, subject, claim, evidence_for, evidence_against, "
        "confidence, mention_count, source_type, status, first_seen_at, last_updated_at, "
        "suspected_value, suspected_confidence, suspected_since, suspected_evidence, history"
    )
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            _STATUS_FILTER = "status IN ('pending', 'active', 'established', 'suspected', 'confirmed')"
            cur.execute(
                f"SELECT {_FIELDS} FROM hypotheses "
                f"WHERE category = %s AND subject = %s AND {_STATUS_FILTER}",
                (category, subject),
            )
            result = cur.fetchone()
            if result:
                return result
            cat_syns = list(_get_category_synonyms(category))
            subj_syns = list(_get_subject_synonyms(subject))
            if len(cat_syns) > 1 or len(subj_syns) > 1:
                cur.execute(
                    f"SELECT {_FIELDS} FROM hypotheses "
                    f"WHERE category = ANY(%s) AND subject = ANY(%s) AND {_STATUS_FILTER} "
                    f"LIMIT 1",
                    (cat_syns, subj_syns),
                )
                result = cur.fetchone()
                if result:
                    return result
            cur.execute(
                f"SELECT {_FIELDS} FROM hypotheses "
                f"WHERE subject = %s AND {_STATUS_FILTER}",
                (subject,),
            )
            result = cur.fetchone()
            if result:
                return result
            if len(subj_syns) > 1:
                cur.execute(
                    f"SELECT {_FIELDS} FROM hypotheses "
                    f"WHERE subject = ANY(%s) AND {_STATUS_FILTER} "
                    f"LIMIT 1",
                    (subj_syns,),
                )
                result = cur.fetchone()
                if result:
                    return result
            cur.execute(
                f"SELECT {_FIELDS} FROM hypotheses "
                f"WHERE category = ANY(%s) AND {_STATUS_FILTER} "
                "AND (subject ILIKE '%%' || %s || '%%' OR %s ILIKE '%%' || subject || '%%') "
                "ORDER BY mention_count DESC LIMIT 1",
                (cat_syns, subject, subject),
            )
            result = cur.fetchone()
            if result:
                return result
            return None
    finally:
        conn.close()

def enter_suspicion_mode(hypothesis_id: int, suspected_value: str):
    now = get_now()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE hypotheses SET "
                "status = 'suspected', "
                "suspected_value = %s, suspected_confidence = 0, "
                "suspected_since = %s, suspected_evidence = '[]', "
                "last_updated_at = %s "
                "WHERE id = %s",
                (suspected_value, now, now, hypothesis_id),
            )
        conn.commit()
    finally:
        conn.close()

def update_suspected_evidence(hypothesis_id: int, evidence: dict):
    now = get_now()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT suspected_evidence FROM hypotheses WHERE id = %s",
                (hypothesis_id,),
            )
            row = cur.fetchone()
            if not row:
                return
            cur_evidence = row[0] if row[0] else []
            cur_evidence.append(evidence)
            cur.execute(
                "UPDATE hypotheses SET suspected_evidence = %s, "
                "last_updated_at = %s WHERE id = %s",
                (json.dumps(cur_evidence, ensure_ascii=False), now, hypothesis_id),
            )
        conn.commit()
    finally:
        conn.close()

def resolve_suspicion(hypothesis_id: int, accept: bool):
    now = get_now()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT claim, confidence, evidence_for, evidence_against, "
                "first_seen_at, suspected_value, suspected_confidence, "
                "suspected_since, suspected_evidence, history, mention_count "
                "FROM hypotheses WHERE id = %s",
                (hypothesis_id,),
            )
            row = cur.fetchone()
            if not row:
                return
            (old_claim, old_confidence, old_evidence_for, old_evidence_against,
             old_first_seen, suspected_value, suspected_confidence,
             suspected_since, suspected_evidence, history, mention_count) = row

            if accept:
                history = history if history else []
                old_from = old_first_seen.strftime("%Y-%m-%d") if old_first_seen else "?"
                old_to = now.strftime("%Y-%m-%d")
                history.append({
                    "value": old_claim,
                    "from": old_from,
                    "to": old_to,
                    "mention_count": mention_count or 1,
                })

                suspected_evidence = suspected_evidence if suspected_evidence else []
                cur.execute(
                    "UPDATE hypotheses SET "
                    "claim = %s, confidence = 0.5, "
                    "status = 'active', mention_count = 2, "
                    "evidence_for = %s, evidence_against = '[]', "
                    "first_seen_at = %s, "
                    "suspected_value = NULL, suspected_confidence = 0, "
                    "suspected_since = NULL, suspected_evidence = '[]', "
                    "history = %s, last_updated_at = %s "
                    "WHERE id = %s",
                    (suspected_value,
                     json.dumps(suspected_evidence, ensure_ascii=False),
                     suspected_since, json.dumps(history, ensure_ascii=False),
                     now, hypothesis_id),
                )
            else:
                mc = mention_count or 1
                if mc >= 4:
                    restored_status = 'established'
                elif mc >= 2:
                    restored_status = 'active'
                else:
                    restored_status = 'pending'

                old_evidence_against = old_evidence_against if old_evidence_against else []
                suspected_evidence = suspected_evidence if suspected_evidence else []
                _L = get_labels("context.labels", _lang())
                for se in suspected_evidence:
                    old_evidence_against.append({
                        "reason": f"{_L['rejection_tag']} {se.get('reason', '')}",
                    })
                cur.execute(
                    "UPDATE hypotheses SET "
                    "status = %s, "
                    "suspected_value = NULL, suspected_confidence = 0, "
                    "suspected_since = NULL, suspected_evidence = '[]', "
                    "evidence_against = %s, last_updated_at = %s "
                    "WHERE id = %s",
                    (restored_status,
                     json.dumps(old_evidence_against, ensure_ascii=False),
                     now, hypothesis_id),
                )
        conn.commit()
    finally:
        conn.close()

def upgrade_hypothesis_decay(hypothesis_id: int, new_decay_days: int,
                             reference_time=None):
    now = reference_time if reference_time else get_now()
    new_expires = now + timedelta(days=new_decay_days)
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE hypotheses SET decay_days = %s, expires_at = %s, last_updated_at = %s "
                "WHERE id = %s",
                (new_decay_days, new_expires, now, hypothesis_id),
            )
        conn.commit()
    finally:
        conn.close()

def set_hypothesis_status(hypothesis_id: int, status: str):
    now = get_now()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE hypotheses SET status = %s, last_updated_at = %s WHERE id = %s",
                (status, now, hypothesis_id),
            )
        conn.commit()
    finally:
        conn.close()
