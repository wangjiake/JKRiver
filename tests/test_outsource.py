"""Unit tests for the outsource/task-dispatch system.

Pure unit tests — no database, no LLM, no network.

Usage:
    python -m pytest tests/test_outsource.py -v
    python tests/test_outsource.py
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ═══════════════════════════════════════════════════════════
#  task_agent._extract_json
# ═══════════════════════════════════════════════════════════

from agent.task_agent import _extract_json


class TestExtractJson:
    def test_plain_json_object(self):
        assert _extract_json('{"action": "done", "result": "ok"}') == {"action": "done", "result": "ok"}

    def test_json_in_fenced_block(self):
        text = '```json\n{"action": "tool", "tool": "shell_exec"}\n```'
        assert _extract_json(text) == {"action": "tool", "tool": "shell_exec"}

    def test_json_in_plain_code_block(self):
        text = '```\n{"action": "error", "reason": "not found"}\n```'
        assert _extract_json(text) == {"action": "error", "reason": "not found"}

    def test_json_embedded_in_prose(self):
        text = 'Here is my response: {"action": "done", "result": "success"} — done.'
        result = _extract_json(text)
        assert result == {"action": "done", "result": "success"}

    def test_json_with_braces_in_string_value(self):
        text = '{"action": "tool", "reasoning": "check {this} value"}'
        result = _extract_json(text)
        assert result is not None
        assert result["action"] == "tool"

    def test_none_on_garbage(self):
        assert _extract_json("this is not JSON at all") is None

    def test_none_on_empty(self):
        assert _extract_json("") is None

    def test_none_on_incomplete_json(self):
        assert _extract_json('{"action": "done"') is None

    def test_nested_json(self):
        text = '{"action": "tool", "params": {"path": "/tmp/x.py", "content": "print(1)"}}'
        result = _extract_json(text)
        assert result["params"]["path"] == "/tmp/x.py"

    def test_strips_whitespace(self):
        assert _extract_json('  {"a": 1}  ') == {"a": 1}

    def test_json_with_newlines_in_value(self):
        text = '{"action": "tool", "params": {"content": "line1\\nline2"}}'
        result = _extract_json(text)
        assert result is not None
        assert result["action"] == "tool"


# ═══════════════════════════════════════════════════════════
#  DispatchTaskTool — manifest, is_available, action routing
# ═══════════════════════════════════════════════════════════

from agent.tools.dispatch_task import DispatchTaskTool, _STRICT_SHELL_WHITELIST, _LOOSE_SHELL_WHITELIST


class TestDispatchTaskToolManifest:
    def _tool(self, lang="en", enabled=True):
        cfg = {"language": lang, "tools": {"dispatch_task": {"enabled": enabled}}}
        return DispatchTaskTool(cfg)

    def test_manifest_name(self):
        assert self._tool().manifest().name == "dispatch_task"

    def test_manifest_has_description(self):
        m = self._tool().manifest()
        assert m.description and len(m.description) > 10

    def test_manifest_zh_language(self):
        m = self._tool(lang="zh").manifest()
        assert m.description  # non-empty

    def test_manifest_ja_language(self):
        m = self._tool(lang="ja").manifest()
        assert m.description

    def test_is_available_true_by_default(self):
        tool = DispatchTaskTool({"tools": {"dispatch_task": {}}})
        assert tool.is_available() is True

    def test_is_available_false_when_disabled(self):
        tool = DispatchTaskTool({"tools": {"dispatch_task": {"enabled": False}}})
        assert tool.is_available() is False


class TestDispatchTaskToolExecuteRouting:
    def _tool(self):
        return DispatchTaskTool({"language": "en", "tools": {"dispatch_task": {}}})

    def test_unknown_action_returns_error(self):
        tool = self._tool()
        result = tool.execute({"action": "invalid_action"})
        assert result.success is False
        assert "Unknown action" in result.error

    def test_missing_task_id_for_start(self):
        tool = self._tool()
        result = tool.execute({"action": "start", "task_id": ""})
        assert result.success is False
        assert "task_id" in result.error.lower() or "missing" in result.error.lower()

    def test_missing_task_for_preview(self):
        tool = self._tool()
        result = tool.execute({"action": "preview", "task": ""})
        assert result.success is False
        assert "task" in result.error.lower() or "missing" in result.error.lower()

    def test_missing_task_id_for_retry(self):
        tool = self._tool()
        result = tool.execute({"action": "retry", "task_id": ""})
        assert result.success is False
        assert "task_id" in result.error.lower() or "missing" in result.error.lower()

    def test_default_action_is_preview(self):
        tool = self._tool()
        # No action key — should route to preview and fail with missing 'task'
        result = tool.execute({"task": ""})
        assert result.success is False


class TestDispatchTaskToolStart:
    def _tool(self, tool_cfg=None):
        cfg = {"language": "en", "tools": {"dispatch_task": tool_cfg or {}}}
        return DispatchTaskTool(cfg)

    def _make_mock_conn(self, running_count=0):
        mock_cur = MagicMock()
        mock_cur.__enter__ = lambda s: s
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchone.return_value = (running_count,)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        return mock_conn

    @patch("agent.storage.outsource.get_task")
    def test_start_task_not_found(self, mock_get_task):
        mock_get_task.return_value = None
        tool = self._tool()
        result = tool._start({"task_id": "abc12345-0000-0000-0000-000000000000"})
        assert result.success is False
        assert "not found" in result.error

    @patch("agent.storage.outsource.get_task")
    def test_start_already_running(self, mock_get_task):
        mock_get_task.return_value = {"task_id": "abc", "title": "test", "status": "running", "strict_mode": True}
        tool = self._tool()
        result = tool._start({"task_id": "abc12345-0000-0000-0000-000000000000"})
        assert result.success is True
        assert "already running" in result.data

    @patch("agent.storage.outsource.get_task")
    def test_start_already_done(self, mock_get_task):
        mock_get_task.return_value = {"task_id": "abc", "title": "test", "status": "done", "strict_mode": True}
        tool = self._tool()
        result = tool._start({"task_id": "abc12345-0000-0000-0000-000000000000"})
        assert result.success is False
        assert "finished" in result.error or "done" in result.error

    @patch("agent.storage.outsource.get_task")
    def test_start_already_cancelled(self, mock_get_task):
        mock_get_task.return_value = {"task_id": "abc", "title": "test", "status": "cancelled", "strict_mode": True}
        tool = self._tool()
        result = tool._start({"task_id": "abc12345-0000-0000-0000-000000000000"})
        assert result.success is False

    @patch("agent.storage.outsource.update_task")
    @patch("agent.storage.get_db_connection")
    @patch("agent.storage.outsource.get_task")
    def test_start_suspends_when_at_limit(self, mock_get_task, mock_get_conn, mock_update):
        mock_get_task.return_value = {"task_id": "abc12345-0000-0000-0000-000000000000",
                                      "title": "test task", "status": "pending", "strict_mode": True}
        mock_conn = self._make_mock_conn(running_count=6)
        mock_get_conn.return_value = mock_conn
        tool = self._tool({"max_concurrent": 6})
        result = tool._start({"task_id": "abc12345-0000-0000-0000-000000000000"})
        assert result.success is True
        assert "suspended" in result.data.lower() or "⏸" in result.data
        mock_update.assert_called_once()
        call_kwargs = mock_update.call_args
        assert call_kwargs[1].get("status") == "suspended"

    @patch("agent.storage.outsource.update_task")
    @patch("agent.storage.get_db_connection")
    @patch("agent.storage.outsource.get_task")
    def test_start_suspends_message_zh(self, mock_get_task, mock_get_conn, mock_update):
        mock_get_task.return_value = {"task_id": "abc12345-0000-0000-0000-000000000000",
                                      "title": "test task", "status": "pending", "strict_mode": True}
        mock_conn = self._make_mock_conn(running_count=6)
        mock_get_conn.return_value = mock_conn
        cfg = {"language": "zh", "tools": {"dispatch_task": {"max_concurrent": 6}}}
        tool = DispatchTaskTool(cfg)
        result = tool._start({"task_id": "abc12345-0000-0000-0000-000000000000"})
        assert result.success is True
        assert "挂起" in result.data or "继续执行" in result.data


class TestDispatchTaskToolRetry:
    def _tool(self):
        return DispatchTaskTool({"language": "en", "tools": {"dispatch_task": {}}})

    @patch("agent.storage.outsource.get_task")
    def test_retry_task_not_found(self, mock_get_task):
        mock_get_task.return_value = None
        tool = self._tool()
        result = tool._retry({"task_id": "abc12345-0000-0000-0000-000000000000"})
        assert result.success is False
        assert "not found" in result.error

    @patch("agent.storage.outsource.get_task")
    def test_retry_task_still_running(self, mock_get_task):
        mock_get_task.return_value = {"task_id": "abc", "title": "t", "status": "running"}
        tool = self._tool()
        result = tool._retry({"task_id": "abc12345-0000-0000-0000-000000000000"})
        assert result.success is False
        assert "not failed or cancelled" in result.error

    @patch("agent.storage.outsource.get_task")
    def test_retry_task_pending(self, mock_get_task):
        mock_get_task.return_value = {"task_id": "abc", "title": "t", "status": "pending"}
        tool = self._tool()
        result = tool._retry({"task_id": "abc12345-0000-0000-0000-000000000000"})
        assert result.success is False


class TestDispatchTaskToolResume:
    def _tool(self, tool_cfg=None):
        cfg = {"language": "en", "tools": {"dispatch_task": tool_cfg or {}}}
        return DispatchTaskTool(cfg)

    @patch("agent.storage.outsource.get_task")
    def test_resume_task_not_found(self, mock_get_task):
        mock_get_task.return_value = None
        tool = self._tool()
        result = tool._resume({"task_id": "abc12345-0000-0000-0000-000000000000"})
        assert result.success is False
        assert "not found" in result.error

    @patch("agent.storage.outsource.get_task")
    def test_resume_task_not_suspended(self, mock_get_task):
        mock_get_task.return_value = {"task_id": "abc", "title": "t", "status": "running"}
        tool = self._tool()
        result = tool._resume({"task_id": "abc12345-0000-0000-0000-000000000000"})
        assert result.success is False
        assert "not suspended" in result.error

    @patch("agent.storage.get_db_connection")
    @patch("agent.storage.outsource.get_task")
    def test_resume_blocked_by_limit(self, mock_get_task, mock_get_conn):
        mock_get_task.return_value = {"task_id": "abc12345-0000-0000-0000-000000000000",
                                      "title": "t", "status": "suspended"}
        mock_cur = MagicMock()
        mock_cur.__enter__ = lambda s: s
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchone.return_value = (6,)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_get_conn.return_value = mock_conn
        tool = self._tool({"max_concurrent": 6})
        result = tool._resume({"task_id": "abc12345-0000-0000-0000-000000000000"})
        assert result.success is False
        assert "running" in result.error or "limit" in result.error


# ═══════════════════════════════════════════════════════════
#  Shell whitelists
# ═══════════════════════════════════════════════════════════

class TestShellWhitelists:
    def test_strict_contains_find(self):
        assert "find" in _STRICT_SHELL_WHITELIST

    def test_strict_contains_grep(self):
        assert "grep" in _STRICT_SHELL_WHITELIST

    def test_strict_contains_pytest(self):
        assert "python3 -m pytest" in _STRICT_SHELL_WHITELIST

    def test_strict_excludes_pip(self):
        assert "pip3 install" not in _STRICT_SHELL_WHITELIST
        assert "pip install" not in _STRICT_SHELL_WHITELIST

    def test_strict_excludes_npm_install(self):
        assert "npm install" not in _STRICT_SHELL_WHITELIST

    def test_loose_contains_pip(self):
        assert "pip3 install" in _LOOSE_SHELL_WHITELIST

    def test_loose_contains_npm(self):
        assert "npm install" in _LOOSE_SHELL_WHITELIST

    def test_loose_contains_python3(self):
        assert "python3" in _LOOSE_SHELL_WHITELIST

    def test_strict_subset_of_loose(self):
        # Every read-only command in strict must also be in loose
        read_only = {"ls", "find", "grep", "cat", "wc -l", "git status", "python3 -m pytest"}
        for cmd in read_only:
            assert cmd in _LOOSE_SHELL_WHITELIST, f"{cmd!r} missing from loose whitelist"


# ═══════════════════════════════════════════════════════════
#  update_task — field filtering logic
# ═══════════════════════════════════════════════════════════

class TestUpdateTaskFieldFiltering:
    """Test that update_task silently drops unknown/disallowed fields."""

    def test_allowed_fields_accepted(self):
        """Verify the allowed-set contract — no DB needed, just import the set."""
        from agent.storage.outsource import update_task
        import inspect
        src = inspect.getsource(update_task)
        for field in ("status", "plan", "steps", "result", "session_id", "pending_question"):
            assert field in src, f"Expected allowed field {field!r} in update_task source"

    def test_disallowed_fields_filtered(self):
        """update_task with only unknown fields should do nothing (no DB call)."""
        from agent.storage.outsource import update_task
        with patch("agent.storage.outsource.get_db_connection") as mock_conn:
            update_task("fake-id", nonexistent_field="x", another_bad="y")
            mock_conn.assert_not_called()


# ═══════════════════════════════════════════════════════════
#  storage.outsource — pure logic (mocked DB)
# ═══════════════════════════════════════════════════════════

class TestOutsourceStorage:
    def _mock_conn(self, fetchone=None, fetchall=None, rowcount=1):
        mock_cur = MagicMock()
        mock_cur.__enter__ = lambda s: s
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchone.return_value = fetchone
        mock_cur.fetchall.return_value = fetchall or []
        mock_cur.rowcount = rowcount
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        return mock_conn

    @patch("agent.storage.outsource.get_db_connection")
    def test_create_task_returns_uuid(self, mock_get_conn):
        mock_get_conn.return_value = self._mock_conn()
        from agent.storage.outsource import create_task
        task_id = create_task("my task")
        assert len(task_id) == 36  # standard UUID length
        assert task_id.count("-") == 4

    @patch("agent.storage.outsource.get_db_connection")
    def test_get_task_returns_none_when_missing(self, mock_get_conn):
        mock_get_conn.return_value = self._mock_conn(fetchone=None)
        from agent.storage.outsource import get_task
        assert get_task("nonexistent-id") is None

    @patch("agent.storage.outsource.get_db_connection")
    def test_delete_task_returns_true_on_success(self, mock_get_conn):
        mock_get_conn.return_value = self._mock_conn(rowcount=1)
        from agent.storage.outsource import delete_task
        assert delete_task("some-id") is True

    @patch("agent.storage.outsource.get_db_connection")
    def test_delete_task_returns_false_when_not_found(self, mock_get_conn):
        mock_get_conn.return_value = self._mock_conn(rowcount=0)
        from agent.storage.outsource import delete_task
        assert delete_task("nonexistent-id") is False

    @patch("agent.storage.outsource.get_db_connection")
    def test_count_active_returns_int(self, mock_get_conn):
        mock_get_conn.return_value = self._mock_conn(fetchone=(3,))
        from agent.storage.outsource import count_active
        assert count_active() == 3


if __name__ == "__main__":
    import unittest
    loader = unittest.TestLoader()
    # pytest-style classes need manual discovery
    import sys
    import traceback
    passed = failed = 0
    for name, obj in list(globals().items()):
        if isinstance(obj, type) and name.startswith("Test"):
            for mname in dir(obj):
                if mname.startswith("test_"):
                    try:
                        getattr(obj(), mname)()
                        print(f"  PASS  {name}.{mname}")
                        passed += 1
                    except Exception as e:
                        print(f"  FAIL  {name}.{mname}: {e}")
                        traceback.print_exc()
                        failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
