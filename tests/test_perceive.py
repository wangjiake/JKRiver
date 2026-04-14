"""Pure unit tests — no database, no LLM, no network."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.cognition._perceive import parse_perceive_output, _parse_perceive_json


class TestParsePerceiveJson:
    """Tests for _parse_perceive_json (JSON structured output parser)."""

    def test_full_json_zh(self):
        raw = '{"correction": "你好世界", "category": "personal", "intent": "用户想打招呼", "ai_summary": "打招呼", "keywords": ["问候", "社交"], "need_online": false, "need_tools": false}'
        r = _parse_perceive_json(raw, "你好", "zh")
        assert r is not None
        assert r["corrected_input"] == "你好世界"
        assert r["category"] == "personal"
        assert r["intent"] == "用户想打招呼"
        assert r["ai_summary"] == "打招呼"
        assert r["topic_keywords"] == ["问候", "社交"]
        assert r["need_online"] is False
        assert r["need_tools"] is False
        assert r["need_memory"] is True
        assert r["memory_type"] == "personal"

    def test_full_json_en(self):
        raw = '{"correction": "How to read a file", "category": "knowledge", "intent": "User wants file reading info", "ai_summary": "How to read a file", "keywords": ["Python", "file"], "need_online": false, "need_tools": false}'
        r = _parse_perceive_json(raw, "how to read file", "en")
        assert r is not None
        assert r["category"] == "knowledge"
        assert r["need_memory"] is False
        assert r["topic_keywords"] == ["Python", "file"]

    def test_markdown_fenced_json(self):
        raw = '```json\n{"correction": "test", "category": "chat", "intent": "greet", "ai_summary": "test", "keywords": ["hi"], "need_online": false, "need_tools": false}\n```'
        r = _parse_perceive_json(raw, "test", "en")
        assert r is not None
        assert r["category"] == "chat"

    def test_string_booleans(self):
        raw = '{"correction": "hi", "category": "personal", "intent": "greet", "ai_summary": "hi", "keywords": ["hi"], "need_online": "yes", "need_tools": "true"}'
        r = _parse_perceive_json(raw, "hi", "en")
        assert r is not None
        assert r["need_online"] is True
        assert r["need_tools"] is True

    def test_string_booleans_zh(self):
        raw = '{"correction": "你好", "category": "personal", "intent": "问候", "ai_summary": "你好", "keywords": ["你好"], "need_online": "是", "need_tools": "no"}'
        r = _parse_perceive_json(raw, "你好", "zh")
        assert r is not None
        assert r["need_online"] is True
        assert r["need_tools"] is False

    def test_keywords_as_string(self):
        raw = '{"correction": "hi", "category": "chat", "intent": "greet", "ai_summary": "hi", "keywords": "weather, cold", "need_online": false, "need_tools": false}'
        r = _parse_perceive_json(raw, "hi", "en")
        assert r is not None
        assert r["topic_keywords"] == ["weather", "cold"]

    def test_fallback_on_garbage(self):
        r = _parse_perceive_json("not json at all", "hi", "en")
        assert r is None

    def test_fallback_on_no_category(self):
        raw = '{"correction": "hi", "intent": "greet"}'
        r = _parse_perceive_json(raw, "hi", "en")
        assert r is None

    def test_fallback_on_invalid_category(self):
        raw = '{"correction": "hi", "category": "invalid", "intent": "x", "ai_summary": "x", "keywords": [], "need_online": false, "need_tools": false}'
        r = _parse_perceive_json(raw, "hi", "en")
        assert r is None


class TestParsePerceiveOutputFallback:
    """Verify parse_perceive_output tries JSON first, then falls back to string."""

    def test_json_takes_priority(self):
        raw = '{"correction": "hello world", "category": "knowledge", "intent": "test", "ai_summary": "hello", "keywords": ["test"], "need_online": false, "need_tools": false}'
        r = parse_perceive_output(raw, "hello", language="en")
        assert r["category"] == "knowledge"
        assert r["corrected_input"] == "hello world"

    def test_string_fallback(self):
        labels = {
            "correction": "Correction",
            "category": "Category",
            "intent": "Intent",
            "summary": "AI Summary",
            "keywords": "Topic Keywords",
            "need_online": "Need Online",
            "need_tools": "Need Tools",
        }
        raw = "Correction：fixed\nCategory：personal\nIntent：wants info"
        r = parse_perceive_output(raw, "test", labels, "en")
        assert r["category"] == "personal"
        assert r["corrected_input"] == "fixed"


class TestParsePerceiveOutput:
    """Tests for parse_perceive_output (line-by-line LLM output parser)."""

    def _zh_labels(self):
        return {
            "correction": "纠错",
            "category": "分类",
            "intent": "意图",
            "summary": "AI摘要",
            "keywords": "话题关键词",
            "need_online": "需要联网",
            "need_tools": "需要工具",
        }

    def test_full_output_zh(self):
        raw = (
            "纠错：你好世界\n"
            "分类：personal\n"
            "意图：用户想打招呼\n"
            "AI摘要：打招呼\n"
            "话题关键词：问候, 社交\n"
            "需要联网：否\n"
            "需要工具：否\n"
        )
        r = parse_perceive_output(raw, "你好", self._zh_labels(), "zh")
        assert r["corrected_input"] == "你好世界"
        assert r["category"] == "personal"
        assert r["intent"] == "用户想打招呼"
        assert r["ai_summary"] == "打招呼"
        assert r["topic_keywords"] == ["问候", "社交"]
        assert r["need_online"] is False
        assert r["need_tools"] is False
        assert r["need_memory"] is True  # personal → True
        assert r["memory_type"] == "personal"

    def test_chinese_colon_and_english_colon(self):
        raw_cn = "分类：knowledge\n意图：查天气"
        raw_en = "分类:knowledge\n意图:查天气"
        r_cn = parse_perceive_output(raw_cn, "天气", self._zh_labels(), "zh")
        r_en = parse_perceive_output(raw_en, "天气", self._zh_labels(), "zh")
        assert r_cn["category"] == r_en["category"] == "knowledge"
        assert r_cn["intent"] == r_en["intent"] == "查天气"

    def test_category_only_accepts_valid(self):
        raw = "分类：invalid_type"
        r = parse_perceive_output(raw, "hi", self._zh_labels(), "zh")
        assert r["category"] == "chat"  # default

    def test_knowledge_category_no_memory(self):
        raw = "分类：knowledge"
        r = parse_perceive_output(raw, "hi", self._zh_labels(), "zh")
        assert r["need_memory"] is False

    def test_chat_category_need_memory(self):
        raw = "分类：chat"
        r = parse_perceive_output(raw, "hi", self._zh_labels(), "zh")
        assert r["need_memory"] is True
        assert r["memory_type"] != "personal"

    def test_need_online_truthy(self):
        raw = "需要联网：是"
        r = parse_perceive_output(raw, "hi", self._zh_labels(), "zh")
        assert r["need_online"] is True

    def test_need_tools_truthy(self):
        raw = "需要工具：yes"
        r = parse_perceive_output(raw, "hi", self._zh_labels(), "zh")
        assert r["need_tools"] is True

    def test_empty_input_safe_defaults(self):
        r = parse_perceive_output("", "hello", self._zh_labels(), "zh")
        assert r["category"] == "chat"
        assert r["intent"] == "hello"
        assert r["ai_summary"] == "hello"
        assert r["topic_keywords"] == []
        assert r["need_memory"] is True

    def test_english_labels(self):
        en_labels = {
            "correction": "Correction",
            "category": "Category",
            "intent": "Intent",
            "summary": "AI Summary",
            "keywords": "Topic Keywords",
            "need_online": "Need Online",
            "need_tools": "Need Tools",
        }
        raw = (
            "Correction：fixed input\n"
            "Category：knowledge\n"
            "Intent：user wants info\n"
            "AI Summary：info request\n"
            "Topic Keywords：science, math\n"
            "Need Online：yes\n"
            "Need Tools：no\n"
        )
        r = parse_perceive_output(raw, "tell me", en_labels, "en")
        assert r["corrected_input"] == "fixed input"
        assert r["category"] == "knowledge"
        assert r["need_online"] is True
        assert r["topic_keywords"] == ["science", "math"]


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
