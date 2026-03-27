import asyncio
import copy
import logging
import os
import re
import shutil
import tempfile
import threading

from agent.tools import BaseTool, ToolManifest, ToolResult

_STRICT_SHELL_WHITELIST = [
    "ls", "dir", "cat", "head", "tail", "find", "grep", "wc -l", "wc -c", "wc", "date",
    "df", "df -h", "du", "du -sh", "free", "free -h", "uname", "uptime", "ps",
    "python3 -m py_compile", "python3 -m pytest", "python3 -m unittest",
    "git status", "git log", "git diff", "git branch",
]

_LOOSE_SHELL_WHITELIST = [
    "ls", "dir", "cat", "head", "tail", "find", "grep", "wc -l", "wc -c", "wc", "date",
    "df", "df -h", "du", "du -sh", "free", "free -h", "uname", "uptime", "ps", "top", "htop",
    "python3", "python",
    "python3 -m py_compile", "python3 -m pytest", "python3 -m unittest",
    "pip3 install", "pip install", "pip3 list", "pip list",
    "npm install", "npm run", "node",
    "git status", "git log", "git diff", "git branch",
    "afplay", "mpg123", "ffplay",
]

_FALLBACK = {
    "en": {
        "description": (
            "Delegate a complex multi-step task to an autonomous sub-agent.\n"
            "ALWAYS use a two-step flow:\n"
            "  Step 1: action='preview' + task description → generates a plan. You MUST output the tool result verbatim to the user. Do NOT summarize, paraphrase, or replace it with your own words.\n"
            "  Step 2: action='start' + task_id → starts background execution after user confirms.\n"
            "Never skip the preview step. Never start without user confirmation. Never rewrite the plan output."
        ),
        "parameters": {
            "action": "'preview' to generate plan, 'start' to begin execution",
            "task": "Task description (required for preview)",
            "task_id": "Task ID returned from preview (required for start)",
        },
        "examples": [
            "Scan project structure and generate README",
            "Refactor the finance module to add currency conversion",
        ],
    },
    "zh": {
        "description": (
            "将复杂任务外包给自主子智能体执行。\n"
            "必须按两步走：\n"
            "  第一步：action='preview' + 任务描述 → 生成执行计划。你必须将工具返回内容原样输出给用户，禁止概括、改写或用自己的话替代。\n"
            "  第二步：用户确认后：action='start' + task_id → 后台开始执行。\n"
            "禁止跳过预览步骤，禁止未经用户确认就开始执行，禁止改写计划内容。"
        ),
        "parameters": {
            "action": "'preview' 生成计划，'start' 开始执行",
            "task": "任务描述（preview 时必填）",
            "task_id": "preview 返回的任务号（start 时必填）",
        },
        "examples": [
            "扫描项目结构生成 README",
            "重构 finance 模块，添加货币转换功能",
        ],
    },
    "ja": {
        "description": (
            "複雑なタスクを自律サブエージェントに委託します。\n"
            "必ず2ステップで実行してください：\n"
            "  Step1: action='preview' + タスク説明 → 実行計画を生成。ツールの返却内容をそのままユーザーに出力すること。要約・言い換え・自分の言葉への置き換えは禁止。\n"
            "  Step2: ユーザー確認後：action='start' + task_id → バックグラウンドで実行開始。\n"
            "プレビューをスキップしないこと。ユーザー確認なしに開始しないこと。計画内容を書き換えないこと。"
        ),
        "parameters": {
            "action": "'preview' で計画生成、'start' で実行開始",
            "task": "タスクの説明（preview 時に必須）",
            "task_id": "preview で返されたタスクID（start 時に必須）",
        },
        "examples": [
            "プロジェクト構造をスキャンして README を生成",
            "finance モジュールを通貨換算に対応するようリファクタリング",
        ],
    },
}


def _run_in_background(coro):
    def runner():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(coro)
        finally:
            loop.close()
    threading.Thread(target=runner, daemon=True).start()


class DispatchTaskTool(BaseTool):

    def __init__(self, config: dict):
        self.config = config
        self._tool_cfg = config.get("tools", {}).get("dispatch_task", {})

    def manifest(self) -> ToolManifest:
        lang = self.config.get("language", "en")
        fb = _FALLBACK.get(lang, _FALLBACK["en"])
        return ToolManifest(
            name="dispatch_task",
            description=fb["description"],
            parameters=fb["parameters"],
            examples=fb["examples"],
        )

    def is_available(self) -> bool:
        return self._tool_cfg.get("enabled", True)

    def execute(self, params: dict) -> ToolResult:
        action = params.get("action", "preview").strip()

        if action == "preview":
            return self._preview(params)
        elif action == "start":
            return self._start(params)
        elif action == "resume":
            return self._resume(params)
        elif action == "retry":
            return self._retry(params)
        else:
            return ToolResult(success=False, data="", error=f"Unknown action '{action}'. Use 'preview', 'start', 'resume', or 'retry'.")

    def _preview(self, params: dict) -> ToolResult:
        task = params.get("task", "").strip()
        if not task:
            return ToolResult(success=False, data="", error="Missing 'task' parameter for preview.")

        strict_mode = self._tool_cfg.get("strict_mode", True)

        try:
            from agent.storage.outsource import create_task, update_task
            from agent.task_agent import plan_task_async

            # Create pending record
            session_id = self.config.get("_session_id", "")
            task_id = create_task(task, strict_mode=strict_mode)
            update_task(task_id, status="pending", session_id=session_id)

            # Generate plan synchronously (just planning, fast)
            result = {}
            def runner():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result["plan"] = loop.run_until_complete(plan_task_async(task, self.config))
                finally:
                    loop.close()
            t = threading.Thread(target=runner)
            t.start()
            t.join(timeout=30)
            plan = result.get("plan", [{"step": 1, "description": task}])

            update_task(task_id, plan=plan, total_steps=len(plan))

            # Format plan for display
            lang = self.config.get("language", "en")
            lines = []
            if lang == "zh":
                lines.append(f"📋 **外包任务计划**（任务号：`{task_id[:8]}`）\n")
                lines.append(f"**任务**：{task}\n")
                lines.append("**执行步骤**：")
                for step in plan:
                    lines.append(f"  {step.get('step', '?')}. {step.get('description', '')}")
                lines.append(f"\n确认后我会开始执行，你可以在 [/outsource](/outsource) 页面实时查看进度。")
                lines.append("\n**确认开始吗？**（回复「是」或「开始」）")
            elif lang == "ja":
                lines.append(f"📋 **タスク計画**（ID：`{task_id[:8]}`）\n")
                lines.append(f"**タスク**：{task}\n")
                lines.append("**実行ステップ**：")
                for step in plan:
                    lines.append(f"  {step.get('step', '?')}. {step.get('description', '')}")
                lines.append(f"\n確認後、バックグラウンドで実行します。[/outsource](/outsource) で進捗を確認できます。")
                lines.append(f"\n**実行を開始しますか？**")
            else:
                lines.append(f"📋 **Task Plan** (ID: `{task_id[:8]}`)\n")
                lines.append(f"**Task**: {task}\n")
                lines.append("**Steps**:")
                for step in plan:
                    lines.append(f"  {step.get('step', '?')}. {step.get('description', '')}")
                lines.append(f"\nTrack progress at [/outsource](/outsource) once started.")
                lines.append(f"\n**Shall I proceed?**")

            data = "\n".join(lines)
            # Embed task_id so AI can extract it for the start call
            data += f"\n\n<!-- task_id:{task_id} -->"
            return ToolResult(success=True, data=data)

        except Exception as e:
            return ToolResult(success=False, data="", error=f"Preview failed: {e}")

    def _start(self, params: dict) -> ToolResult:
        task_id = params.get("task_id", "").strip()
        if not task_id:
            return ToolResult(success=False, data="", error="Missing 'task_id' for start. Call preview first.")

        max_steps = self._tool_cfg.get("max_steps", 20)
        strict_mode = self._tool_cfg.get("strict_mode", True)

        try:
            from agent.storage.outsource import get_task, update_task
            from agent.storage import get_db_connection
            from agent.tools import ToolRegistry
            from agent.task_agent import run_task_async
            # If task_id is not a valid UUID/short-id, find the latest pending task
            is_valid_id = bool(re.match(r'^[0-9a-f\-]{8,36}$', task_id, re.I))
            if not is_valid_id:
                conn = get_db_connection()
                try:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT task_id FROM outsource_tasks
                            WHERE status = 'pending'
                            ORDER BY created_at DESC LIMIT 1
                        """)
                        row = cur.fetchone()
                        if row:
                            task_id = row[0]
                        else:
                            return ToolResult(success=False, data="", error="No pending task found.")
                finally:
                    conn.close()
            elif len(task_id) == 8:
                conn = get_db_connection()
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT task_id FROM outsource_tasks WHERE task_id LIKE %s LIMIT 1",
                                    (task_id + "%",))
                        row = cur.fetchone()
                        if row:
                            task_id = row[0]
                finally:
                    conn.close()

            record = get_task(task_id)
            if not record:
                return ToolResult(success=False, data="", error=f"Task {task_id} not found.")

            status = record.get("status", "")
            if status == "running":
                return ToolResult(success=True, data=f"Task `{task_id[:8]}` is already running.")
            if status in ("done", "failed", "cancelled"):
                return ToolResult(success=False, data="", error=f"Task `{task_id[:8]}` already finished (status: {status}). Use preview to create a new task.")

            # Check concurrent task limit
            max_concurrent = self._tool_cfg.get("max_concurrent", 6)
            conn = get_db_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM outsource_tasks WHERE status = 'running' AND deleted_at IS NULL")
                    running_count = cur.fetchone()[0]
            finally:
                conn.close()

            if running_count >= max_concurrent:
                update_task(task_id, status="suspended")
                lang = self.config.get("language", "en")
                if lang == "zh":
                    msg = f"⏸️ 任务已挂起（`{task_id[:8]}`）——当前已有 {running_count} 个任务在执行（上限 {max_concurrent}）。\n有空位后，你可以说「**继续执行**」或前往 [/outsource](/outsource) 手动继续。"
                elif lang == "ja":
                    msg = f"⏸️ タスクは一時停止されました（`{task_id[:8]}`）——現在 {running_count} 件実行中（上限 {max_concurrent}）。\n空きができたら「**再開して**」と言うか [/outsource](/outsource) で再開できます。"
                else:
                    msg = f"⏸️ Task suspended (`{task_id[:8]}`) — {running_count} tasks already running (limit {max_concurrent}).\nWhen a slot is free, say **"resume task"** or go to [/outsource](/outsource) to continue."
                return ToolResult(success=True, data=msg)

            task = record["title"]

            agent_config = copy.deepcopy(self.config)
            # Task agent needs higher token limit to output large file content
            task_max_tokens = self._tool_cfg.get("max_tokens", 8192)
            agent_config.setdefault("llm", {})["max_tokens"] = task_max_tokens

            if strict_mode:
                agent_config.setdefault("tools", {}).setdefault("shell_exec", {}).update({
                    "enabled": True,
                    "whitelist": _STRICT_SHELL_WHITELIST,
                    "timeout": 30,
                })
            else:
                agent_config.setdefault("tools", {}).setdefault("shell_exec", {}).update({
                    "enabled": True,
                    "whitelist": _LOOSE_SHELL_WHITELIST,
                    "timeout": 120,
                })

            # Capture the main FastAPI event loop for pushing results back
            try:
                _main_loop = asyncio.get_event_loop()
            except RuntimeError:
                _main_loop = None

            # Create a dedicated temp directory for this task's temporary files
            _tmp_dir = os.path.join(tempfile.gettempdir(), "jkriver_tasks", task_id[:8])
            os.makedirs(_tmp_dir, exist_ok=True)

            # Inject task context into agent config so ask_user tool can use it
            agent_config["_task_id"] = task_id
            agent_config["_main_loop"] = _main_loop
            agent_config["_tmp_dir"] = _tmp_dir

            from agent.api import _cancel_flags
            cancel_event = threading.Event()
            _cancel_flags[task_id] = cancel_event

            async def _run():
                try:
                    update_task(task_id, status="running")
                    registry = ToolRegistry(agent_config)
                    # Sub-agent must not recursively dispatch new tasks
                    registry._tools.pop("dispatch_task", None)
                    executed_steps = []

                    async def on_step(step_data: dict):
                        executed_steps.append(step_data)
                        update_task(task_id, steps=executed_steps, current_step=len(executed_steps))

                    result = await run_task_async(
                        task, agent_config, registry,
                        max_steps=max_steps,
                        strict_mode=strict_mode,
                        progress_callback=on_step,
                        cancel_event=cancel_event,
                    )
                    final_status = "done" if result["success"] else ("cancelled" if result.get("cancelled") else "failed")
                    update_task(task_id,
                        status=final_status,
                        result=result["result"],
                        files_changed=result["files_changed"],
                        steps=result["steps"],
                        current_step=len(result["steps"]),
                    )
                    _cancel_flags.pop(task_id, None)
                    # Clean up temp directory
                    try:
                        if os.path.exists(_tmp_dir):
                            shutil.rmtree(_tmp_dir, ignore_errors=True)
                    except Exception:
                        pass
                    # Push result back to the originating chat session via main loop
                    _session_id = self.config.get("_session_id", "")
                    if _session_id and _main_loop and _main_loop.is_running():
                        try:
                            from agent.api import push_task_result_to_session
                            asyncio.run_coroutine_threadsafe(
                                push_task_result_to_session(
                                    _session_id, task_id,
                                    result["success"], result["result"],
                                    files_changed=result.get("files_changed", []),
                                    steps_count=len(result.get("steps", [])),
                                    language=self.config.get("language", "zh"),
                                ),
                                _main_loop,
                            )
                        except Exception:
                            pass
                    # Auto-resume oldest suspended task if slot is now free
                    if final_status in ("done", "failed"):
                        try:
                            from agent.storage import get_db_connection as _gdc
                            _conn = _gdc()
                            try:
                                with _conn.cursor() as _cur:
                                    _cur.execute("""
                                        SELECT task_id FROM outsource_tasks
                                        WHERE status = 'suspended' AND deleted_at IS NULL
                                        ORDER BY created_at ASC LIMIT 1
                                    """)
                                    _row = _cur.fetchone()
                            finally:
                                _conn.close()
                            if _row:
                                _next_id = _row[0]
                                update_task(_next_id, status="pending")
                                _self_tool = DispatchTaskTool(self.config)
                                _self_tool._start({"task_id": _next_id})
                        except Exception:
                            pass
                except Exception as e:
                    logging.getLogger(__name__).exception("Unhandled error in task %s", task_id)
                    try:
                        update_task(task_id, status="failed", result=f"Unexpected error: {e}")
                    except Exception:
                        pass
                    _cancel_flags.pop(task_id, None)
                    try:
                        if os.path.exists(_tmp_dir):
                            shutil.rmtree(_tmp_dir, ignore_errors=True)
                    except Exception:
                        pass
                    # Auto-resume on failure too
                    try:
                        from agent.storage import get_db_connection as _gdc
                        _conn = _gdc()
                        try:
                            with _conn.cursor() as _cur:
                                _cur.execute("""
                                    SELECT task_id FROM outsource_tasks
                                    WHERE status = 'suspended' AND deleted_at IS NULL
                                    ORDER BY created_at ASC LIMIT 1
                                """)
                                _row = _cur.fetchone()
                        finally:
                            _conn.close()
                        if _row:
                            _next_id = _row[0]
                            update_task(_next_id, status="pending")
                            DispatchTaskTool(self.config)._start({"task_id": _next_id})
                    except Exception:
                        pass

            _run_in_background(_run())

            lang = self.config.get("language", "en")
            if lang == "zh":
                msg = f"🚀 任务已开始（`{task_id[:8]}`），在后台执行中。\n前往 [/outsource](/outsource) 查看实时进度。"
            elif lang == "ja":
                msg = f"🚀 タスクを開始しました（`{task_id[:8]}`）。バックグラウンドで実行中。\n[/outsource](/outsource) で進捗を確認できます。"
            else:
                msg = f"🚀 Task started (`{task_id[:8]}`), running in background.\nTrack progress at [/outsource](/outsource)."

            return ToolResult(success=True, data=msg)

        except Exception as e:
            return ToolResult(success=False, data="", error=f"Failed to start task: {e}")

    def _retry(self, params: dict) -> ToolResult:
        task_id = params.get("task_id", "").strip()
        if not task_id:
            return ToolResult(success=False, data="", error="Missing 'task_id' for retry.")
        try:
            from agent.storage.outsource import get_task, update_task
            record = get_task(task_id)
            if not record:
                return ToolResult(success=False, data="", error=f"Task {task_id} not found.")
            if record.get("status") not in ("failed", "cancelled"):
                return ToolResult(success=False, data="", error=f"Task `{task_id[:8]}` is not failed or cancelled (status: {record.get('status')}).")
            # Reset task state and re-run
            update_task(task_id, status="pending", result="", steps=[], current_step=0)
            return self._start({"task_id": task_id})
        except Exception as e:
            return ToolResult(success=False, data="", error=f"Failed to retry task: {e}")

    def _resume(self, params: dict) -> ToolResult:
        task_id = params.get("task_id", "").strip()
        if not task_id:
            # Auto-find the latest suspended task
            try:
                from agent.storage import get_db_connection
                conn = get_db_connection()
                try:
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT task_id FROM outsource_tasks
                            WHERE status = 'suspended' AND deleted_at IS NULL
                            ORDER BY created_at DESC LIMIT 1
                        """)
                        row = cur.fetchone()
                        if row:
                            task_id = row[0]
                        else:
                            return ToolResult(success=False, data="", error="No suspended task found.")
                finally:
                    conn.close()
            except Exception as e:
                return ToolResult(success=False, data="", error=f"Failed to find suspended task: {e}")
        try:
            from agent.storage.outsource import get_task, update_task
            from agent.storage import get_db_connection
            record = get_task(task_id)
            if not record:
                return ToolResult(success=False, data="", error=f"Task {task_id} not found.")
            if record.get("status") != "suspended":
                return ToolResult(success=False, data="", error=f"Task `{task_id[:8]}` is not suspended (status: {record.get('status')}).")
            max_concurrent = self._tool_cfg.get("max_concurrent", 6)
            conn = get_db_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM outsource_tasks WHERE status = 'running' AND deleted_at IS NULL")
                    running_count = cur.fetchone()[0]
            finally:
                conn.close()
            if running_count >= max_concurrent:
                lang = self.config.get("language", "en")
                if lang == "zh":
                    return ToolResult(success=False, data="", error=f"当前仍有 {running_count} 个任务在执行（上限 {max_concurrent}），请等待任务完成后再继续。")
                elif lang == "ja":
                    return ToolResult(success=False, data="", error=f"現在 {running_count} 件実行中（上限 {max_concurrent}）。他のタスク完了後に再開してください。")
                else:
                    return ToolResult(success=False, data="", error=f"Still {running_count} tasks running (limit {max_concurrent}). Wait for one to finish before resuming.")
            # Reset to pending and delegate to _start
            update_task(task_id, status="pending")
            return self._start({"task_id": task_id})
        except Exception as e:
            return ToolResult(success=False, data="", error=f"Failed to resume task: {e}")
