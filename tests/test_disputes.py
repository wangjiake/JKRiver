"""Pure unit tests — no database, no LLM, no network."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.sleep.disputes import (
    _preprocess_disputes,
    _parse_dispute_result,
    _build_traj_context,
)
from datetime import datetime, timezone
from unittest.mock import patch


def _make_dispute_pair(old_id=1, new_id=2, old_mc=1, new_mc=1,
                       old_start=None, new_start=None):
    """Helper to build a dispute pair dict."""
    return {
        "old": {
            "id": old_id,
            "value": "old_val",
            "mention_count": old_mc,
            "start_time": old_start or datetime(2025, 1, 1, tzinfo=timezone.utc),
            "layer": "suspected",
            "category": "位置",
            "subject": "居住地",
        },
        "new": {
            "id": new_id,
            "value": "new_val",
            "mention_count": new_mc,
            "start_time": new_start or datetime(2025, 6, 1, tzinfo=timezone.utc),
            "layer": "suspected",
            "category": "位置",
            "subject": "居住地",
        },
    }


class TestPreprocessDisputes:
    @patch("agent.sleep.disputes.get_now")
    def test_new_mention_ge2_accept_new(self, mock_now):
        mock_now.return_value = datetime(2025, 7, 1, tzinfo=timezone.utc)
        pairs = [_make_dispute_pair(new_mc=3)]
        rules, llm = _preprocess_disputes(pairs)
        assert len(rules) == 1
        assert rules[0]["action"] == "accept_new"
        assert llm == []

    @patch("agent.sleep.disputes.get_now")
    def test_old_90days_new_mention_higher_accept(self, mock_now):
        mock_now.return_value = datetime(2025, 10, 1, tzinfo=timezone.utc)
        pairs = [_make_dispute_pair(
            old_mc=2, new_mc=5,
            new_start=datetime(2025, 6, 1, tzinfo=timezone.utc),
        )]
        rules, llm = _preprocess_disputes(pairs)
        assert len(rules) == 1
        assert rules[0]["action"] == "accept_new"

    @patch("agent.sleep.disputes.get_now")
    def test_old_90days_old_mention_higher_reject(self, mock_now):
        mock_now.return_value = datetime(2025, 10, 1, tzinfo=timezone.utc)
        # new_mc=1 so we bypass the first rule (new_mc>=2 → accept)
        pairs = [_make_dispute_pair(
            old_mc=10, new_mc=1,
            new_start=datetime(2025, 6, 1, tzinfo=timezone.utc),
        )]
        rules, llm = _preprocess_disputes(pairs)
        assert len(rules) == 1
        assert rules[0]["action"] == "reject_new"

    @patch("agent.sleep.disputes.get_now")
    def test_recent_low_mention_goes_to_llm(self, mock_now):
        mock_now.return_value = datetime(2025, 7, 1, tzinfo=timezone.utc)
        pairs = [_make_dispute_pair(new_mc=1)]
        rules, llm = _preprocess_disputes(pairs)
        assert rules == []
        assert len(llm) == 1

    @patch("agent.sleep.disputes.get_now")
    def test_empty_input(self, mock_now):
        mock_now.return_value = datetime(2025, 7, 1, tzinfo=timezone.utc)
        rules, llm = _preprocess_disputes([])
        assert rules == []
        assert llm == []

    @patch("agent.sleep.disputes.get_now")
    def test_mixed_scenario(self, mock_now):
        mock_now.return_value = datetime(2025, 10, 1, tzinfo=timezone.utc)
        pairs = [
            _make_dispute_pair(old_id=1, new_id=2, new_mc=3),  # rule: accept
            _make_dispute_pair(old_id=3, new_id=4, new_mc=1,   # llm candidate
                               new_start=datetime(2025, 9, 1, tzinfo=timezone.utc)),
        ]
        rules, llm = _preprocess_disputes(pairs)
        assert len(rules) == 1
        assert len(llm) == 1


class TestParseDisputeResult:
    def test_valid_json(self):
        raw = '{"old_fact_id": 1, "new_fact_id": 2, "action": "accept_new", "reason": "ok"}'
        r = _parse_dispute_result(raw, 1, 2)
        assert r["action"] == "accept_new"

    def test_array_wrapped(self):
        raw = '[{"old_fact_id": 1, "new_fact_id": 2, "action": "reject_new", "reason": "nah"}]'
        r = _parse_dispute_result(raw, 1, 2)
        assert r["action"] == "reject_new"

    def test_invalid_action_returns_none(self):
        raw = '{"old_fact_id": 1, "new_fact_id": 2, "action": "maybe", "reason": "x"}'
        assert _parse_dispute_result(raw, 1, 2) is None

    def test_missing_id_auto_filled(self):
        raw = '{"action": "keep", "reason": "unsure"}'
        r = _parse_dispute_result(raw, 10, 20)
        assert r["old_fact_id"] == 10
        assert r["new_fact_id"] == 20

    def test_invalid_json_returns_none(self):
        assert _parse_dispute_result("not json", 1, 2) is None

    def test_keep_action_valid(self):
        raw = '{"old_fact_id": 1, "new_fact_id": 2, "action": "keep", "reason": "both valid"}'
        r = _parse_dispute_result(raw, 1, 2)
        assert r["action"] == "keep"


class TestBuildTrajContext:
    def test_with_trajectory(self):
        traj = {
            "life_phase": "early career",
            "key_anchors": ["job", "city"],
            "volatile_areas": ["hobby"],
        }
        result = _build_traj_context(traj, language="zh")
        assert "锚点" in result or "job" in result
        assert result != ""

    def test_none_trajectory(self):
        assert _build_traj_context(None) == ""

    def test_no_life_phase(self):
        assert _build_traj_context({"key_anchors": ["x"]}) == ""


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
