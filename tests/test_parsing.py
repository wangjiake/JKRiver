"""Pure unit tests — no database, no LLM, no network."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
        raw = '[{"subject": "\u5c45\u4f4f\u5730", "value": "\u6df1\u5733"}]'
        result = _parse_json_array(raw)
        assert result[0]["subject"] == "\u5c45\u4f4f\u5730"


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
