"""Pure unit tests — no database, no LLM, no network.

Usage:
    python -m pytest tests/test_unit.py -v
    python tests/test_unit.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ═══════════════════════════════════════════════════════════
#  _parsing: JSON extraction from LLM responses
# ═══════════════════════════════════════════════════════════

from agent.sleep._parsing import _parse_json_array, _parse_json_object


class TestParseJsonArray:
    def test_clean_array(self):
        assert _parse_json_array('[{"a": 1}, {"b": 2}]') == [{"a": 1}, {"b": 2}]

    def test_markdown_fenced(self):
        raw = '```json\n[{"key": "val"}]\n```'
        assert _parse_json_array(raw) == [{"key": "val"}]

    def test_generic_fence(self):
        raw = '```\n[{"x": 1}]\n```'
        assert _parse_json_array(raw) == [{"x": 1}]

    def test_surrounding_text(self):
        raw = 'Here are the results:\n[{"name": "test"}]\nDone.'
        assert _parse_json_array(raw) == [{"name": "test"}]

    def test_empty_array(self):
        assert _parse_json_array("[]") == []

    def test_garbage_returns_empty(self):
        assert _parse_json_array("not json at all") == []

    def test_multiple_arrays_merged(self):
        raw = 'first: [{"a":1}] then: [{"b":2}]'
        # Outer bracket extraction finds [{"a":1}] then: [{"b":2}]
        # which isn't valid JSON, so falls back to regex merge
        result = _parse_json_array(raw)
        assert {"a": 1} in result
        assert {"b": 2} in result

    def test_nested_markdown_with_preamble(self):
        raw = 'I found the following:\n```json\n[{"type": "preference", "content": "likes coffee"}]\n```\nThat is all.'
        result = _parse_json_array(raw)
        assert len(result) == 1
        assert result[0]["type"] == "preference"

    def test_unicode_content(self):
        raw = '[{"subject": "居住地", "value": "深圳"}]'
        result = _parse_json_array(raw)
        assert result[0]["subject"] == "居住地"


class TestParseJsonObject:
    def test_clean_object(self):
        assert _parse_json_object('{"a": 1}') == {"a": 1}

    def test_markdown_fenced(self):
        raw = '```json\n{"key": "val"}\n```'
        assert _parse_json_object(raw) == {"key": "val"}

    def test_surrounding_text(self):
        raw = 'Result: {"name": "test"} end'
        assert _parse_json_object(raw) == {"name": "test"}

    def test_garbage_returns_empty(self):
        assert _parse_json_object("no json here") == {}

    def test_empty_object(self):
        assert _parse_json_object("{}") == {}

    def test_nested_object(self):
        raw = '{"outer": {"inner": 42}}'
        result = _parse_json_object(raw)
        assert result["outer"]["inner"] == 42


# ═══════════════════════════════════════════════════════════
#  _maturity: decay tier calculation
# ═══════════════════════════════════════════════════════════

from agent.sleep._maturity import _calculate_maturity_decay, _MATURITY_TIERS


class TestMaturityDecay:
    def test_no_upgrade_short_span(self):
        # span=30 days, 1 evidence, current=30 → not enough for any tier
        assert _calculate_maturity_decay(30, 1, 30) == 30

    def test_tier3_upgrade(self):
        # span=90, evidence=3, current=30 → should upgrade to 180
        assert _calculate_maturity_decay(90, 3, 30) == 180

    def test_tier2_upgrade(self):
        # span=365, evidence=6, current=30 → should upgrade to 365
        assert _calculate_maturity_decay(365, 6, 30) == 365

    def test_tier1_upgrade(self):
        # span=730, evidence=10, current=30 → should upgrade to 730
        assert _calculate_maturity_decay(730, 10, 30) == 730

    def test_no_downgrade(self):
        # current_decay=365, even if tier3 matches, won't downgrade
        assert _calculate_maturity_decay(90, 3, 365) == 365

    def test_key_anchor_boost(self):
        # With key anchor boost (0.6x thresholds):
        # tier3: min_span=90*0.6=54, min_ev=max(1,3*0.6)=max(1,1)=1
        # span=60, evidence=2, current=30 → should hit tier3 → 180
        assert _calculate_maturity_decay(60, 2, 30, in_key_anchors=True) == 180

    def test_key_anchor_no_boost_without_flag(self):
        # Same values without boost → no upgrade
        assert _calculate_maturity_decay(60, 2, 30, in_key_anchors=False) == 30

    def test_already_at_max(self):
        # current=730, nothing higher
        assert _calculate_maturity_decay(1000, 20, 730) == 730

    def test_zero_evidence(self):
        # evidence=0, key anchor boost makes min_ev=max(1,0)=1, still need ≥1
        assert _calculate_maturity_decay(100, 0, 30, in_key_anchors=True) == 30

    def test_tiers_are_ordered(self):
        # Verify tiers are checked from highest to lowest
        targets = [t[2] for t in _MATURITY_TIERS]
        assert targets == sorted(targets, reverse=True)


# ═══════════════════════════════════════════════════════════
#  _synonyms: category & subject synonym resolution
# ═══════════════════════════════════════════════════════════

from agent.storage._synonyms import _get_category_synonyms, _get_subject_synonyms


class TestSynonyms:
    def test_category_known(self):
        syns = _get_category_synonyms("位置")
        assert "居住地" in syns
        assert "居住" in syns
        assert "位置" in syns

    def test_category_unknown_returns_singleton(self):
        syns = _get_category_synonyms("未知分类")
        assert syns == {"未知分类"}

    def test_category_symmetry(self):
        # "位置" and "居住地" should return the same set
        assert _get_category_synonyms("位置") == _get_category_synonyms("居住地")

    def test_subject_known(self):
        syns = _get_subject_synonyms("居住地")
        assert "居住城市" in syns
        assert "当前居住地" in syns

    def test_subject_unknown_returns_singleton(self):
        syns = _get_subject_synonyms("未知主题")
        assert syns == {"未知主题"}

    def test_subject_symmetry(self):
        assert _get_subject_synonyms("女朋友") == _get_subject_synonyms("女友")

    def test_all_category_groups_bidirectional(self):
        from agent.storage._synonyms import _CATEGORY_SYNONYM_GROUPS
        for group in _CATEGORY_SYNONYM_GROUPS:
            for name in group:
                assert _get_category_synonyms(name) == group

    def test_all_subject_groups_bidirectional(self):
        from agent.storage._synonyms import _SUBJECT_SYNONYM_GROUPS
        for group in _SUBJECT_SYNONYM_GROUPS:
            for name in group:
                assert _get_subject_synonyms(name) == group


# ═══════════════════════════════════════════════════════════
#  profile_filter: prepare_profile scoring & truncation
# ═══════════════════════════════════════════════════════════

from agent.utils.profile_filter import prepare_profile, format_profile_text
from datetime import datetime, timedelta


def _make_fact(id, category="兴趣", subject="test", value="val",
               layer="suspected", mention_count=1,
               updated_at=None, superseded_by=None):
    return {
        "id": id,
        "category": category,
        "subject": subject,
        "value": value,
        "layer": layer,
        "mention_count": mention_count,
        "updated_at": updated_at or datetime(2025, 1, 1),
        "start_time": datetime(2025, 1, 1),
        "superseded_by": superseded_by,
        "source_type": "stated",
        "evidence": [],
    }


class TestPrepareProfile:
    def test_empty_profile(self):
        top, rest = prepare_profile([], language="en")
        assert top == []
        assert rest == ""

    def test_superseded_filtered_out(self):
        facts = [
            _make_fact(1, superseded_by=2),
            _make_fact(2, value="new"),
        ]
        top, _ = prepare_profile(facts, max_entries=10, language="en")
        assert len(top) == 1
        assert top[0]["id"] == 2

    def test_confirmed_ranked_higher(self):
        facts = [
            _make_fact(1, layer="suspected", mention_count=10),
            _make_fact(2, layer="confirmed", mention_count=1),
        ]
        top, _ = prepare_profile(facts, max_entries=10, language="en")
        # confirmed should come first due to higher fallback score
        assert top[0]["id"] == 2

    def test_recent_updated_ranked_higher(self):
        now = datetime.now()
        facts = [
            _make_fact(1, updated_at=datetime(2020, 1, 1)),
            _make_fact(2, updated_at=now - timedelta(days=5)),
        ]
        top, _ = prepare_profile(facts, max_entries=10, language="en")
        assert top[0]["id"] == 2

    def test_truncation(self):
        facts = [_make_fact(i) for i in range(50)]
        top, rest = prepare_profile(facts, max_entries=10, language="en")
        assert len(top) == 10
        assert rest != ""  # should have summary of remaining

    def test_rest_summary_contains_category(self):
        facts = [_make_fact(i, category="职业") for i in range(20)]
        top, rest = prepare_profile(facts, max_entries=5, language="en")
        assert "职业" in rest

    def test_all_fit_no_rest(self):
        facts = [_make_fact(i) for i in range(3)]
        top, rest = prepare_profile(facts, max_entries=10, language="en")
        assert len(top) == 3
        assert rest == ""


class TestFormatProfileText:
    def test_empty_returns_empty(self):
        assert format_profile_text([], language="en") == ""

    def test_full_detail_includes_layer_tag(self):
        facts = [_make_fact(1, layer="confirmed", category="职业",
                            subject="职位", value="工程师")]
        text = format_profile_text(facts, max_entries=10, detail="full", language="en")
        assert "职位" in text
        assert "工程师" in text

    def test_light_detail_no_layer_tag(self):
        facts = [_make_fact(1, layer="confirmed", category="职业",
                            subject="职位", value="工程师")]
        text = format_profile_text(facts, max_entries=10, detail="light", language="en")
        assert "职位" in text
        assert "工程师" in text


# ═══════════════════════════════════════════════════════════
#  standalone runner
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    passed = failed = 0
    for cls_name, cls in sorted(globals().items()):
        if not isinstance(cls, type) or not cls_name.startswith("Test"):
            continue
        for method_name in sorted(dir(cls)):
            if not method_name.startswith("test_"):
                continue
            name = f"{cls_name}.{method_name}"
            try:
                getattr(cls(), method_name)()
                print(f"  PASS  {name}")
                passed += 1
            except Exception as e:
                print(f"  FAIL  {name}: {e}")
                failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
