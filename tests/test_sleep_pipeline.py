"""Sleep pipeline step-function tests.

Unit tests (no DB) for _PipelineState, _build_fact_lookup, _find_fact_in_profile.
Integration tests (DB required) for key pipeline steps using SAVEPOINT isolation.

Usage:
    python -m pytest tests/test_sleep_pipeline.py -v
    python tests/test_sleep_pipeline.py
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── DB availability check ────────────────────────────────

try:
    import psycopg2
    from agent.storage._db import _get_db_config, _thread_local
    _test_conn = psycopg2.connect(**_get_db_config())
    _test_conn.close()
    DB_AVAILABLE = True
except Exception:
    DB_AVAILABLE = False

try:
    import pytest
    _skip = pytest.mark.skipif(not DB_AVAILABLE, reason="PostgreSQL not available")
except ImportError:
    pytest = None
    _skip = lambda cls: cls  # noqa: E731


# ── Base test class with SAVEPOINT isolation ─────────────

class _DBTestBase:
    """Injects a shared connection via _thread_local.conn + SAVEPOINT."""

    def setup_method(self):
        if not DB_AVAILABLE:
            return
        self.conn = psycopg2.connect(**_get_db_config())
        self.conn.autocommit = False
        _thread_local.conn = self.conn
        with self.conn.cursor() as cur:
            cur.execute("SAVEPOINT test_sp")

    def teardown_method(self):
        if not DB_AVAILABLE:
            return
        try:
            with self.conn.cursor() as cur:
                cur.execute("ROLLBACK TO SAVEPOINT test_sp")
        except Exception:
            pass
        _thread_local.conn = None
        try:
            self.conn.close()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════
#  Unit tests — PipelineState + fact lookup (no DB)
# ═══════════════════════════════════════════════════════════

from agent.sleep._pipeline_state import _PipelineState, _build_fact_lookup, _find_fact_in_profile


def _make_fact(id, category="位置", subject="居住地", value="深圳",
               layer="suspected", **kwargs):
    return {
        "id": id,
        "category": category,
        "subject": subject,
        "value": value,
        "layer": layer,
        "mention_count": 1,
        "source_type": "stated",
        "evidence": [],
        "start_time": datetime(2025, 1, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        "superseded_by": None,
        **kwargs,
    }


class TestPipelineState:

    def test_dataclass_init(self):
        state = _PipelineState(
            session_convs={}, config={}, language="en", L={},
        )
        assert state.pipeline_errors == 0
        assert state.all_msg_ids == []
        assert state.new_fact_count == 0
        assert state.confirmed_count == 0
        assert state.dispute_resolved == 0
        assert state.affected_fact_ids == set()

    def test_mutation(self):
        state = _PipelineState(
            session_convs={}, config={}, language="en", L={},
        )
        state.pipeline_errors += 1
        state.all_msg_ids.append(42)
        state.affected_fact_ids.add(7)
        assert state.pipeline_errors == 1
        assert state.all_msg_ids == [42]
        assert 7 in state.affected_fact_ids


class TestBuildFactLookup:

    def test_empty_profile(self):
        lookup = _build_fact_lookup([])
        assert lookup == {}

    def test_basic_lookup(self):
        profile = [_make_fact(1, "位置", "居住地", "深圳")]
        lookup = _build_fact_lookup(profile)
        result = _find_fact_in_profile(lookup, "位置", "居住地")
        assert result is not None
        assert result["id"] == 1

    def test_case_insensitive(self):
        profile = [_make_fact(1, "Location", "City", "Shenzhen")]
        lookup = _build_fact_lookup(profile)
        result = _find_fact_in_profile(lookup, "location", "city")
        assert result is not None
        assert result["id"] == 1

    def test_synonym_expansion(self):
        profile = [_make_fact(1, "位置", "居住地", "深圳")]
        lookup = _build_fact_lookup(profile)
        # "居住城市" is a synonym of "居住地"
        result = _find_fact_in_profile(lookup, "位置", "居住城市")
        assert result is not None
        assert result["id"] == 1

    def test_category_synonym(self):
        profile = [_make_fact(1, "位置", "居住地", "深圳")]
        lookup = _build_fact_lookup(profile)
        # "居住" is a category synonym of "位置"
        result = _find_fact_in_profile(lookup, "居住", "居住地")
        assert result is not None
        assert result["id"] == 1

    def test_not_found(self):
        profile = [_make_fact(1, "位置", "居住地", "深圳")]
        lookup = _build_fact_lookup(profile)
        result = _find_fact_in_profile(lookup, "职业", "工作")
        assert result is None

    def test_multiple_facts(self):
        profile = [
            _make_fact(1, "位置", "居住地", "深圳"),
            _make_fact(2, "职业", "工作", "工程师"),
        ]
        lookup = _build_fact_lookup(profile)
        assert _find_fact_in_profile(lookup, "位置", "居住地")["id"] == 1
        assert _find_fact_in_profile(lookup, "职业", "工作")["id"] == 2

    def test_first_fact_wins(self):
        """When multiple facts share the same (cat, subj), the first one wins."""
        profile = [
            _make_fact(1, "位置", "居住地", "深圳"),
            _make_fact(2, "位置", "居住地", "北京"),
        ]
        lookup = _build_fact_lookup(profile)
        result = _find_fact_in_profile(lookup, "位置", "居住地")
        assert result["id"] == 1


# ═══════════════════════════════════════════════════════════
#  Integration tests — pipeline steps (DB required)
# ═══════════════════════════════════════════════════════════

from agent.storage import (
    save_profile_fact, find_current_fact, confirm_profile_fact,
    load_full_current_profile, load_suspected_profile,
    load_disputed_facts, resolve_dispute,
)


def _make_state(**overrides) -> _PipelineState:
    """Create a _PipelineState with sensible defaults for testing."""
    from agent.config.prompts import get_labels
    defaults = dict(
        session_convs={},
        config={"llm": {"model": "test", "api_base": "http://localhost:11434"}},
        language="en",
        L=get_labels("context.labels", "en"),
    )
    defaults.update(overrides)
    return _PipelineState(**defaults)


@_skip
class TestStepExtractSessions(_DBTestBase):

    @patch("agent.sleep.orchestration.extract_events", return_value=[])
    @patch("agent.sleep.orchestration.extract_observations_and_tags")
    def test_observations_saved(self, mock_extract, mock_events):
        mock_extract.return_value = {
            "observations": [
                {"type": "statement", "content": "I live in Shenzhen",
                 "about": "user", "subject": "location"},
            ],
            "tags": [],
            "relationships": [],
        }
        state = _make_state(session_convs={
            "test-sess": [
                {"id": 1, "user_input": "hi", "assistant_reply": "hello",
                 "user_input_at": datetime(2025, 6, 1, tzinfo=timezone.utc), "intent": "greeting"},
            ],
        })
        state.existing_profile = []

        from agent.sleep.orchestration import _step_extract_sessions
        _step_extract_sessions(state)

        assert len(state.all_msg_ids) == 1
        assert len(state.all_observations) == 1
        assert state.all_observations[0]["content"] == "I live in Shenzhen"


@_skip
class TestStepClassify(_DBTestBase):

    @patch("agent.sleep.orchestration.generate_strategies", return_value=[])
    @patch("agent.sleep.orchestration.create_new_facts")
    @patch("agent.sleep.orchestration.classify_observations")
    def test_new_facts_created(self, mock_classify, mock_create, mock_strat):
        # Seed a fact
        save_profile_fact("位置", "居住地", "深圳")

        mock_classify.return_value = [
            {"obs_index": 0, "action": "new", "reason": "new info"},
        ]
        mock_create.return_value = [
            {"category": "职业", "subject": "工作", "value": "工程师",
             "source_type": "stated"},
        ]

        state = _make_state()
        state.current_profile = load_full_current_profile(exclude_superseded=True)
        state.all_observations = [
            {"type": "statement", "content": "I am an engineer",
             "subject": "work", "_conv_time": datetime(2025, 6, 1, tzinfo=timezone.utc)},
        ]
        state.all_convs = [{"user_input_at": datetime(2025, 6, 1, tzinfo=timezone.utc)}]

        from agent.sleep.orchestration import _step_classify_and_integrate
        _step_classify_and_integrate(state)

        assert state.new_fact_count >= 1
        assert len(state.changed_items) >= 1
        assert state.changed_items[0]["change_type"] == "new"

    @patch("agent.sleep.orchestration.generate_strategies", return_value=[])
    @patch("agent.sleep.orchestration.classify_observations")
    def test_support_adds_evidence(self, mock_classify, mock_strat):
        fid = save_profile_fact("位置", "居住地", "深圳")

        mock_classify.return_value = [
            {"obs_index": 0, "action": "support", "fact_id": fid, "reason": "confirmed"},
        ]

        state = _make_state()
        state.current_profile = load_full_current_profile(exclude_superseded=True)
        state.all_observations = [
            {"type": "statement", "content": "Still in Shenzhen",
             "subject": "location", "_conv_time": datetime(2025, 6, 1, tzinfo=timezone.utc)},
        ]
        state.all_convs = [{"user_input_at": datetime(2025, 6, 1, tzinfo=timezone.utc)}]

        from agent.sleep.orchestration import _step_classify_and_integrate
        _step_classify_and_integrate(state)

        assert fid in state.affected_fact_ids


@_skip
class TestStepCrossVerify(_DBTestBase):

    @patch("agent.sleep.orchestration.cross_verify_suspected_facts")
    def test_confirm_suspected(self, mock_verify):
        fid = save_profile_fact("职业", "工作", "工程师")
        mock_verify.return_value = [
            {"fact_id": fid, "action": "confirm", "reason": "consistent"},
        ]

        state = _make_state()
        state.latest_conv_time = datetime(2025, 6, 1, tzinfo=timezone.utc)

        from agent.sleep.orchestration import _step_cross_verify
        _step_cross_verify(state)

        assert state.confirmed_count == 1
        assert fid in state.affected_fact_ids
        fact = find_current_fact("职业", "工作")
        assert fact["layer"] == "confirmed"


@_skip
class TestStepResolveDisputes(_DBTestBase):

    @patch("agent.sleep.orchestration.resolve_disputes_with_llm")
    def test_accept_new_resolves(self, mock_resolve):
        old_id = save_profile_fact("位置", "居住地", "深圳")
        new_id = save_profile_fact("位置", "居住地", "北京")

        mock_resolve.return_value = [
            {"old_fact_id": old_id, "new_fact_id": new_id,
             "action": "accept_new", "reason": "moved"},
        ]

        state = _make_state()
        state.latest_conv_time = datetime(2025, 6, 1, tzinfo=timezone.utc)
        state.current_profile = load_full_current_profile(exclude_superseded=True)

        from agent.sleep.orchestration import _step_resolve_disputes
        _step_resolve_disputes(state)

        assert state.dispute_resolved == 1
        assert new_id in state.affected_fact_ids


# ═══════════════════════════════════════════════════════════
#  Error counting
# ═══════════════════════════════════════════════════════════

class TestErrorCounting:

    @patch("agent.sleep.orchestration.load_full_current_profile", return_value=[])
    @patch("agent.sleep.orchestration.extract_fact_edges", side_effect=RuntimeError("boom"))
    def test_edge_extraction_error_increments(self, mock_edges, mock_profile):
        state = _make_state()
        state.affected_fact_ids = {1, 2}

        from agent.sleep.orchestration import _step_extract_edges
        _step_extract_edges(state)

        assert state.pipeline_errors == 1

    @patch("agent.sleep.orchestration.load_full_current_profile", return_value=[])
    @patch("agent.sleep.orchestration.format_profile_text", side_effect=RuntimeError("snapshot fail"))
    def test_snapshot_error_increments(self, mock_format, mock_profile):
        state = _make_state()

        from agent.sleep.orchestration import _step_snapshot
        _step_snapshot(state)

        assert state.pipeline_errors == 1


# ═══════════════════════════════════════════════════════════
#  standalone runner
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    passed = failed = skipped = 0
    for cls_name, cls in sorted(globals().items()):
        if not isinstance(cls, type) or not cls_name.startswith("Test"):
            continue

        needs_db = issubclass(cls, _DBTestBase)
        if needs_db and not DB_AVAILABLE:
            for method_name in sorted(dir(cls)):
                if method_name.startswith("test_"):
                    print(f"  SKIP  {cls_name}.{method_name} (no DB)")
                    skipped += 1
            continue

        for method_name in sorted(dir(cls)):
            if not method_name.startswith("test_"):
                continue
            name = f"{cls_name}.{method_name}"
            instance = cls()
            try:
                if hasattr(instance, "setup_method"):
                    instance.setup_method()
                getattr(instance, method_name)()
                print(f"  PASS  {name}")
                passed += 1
            except Exception as e:
                print(f"  FAIL  {name}: {e}")
                failed += 1
            finally:
                if hasattr(instance, "teardown_method"):
                    try:
                        instance.teardown_method()
                    except Exception:
                        pass
    print(f"\n{passed} passed, {failed} failed, {skipped} skipped")
    sys.exit(1 if failed else 0)
