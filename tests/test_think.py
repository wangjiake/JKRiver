"""Pure unit tests — no database, no LLM, no network."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.cognition._think import (
    parse_verify_raw,
    summarize_response,
    strip_internal_sections,
    make_thinking_notes,
)


class TestParseVerifyRaw:
    def test_fail_english_colon(self):
        assert parse_verify_raw("FAIL:wrong info") == "FAIL:wrong info"

    def test_fail_chinese_colon(self):
        assert parse_verify_raw("FAIL：错误信息") == "FAIL：错误信息"

    def test_pass_on_other(self):
        assert parse_verify_raw("looks good") == "PASS"

    def test_pass_exact(self):
        assert parse_verify_raw("PASS") == "PASS"

    def test_fail_prefix_only(self):
        # "FAILURE" doesn't start with "FAIL:" so → PASS
        assert parse_verify_raw("FAILURE") == "PASS"


class TestSummarizeResponse:
    def test_short_text_returned_as_is(self):
        assert summarize_response("Hello world") == "Hello world"

    def test_truncate_at_period(self):
        text = "First sentence。Second sentence"
        assert summarize_response(text) == "First sentence。"

    def test_truncate_at_english_period(self):
        text = "First sentence. Second sentence"
        assert summarize_response(text) == "First sentence."

    def test_long_text_with_ellipsis(self):
        text = "a" * 200
        result = summarize_response(text, max_len=120)
        assert result.endswith("...")
        assert len(result) == 123  # 120 + "..."

    def test_chinese_punctuation(self):
        text = "第一句话！第二句话"
        assert summarize_response(text) == "第一句话！"

    def test_question_mark(self):
        text = "你好吗？我很好"
        assert summarize_response(text) == "你好吗？"

    def test_newlines_replaced(self):
        text = "line1\nline2\nline3"
        result = summarize_response(text)
        assert "\n" not in result


class TestStripInternalSections:
    def test_filters_high_prob_section(self):
        text = "正常段落\n【高概率推测】\n推测内容\n【其他段落】\n正常内容"
        result = strip_internal_sections(text, language="zh")
        assert "推测内容" not in result
        assert "正常段落" in result
        assert "正常内容" in result

    def test_multiple_sections_filtered(self):
        text = "前面\n【高概率推测】\n内容1\n【待验证信息】\n内容2\n【正常段落】\n保留"
        result = strip_internal_sections(text, language="zh")
        assert "内容1" not in result
        assert "内容2" not in result
        assert "保留" in result

    def test_empty_input_returns_fallback(self):
        result = strip_internal_sections("", language="zh")
        assert result == "无"

    def test_no_markers_returns_original(self):
        text = "这是普通文本"
        assert strip_internal_sections(text, language="zh") == "这是普通文本"

    def test_english_markers(self):
        # After an English marker, skip only resets on 【, so use 【 to end section
        text = "Normal\n[High Probability Inference]\nSpec content\n【Other】\nKept"
        result = strip_internal_sections(text, language="en")
        assert "Spec content" not in result
        assert "Normal" in result
        assert "Kept" in result

    def test_all_stripped_returns_fallback(self):
        text = "【高概率推测】\n全部是推测"
        result = strip_internal_sections(text, language="zh")
        assert result == "无"


class TestMakeThinkingNotes:
    def _perception(self, category="chat"):
        return {"category": category}

    def test_knowledge_skips_memory(self):
        notes = make_thinking_notes(
            self._perception("knowledge"), "", "response", "PASS", "final", "zh"
        )
        assert "跳过记忆" in notes

    def test_personal_with_memory_loaded(self):
        notes = make_thinking_notes(
            self._perception("personal"), "some memory text", "r", "PASS", "f", "zh"
        )
        assert "记忆已加载" in notes

    def test_chat_no_memory(self):
        notes = make_thinking_notes(
            self._perception("chat"), "", "r", "PASS", "f", "zh"
        )
        assert "未找到" in notes

    def test_fail_verification(self):
        notes = make_thinking_notes(
            self._perception("chat"), "mem", "r", "FAIL:bad", "f", "zh"
        )
        assert "拦截" in notes

    def test_pass_verification(self):
        notes = make_thinking_notes(
            self._perception("chat"), "mem", "r", "PASS", "f", "zh"
        )
        assert "通过" in notes


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
