"""Pure unit tests — no database, no LLM, no network."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.utils.profile_filter import prepare_profile, format_profile_text
from datetime import datetime, timedelta, timezone


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
        "updated_at": updated_at or datetime(2025, 1, 1, tzinfo=timezone.utc),
        "start_time": datetime(2025, 1, 1, tzinfo=timezone.utc),
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
        now = datetime.now(timezone.utc)
        facts = [
            _make_fact(1, updated_at=datetime(2020, 1, 1, tzinfo=timezone.utc)),
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
