"""Pure unit tests — no database, no LLM, no network."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.cognition._session_memory import SessionMemory
from datetime import datetime
import asyncio


def _make_sm(keep_recent=3, char_budget=3000, language="en"):
    """Helper: create a SessionMemory with no LLM/embedding deps."""
    config = {
        "session_memory": {
            "keep_recent": keep_recent,
            "char_budget": char_budget,
            "summary_ratio": 0.4,
            "recall_max": 3,
            "recall_min_score": 0.45,
        },
    }
    return SessionMemory(config, llm_config={}, language=language)


class TestSessionMemoryBasic:
    def test_add_turn_and_get_recent(self):
        sm = _make_sm()
        sm.add_turn("hello", "hi there")
        assert sm._turns[0]["user_summary"] == "hello"
        assert sm._turns[0]["assistant_summary"] == "hi there"
        # get_recent_turns returns same data
        result = sm.get_recent_turns(3)
        assert len(result) == 1
        assert result[0]["user_summary"] == "hello"

    def test_get_recent_returns_last_n(self):
        sm = _make_sm()
        for i in range(10):
            sm.add_turn(f"u{i}", f"a{i}")
        result = sm.get_recent_turns(3)
        assert len(result) == 3
        assert result[0]["user_summary"] == "u7"
        assert result[2]["user_summary"] == "u9"

    def test_get_recent_empty(self):
        sm = _make_sm()
        assert sm.get_recent_turns(3) == []

    def test_defaults_when_no_config(self):
        sm = SessionMemory({}, llm_config={}, language="en")
        assert sm.char_budget == 3000
        assert sm.keep_recent == 5

    def test_config_overrides_defaults(self):
        config = {"session_memory": {"char_budget": 5000, "keep_recent": 10}}
        sm = SessionMemory(config, llm_config={}, language="zh")
        assert sm.char_budget == 5000
        assert sm.keep_recent == 10
        assert sm.summary_ratio == 0.4  # not overridden → default


class TestSessionMemoryBuildContext:
    def test_empty_returns_empty_string(self):
        sm = _make_sm()
        assert sm.build_context() == ""

    def test_recent_turns_with_label(self):
        sm = _make_sm(keep_recent=5)
        sm.add_turn("hello", "hi")
        ctx = sm.build_context()
        assert "hello" in ctx
        assert "hi" in ctx
        assert "Current Session" in ctx

    def test_old_turns_excluded_without_summary(self):
        sm = _make_sm(keep_recent=2)
        for i in range(5):
            sm.add_turn(f"user_{i}", f"asst_{i}")
        ctx = sm.build_context()
        assert "user_3" in ctx
        assert "user_4" in ctx
        assert "user_0" not in ctx

    def test_summary_included_when_set(self):
        sm = _make_sm(keep_recent=2)
        for i in range(4):
            sm.add_turn(f"u{i}", f"a{i}")
        sm._summary = "Earlier they discussed Python and fishing."
        sm._summary_covers = 2
        ctx = sm.build_context()
        assert "Python and fishing" in ctx
        assert "[Session Summary]" in ctx
        assert "u2" in ctx
        assert "u3" in ctx

    def test_language_labels_zh(self):
        sm = _make_sm(keep_recent=3, language="zh")
        sm.add_turn("你好", "嗨")
        sm._summary = "聊了天气"
        sm._summary_covers = 0
        ctx = sm.build_context()
        assert "本轮对话" in ctx
        assert "用户" in ctx
        assert "【会话摘要】" in ctx


class TestSessionMemoryCompression:
    def test_no_compression_below_threshold(self):
        sm = _make_sm(keep_recent=5)
        for i in range(5):
            sm.add_turn(f"u{i}", f"a{i}")
        assert sm._summary == ""
        assert sm._summary_covers == 0

    def test_compression_triggered_async(self):
        sm = _make_sm(keep_recent=2)
        for i in range(4):
            sm.add_turn(f"u{i}", f"a{i}")

        import agent.utils.llm_client as llm_mod
        original = llm_mod.call_llm_async

        async def mock_call(messages, config):
            return "Summary of turns 0 and 1."

        llm_mod.call_llm_async = mock_call
        try:
            asyncio.run(sm._maybe_compress_async())
            assert sm._summary == "Summary of turns 0 and 1."
            assert sm._summary_covers == 2
        finally:
            llm_mod.call_llm_async = original

    def test_compression_failure_keeps_state(self):
        sm = _make_sm(keep_recent=2)
        for i in range(4):
            sm.add_turn(f"u{i}", f"a{i}")

        import agent.utils.llm_client as llm_mod
        original = llm_mod.call_llm_async

        async def mock_fail(messages, config):
            raise RuntimeError("LLM down")

        llm_mod.call_llm_async = mock_fail
        try:
            asyncio.run(sm._maybe_compress_async())
            assert sm._summary == ""
            assert sm._summary_covers == 0
        finally:
            llm_mod.call_llm_async = original

    def test_already_compressed_skips_llm(self):
        sm = _make_sm(keep_recent=2)
        for i in range(4):
            sm.add_turn(f"u{i}", f"a{i}")
        sm._summary = "old summary"
        sm._summary_covers = 2
        call_count = 0

        import agent.utils.llm_client as llm_mod
        original = llm_mod.call_llm_async

        async def mock_call(messages, config):
            nonlocal call_count
            call_count += 1
            return "new summary"

        llm_mod.call_llm_async = mock_call
        try:
            asyncio.run(sm._maybe_compress_async())
            assert call_count == 0
            assert sm._summary == "old summary"
        finally:
            llm_mod.call_llm_async = original


class TestSessionMemoryRecall:
    def test_recall_disabled_without_embedding(self):
        sm = _make_sm()
        sm.add_turn("u1", "a1")
        assert sm._recall_turns("query", 1000) == ""

    def test_recall_only_from_compressed_turns(self):
        sm = _make_sm(keep_recent=3)
        for i in range(3):
            sm.add_turn(f"u{i}", f"a{i}")
        for i in range(3):
            sm._embeddings.append({"index": i, "vec": [1.0] * 10, "user_input_at": None})
        sm._full_config["embedding"] = {"enabled": True}

        import agent.utils.embedding as emb_mod
        orig_get = emb_mod.get_embedding
        emb_mod.get_embedding = lambda text, model="", api_base="": [1.0] * 10
        try:
            assert sm._recall_turns("query", 1000) == ""
        finally:
            emb_mod.get_embedding = orig_get

    def test_recall_returns_compressed_turn_content(self):
        sm = _make_sm(keep_recent=2)
        for i in range(5):
            sm.add_turn(f"u{i}", f"a{i}")
        for i in range(3):
            sm._embeddings.append({"index": i, "vec": [1.0] * 10, "user_input_at": None})
        sm._full_config["embedding"] = {"enabled": True}
        sm.recall_min_score = 0.0

        import agent.utils.embedding as emb_mod
        orig_get = emb_mod.get_embedding
        orig_cos = emb_mod.cosine_similarity
        emb_mod.get_embedding = lambda text, model="", api_base="": [1.0] * 10
        emb_mod.cosine_similarity = lambda a, b: 0.9
        try:
            result = sm._recall_turns("query", 10000)
            assert "u0" in result
            assert "a0" in result
        finally:
            emb_mod.get_embedding = orig_get
            emb_mod.cosine_similarity = orig_cos


class TestSessionMemoryIntegration:
    def test_build_think_messages_with_session_context(self):
        from agent.cognition._think import build_think_messages
        ctx = "Current Session：\nUser：hello\nAssistant：hi"
        msgs = build_think_messages("new question", {}, {}, ctx, "en")
        assert len(msgs) == 3
        assert msgs[1]["content"] == ctx

    def test_build_verify_no_duplicate_label(self):
        from agent.cognition._think import build_verify_messages
        ctx = "Current Session：\nUser：hello\nAssistant：hi"
        msgs = build_verify_messages("q", {}, "memory", "response", ctx, "en")
        content = msgs[1]["content"]
        assert ctx in content
        assert "Current Session：\nCurrent Session：" not in content

    def test_build_verify_empty_context_fallback(self):
        from agent.cognition._think import build_verify_messages
        msgs = build_verify_messages("q", {}, "memory", "response", "", "en")
        assert "(none)" in msgs[1]["content"]

    def test_finish_think_result_new_signature(self):
        from agent.cognition._think import finish_think_result
        result = finish_think_result(
            raw_response="raw",
            raw_response_at=datetime(2025, 1, 1),
            user_input="input",
            perception={"category": "chat"},
            memory_text="",
            verification_result="SKIP",
            verification_at=datetime(2025, 1, 1),
            final_response="final",
            final_response_at=datetime(2025, 1, 1),
            language="en",
        )
        assert result["final_response"] == "final"
        assert "thinking_notes" in result


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
