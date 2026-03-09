"""Storage integration tests — requires PostgreSQL, no LLM.

Uses SAVEPOINT/ROLLBACK isolation: each test runs inside a savepoint
that is rolled back after completion, leaving the database clean.

Usage:
    python -m pytest tests/test_storage.py -v
    python tests/test_storage.py
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── DB availability check ────────────────────────────────

try:
    import psycopg2
    from agent.storage._db import _get_db_config, _thread_local
    _test_conn = psycopg2.connect(**_get_db_config())
    _test_conn.close()
    DB_AVAILABLE = True
except Exception:
    DB_AVAILABLE = False

try:
    import pytest
    _skip = pytest.mark.skipif(not DB_AVAILABLE, reason="PostgreSQL not available")
except ImportError:
    pytest = None
    _skip = lambda cls: cls  # noqa: E731


# ── Base test class with SAVEPOINT isolation ─────────────

class _DBTestBase:
    """Injects a shared connection via _thread_local.conn + SAVEPOINT."""

    def setup_method(self):
        if not DB_AVAILABLE:
            return
        self.conn = psycopg2.connect(**_get_db_config())
        self.conn.autocommit = False
        _thread_local.conn = self.conn
        with self.conn.cursor() as cur:
            cur.execute("SAVEPOINT test_sp")

    def teardown_method(self):
        if not DB_AVAILABLE:
            return
        try:
            with self.conn.cursor() as cur:
                cur.execute("ROLLBACK TO SAVEPOINT test_sp")
        except Exception:
            pass
        _thread_local.conn = None
        try:
            self.conn.close()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════
#  Profile Fact lifecycle
# ═══════════════════════════════════════════════════════════

from agent.storage import (
    save_profile_fact,
    find_current_fact,
    load_disputed_facts,
    resolve_dispute,
    confirm_profile_fact,
    get_expired_facts,
    load_full_current_profile,
    save_fact_edge,
    load_fact_edges,
    save_observation,
    load_observations,
    save_hypothesis,
    load_active_hypotheses,
    get_hypothesis_by_subject,
    resolve_suspicion,
    set_hypothesis_status,
)


@_skip
class TestProfileFacts(_DBTestBase):

    def test_save_and_load_roundtrip(self):
        fid = save_profile_fact("位置", "居住地", "深圳", source_type="stated")
        fact = find_current_fact("位置", "居住地")
        assert fact is not None
        assert fact["value"] == "深圳"
        assert fact["id"] == fid

    def test_same_value_increments_mention(self):
        fid = save_profile_fact("位置", "居住地", "北京")
        save_profile_fact("位置", "居住地", "北京")
        fact = find_current_fact("位置", "居住地")
        assert fact["mention_count"] == 2
        assert fact["id"] == fid  # same row

    def test_evidence_merged_on_repeat(self):
        save_profile_fact("位置", "居住地", "上海",
                         evidence=[{"observation": "第一次说"}])
        save_profile_fact("位置", "居住地", "上海",
                         evidence=[{"observation": "第二次说"}])
        fact = find_current_fact("位置", "居住地")
        assert len(fact["evidence"]) == 2

    def test_different_value_creates_supersede(self):
        old_id = save_profile_fact("位置", "居住地", "深圳")
        new_id = save_profile_fact("位置", "居住地", "北京")
        assert new_id != old_id
        # old should have superseded_by = new_id
        profile = load_full_current_profile(exclude_superseded=False)
        old_facts = [f for f in profile if f["id"] == old_id]
        assert len(old_facts) == 1
        assert old_facts[0]["superseded_by"] == new_id

    def test_load_disputed_facts_returns_pair(self):
        old_id = save_profile_fact("位置", "居住地", "深圳")
        new_id = save_profile_fact("位置", "居住地", "北京")
        pairs = load_disputed_facts()
        matching = [p for p in pairs
                    if p["old"]["id"] == old_id and p["new"]["id"] == new_id]
        assert len(matching) == 1

    def test_resolve_dispute_accept_new(self):
        old_id = save_profile_fact("位置", "居住地", "深圳")
        new_id = save_profile_fact("位置", "居住地", "北京")
        resolve_dispute(old_id, new_id, accept_new=True)
        # After accept: old gets end_time (removed from current), new stays
        profile = load_full_current_profile(exclude_superseded=True)
        our_ids = {f["id"] for f in profile}
        assert new_id in our_ids
        assert old_id not in our_ids

    def test_resolve_dispute_reject_new(self):
        old_id = save_profile_fact("位置", "居住地", "深圳")
        new_id = save_profile_fact("位置", "居住地", "北京")
        resolve_dispute(old_id, new_id, accept_new=False)
        # After reject: new gets end_time, old's superseded_by cleared
        profile = load_full_current_profile(exclude_superseded=True)
        our_ids = {f["id"] for f in profile}
        assert old_id in our_ids
        assert new_id not in our_ids

    def test_confirm_profile_fact(self):
        fid = save_profile_fact("职业", "工作", "工程师")
        confirm_profile_fact(fid)
        fact = find_current_fact("职业", "工作")
        assert fact["layer"] == "confirmed"

    def test_find_current_fact_synonym_match(self):
        save_profile_fact("位置", "居住地", "广州")
        # "居住城市" is a synonym of "居住地"
        fact = find_current_fact("位置", "居住城市")
        assert fact is not None
        assert fact["value"] == "广州"

    def test_get_expired_facts(self):
        now = datetime.now(timezone.utc)
        fid = save_profile_fact("位置", "居住地", "深圳",
                               decay_days=1, start_time=now - timedelta(days=10))
        expired = get_expired_facts(reference_time=now)
        expired_ids = [f["id"] for f in expired]
        assert fid in expired_ids

    def test_interest_category_no_supersede(self):
        id1 = save_profile_fact("兴趣", "运动", "篮球")
        id2 = save_profile_fact("兴趣", "运动", "足球")
        # Both should exist as separate facts, no supersede
        profile = load_full_current_profile(exclude_superseded=False)
        interest_facts = [f for f in profile
                         if f["category"] == "兴趣" and f["subject"] == "运动"]
        values = {f["value"] for f in interest_facts}
        assert "篮球" in values
        assert "足球" in values
        # Neither should have superseded_by
        for f in interest_facts:
            assert f.get("superseded_by") is None


# ═══════════════════════════════════════════════════════════
#  Fact Edges
# ═══════════════════════════════════════════════════════════

@_skip
class TestFactEdges(_DBTestBase):

    def setup_method(self):
        super().setup_method()
        if not DB_AVAILABLE:
            return
        # Ensure schema has columns the code expects
        with self.conn.cursor() as cur:
            cur.execute(
                "ALTER TABLE fact_edges "
                "ADD COLUMN IF NOT EXISTS confidence FLOAT DEFAULT 0.8"
            )
            cur.execute(
                "ALTER TABLE fact_edges "
                "ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()"
            )

    def test_save_and_load_roundtrip(self):
        src = save_profile_fact("位置", "居住地", "深圳")
        tgt = save_profile_fact("职业", "工作", "程序员")
        eid = save_fact_edge(src, tgt, "related", "lives near work", 0.9)
        assert eid > 0
        edges = load_fact_edges(fact_ids=[src])
        assert len(edges) >= 1
        e = [e for e in edges if e["id"] == eid][0]
        assert e["edge_type"] == "related"

    def test_upsert_no_duplicate(self):
        src = save_profile_fact("位置", "居住地", "北京")
        tgt = save_profile_fact("职业", "工作", "设计师")
        eid1 = save_fact_edge(src, tgt, "related", "desc1")
        eid2 = save_fact_edge(src, tgt, "related", "desc2")
        # ON CONFLICT → same row updated
        assert eid1 == eid2
        edges = load_fact_edges(fact_ids=[src])
        matching = [e for e in edges if e["id"] == eid1]
        assert matching[0]["description"] == "desc2"

    def test_fact_ids_filter(self):
        src = save_profile_fact("位置", "居住地", "上海")
        tgt = save_profile_fact("职业", "工作", "产品经理")
        other_src = save_profile_fact("教育", "学校", "北大")
        other_tgt = save_profile_fact("教育", "专业", "计算机")
        save_fact_edge(src, tgt, "related")
        save_fact_edge(other_src, other_tgt, "related")
        edges = load_fact_edges(fact_ids=[src, tgt])
        # Should only include edges touching src or tgt
        for e in edges:
            assert e["source_fact_id"] in (src, tgt) or e["target_fact_id"] in (src, tgt)

    def test_different_edge_types(self):
        src = save_profile_fact("位置", "居住地", "成都")
        tgt = save_profile_fact("兴趣", "美食", "火锅")
        eid1 = save_fact_edge(src, tgt, "causes")
        eid2 = save_fact_edge(src, tgt, "related")
        assert eid1 != eid2  # different edge_type → different row


# ═══════════════════════════════════════════════════════════
#  Observations
# ═══════════════════════════════════════════════════════════

@_skip
class TestObservations(_DBTestBase):

    def test_save_and_load_roundtrip(self):
        save_observation("sess-1", "behavior", "用户提到喜欢咖啡",
                        subject="饮食")
        obs = load_observations(session_id="sess-1")
        assert len(obs) >= 1
        assert obs[0]["content"] == "用户提到喜欢咖啡"

    def test_session_id_filter(self):
        save_observation("sess-A", "behavior", "观察A")
        save_observation("sess-B", "behavior", "观察B")
        obs_a = load_observations(session_id="sess-A")
        obs_b = load_observations(session_id="sess-B")
        assert all(o["session_id"] == "sess-A" for o in obs_a)
        assert all(o["session_id"] == "sess-B" for o in obs_b)

    def test_subject_filter(self):
        save_observation("sess-1", "behavior", "喜欢编程", subject="技能")
        save_observation("sess-1", "behavior", "喜欢篮球", subject="运动")
        obs = load_observations(subject="技能")
        assert all(o["subject"] == "技能" for o in obs)


# ═══════════════════════════════════════════════════════════
#  Hypothesis state machine
# ═══════════════════════════════════════════════════════════

@_skip
class TestHypothesisStateMachine(_DBTestBase):

    def test_new_hypothesis_creates_active(self):
        hid = save_hypothesis("位置", "居住地", "北京")
        h = get_hypothesis_by_subject("位置", "居住地")
        assert h is not None
        assert h["status"] == "active"
        assert h["claim"] == "北京"
        assert h["mention_count"] == 1

    def test_same_claim_increments_mention(self):
        hid = save_hypothesis("位置", "居住地", "北京")
        save_hypothesis("位置", "居住地", "北京")
        h = get_hypothesis_by_subject("位置", "居住地")
        assert h["mention_count"] == 2
        assert h["status"] == "active"
        assert h["id"] == hid

    def test_different_claim_enters_suspected(self):
        hid = save_hypothesis("位置", "居住地", "北京")
        save_hypothesis("位置", "居住地", "上海")
        h = get_hypothesis_by_subject("位置", "居住地")
        assert h["status"] == "suspected"
        assert h["suspected_value"] == "上海"
        assert h["claim"] == "北京"  # original unchanged

    def test_suspected_repeat_adds_evidence(self):
        hid = save_hypothesis("位置", "居住地", "北京")
        save_hypothesis("位置", "居住地", "上海")
        save_hypothesis("位置", "居住地", "上海")  # third mention of new value
        h = get_hypothesis_by_subject("位置", "居住地")
        assert h["status"] == "suspected"
        assert len(h["suspected_evidence"]) >= 1

    def test_resolve_suspicion_accept(self):
        hid = save_hypothesis("位置", "居住地", "北京")
        save_hypothesis("位置", "居住地", "北京")
        save_hypothesis("位置", "居住地", "北京")  # mention_count=3
        save_hypothesis("位置", "居住地", "上海")  # enters suspected
        resolve_suspicion(hid, accept=True)
        h = get_hypothesis_by_subject("位置", "居住地")
        assert h["claim"] == "上海"  # new value is now the claim
        assert h["status"] == "active"
        assert h["mention_count"] == 2  # reset for new claim
        assert h["suspected_value"] is None
        # old value archived in history
        assert len(h["history"]) == 1
        assert h["history"][0]["value"] == "北京"
        assert h["history"][0]["mention_count"] == 3

    def test_resolve_suspicion_reject(self):
        hid = save_hypothesis("位置", "居住地", "北京")
        save_hypothesis("位置", "居住地", "北京")  # mention_count=2
        save_hypothesis("位置", "居住地", "上海")  # enters suspected
        resolve_suspicion(hid, accept=False)
        h = get_hypothesis_by_subject("位置", "居住地")
        assert h["claim"] == "北京"  # original restored
        assert h["status"] == "active"  # mention_count=2 → active
        assert h["suspected_value"] is None
        # rejected evidence merged into evidence_against
        assert h["evidence_against"] is not None

    def test_resolve_suspicion_reject_high_mention_restores_established(self):
        hid = save_hypothesis("位置", "居住地", "北京")
        for _ in range(4):  # total mention_count = 5
            save_hypothesis("位置", "居住地", "北京")
        save_hypothesis("位置", "居住地", "上海")  # enters suspected
        resolve_suspicion(hid, accept=False)
        h = get_hypothesis_by_subject("位置", "居住地")
        assert h["status"] == "established"  # mention_count >= 4

    def test_dormant_reactivation(self):
        hid = save_hypothesis("位置", "居住地", "北京")
        set_hypothesis_status(hid, "dormant")
        # dormant is excluded from get_hypothesis_by_subject
        h = get_hypothesis_by_subject("位置", "居住地")
        assert h is None
        # re-mentioning same claim reactivates
        save_hypothesis("位置", "居住地", "北京")
        h = get_hypothesis_by_subject("位置", "居住地")
        assert h is not None
        assert h["status"] == "active"
        assert h["mention_count"] == 2


# ═══════════════════════════════════════════════════════════
#  _find_current_fact_cursor fuzzy match
# ═══════════════════════════════════════════════════════════

@_skip
class TestFindCurrentFactFuzzy(_DBTestBase):

    def test_exact_match(self):
        save_profile_fact("位置", "居住地", "东京")
        fact = find_current_fact("位置", "居住地")
        assert fact is not None
        assert fact["value"] == "东京"

    def test_synonym_match(self):
        save_profile_fact("位置", "居住地", "大阪")
        fact = find_current_fact("位置", "居住城市")
        assert fact is not None
        assert fact["value"] == "大阪"

    def test_ilike_match_substring(self):
        """subject '居住地' should match query '居住地点' via ILIKE."""
        save_profile_fact("位置", "居住地", "名古屋")
        fact = find_current_fact("位置", "居住地点")
        assert fact is not None
        assert fact["value"] == "名古屋"

    def test_no_cross_category_fuzzy(self):
        """Fuzzy match should not cross unrelated categories."""
        save_profile_fact("位置", "居住地", "北京")
        # 完全不同的 category，subject 也不相关
        fact = find_current_fact("职业", "公司")
        assert fact is None

    def test_no_false_positive_short_subject(self):
        """Short subjects like '名' should not match '姓名' in different categories."""
        save_profile_fact("基本信息", "姓名", "张三")
        # '名' is substring of '姓名', but different category should prevent match
        fact = find_current_fact("兴趣", "名")
        assert fact is None

    def test_closed_fact_not_returned(self):
        """Facts with end_time should not be found."""
        from agent.storage import close_time_period
        fid = save_profile_fact("位置", "居住地", "深圳")
        close_time_period(fid)
        fact = find_current_fact("位置", "居住地")
        assert fact is None

    def test_superseded_fact_still_findable(self):
        """Superseded facts (no end_time) should still be found."""
        old_id = save_profile_fact("位置", "居住地", "深圳")
        new_id = save_profile_fact("位置", "居住地", "北京")
        fact = find_current_fact("位置", "居住地")
        # Should return the one without superseded_by first
        assert fact is not None
        assert fact["id"] == new_id


# ═══════════════════════════════════════════════════════════
#  Interest category multi-value paths
# ═══════════════════════════════════════════════════════════

@_skip
class TestInterestMultiValue(_DBTestBase):

    def test_interest_same_value_increments_mention(self):
        """Writing the same interest value twice should increment, not create duplicate."""
        id1 = save_profile_fact("兴趣", "运动", "篮球")
        id2 = save_profile_fact("兴趣", "运动", "篮球")
        assert id1 == id2
        fact = find_current_fact("兴趣", "运动")
        assert fact["mention_count"] == 2

    def test_interest_exact_match_updates_existing(self):
        """Third distinct value should match its own row, not the first-found."""
        save_profile_fact("兴趣", "运动", "篮球")
        save_profile_fact("兴趣", "运动", "足球")
        save_profile_fact("兴趣", "运动", "篮球")  # re-mention first value
        profile = load_full_current_profile(exclude_superseded=False)
        basketball = [f for f in profile
                      if f["category"] == "兴趣" and f["value"] == "篮球"]
        assert len(basketball) == 1
        assert basketball[0]["mention_count"] == 2

    def test_interest_different_values_coexist(self):
        """Multiple distinct interest values should all remain active."""
        save_profile_fact("兴趣", "运动", "篮球")
        save_profile_fact("兴趣", "运动", "足球")
        save_profile_fact("兴趣", "运动", "游泳")
        profile = load_full_current_profile(exclude_superseded=False)
        interests = [f for f in profile
                     if f["category"] == "兴趣" and f["subject"] == "运动"
                     and f.get("end_time") is None]
        values = {f["value"] for f in interests}
        assert values == {"篮球", "足球", "游泳"}

    def test_interest_no_supersede_chain(self):
        """Interest facts should never have superseded_by set."""
        save_profile_fact("兴趣", "运动", "篮球")
        save_profile_fact("兴趣", "运动", "足球")
        profile = load_full_current_profile(exclude_superseded=False)
        interests = [f for f in profile
                     if f["category"] == "兴趣" and f["subject"] == "运动"]
        for f in interests:
            assert f.get("superseded_by") is None


# ═══════════════════════════════════════════════════════════
#  standalone runner
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    if not DB_AVAILABLE:
        print("SKIP: PostgreSQL not available — all storage tests skipped")
        sys.exit(0)

    passed = failed = 0
    for cls_name, cls in sorted(globals().items()):
        if not isinstance(cls, type) or not cls_name.startswith("Test"):
            continue
        for method_name in sorted(dir(cls)):
            if not method_name.startswith("test_"):
                continue
            name = f"{cls_name}.{method_name}"
            instance = cls()
            try:
                instance.setup_method()
                getattr(instance, method_name)()
                print(f"  PASS  {name}")
                passed += 1
            except Exception as e:
                print(f"  FAIL  {name}: {e}")
                failed += 1
            finally:
                try:
                    instance.teardown_method()
                except Exception:
                    pass
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
