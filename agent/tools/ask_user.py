import threading

from agent.tools import BaseTool, ToolManifest, ToolResult

_FALLBACK = {
    "en": {
        "description": (
            "Ask the user a question and wait for their response. "
            "Use this when you need clarification before proceeding — "
            "e.g. local vs remote, which branch, which file to overwrite."
        ),
        "param": "The question to ask the user",
        "example": "Is this a local project or a GitHub repository?",
    },
    "zh": {
        "description": (
            "向用户提问并等待回复。"
            "当你需要确认才能继续时使用，例如：本地还是远端、用哪个分支、是否覆盖文件等。"
        ),
        "param": "向用户提出的问题",
        "example": "这是本地项目还是 GitHub 仓库？",
    },
    "ja": {
        "description": (
            "ユーザーに質問して回答を待ちます。"
            "続行前に確認が必要な場合に使用してください。"
        ),
        "param": "ユーザーへの質問",
        "example": "これはローカルプロジェクトですか、それとも GitHub リポジトリですか？",
    },
}


class AskUserTool(BaseTool):

    def __init__(self, config: dict):
        self.config = config

    def manifest(self) -> ToolManifest:
        lang = self.config.get("language", "en")
        fb = _FALLBACK.get(lang, _FALLBACK["en"])
        return ToolManifest(
            name="ask_user",
            description=fb["description"],
            parameters={"question": fb["param"]},
            examples=[fb["example"]],
            parameter_types={"question": "string"},
        )

    def is_available(self) -> bool:
        # Only available inside a task that has session + main loop context
        return bool(
            self.config.get("_session_id")
            and self.config.get("_task_id")
            and self.config.get("_main_loop")
        )

    def execute(self, params: dict) -> ToolResult:
        import asyncio

        question = params.get("question", "").strip()
        if not question:
            return ToolResult(success=False, data="", error="'question' parameter is required")

        task_id = self.config.get("_task_id", "")
        session_id = self.config.get("_session_id", "")
        main_loop = self.config.get("_main_loop")

        if not (task_id and session_id and main_loop):
            return ToolResult(success=False, data="", error="Missing session context — cannot ask user")

        try:
            from agent.routers._state import _task_questions
            from agent.routers.outsource import push_task_question_to_session
        except ImportError as e:
            return ToolResult(success=False, data="", error=f"Import error: {e}")

        event = threading.Event()
        holder: dict = {}
        _task_questions[task_id] = (event, holder)

        # Persist question to DB so client can recover it after refresh
        try:
            from agent.storage.outsource import update_task as _ot_update
            _ot_update(task_id, pending_question=question)
        except Exception:
            pass

        # Push question to the user's chat via the main event loop
        try:
            asyncio.run_coroutine_threadsafe(
                push_task_question_to_session(session_id, task_id, question),
                main_loop,
            )
        except Exception as e:
            _task_questions.pop(task_id, None)
            try:
                from agent.storage.outsource import update_task as _ot_update
                _ot_update(task_id, pending_question=None)
            except Exception:
                pass
            return ToolResult(success=False, data="", error=f"Failed to send question: {e}")

        # Block until user replies (5-minute timeout)
        answered = event.wait(timeout=300)
        _task_questions.pop(task_id, None)

        # Clear pending_question from DB regardless of outcome
        try:
            from agent.storage.outsource import update_task as _ot_update
            _ot_update(task_id, pending_question=None)
        except Exception:
            pass

        if not answered:
            return ToolResult(success=False, data="", error="User did not respond within 5 minutes — task aborted")

        return ToolResult(success=True, data=holder.get("answer", ""))
