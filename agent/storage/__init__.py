
import json
import os
import re
from datetime import datetime, timedelta
from decimal import Decimal
import psycopg2
from psycopg2.extras import RealDictCursor

from agent.utils.time_context import get_now
from agent.config import load_config
from agent.config.prompts import get_labels

def _load_db_config():
    db = load_config().get("database", {})
    return {
        "dbname": db.get("name", "Riverse"),
        "user": db.get("user", "postgres"),
        "host": db.get("host", "localhost"),
        "options": "-c client_encoding=UTF8",
    }

DB_CONFIG = _load_db_config()

def get_db_connection():
    conn = psycopg2.connect(**DB_CONFIG)
    return conn

_CATEGORY_SYNONYM_GROUPS = [
    {"位置", "居住地", "居住城市", "地点", "住址", "居住", "所在地"},
    {"职业", "职位", "工作", "岗位"},
    {"教育", "教育背景", "学历"},
    {"家乡", "籍贯", "出生地", "老家"},
    {"兴趣", "爱好", "休闲活动", "休闲", "运动", "运动与锻炼"},
    {"感情", "恋爱", "情感", "婚恋"},
    {"出生年份", "年龄", "出生年"},
    {"专业", "学科", "主修"},
    {"娱乐", "游戏"},
    {"宠物", "养宠"},
    {"技能", "技术", "编程"},
    {"身份", "个人信息"},
    {"饮食", "饮食与美食", "美食"},
]

_CAT_SYNONYM_MAP: dict[str, set[str]] = {}
for _group in _CATEGORY_SYNONYM_GROUPS:
    for _name in _group:
        _CAT_SYNONYM_MAP[_name] = _group

_SUBJECT_SYNONYM_GROUPS = [
    {"居住地", "居住城市", "当前居住地", "所在城市"},
    {"职业", "当前职位", "工作", "职位", "岗位"},
    {"学校", "大学", "毕业学校"},
    {"专业", "主修", "学科"},
    {"家乡", "老家", "出生地"},
    {"运动", "体育", "锻炼"},
    {"游戏", "电子游戏"},
    {"出生年", "出生年份"},
    {"女朋友", "女友", "对象"},
    {"男朋友", "男友"},
]

_SUBJ_SYNONYM_MAP: dict[str, set[str]] = {}
for _group in _SUBJECT_SYNONYM_GROUPS:
    for _name in _group:
        _SUBJ_SYNONYM_MAP[_name] = _group

def _get_category_synonyms(category: str) -> set[str]:
    return _CAT_SYNONYM_MAP.get(category, {category})

def _get_subject_synonyms(subject: str) -> set[str]:
    return _SUBJ_SYNONYM_MAP.get(subject, {subject})

def save_raw_conversation(session_id: str, session_created_at,
                          user_input: str, user_input_at,
                          assistant_reply: str, assistant_reply_at):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO raw_conversations "
                "(session_id, session_created_at, user_input, user_input_at, "
                " assistant_reply, assistant_reply_at, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (session_id, session_created_at,
                 user_input, user_input_at,
                 assistant_reply, assistant_reply_at, get_now()),
            )
        conn.commit()
    finally:
        conn.close()

def save_conversation_turn(turn: dict):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO conversation_turns "
                "(session_id, session_created_at, "
                " user_input, user_input_at, assistant_reply, assistant_reply_at, "
                " intent, need_memory, memory_type, ai_summary, perception_at, "
                " memories_used, memories_used_at, "
                " raw_response, raw_response_at, "
                " verification_result, verification_result_at, "
                " final_response, final_response_at, "
                " thinking_notes, thinking_notes_at, "
                " completed_at,"
                " input_type, file_path, file_data, tool_results) "
                "VALUES ("
                " %s, %s, %s, %s, %s, %s, "
                " %s, %s, %s, %s, %s, "
                " %s, %s, "
                " %s, %s, "
                " %s, %s, "
                " %s, %s, "
                " %s, %s, "
                " %s,"
                " %s, %s, %s, %s)",
                (
                    turn["session_id"], turn["session_created_at"],
                    turn["user_input"], turn["user_input_at"],
                    turn["assistant_reply"], turn["assistant_reply_at"],
                    turn.get("intent"), turn.get("need_memory"),
                    turn.get("memory_type"), turn.get("ai_summary"),
                    turn.get("perception_at"),
                    json.dumps(turn.get("memories_used", []), ensure_ascii=False),
                    turn.get("memories_used_at"),
                    turn.get("raw_response"), turn.get("raw_response_at"),
                    turn.get("verification_result"), turn.get("verification_result_at"),
                    turn.get("final_response"), turn.get("final_response_at"),
                    turn.get("thinking_notes"), turn.get("thinking_notes_at"),
                    turn.get("completed_at"),
                    turn.get("input_type", "text"),
                    turn.get("file_path", ""),
                    turn.get("file_data"),
                    json.dumps(turn.get("tool_results", []), ensure_ascii=False),
                ),
            )
        conn.commit()
    finally:
        conn.close()

def save_event(category: str, summary: str, session_id: str | None = None,
               importance: float | None = None, decay_days: int | None = None,
               reference_time=None):
    if importance is None:
        importance = 0.5

    now = reference_time if reference_time else get_now()
    if decay_days and decay_days > 0:
        expires_at = now + timedelta(days=decay_days)
    else:
        expires_at = None

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, summary FROM event_log "
                "WHERE category = %s "
                "AND (expires_at IS NULL OR expires_at > %s) "
                "ORDER BY created_at DESC LIMIT 5",
                (category, now),
            )
            rows = cur.fetchall()

            existing_id = None
            for row_id, row_summary in rows:
                if _is_similar_event(row_summary, summary):
                    existing_id = row_id
                    break

            if existing_id:
                cur.execute(
                    "UPDATE event_log SET expires_at = %s, importance = %s WHERE id = %s",
                    (expires_at, importance, existing_id),
                )
            else:
                cur.execute(
                    "INSERT INTO event_log (category, summary, importance, expires_at, source_session, created_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (category, summary, importance, expires_at, session_id, get_now()),
                )
        conn.commit()
    finally:
        conn.close()

def _is_similar_event(existing: str, new: str) -> bool:
    STOPWORDS = ["用户", "的", "是", "了", "在", "很", "比较", "非常",
                 "喜欢", "感兴趣", "关注", " ", "。", "，"]
    def clean(s):
        s = s.strip()
        for w in STOPWORDS:
            s = s.replace(w, "")
        return s
    a, b = clean(existing), clean(new)
    if not a or not b:
        return True
    return a == b or a in b or b in a

def load_active_events(top_k: int = 10, category: str | None = None) -> list[dict]:
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            conditions = ["(expires_at IS NULL OR expires_at > %s)"]
            params: list = [get_now()]
            if category:
                conditions.append("category = %s")
                params.append(category)
            where = "WHERE " + " AND ".join(conditions)
            params.append(top_k)
            cur.execute(
                f"SELECT id, category, summary, importance, expires_at, created_at "
                f"FROM event_log {where} "
                f"ORDER BY importance DESC, created_at DESC "
                f"LIMIT %s",
                params,
            )
            return list(cur.fetchall())
    finally:
        conn.close()

def save_session_tag(session_id: str, tag: str, summary: str = ""):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO session_tags (session_id, tag, summary, created_at) "
                "VALUES (%s, %s, %s, %s)",
                (session_id, tag, summary, get_now()),
            )
        conn.commit()
    finally:
        conn.close()

def load_existing_tags(limit: int = 50) -> list[str]:
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT tag FROM session_tags "
                "ORDER BY tag LIMIT %s",
                (limit,),
            )
            return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()

def save_session_summary(session_id: str, intent_summary: str):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO session_summaries (session_id, intent_summary, created_at) "
                "VALUES (%s, %s, %s) "
                "ON CONFLICT (session_id) DO UPDATE SET intent_summary = EXCLUDED.intent_summary",
                (session_id, intent_summary, get_now()),
            )
        conn.commit()
    finally:
        conn.close()

def search_sessions_by_tag(tag_keyword: str, limit: int = 10) -> list[dict]:
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT session_id, tag, summary, created_at "
                "FROM session_tags "
                "WHERE tag LIKE %s "
                "ORDER BY created_at DESC LIMIT %s",
                (f"%{tag_keyword}%", limit),
            )
            return list(cur.fetchall())
    finally:
        conn.close()

def save_observation(session_id: str, observation_type: str, content: str,
                     subject: str | None = None, context: str | None = None,
                     source_turn_id: int | None = None):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO observations "
                "(session_id, observation_type, content, subject, context, source_turn_id, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (session_id, observation_type, content, subject, context, source_turn_id, get_now()),
            )
        conn.commit()
    finally:
        conn.close()

def load_observations(session_id: str | None = None, subject: str | None = None,
                      limit: int = 50) -> list[dict]:
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            conditions = ["rejected = false"]
            params: list = []
            if session_id:
                conditions.append("session_id = %s")
                params.append(session_id)
            if subject:
                conditions.append("subject = %s")
                params.append(subject)
            where = "WHERE " + " AND ".join(conditions)
            params.append(limit)
            cur.execute(
                f"SELECT id, session_id, observation_type, content, subject, context, created_at "
                f"FROM observations {where} "
                f"ORDER BY created_at DESC LIMIT %s",
                params,
            )
            return list(cur.fetchall())
    finally:
        conn.close()

def load_observations_by_time_range(pivot_time, keywords: set | None = None,
                                     limit: int = 200) -> dict:
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, session_id, observation_type, content, subject, "
                "context, created_at "
                "FROM observations "
                "WHERE rejected = false "
                "ORDER BY created_at ASC LIMIT %s",
                (limit,),
            )
            all_obs = list(cur.fetchall())
    finally:
        conn.close()

    if keywords:
        filtered = []
        for o in all_obs:
            text = (o.get("content", "") + " " + (o.get("subject", "") or "")).lower()
            if any(kw.lower() in text for kw in keywords if kw and len(kw) >= 2):
                filtered.append(o)
    else:
        filtered = all_obs

    before = []
    after = []
    for o in filtered:
        obs_time = o.get("created_at")
        if not obs_time:
            before.append(o)
            continue
        obs_naive = obs_time.replace(tzinfo=None) if hasattr(obs_time, 'tzinfo') and obs_time.tzinfo else obs_time
        pivot_naive = pivot_time.replace(tzinfo=None) if hasattr(pivot_time, 'tzinfo') and pivot_time.tzinfo else pivot_time
        if obs_naive < pivot_naive:
            before.append(o)
        else:
            after.append(o)

    return {"before": before, "after": after}

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
    if not decay_days or decay_days <= 0:
        decay_days = 365
    expires_at = now + timedelta(days=decay_days)
    confidence = 0.5
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
                        _L = get_labels("context.labels", "zh")
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
                    "confidence = 0.5, mention_count = %s, status = %s, "
                    "last_updated_at = %s, "
                    "decay_days = COALESCE(%s, decay_days), "
                    "expires_at = COALESCE(%s, expires_at) "
                    "WHERE id = %s",
                    (claim, json.dumps(merged_evidence, ensure_ascii=False),
                     new_mention_count, new_status, now,
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
                        "VALUES (%s, %s, %s, %s, 0.5, 1, 'active', %s, %s, %s, %s, %s) "
                        "RETURNING id",
                        (category, subject, claim,
                         json.dumps(evidence_for, ensure_ascii=False),
                         source_type,
                         effective_decay, effective_expires, now, now),
                    )
                    hyp_id = cur.fetchone()[0]
                    conn.commit()
                    return hyp_id
                except Exception:
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
                _L = get_labels("context.labels", "zh")
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

def save_strategy(hypothesis_category: str, hypothesis_subject: str,
                  strategy_type: str, description: str,
                  trigger_condition: str, approach: str,
                  priority: float = 0.5, expires_days: int = 30,
                  reference_time=None):
    now = reference_time if reference_time else get_now()
    expires_at = now + timedelta(days=expires_days) if expires_days > 0 else None
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM strategies "
                "WHERE hypothesis_category = %s AND hypothesis_subject = %s "
                "AND strategy_type = %s AND status = 'pending'",
                (hypothesis_category, hypothesis_subject, strategy_type),
            )
            if cur.fetchone():
                return False

            cur.execute("SELECT COUNT(*) FROM strategies WHERE status = 'pending'")
            if cur.fetchone()[0] >= 30:
                return False

            cur.execute(
                "INSERT INTO strategies "
                "(hypothesis_category, hypothesis_subject, strategy_type, description, "
                " trigger_condition, approach, priority, status, created_at, expires_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending', %s, %s)",
                (hypothesis_category, hypothesis_subject, strategy_type, description,
                 trigger_condition, approach, priority, now, expires_at),
            )
        conn.commit()
        return True
    finally:
        conn.close()

def load_pending_strategies(topic_keywords: list[str] | None = None) -> list[dict]:
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            conditions = [
                "status = 'pending'",
                "(expires_at IS NULL OR expires_at > %s)",
            ]
            params: list = [get_now()]

            if topic_keywords:
                keyword_conditions = []
                for kw in topic_keywords:
                    keyword_conditions.append("trigger_condition LIKE %s")
                    params.append(f"%{kw}%")
                conditions.append("(" + " OR ".join(keyword_conditions) + ")")

            where = "WHERE " + " AND ".join(conditions)
            cur.execute(
                f"SELECT id, hypothesis_category, hypothesis_subject, strategy_type, "
                f"description, trigger_condition, approach, priority "
                f"FROM strategies {where} "
                f"ORDER BY priority DESC",
                params,
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
                conn.commit()
                return rid
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
                    conn.commit()
                    return existing["id"]
                elif existing["category"] in (get_labels("context.labels", "zh").get("interest_category", "兴趣"),):
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
                        conn.commit()
                        return exact_match["id"]
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
                        new_id = cur.fetchone()["id"]
                        conn.commit()
                        return new_id
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
                    new_id = cur.fetchone()["id"]
                    cur.execute(
                        "UPDATE user_profile SET superseded_by = %s WHERE id = %s",
                        (new_id, existing["id"]),
                    )
                    conn.commit()
                    return new_id
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
                new_id = cur.fetchone()["id"]
                conn.commit()
                return new_id
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
                "created_at, updated_at "
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

def load_conversation_summaries_around(pivot_time, limit_before=30, limit_after=50) -> dict:
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT ai_summary, intent, user_input_at, session_id "
                "FROM conversation_turns "
                "WHERE user_input_at < %s AND ai_summary IS NOT NULL "
                "ORDER BY user_input_at DESC LIMIT %s",
                (pivot_time, limit_before),
            )
            before = list(reversed(cur.fetchall()))

            cur.execute(
                "SELECT ai_summary, intent, user_input_at, session_id "
                "FROM conversation_turns "
                "WHERE user_input_at >= %s AND ai_summary IS NOT NULL "
                "ORDER BY user_input_at ASC LIMIT %s",
                (pivot_time, limit_after),
            )
            after = list(cur.fetchall())

        return {"before": before, "after": after}
    finally:
        conn.close()

def load_summaries_by_observation_subject(subject: str, pivot_time=None) -> dict:
    subject_syns = list(_get_subject_synonyms(subject))

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT DISTINCT session_id FROM observations "
                "WHERE rejected = false AND ("
                "   subject = ANY(%s) "
                "   OR subject ILIKE '%%' || %s || '%%' "
                "   OR %s ILIKE '%%' || subject || '%%')",
                (subject_syns, subject, subject),
            )
            session_ids = [r["session_id"] for r in cur.fetchall()]

            if not session_ids:
                return {"before": [], "after": []}

            cur.execute(
                "SELECT ai_summary, intent, user_input_at, session_id "
                "FROM conversation_turns "
                "WHERE session_id = ANY(%s) AND ai_summary IS NOT NULL "
                "ORDER BY user_input_at ASC",
                (session_ids,),
            )
            all_summaries = list(cur.fetchall())
    finally:
        conn.close()

    if not pivot_time:
        return {"before": all_summaries, "after": []}

    before, after = [], []
    for s in all_summaries:
        s_time = s.get("user_input_at")
        if not s_time:
            before.append(s)
            continue
        s_naive = s_time.replace(tzinfo=None) if hasattr(s_time, "tzinfo") and s_time.tzinfo else s_time
        p_naive = pivot_time.replace(tzinfo=None) if hasattr(pivot_time, "tzinfo") and pivot_time.tzinfo else pivot_time
        if s_naive < p_naive:
            before.append(s)
        else:
            after.append(s)
    return {"before": before, "after": after}

_proactive_table_ensured = False

def _ensure_proactive_table():
    global _proactive_table_ensured
    if _proactive_table_ensured:
        return
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS proactive_log (
                    id SERIAL PRIMARY KEY,
                    chat_id BIGINT NOT NULL,
                    trigger_type VARCHAR(50) NOT NULL,
                    trigger_ref TEXT,
                    message_text TEXT NOT NULL,
                    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_proactive_log_chat_sent
                    ON proactive_log (chat_id, sent_at DESC)
            """)
        conn.commit()
        _proactive_table_ensured = True
    finally:
        conn.close()

def save_proactive_log(chat_id: int, trigger_type: str,
                       trigger_ref: str | None, message_text: str):
    _ensure_proactive_table()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO proactive_log (chat_id, trigger_type, trigger_ref, "
                "message_text, sent_at) VALUES (%s, %s, %s, %s, %s)",
                (chat_id, trigger_type, trigger_ref, message_text, get_now()),
            )
        conn.commit()
    finally:
        conn.close()

def load_proactive_log(chat_id: int, since_hours: int = 24) -> list[dict]:
    _ensure_proactive_table()
    since = get_now() - timedelta(hours=since_hours)
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, chat_id, trigger_type, trigger_ref, message_text, sent_at "
                "FROM proactive_log "
                "WHERE chat_id = %s AND sent_at > %s "
                "ORDER BY sent_at DESC",
                (chat_id, since),
            )
            return list(cur.fetchall())
    finally:
        conn.close()

def get_last_interaction_time(session_id: str):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT MAX(user_input_at) FROM conversation_turns "
                "WHERE session_id = %s",
                (session_id,),
            )
            row = cur.fetchone()
            return row[0] if row and row[0] else None
    finally:
        conn.close()

def mark_strategy_executed(strategy_id: int, result: str):
    now = get_now()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE strategies SET status = 'executed', result = %s, executed_at = %s "
                "WHERE id = %s",
                (result, now, strategy_id),
            )
        conn.commit()
    finally:
        conn.close()

_finance_tables_ensured = False

def _ensure_finance_tables():
    global _finance_tables_ensured
    if _finance_tables_ensured:
        return
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS finance_transactions (
                    id SERIAL PRIMARY KEY,
                    transaction_date TIMESTAMPTZ NOT NULL,
                    merchant TEXT NOT NULL,
                    amount NUMERIC(12, 2) NOT NULL,
                    currency VARCHAR(8) NOT NULL DEFAULT 'JPY',
                    amount_jpy NUMERIC(12, 2),
                    category TEXT,
                    card_name TEXT DEFAULT 'credit_card',
                    email_id TEXT UNIQUE,
                    note TEXT,
                    metadata JSONB DEFAULT '{}',
                    imported_at TIMESTAMPTZ DEFAULT NOW(),
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_ft_date
                    ON finance_transactions(transaction_date DESC)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_ft_merchant
                    ON finance_transactions(merchant)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_ft_category
                    ON finance_transactions(category)
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS finance_merchant_categories (
                    id SERIAL PRIMARY KEY,
                    merchant_pattern TEXT NOT NULL UNIQUE,
                    category TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            defaults = [
                ("イオン", "食品"), ("セリア", "日用品"),
                ("AMAZON", "网购"), ("CLAUDE.AI", "订阅"),
                ("OPENAI", "订阅"), ("NETFLIX", "订阅"),
                ("SPOTIFY", "订阅"), ("JR ", "交通"),
                ("SUICA", "交通"), ("スターバックス", "餐饮"),
                ("マクドナルド", "餐饮"), ("ユニクロ", "衣服"),
            ]
            for pattern, cat in defaults:
                cur.execute(
                    "INSERT INTO finance_merchant_categories (merchant_pattern, category) "
                    "VALUES (%s, %s) ON CONFLICT (merchant_pattern) DO NOTHING",
                    (pattern, cat),
                )
        conn.commit()
        _finance_tables_ensured = True
    finally:
        conn.close()

def parse_smcc_email(email_body: str) -> dict | None:
    if not email_body:
        return None

    date_match = re.search(r'◇利用日[：:\s]*(\d{4}/\d{1,2}/\d{1,2})', email_body)
    if not date_match:
        return None

    merchant_match = re.search(r'◇利用先[：:\s]*(.+?)[\r\n]', email_body)
    if not merchant_match:
        return None

    amount_match = re.search(
        r'◇利用金額[：:\s]*([\d,]+(?:\.\d+)?)\s*(円|JPY|USD|EUR|GBP|CNY)',
        email_body, re.IGNORECASE
    )
    if not amount_match:
        return None

    date_str = date_match.group(1)
    merchant = merchant_match.group(1).strip()
    amount_str = amount_match.group(1).replace(",", "")
    currency_raw = amount_match.group(2)

    currency = "JPY" if currency_raw in ("円", "JPY") else currency_raw.upper()

    try:
        txn_date = datetime.strptime(date_str, "%Y/%m/%d")
    except ValueError:
        return None

    try:
        amount = Decimal(amount_str)
    except Exception:
        return None

    return {
        "date": txn_date,
        "merchant": merchant,
        "amount": amount,
        "currency": currency,
    }

def _normalize_fullwidth(text: str) -> str:
    result = []
    for ch in text:
        cp = ord(ch)
        if 0xFF01 <= cp <= 0xFF5E:
            result.append(chr(cp - 0xFEE0))
        elif cp == 0x3000:
            result.append(' ')
        else:
            result.append(ch)
    return ''.join(result)

def _auto_categorize_merchant(merchant: str) -> str | None:
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT merchant_pattern, category "
                "FROM finance_merchant_categories ORDER BY id"
            )
            rows = cur.fetchall()
            merchant_normalized = _normalize_fullwidth(merchant).upper()
            for pattern, category in rows:
                if _normalize_fullwidth(pattern).upper() in merchant_normalized:
                    return category
            return None
    finally:
        conn.close()

def save_finance_transaction(
    transaction_date, merchant: str, amount,
    currency: str = "JPY", amount_jpy=None,
    category: str | None = None,
    card_name: str = "credit_card",
    email_id: str | None = None,
    note: str | None = None,
    metadata: dict | None = None,
) -> int | None:
    _ensure_finance_tables()
    if not category:
        category = _auto_categorize_merchant(merchant)
    if currency == "JPY" and amount_jpy is None:
        amount_jpy = amount

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    "INSERT INTO finance_transactions "
                    "(transaction_date, merchant, amount, currency, amount_jpy, "
                    " category, card_name, email_id, note, metadata, "
                    " imported_at, created_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                    "RETURNING id",
                    (transaction_date, merchant, amount, currency, amount_jpy,
                     category, card_name, email_id, note,
                     json.dumps(metadata or {}, ensure_ascii=False),
                     get_now(), get_now()),
                )
                txn_id = cur.fetchone()[0]
                conn.commit()
                return txn_id
            except psycopg2.errors.UniqueViolation:
                conn.rollback()
                return None
    finally:
        conn.close()

def load_finance_transactions(
    year: int | None = None,
    month: int | None = None,
    day: int | None = None,
    category: str | None = None,
    merchant: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    _ensure_finance_tables()
    conditions = []
    params: list = []

    if year:
        conditions.append("EXTRACT(YEAR FROM transaction_date) = %s")
        params.append(year)
    if month:
        conditions.append("EXTRACT(MONTH FROM transaction_date) = %s")
        params.append(month)
    if day:
        conditions.append("EXTRACT(DAY FROM transaction_date) = %s")
        params.append(day)
    if category:
        conditions.append("category = %s")
        params.append(category)
    if merchant:
        conditions.append("merchant ILIKE %s")
        params.append(f"%{merchant}%")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params.extend([limit, offset])

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"SELECT id, transaction_date, merchant, amount, currency, "
                f"amount_jpy, category, card_name, email_id, note, metadata, "
                f"imported_at, created_at "
                f"FROM finance_transactions {where} "
                f"ORDER BY transaction_date DESC "
                f"LIMIT %s OFFSET %s",
                params,
            )
            return list(cur.fetchall())
    finally:
        conn.close()

def update_finance_transaction(txn_id: int, category: str | None = None,
                                note: str | None = None) -> bool:
    _ensure_finance_tables()
    updates = []
    params: list = []
    if category is not None:
        updates.append("category = %s")
        params.append(category)
    if note is not None:
        updates.append("note = %s")
        params.append(note)
    if not updates:
        return False
    params.append(txn_id)

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE finance_transactions SET {', '.join(updates)} "
                f"WHERE id = %s",
                params,
            )
            updated = cur.rowcount > 0
        conn.commit()
        return updated
    finally:
        conn.close()

def get_finance_summary(
    group_by: str = "month",
    year: int | None = None,
    month: int | None = None,
) -> list[dict]:
    _ensure_finance_tables()
    conditions = []
    params: list = []

    if year:
        conditions.append("EXTRACT(YEAR FROM transaction_date) = %s")
        params.append(year)
    if month:
        conditions.append("EXTRACT(MONTH FROM transaction_date) = %s")
        params.append(month)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    if group_by == "year":
        group_expr = "EXTRACT(YEAR FROM transaction_date)"
        label_expr = "EXTRACT(YEAR FROM transaction_date)::int AS period"
        order = "period DESC"
    elif group_by == "day":
        group_expr = "transaction_date::date"
        label_expr = "transaction_date::date AS period"
        order = "period DESC"
    else:
        group_expr = "DATE_TRUNC('month', transaction_date)"
        label_expr = "TO_CHAR(DATE_TRUNC('month', transaction_date), 'YYYY-MM') AS period"
        order = "period DESC"

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"SELECT {label_expr}, "
                f"COUNT(*) AS count, "
                f"SUM(COALESCE(amount_jpy, amount)) AS total_jpy "
                f"FROM finance_transactions {where} "
                f"GROUP BY {group_expr} ORDER BY {order}",
                params,
            )
            summaries = list(cur.fetchall())

            for s in summaries:
                period_val = s["period"]
                if group_by == "year":
                    cat_cond = "EXTRACT(YEAR FROM transaction_date) = %s"
                    cat_params = [period_val]
                elif group_by == "day":
                    cat_cond = "transaction_date::date = %s"
                    cat_params = [period_val]
                else:
                    cat_cond = "TO_CHAR(DATE_TRUNC('month', transaction_date), 'YYYY-MM') = %s"
                    cat_params = [str(period_val)]

                extra_conds = conditions.copy()
                extra_params = params.copy()

                _uncategorized = get_labels("context.labels", "zh").get("uncategorized", "未分类")
                cur.execute(
                    f"SELECT COALESCE(category, %s) AS category, "
                    f"COUNT(*) AS count, "
                    f"SUM(COALESCE(amount_jpy, amount)) AS total_jpy "
                    f"FROM finance_transactions "
                    f"WHERE {cat_cond} "
                    f"GROUP BY category ORDER BY total_jpy DESC",
                    [_uncategorized] + cat_params,
                )
                s["categories"] = list(cur.fetchall())

            return summaries
    finally:
        conn.close()

def get_finance_merchant_stats(
    year: int | None = None,
    month: int | None = None,
    limit: int = 20,
) -> list[dict]:
    _ensure_finance_tables()
    conditions = []
    params: list = []

    if year:
        conditions.append("EXTRACT(YEAR FROM transaction_date) = %s")
        params.append(year)
    if month:
        conditions.append("EXTRACT(MONTH FROM transaction_date) = %s")
        params.append(month)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params.append(limit)

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"SELECT merchant, "
                f"COUNT(*) AS count, "
                f"SUM(COALESCE(amount_jpy, amount)) AS total_jpy, "
                f"MAX(category) AS category "
                f"FROM finance_transactions {where} "
                f"GROUP BY merchant ORDER BY total_jpy DESC "
                f"LIMIT %s",
                params,
            )
            return list(cur.fetchall())
    finally:
        conn.close()

def get_finance_category_stats(
    year: int | None = None,
    month: int | None = None,
) -> list[dict]:
    _ensure_finance_tables()
    conditions = []
    params: list = []

    if year:
        conditions.append("EXTRACT(YEAR FROM transaction_date) = %s")
        params.append(year)
    if month:
        conditions.append("EXTRACT(MONTH FROM transaction_date) = %s")
        params.append(month)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    conn = get_db_connection()
    try:
        _uncategorized = get_labels("context.labels", "zh").get("uncategorized", "未分类")
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"SELECT COALESCE(category, %s) AS category, "
                f"COUNT(*) AS count, "
                f"SUM(COALESCE(amount_jpy, amount)) AS total_jpy "
                f"FROM finance_transactions {where} "
                f"GROUP BY category ORDER BY total_jpy DESC",
                [_uncategorized] + params,
            )
            return list(cur.fetchall())
    finally:
        conn.close()

def get_finance_overview() -> dict:
    _ensure_finance_tables()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM finance_transactions")
            total_count = cur.fetchone()[0]
            cur.execute("SELECT COALESCE(SUM(COALESCE(amount_jpy, amount)), 0) FROM finance_transactions")
            total_amount = cur.fetchone()[0]
            cur.execute("SELECT COUNT(DISTINCT merchant) FROM finance_transactions")
            merchant_count = cur.fetchone()[0]
            cur.execute("SELECT MIN(transaction_date), MAX(transaction_date) FROM finance_transactions")
            row = cur.fetchone()
            date_from = row[0]
            date_to = row[1]
            return {
                "total_count": total_count,
                "total_amount": float(total_amount) if total_amount else 0,
                "merchant_count": merchant_count,
                "date_from": date_from.isoformat() if date_from else None,
                "date_to": date_to.isoformat() if date_to else None,
            }
    finally:
        conn.close()

def get_last_import_date() -> str | None:
    _ensure_finance_tables()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT MAX(transaction_date) FROM finance_transactions"
            )
            row = cur.fetchone()
            if row and row[0]:
                d = row[0] - timedelta(days=3)
                return d.strftime("%Y/%m/%d")
            return None
    finally:
        conn.close()

def get_imported_email_ids() -> set[str]:
    _ensure_finance_tables()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT email_id FROM finance_transactions "
                "WHERE email_id IS NOT NULL"
            )
            return {row[0] for row in cur.fetchall()}
    finally:
        conn.close()

def import_finance_from_email(email_id: str, email_subject: str,
                               email_body: str) -> dict:
    parsed = parse_smcc_email(email_body)
    if not parsed:
        return {"success": False, "duplicate": False, "parsed": None,
                "error": get_labels("context.labels", "zh")["parse_failed"]}

    txn_id = save_finance_transaction(
        transaction_date=parsed["date"],
        merchant=parsed["merchant"],
        amount=parsed["amount"],
        currency=parsed["currency"],
        email_id=email_id,
        metadata={"email_subject": email_subject},
    )

    if txn_id is None:
        return {"success": False, "duplicate": True, "parsed": parsed,
                "transaction_id": None}

    return {"success": True, "duplicate": False, "parsed": parsed,
            "transaction_id": txn_id}

def save_merchant_category(merchant_pattern: str, category: str) -> int:
    _ensure_finance_tables()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO finance_merchant_categories (merchant_pattern, category) "
                "VALUES (%s, %s) "
                "ON CONFLICT (merchant_pattern) DO UPDATE SET category = EXCLUDED.category "
                "RETURNING id",
                (merchant_pattern, category),
            )
            mid = cur.fetchone()[0]
        conn.commit()
        return mid
    finally:
        conn.close()

def load_merchant_categories() -> list[dict]:
    _ensure_finance_tables()
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, merchant_pattern, category, created_at "
                "FROM finance_merchant_categories ORDER BY id"
            )
            return list(cur.fetchall())
    finally:
        conn.close()

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

def load_withings_tokens() -> dict | None:
    _ensure_health_tables()
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
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
                           days: int = 90) -> list[dict]:
    _ensure_health_tables()
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            conditions = []
            params = []
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

def load_withings_activity(days: int = 90) -> list[dict]:
    _ensure_health_tables()
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            conditions = []
            params = []
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

def load_withings_sleep(days: int = 90) -> list[dict]:
    _ensure_health_tables()
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            conditions = []
            params = []
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

def get_health_overview() -> dict:
    _ensure_health_tables()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM withings_measures")
            total_measures = cur.fetchone()[0]

            cur.execute(
                "SELECT value FROM withings_measures "
                "WHERE measure_type = 1 ORDER BY measured_at DESC LIMIT 1"
            )
            row = cur.fetchone()
            latest_weight = float(row[0]) if row else None

            cur.execute("SELECT COUNT(*) FROM withings_activity")
            activity_days = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM withings_sleep")
            sleep_days = cur.fetchone()[0]

            cur.execute(
                "SELECT COALESCE(AVG(steps), 0) FROM withings_activity "
                "WHERE activity_date >= %s",
                ((get_now() - timedelta(days=30)).date(),),
            )
            avg_steps_30d = round(float(cur.fetchone()[0]))

            cur.execute(
                "SELECT COALESCE(AVG(sleep_score), 0) FROM withings_sleep "
                "WHERE sleep_date >= %s AND sleep_score IS NOT NULL",
                ((get_now() - timedelta(days=30)).date(),),
            )
            avg_sleep_score_30d = round(float(cur.fetchone()[0]))

            cur.execute(
                "SELECT expires_at FROM withings_tokens "
                "ORDER BY updated_at DESC LIMIT 1"
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


def save_memory_snapshot(text: str, profile_count: int = 0):
    """保存预编译的记忆快照"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "CREATE TABLE IF NOT EXISTS memory_snapshot ("
                "  id SERIAL PRIMARY KEY,"
                "  snapshot_text TEXT NOT NULL,"
                "  profile_count INTEGER DEFAULT 0,"
                "  created_at TIMESTAMPTZ DEFAULT NOW()"
                ")"
            )
            cur.execute(
                "INSERT INTO memory_snapshot (snapshot_text, profile_count) "
                "VALUES (%s, %s)",
                (text, profile_count),
            )
        conn.commit()
    finally:
        conn.close()


def load_memory_snapshot() -> dict | None:
    """加载最新快照，返回 {"snapshot_text": str, "profile_count": int, "created_at": datetime}"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                cur.execute(
                    "SELECT snapshot_text, profile_count, created_at "
                    "FROM memory_snapshot ORDER BY id DESC LIMIT 1"
                )
            except Exception:
                conn.rollback()
                return None
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def save_fact_edge(source_fact_id: int, target_fact_id: int,
                   edge_type: str, description: str = "",
                   confidence: float = 0.8) -> int:
    now = get_now()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO fact_edges "
                "(source_fact_id, target_fact_id, edge_type, description, confidence, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (source_fact_id, target_fact_id, edge_type) DO UPDATE "
                "SET description = EXCLUDED.description, confidence = EXCLUDED.confidence, "
                "updated_at = EXCLUDED.updated_at "
                "RETURNING id",
                (source_fact_id, target_fact_id, edge_type, description, confidence, now, now),
            )
            row = cur.fetchone()
            edge_id = row[0] if row else -1
        conn.commit()
        return edge_id
    except Exception:
        conn.rollback()
        return -1
    finally:
        conn.close()


def load_fact_edges(fact_ids: list[int] | None = None) -> list[dict]:
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                if fact_ids:
                    cur.execute(
                        "SELECT fe.id, fe.source_fact_id, fe.target_fact_id, "
                        "fe.edge_type, fe.description, fe.confidence, "
                        "src.category AS src_category, src.subject AS src_subject, "
                        "tgt.category AS tgt_category, tgt.subject AS tgt_subject "
                        "FROM fact_edges fe "
                        "JOIN user_profile src ON fe.source_fact_id = src.id "
                        "JOIN user_profile tgt ON fe.target_fact_id = tgt.id "
                        "WHERE fe.source_fact_id = ANY(%s) OR fe.target_fact_id = ANY(%s) "
                        "ORDER BY fe.confidence DESC, fe.updated_at DESC",
                        (fact_ids, fact_ids),
                    )
                else:
                    cur.execute(
                        "SELECT fe.id, fe.source_fact_id, fe.target_fact_id, "
                        "fe.edge_type, fe.description, fe.confidence, "
                        "src.category AS src_category, src.subject AS src_subject, "
                        "tgt.category AS tgt_category, tgt.subject AS tgt_subject "
                        "FROM fact_edges fe "
                        "JOIN user_profile src ON fe.source_fact_id = src.id "
                        "JOIN user_profile tgt ON fe.target_fact_id = tgt.id "
                        "ORDER BY fe.confidence DESC, fe.updated_at DESC "
                        "LIMIT 50"
                    )
                return [dict(r) for r in cur.fetchall()]
            except Exception:
                conn.rollback()
                return []
    finally:
        conn.close()


def delete_fact_edges_for(fact_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    "DELETE FROM fact_edges WHERE source_fact_id = %s OR target_fact_id = %s",
                    (fact_id, fact_id),
                )
            except Exception:
                conn.rollback()
                return
        conn.commit()
    finally:
        conn.close()
