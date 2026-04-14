"""Pure unit tests — no database, no LLM, no network."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.cognition._trajectory import parse_trajectory_result, finish_trajectory_result


class TestParseTrajectoryResult:
    def test_pure_json(self):
        raw = '{"trajectory": "off_track", "reason": "unexpected"}'
        r = parse_trajectory_result(raw)
        assert r["trajectory"] == "off_track"

    def test_markdown_fence(self):
        raw = '```json\n{"trajectory": "on_track"}\n```'
        r = parse_trajectory_result(raw)
        assert r["trajectory"] == "on_track"

    def test_invalid_json(self):
        assert parse_trajectory_result("not json") is None

    def test_json_with_surrounding_text(self):
        raw = 'Analysis result:\n{"trajectory": "off_track", "detail": "x"}\nEnd.'
        r = parse_trajectory_result(raw)
        assert r is not None
        assert r["trajectory"] == "off_track"


class TestFinishTrajectoryResult:
    def test_on_track_returns_none(self):
        raw = '{"trajectory": "on_track"}'
        assert finish_trajectory_result(raw) is None

    def test_no_data_returns_none(self):
        raw = '{"trajectory": "no_data"}'
        assert finish_trajectory_result(raw) is None

    def test_off_track_returns_dict(self):
        raw = '{"trajectory": "off_track", "reason": "moved city"}'
        r = finish_trajectory_result(raw)
        assert r is not None
        assert r["trajectory"] == "off_track"

    def test_invalid_json_returns_none(self):
        assert finish_trajectory_result("garbage") is None


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
