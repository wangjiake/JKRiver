import asyncio
import logging

from agent.utils.time_context import get_now
from agent.tools.preprocess import preprocess_input
from agent.tools._resolver import resolve_tools_async
from agent.utils.llm_client import is_llm_error
from agent.config.prompts import get_labels

from agent.core.session import Session, _load_resolver_profile
from agent.core.memory import build_memory_context_async
from agent.core.handlers import (
    _build_trajectory_block,
    _inject_tool_context,
    _handle_skills,
    _save_turn_data,
    _finalize_response,
)
from agent.core._outsource import (
    OUTSOURCE_TRIGGER_RE,
    OUTSOURCE_RESUME_KEYWORDS,
    OUTSOURCE_CONFIRM_WORDS,
)

logger = logging.getLogger(__name__)


def _try_outsource_intercept(
    processed_text: str,
    perception: dict,
    session: Session,
    input_metadata: dict,
    user_input_at,
    raw_user_input: str,
    L: dict,
) -> dict | None:
    """
    Check if this turn should be handled entirely by the outsource pipeline
    without going through the normal memory-build + LLM think cycle.

    Returns a result dict (same shape as run_cycle_async return value) if
    intercepted, or None to let the normal pipeline continue.
    """
    _stripped = processed_text.strip()

    # If user sent a short confirmation and there is exactly 1 pending outsource
    # task for this session, force tool resolution so dispatch_task(start) can run.
    if (not perception.get("need_tools")
            and _stripped.lower() in OUTSOURCE_CONFIRM_WORDS
            and len(_stripped) <= 10):
        try:
            from agent.storage.outsource import list_tasks
            _pending = [
                t for t in list_tasks(limit=20)
                if t.get("status") == "pending"
                and t.get("session_id") == session.id
            ]
            if len(_pending) == 1:
                perception["need_tools"] = True
                perception["_outsource_pending_id"] = _pending[0]["task_id"]
        except Exception:
            pass
        return None  # let normal pipeline run with updated perception

    # If outsource skill matched, directly run dispatch_task preview/resume
    # and short-circuit everything else (resolver, memory build, think step).
    _outsource_skills = session.skill_registry.match_keywords(processed_text)
    _outsource_skill = next((s for s in _outsource_skills if s.name == "outsource"), None)
    if not _outsource_skill:
        return None

    _is_resume = any(kw in processed_text.lower() for kw in OUTSOURCE_RESUME_KEYWORDS)
    _dispatch_tool = session.tool_registry.get_tool("dispatch_task")

    if _dispatch_tool and _is_resume:
        _resume_result = _dispatch_tool.execute({"action": "resume"})
        _resume_data = _resume_result.data if _resume_result.success else (_resume_result.error or "Resume failed")
        now = get_now()
        think_result = {
            "raw_response": _resume_data, "raw_response_at": now,
            "final_response": _resume_data, "final_response_at": now,
            "verification_result": "", "verification_result_at": now,
            "thinking_notes": "", "thinking_notes_at": now,
        }
        _save_turn_data(
            session, {"intent": "outsource_resume", "need_memory": False, "memory_type": "无",
                      "ai_summary": processed_text, "perception_at": now,
                      "topic_keywords": [], "category": "chat"},
            think_result,
            {"profile": [], "hypotheses": [], "strategies": [], "user_model": [],
             "events": [], "strategy_ids": [], "memory_text": ""},
            now, user_input_at, raw_user_input, _resume_data, [], input_metadata, L,
        )
        return {"response": _resume_data, "perception": {}, "memories": {},
                "trajectory": None, "think_result": think_result}

    _task_desc = OUTSOURCE_TRIGGER_RE.sub('', processed_text).strip() or processed_text
    if _dispatch_tool:
        _preview_result = _dispatch_tool.execute({"action": "preview", "task": _task_desc})
        if _preview_result.success:
            now = get_now()
            _preview_data = _preview_result.data
            think_result = {
                "raw_response": _preview_data, "raw_response_at": now,
                "final_response": _preview_data, "final_response_at": now,
                "verification_result": "", "verification_result_at": now,
                "thinking_notes": "", "thinking_notes_at": now,
            }
            _save_turn_data(
                session, {"intent": "outsource", "need_memory": False, "memory_type": "无",
                          "ai_summary": _task_desc, "perception_at": now,
                          "topic_keywords": [], "category": "chat"},
                think_result,
                {"profile": [], "hypotheses": [], "strategies": [], "user_model": [],
                 "events": [], "strategy_ids": [], "memory_text": ""},
                now, user_input_at, raw_user_input, _preview_data, [], input_metadata, L,
            )
            return {"response": _preview_data, "perception": {}, "memories": {},
                    "trajectory": None, "think_result": think_result}

    return None


async def run_cycle_async(user_input: str | dict, session: Session,
                          log_fn=None) -> dict:
    def log(level, msg):
        if log_fn:
            log_fn(level, msg)

    user_input_at = get_now()

    if isinstance(user_input, str):
        raw_input = {"type": "text", "text": user_input}
    else:
        raw_input = user_input

    language = session.full_config.get("language", "en")
    L = get_labels("context.labels", language)

    processed_text, input_metadata = preprocess_input(raw_input, session.tool_registry, language=language)
    log("info", f"输入类型={input_metadata['type']} 处理后={processed_text[:80]}")

    raw_user_input = raw_input.get("text", "") or processed_text

    log("info", "感知中...")
    perception = await session.cognition.perceive_async(
        processed_text,
        available_tools=session.tool_registry.list_available(),
    )
    category = perception.get("category", "chat")
    log("info", f"分类={category} 意图={perception['intent']}")

    corrected_input = perception.get("corrected_input", processed_text)
    if corrected_input != processed_text:
        llm_input = f"{corrected_input}\n{L['original_input_suffix'].format(text=processed_text)}"
    else:
        llm_input = processed_text

    trajectory = None
    _resolver_input = perception.get("ai_summary", processed_text)

    # Inject session_id into tool config so dispatch_task can push results back
    session.tool_registry.config["_session_id"] = session.id

    # Check if the outsource pipeline should handle this turn entirely
    _intercept = _try_outsource_intercept(
        processed_text, perception, session,
        input_metadata, user_input_at, raw_user_input, L,
    )
    if _intercept is not None:
        return _intercept

    if category == "knowledge":
        memories = {
            "profile": [], "hypotheses": [], "strategies": [],
            "user_model": [], "events": [], "strategy_ids": [],
            "memory_text": "",
        }
        memories_used_at = get_now()
        _profile = await asyncio.to_thread(_load_resolver_profile)
        tool_results = await resolve_tools_async(
            _resolver_input, perception, session.tool_registry,
            session.cognition.config, input_metadata,
            language=language, profile=_profile,
        )
    else:
        # Memory build + tool resolution in parallel
        log("info", "记忆构建 + 工具调度 并行中...")

        _profile = await asyncio.to_thread(_load_resolver_profile)
        memories, tool_results = await asyncio.gather(
            build_memory_context_async(perception, session.executed_strategy_ids,
                                       config=session.full_config),
            resolve_tools_async(
                _resolver_input, perception, session.tool_registry,
                session.cognition.config, input_metadata,
                language=language, profile=_profile,
            ),
        )

        session.executed_strategy_ids.update(memories.get("strategy_ids", []))
        memories_used_at = get_now()

        if category == "personal":
            trajectory = await session.cognition.analyze_trajectory_async(llm_input, memories)
            if trajectory:
                trajectory_block = _build_trajectory_block(trajectory, L)
                if memories["memory_text"]:
                    memories["memory_text"] += "\n\n" + trajectory_block
                else:
                    memories["memory_text"] = trajectory_block

    llm_input = _inject_tool_context(tool_results, memories, llm_input, L, log_fn)
    _handle_skills(processed_text, session, memories, L, log_fn)

    # Short-circuit: web_search result is the final response — skip LLM think step
    _web_search_result = next(
        (t for t in (tool_results or [])
         if t["tool"] == "web_search" and t["result"].success),
        None,
    )
    # Short-circuit: dispatch_task preview result is the final response — skip LLM think step
    _outsource_preview_data = memories.get("_outsource_preview")
    _dispatch_preview = next(
        (t for t in (tool_results or [])
         if t["tool"] == "dispatch_task" and t["result"].success and
         "task_id" in (t["result"].data or "")),
        None,
    )
    if _web_search_result:
        logger.info("[core] web_search short-circuit: skipping think step, data length=%d", len(_web_search_result["result"].data))
        now = get_now()
        think_result = {
            "raw_response": _web_search_result["result"].data,
            "raw_response_at": now,
            "final_response": _web_search_result["result"].data,
            "final_response_at": now,
            "verification_result": "SKIP",
            "verification_result_at": now,
            "thinking_notes": "web_search直接输出",
            "thinking_notes_at": now,
        }
        final_response = _finalize_response(think_result, tool_results, language)
    elif _outsource_preview_data or _dispatch_preview:
        now = get_now()
        _preview_data = _outsource_preview_data or _dispatch_preview["result"].data
        think_result = {
            "raw_response": _preview_data,
            "raw_response_at": now,
            "final_response": _preview_data,
            "final_response_at": now,
            "verification_result": "",
            "verification_result_at": now,
            "thinking_notes": "",
            "thinking_notes_at": now,
        }
        # Use empty tool_results to prevent _finalize_response from appending task_id again
        final_response = _finalize_response(think_result, tool_results if _dispatch_preview else [], language)
    else:
        _failed_search = next((t for t in (tool_results or []) if t["tool"] == "web_search"), None)
        if _failed_search:
            logger.warning("[core] web_search failed (success=False), falling through to think. error: %s", _failed_search["result"].error)
        log("info", "思考中...")
        think_result = await session.cognition.think_async(
            llm_input, perception, memories,
            user_input_at=user_input_at)
        final_response = _finalize_response(think_result, tool_results, language)

    if not is_llm_error(final_response):
        _save_turn_data(session, perception, think_result, memories, memories_used_at,
                        user_input_at, raw_user_input, final_response, tool_results, input_metadata, L)
    else:
        logger.warning("Skipping DB save: LLM error response: %s", final_response[:100])

    return {
        "response": final_response,
        "perception": perception,
        "memories": memories,
        "trajectory": trajectory,
        "think_result": think_result,
    }
