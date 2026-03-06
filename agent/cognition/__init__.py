"""Cognition engine — thin coordinator that delegates to submodules."""

__all__ = ["CognitionEngine"]

import asyncio

from agent.utils.llm_client import call_llm_async, is_llm_error
from agent.utils.time_context import get_now
from agent.config.prompts import get_prompt, get_labels, get_failure_keywords

from agent.cognition._perceive import (
    build_perceive_messages, process_perceive_raw,
)
from agent.cognition._think import (
    build_think_messages, build_verify_messages,
    parse_verify_raw, finish_think_result,
)
from agent.cognition._trajectory import (
    build_trajectory_context, finish_trajectory_result,
)


class CognitionEngine:
    def __init__(self, config: dict):
        self.config = config.get("llm", {})
        self.cloud_configs = config.get("cloud_llm_configs", [])
        self.language = config.get("language", "en")
        self.chat_history: list[dict] = []
        esc = config.get("cloud_llm", {}).get("escalation", {})
        self._escalation_auto = esc.get("auto", False)
        self._escalation_keywords = get_failure_keywords(
            self.language, overrides=esc.get("failure_keywords"))
        self._escalation_min_len = esc.get("min_response_length", 20)

    def _should_escalate(self, response: str) -> bool:
        if not response or is_llm_error(response):
            return True
        if len(response.strip()) < self._escalation_min_len:
            return True
        for kw in self._escalation_keywords:
            if kw in response:
                return True
        return False

    # ── Sync shim (for test_demo_pipeline.py backward compat) ──

    def perceive(self, user_input: str, available_tools=None) -> dict:
        return asyncio.run(self.perceive_async(user_input, available_tools))

    # ── Async methods (native async IO via call_llm_async) ──

    async def perceive_async(self, user_input: str, available_tools=None) -> dict:
        messages = build_perceive_messages(
            user_input, available_tools, self.chat_history, self.language)
        raw = (await call_llm_async(messages, self.config)).strip()
        return process_perceive_raw(raw, user_input, self.language)

    async def analyze_trajectory_async(self, user_input: str, memories: dict) -> dict | None:
        messages = build_trajectory_context(user_input, memories, self.language)
        if messages is None:
            return None
        raw = (await call_llm_async(messages, self.config)).strip()
        return finish_trajectory_result(raw)

    async def _verify_async(self, user_input: str, perception: dict,
                memory_text: str, response: str,
                chat_history: list[dict] | None = None) -> str:
        messages = build_verify_messages(
            user_input, perception, memory_text, response, chat_history, self.language)
        raw = (await call_llm_async(messages, self.config)).strip()
        return parse_verify_raw(raw)

    async def think_async(self, user_input: str, perception: dict,
              memories: dict, use_cloud: bool = False) -> dict:
        messages = build_think_messages(
            user_input, perception, memories, self.chat_history, self.language)
        memory_text = memories.get("memory_text", "")

        if use_cloud and self.cloud_configs:
            raw_response = await call_llm_async(messages, self.cloud_configs[0])
        else:
            raw_response = await call_llm_async(messages, self.config)
            if self._escalation_auto and self.cloud_configs and self._should_escalate(raw_response):
                raw_response = await call_llm_async(messages, self.cloud_configs[0])
        raw_response_at = get_now()

        if perception.get("category") == "personal":
            verification_result = await self._verify_async(
                user_input, perception, memory_text, raw_response, self.chat_history)
            verification_at = get_now()
            if verification_result.startswith("FAIL"):
                fail_reason = verification_result.split(":", 1)[-1].split("：", 1)[-1].strip()
                messages.append({"role": "assistant", "content": raw_response})
                messages.append({"role": "user", "content":
                    get_prompt("cognition.regenerate_message", self.language, fail_reason=fail_reason)
                })
                final_response = await call_llm_async(messages, self.config)
                final_response_at = get_now()
            else:
                final_response = raw_response
                final_response_at = verification_at
        else:
            verification_result = "SKIP"
            final_response = raw_response
            verification_at = get_now()
            final_response_at = verification_at

        return finish_think_result(
            raw_response, raw_response_at, user_input, perception,
            memory_text, verification_result, verification_at,
            final_response, final_response_at,
            self.chat_history, self.language)
