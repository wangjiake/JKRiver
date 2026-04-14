"""Pure unit tests — no database, no LLM, no network."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.sleep._formatting import _format_trajectory_block, _format_profile_for_llm
from datetime import datetime, timezone


class TestFormatTrajectoryBlock:
    def test_full_trajectory(self):
        traj = {
            "life_phase": "大学生活",
            "phase_characteristics": "学习为主",
            "trajectory_direction": "稳定",
            "stability_assessment": "高",
            "key_anchors": ["学校"],
            "volatile_areas": ["社交"],
            "recent_momentum": "平稳",
            "full_summary": "一切正常",
        }
        text = _format_trajectory_block(traj, language="zh")
        assert "大学生活" in text
        assert "学校" in text

    def test_none_trajectory(self):
        text = _format_trajectory_block(None, language="zh")
        assert "暂无" in text or "无" in text

    def test_no_life_phase(self):
        text = _format_trajectory_block({"key_anchors": ["x"]}, language="zh")
        assert "暂无" in text or "无" in text


class TestFormatProfileForLlm:
    def test_empty_profile(self):
        text = _format_profile_for_llm([], language="zh")
        assert "暂无" in text

    def test_confirmed_sorted_first(self):
        profile = [
            {"id": 1, "category": "位置", "subject": "城市", "value": "北京",
             "layer": "suspected", "mention_count": 5, "source_type": "stated",
             "start_time": datetime(2025, 1, 1, tzinfo=timezone.utc), "updated_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
             "evidence": [], "superseded_by": None, "supersedes": None},
            {"id": 2, "category": "职业", "subject": "工作", "value": "工程师",
             "layer": "confirmed", "mention_count": 1, "source_type": "stated",
             "start_time": datetime(2025, 1, 1, tzinfo=timezone.utc), "updated_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
             "evidence": [], "superseded_by": None, "supersedes": None},
        ]
        text = _format_profile_for_llm(profile, language="zh")
        # confirmed (#2) should appear before suspected (#1)
        pos_confirmed = text.find("#2")
        pos_suspected = text.find("#1")
        assert pos_confirmed < pos_suspected

    def test_max_items_truncation(self):
        profile = []
        for i in range(20):
            profile.append({
                "id": i, "category": "兴趣", "subject": f"s{i}", "value": f"v{i}",
                "layer": "suspected", "mention_count": 1, "source_type": "stated",
                "start_time": datetime(2025, 1, 1, tzinfo=timezone.utc), "updated_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
                "evidence": [], "superseded_by": None, "supersedes": None,
            })
        text = _format_profile_for_llm(profile, language="zh", max_items=5)
        # should only contain 5 items
        assert text.count("#") == 5

    def test_superseded_by_tag(self):
        profile = [{
            "id": 1, "category": "位置", "subject": "城市", "value": "北京",
            "layer": "suspected", "mention_count": 1, "source_type": "stated",
            "start_time": datetime(2025, 1, 1, tzinfo=timezone.utc), "updated_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
            "evidence": [], "superseded_by": 2, "supersedes": None,
        }]
        text = _format_profile_for_llm(profile, language="zh")
        assert "矛盾" in text or "挑战" in text or "#2" in text

    def test_timeline_closed(self):
        profile = [{
            "id": 1, "category": "位置", "subject": "城市", "value": "上海",
            "layer": "confirmed", "mention_count": 3, "source_type": "stated",
            "start_time": datetime(2024, 1, 1, tzinfo=timezone.utc), "updated_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
            "evidence": [], "superseded_by": None, "supersedes": None,
        }]
        timeline = [{
            "category": "位置", "subject": "城市", "value": "广州",
            "start_time": datetime(2023, 1, 1, tzinfo=timezone.utc),
            "end_time": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "human_end_time": None,
            "rejected": False,
        }]
        text = _format_profile_for_llm(profile, timeline=timeline, language="zh")
        assert "广州" in text
        assert "已关闭" in text or "历史" in text

    def test_timeline_rejected(self):
        profile = [{
            "id": 1, "category": "位置", "subject": "城市", "value": "上海",
            "layer": "confirmed", "mention_count": 3, "source_type": "stated",
            "start_time": datetime(2024, 1, 1, tzinfo=timezone.utc), "updated_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
            "evidence": [], "superseded_by": None, "supersedes": None,
        }]
        timeline = [{
            "category": "位置", "subject": "城市", "value": "错误城市",
            "start_time": datetime(2023, 1, 1, tzinfo=timezone.utc),
            "end_time": None,
            "human_end_time": None,
            "rejected": True,
        }]
        text = _format_profile_for_llm(profile, timeline=timeline, language="zh")
        assert "错误" in text


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
