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

from agent.storage._synonyms import _get_category_synonyms, _get_subject_synonyms, is_significant_category


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

    def test_english_category_synonym(self):
        assert _get_category_synonyms("career") == _get_category_synonyms("职业")

    def test_english_location_synonym(self):
        assert _get_category_synonyms("location") == _get_category_synonyms("居住")

    def test_japanese_category_synonym(self):
        assert _get_category_synonyms("仕事") == _get_category_synonyms("职业")

    def test_japanese_location_synonym(self):
        assert _get_category_synonyms("場所") == _get_category_synonyms("location")

    def test_english_subject_synonym(self):
        syns = _get_subject_synonyms("current city")
        assert "居住城市" in syns
        assert "居住都市" in syns

    def test_japanese_subject_synonym(self):
        syns = _get_subject_synonyms("卒業校")
        assert "学校" in syns
        assert "university" in syns

    def test_girlfriend_multilingual(self):
        syns = _get_subject_synonyms("girlfriend")
        assert "女朋友" in syns
        assert "彼女" in syns

    def test_boyfriend_multilingual(self):
        syns = _get_subject_synonyms("boyfriend")
        assert "男朋友" in syns
        assert "彼氏" in syns

    def test_sports_multilingual(self):
        syns = _get_subject_synonyms("sports")
        assert "运动" in syns
        assert "スポーツ" in syns

    def test_games_multilingual(self):
        syns = _get_subject_synonyms("games")
        assert "游戏" in syns
        assert "ゲーム" in syns


class TestSignificantCategory:
    def test_chinese_career(self):
        assert is_significant_category("职业") is True

    def test_english_career(self):
        assert is_significant_category("career") is True

    def test_english_location(self):
        assert is_significant_category("location") is True

    def test_chinese_family(self):
        assert is_significant_category("家庭") is True

    def test_english_family(self):
        assert is_significant_category("family") is True

    def test_english_health(self):
        assert is_significant_category("health") is True

    def test_english_education(self):
        assert is_significant_category("education") is True

    def test_synonym_expansion(self):
        # "住址" is a synonym of "居住" which is a significant anchor
        assert is_significant_category("住址") is True

    def test_japanese_significant_career(self):
        assert is_significant_category("仕事") is True

    def test_japanese_significant_family(self):
        assert is_significant_category("家族") is True

    def test_japanese_significant_health(self):
        assert is_significant_category("健康") is True

    def test_non_significant(self):
        assert is_significant_category("兴趣") is False
        assert is_significant_category("hobby") is False

    def test_unknown_category(self):
        assert is_significant_category("随便什么") is False


# ═══════════════════════════════════════════════════════════
#  profile_filter: prepare_profile scoring & truncation
# ═══════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════
#  cognition._perceive: parse_perceive_output
# ═══════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════
#  cognition._trajectory: parse & finish trajectory result
# ═══════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════
#  cognition._think: parse_verify_raw, summarize_response,
#                    strip_internal_sections, make_thinking_notes
# ═══════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════
#  sleep.disputes: _preprocess_disputes, _parse_dispute_result,
#                  _build_traj_context
# ═══════════════════════════════════════════════════════════

from agent.sleep.disputes import (
    _preprocess_disputes,
    _parse_dispute_result,
    _build_traj_context,
)
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


# ═══════════════════════════════════════════════════════════
#  sleep._formatting: _format_trajectory_block,
#                     _format_profile_for_llm
# ═══════════════════════════════════════════════════════════

from agent.sleep._formatting import _format_trajectory_block, _format_profile_for_llm


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
