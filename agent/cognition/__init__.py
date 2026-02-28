
import json
from datetime import datetime
from agent.utils.llm_client import call_llm, call_llm_async
from agent.utils.time_context import get_now
from agent.config.prompts import get_prompt, get_labels

class CognitionEngine:
    def __init__(self, config: dict):
        self.config = config.get("llm", {})
        self.cloud_configs = config.get("cloud_llm_configs", [])
        self.language = config.get("language", "zh")
        self.chat_history: list[dict] = []
        esc = config.get("cloud_llm", {}).get("escalation", {})
        self._escalation_auto = esc.get("auto", False)
        self._escalation_keywords = esc.get("failure_keywords", [])
        self._escalation_min_len = esc.get("min_response_length", 20)

    def _should_escalate(self, response: str) -> bool:
        EL = get_labels("errors.llm", self.language)
        fail_prefix = EL.get("call_failed", "").split("{error}")[0]
        if not response or (fail_prefix and response.startswith(fail_prefix)):
            return True
        if len(response.strip()) < self._escalation_min_len:
            return True
        for kw in self._escalation_keywords:
            if kw in response:
                return True
        return False

    def perceive(self, user_input: str, available_tools=None) -> dict:

        L = get_labels("context.labels", self.language)

        recent_context = ""
        if self.chat_history:
            recent = self.chat_history[-3:]
            for turn in recent:
                recent_context += f"{L['user']}：{turn['user_summary']}\n"
                recent_context += f"{L['assistant']}：{turn['assistant_summary']}\n"

        context_block = ""
        if recent_context:
            context_block = (
                f"{L['recent_context']}：\n{recent_context}\n"
                f"{L['use_context_hint']}\n\n"
            )

        system_content = get_prompt("cognition.perceive_system", self.language)

        if available_tools:
            tool_lines = [f"- {m.name}: {m.description}" for m in available_tools]
            system_content += f"\n\n{L['available_tools']}：\n" + "\n".join(tool_lines)

        user_content = get_prompt(
            "cognition.perceive_user", self.language,
            system_time=get_now().strftime('%Y-%m-%dT%H:%M'),
            context_block=context_block,
            user_input=user_input,
        )

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ]

        raw = call_llm(messages, self.config).strip()
        perception_at = get_now()
        labels = get_labels("cognition.perceive_labels", self.language)
        result = self._parse_perceive_output(raw, user_input, labels)
        result["perception_at"] = perception_at
        corrected = result.get("corrected_input", user_input)
        if corrected and corrected != user_input:
            pass
        result["corrected_input"] = corrected if corrected else user_input

        return result

    def _parse_perceive_output(self, raw: str, user_input: str, labels: dict | None = None) -> dict:
        if labels is None:
            labels = get_labels("cognition.perceive_labels", self.language)
        CL = get_labels("context.labels", self.language)
        l_correction = labels.get("correction", "纠错")
        l_category = labels.get("category", "分类")
        l_intent = labels.get("intent", "意图")
        l_summary = labels.get("summary", "AI摘要")
        l_keywords = labels.get("keywords", "话题关键词")
        l_need_online = labels.get("need_online", "需要联网")
        l_need_tools = labels.get("need_tools", "需要工具")
        truthy_values = tuple(CL.get("truthy_values", ["yes", "是", "true"]))

        result = {
            "intent": user_input,
            "category": "chat",
            "need_memory": False,
            "memory_type": CL.get("memory_type_none", "无"),
            "need_online": False,
            "need_tools": False,
            "ai_summary": user_input,
            "topic_keywords": [],
            "raw": raw,
        }
        for line in raw.split("\n"):
            line = line.strip()
            if line.startswith(f"{l_correction}：") or line.startswith(f"{l_correction}:"):
                val = line.split("：", 1)[-1].split(":", 1)[-1].strip()
                if val:
                    result["corrected_input"] = val
            elif line.startswith(f"{l_category}：") or line.startswith(f"{l_category}:"):
                val = line.split("：", 1)[-1].split(":", 1)[-1].strip().lower()
                if val in ("knowledge", "chat", "personal"):
                    result["category"] = val
            elif line.startswith(f"{l_intent}：") or line.startswith(f"{l_intent}:"):
                result["intent"] = line.split("：", 1)[-1].split(":", 1)[-1].strip()
            elif line.startswith(f"{l_summary}：") or line.startswith(f"{l_summary}:"):
                result["ai_summary"] = line.split("：", 1)[-1].split(":", 1)[-1].strip()
            elif line.startswith(f"{l_keywords}：") or line.startswith(f"{l_keywords}:"):
                kw_str = line.split("：", 1)[-1].split(":", 1)[-1].strip()
                result["topic_keywords"] = [k.strip() for k in kw_str.split(",") if k.strip()]
            elif line.startswith(f"{l_need_online}：") or line.startswith(f"{l_need_online}:"):
                val = line.split("：", 1)[-1].split(":", 1)[-1].strip().lower()
                result["need_online"] = val in truthy_values
            elif line.startswith(f"{l_need_tools}：") or line.startswith(f"{l_need_tools}:"):
                val = line.split("：", 1)[-1].split(":", 1)[-1].strip().lower()
                result["need_tools"] = val in truthy_values
        result["need_memory"] = result["category"] in ("chat", "personal")
        result["memory_type"] = "personal" if result["category"] == "personal" else CL.get("memory_type_none", "无")
        return result

    def analyze_trajectory(self, user_input: str, memories: dict) -> dict | None:
        profile = memories.get("profile", [])
        hypotheses = memories.get("hypotheses", [])
        user_model_data = memories.get("user_model", [])

        if len(profile) < 3 and len(hypotheses) < 3:
            return None

        known_keywords = set()
        for p in profile:
            known_keywords.update(p.get("value", "").split())
            known_keywords.update(p.get("field", "").split())
            known_keywords.add(p.get("category", ""))
        for h in hypotheses:
            known_keywords.update(h.get("claim", "").split())
            known_keywords.update(h.get("subject", "").split())
            known_keywords.add(h.get("category", ""))
        known_keywords = {k for k in known_keywords if len(k) >= 2}

        input_chars = user_input.lower()
        overlap = sum(1 for k in known_keywords if k.lower() in input_chars)
        if overlap >= 2:
            return None

        L = get_labels("context.labels", self.language)

        known_parts = []
        if profile:
            lines = [f"  [{p['category']}] {p['field']}: {p['value']}" for p in profile]
            known_parts.append(f"{L['confirmed_profile']}：\n" + "\n".join(lines))
        if hypotheses:
            trusted = [h for h in hypotheses
                       if h.get("status") in ("active", "established", "confirmed")][:10]
            if trusted:
                lines = [f"  [{h['category']}] {h['subject']}: {h['claim']} ({h.get('status', 'active')})"
                         for h in trusted]
                known_parts.append(f"{L['high_prob_hypotheses']}：\n" + "\n".join(lines))
        if user_model_data:
            lines = [f"  {m['dimension']}: {m['assessment']}" for m in user_model_data]
            known_parts.append(f"{L['user_model']}：\n" + "\n".join(lines))

        known_text = "\n\n".join(known_parts)

        messages = [
            {"role": "system", "content": get_prompt("cognition.trajectory_analysis", self.language)},
            {"role": "user", "content": f"[system_time: {get_now().strftime('%Y-%m-%dT%H:%M')}]\n\n{L['known_info']}：\n{known_text}\n\n{L['user_input_label']}：{user_input}"},
        ]
        raw = call_llm(messages, self.config).strip()

        result = self._parse_trajectory_result(raw)
        if not result:
            return None

        trajectory = result.get("trajectory", "no_data")
        if trajectory in ("on_track", "no_data"):
            return None

        return result

    def _parse_trajectory_result(self, raw: str) -> dict | None:
        text = raw.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            text = text[start:end]
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return None

    def think(self, user_input: str, perception: dict,
              memories: dict, use_cloud: bool = False) -> dict:
        messages = [{"role": "system", "content": get_prompt("cognition.system_prompt", self.language)}]

        memory_text = memories.get("memory_text", "")
        if memory_text:
            messages.append({
                "role": "system",
                "content": memory_text,
            })

        if self.chat_history:
            L = get_labels("context.labels", self.language)
            history_lines = []
            for turn in self.chat_history:
                history_lines.append(f"{L['user']}：{turn['user_summary']}")
                history_lines.append(f"{L['assistant']}：{turn['assistant_summary']}")
            messages.append({
                "role": "system",
                "content": f"{L['current_session']}：\n" + "\n".join(history_lines),
            })

        messages.append({"role": "user", "content": f"[system_time: {get_now().strftime('%Y-%m-%dT%H:%M')}]\n{user_input}"})

        for i, msg in enumerate(messages):
            role = msg["role"]
            content = (msg["content"] if isinstance(msg["content"], str) else str(msg["content"]))[:120].replace("\n", " ")

        if use_cloud and self.cloud_configs:
            llm_cfg = self.cloud_configs[0]
            raw_response = call_llm(messages, llm_cfg)
        else:
            raw_response = call_llm(messages, self.config)
            if self._escalation_auto and self.cloud_configs and self._should_escalate(raw_response):
                cloud_cfg = self.cloud_configs[0]
                raw_response = call_llm(messages, cloud_cfg)
        raw_response_at = get_now()

        if perception.get("category") == "personal":
            verification_result = self._verify(
                user_input, perception, memory_text, raw_response,
                self.chat_history,
            )
            verification_at = get_now()
            if verification_result.startswith("FAIL"):
                fail_reason = verification_result.split(":", 1)[-1].split("：", 1)[-1].strip()
                messages.append({"role": "assistant", "content": raw_response})
                messages.append({"role": "user", "content":
                    get_prompt("cognition.regenerate_message", self.language, fail_reason=fail_reason)
                })
                final_response = call_llm(messages, self.config)
                final_response_at = get_now()
            else:
                final_response = raw_response
                final_response_at = verification_at
        else:
            verification_result = "SKIP"
            final_response = raw_response
            verification_at = get_now()
            final_response_at = verification_at

        thinking_notes = self._make_thinking_notes(
            perception, memory_text, raw_response, verification_result, final_response
        )
        thinking_notes_at = get_now()

        self.chat_history.append({
            "user_summary": perception.get("ai_summary", user_input),
            "assistant_summary": self._summarize_response(final_response),
        })

        return {
            "raw_response": raw_response,
            "raw_response_at": raw_response_at,
            "verification_result": verification_result,
            "verification_result_at": verification_at,
            "final_response": final_response,
            "final_response_at": final_response_at,
            "thinking_notes": thinking_notes,
            "thinking_notes_at": thinking_notes_at,
        }

    @staticmethod
    def _strip_internal_sections(memory_text: str, language: str = "zh") -> str:
        L = get_labels("context.labels", language)
        none_fallback = L.get("none_fallback", "无")
        if not memory_text:
            return none_fallback
        lines = memory_text.split("\n")
        result_lines = []
        skip = False
        markers = L.get("strip_markers", ["【高概率推测", "【待验证信息", "【本轮策略提示", "【轨迹偏离分析"])
        for line in lines:
            if any(marker in line for marker in markers):
                skip = True
                continue
            if line.startswith("【") and skip:
                skip = False
            if not skip:
                result_lines.append(line)
        result = "\n".join(result_lines).strip()
        return result if result else none_fallback

    def _verify(self, user_input: str, perception: dict,
                memory_text: str, response: str,
                chat_history: list[dict] | None = None) -> str:
        L = get_labels("context.labels", self.language)
        verify_memory = self._strip_internal_sections(memory_text, language=self.language)

        session_context = ""
        if chat_history:
            lines = []
            for turn in chat_history:
                lines.append(f"{L['user']}：{turn['user_summary']}")
                lines.append(f"{L['assistant']}：{turn['assistant_summary']}")
            session_context = "\n".join(lines)

        messages = [
            {"role": "system", "content": get_prompt("cognition.verify_system", self.language)},
            {"role": "user", "content": (
                f"[system_time: {get_now().strftime('%Y-%m-%dT%H:%M')}]\n"
                f"{L['memory']}：\n{verify_memory}\n"
                f"{L['current_session']}：\n{session_context if session_context else L['none']}\n"
                f"{L['user_asks']}：{user_input}\n"
                f"{L['ai_reply']}：{response}\n\n"
                f"{L['output']}："
            )},
        ]
        result = call_llm(messages, self.config).strip()

        if result.startswith("FAIL:") or result.startswith("FAIL："):
            return result

        return "PASS"

    @staticmethod
    def _summarize_response(response: str, max_len: int = 120) -> str:
        text = response.strip().replace("\n", " ")
        for sep in ["。", "！", "？", ".", "!", "?"]:
            pos = text.find(sep)
            if 0 < pos < max_len:
                return text[:pos + 1]
        if len(text) > max_len:
            return text[:max_len] + "..."
        return text

    def _make_thinking_notes(self, perception: dict, memory_text: str,
                             raw_response: str, verification_result: str,
                             final_response: str) -> str:
        L = get_labels("context.labels", self.language)
        notes = []
        category = perception.get("category", "chat")
        if category == "knowledge":
            notes.append(L.get("note_knowledge_skip", "纯知识问答，跳过记忆"))
        elif memory_text:
            notes.append(L.get("note_memory_loaded", "记忆已加载"))
        else:
            notes.append(L.get("note_memory_not_found", "需要记忆但未找到"))

        if verification_result != "PASS":
            notes.append(L.get("note_verification_blocked", "验证拦截：{result}").format(result=verification_result))
        else:
            notes.append(L.get("note_verification_pass", "验证通过"))

        return "；".join(notes)

    # ── Async versions ──

    async def perceive_async(self, user_input: str, available_tools=None) -> dict:
        L = get_labels("context.labels", self.language)

        recent_context = ""
        if self.chat_history:
            recent = self.chat_history[-3:]
            for turn in recent:
                recent_context += f"{L['user']}：{turn['user_summary']}\n"
                recent_context += f"{L['assistant']}：{turn['assistant_summary']}\n"

        context_block = ""
        if recent_context:
            context_block = (
                f"{L['recent_context']}：\n{recent_context}\n"
                f"{L['use_context_hint']}\n\n"
            )

        system_content = get_prompt("cognition.perceive_system", self.language)

        if available_tools:
            tool_lines = [f"- {m.name}: {m.description}" for m in available_tools]
            system_content += f"\n\n{L['available_tools']}：\n" + "\n".join(tool_lines)

        user_content = get_prompt(
            "cognition.perceive_user", self.language,
            system_time=get_now().strftime('%Y-%m-%dT%H:%M'),
            context_block=context_block,
            user_input=user_input,
        )

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ]

        raw = (await call_llm_async(messages, self.config)).strip()
        perception_at = get_now()
        labels = get_labels("cognition.perceive_labels", self.language)
        result = self._parse_perceive_output(raw, user_input, labels)
        result["perception_at"] = perception_at
        corrected = result.get("corrected_input", user_input)
        result["corrected_input"] = corrected if corrected else user_input
        return result

    async def analyze_trajectory_async(self, user_input: str, memories: dict) -> dict | None:
        profile = memories.get("profile", [])
        hypotheses = memories.get("hypotheses", [])
        user_model_data = memories.get("user_model", [])

        if len(profile) < 3 and len(hypotheses) < 3:
            return None

        known_keywords = set()
        for p in profile:
            known_keywords.update(p.get("value", "").split())
            known_keywords.update(p.get("field", "").split())
            known_keywords.add(p.get("category", ""))
        for h in hypotheses:
            known_keywords.update(h.get("claim", "").split())
            known_keywords.update(h.get("subject", "").split())
            known_keywords.add(h.get("category", ""))
        known_keywords = {k for k in known_keywords if len(k) >= 2}

        input_chars = user_input.lower()
        overlap = sum(1 for k in known_keywords if k.lower() in input_chars)
        if overlap >= 2:
            return None

        L = get_labels("context.labels", self.language)

        known_parts = []
        if profile:
            lines = [f"  [{p['category']}] {p['field']}: {p['value']}" for p in profile]
            known_parts.append(f"{L['confirmed_profile']}：\n" + "\n".join(lines))
        if hypotheses:
            trusted = [h for h in hypotheses
                       if h.get("status") in ("active", "established", "confirmed")][:10]
            if trusted:
                lines = [f"  [{h['category']}] {h['subject']}: {h['claim']} ({h.get('status', 'active')})"
                         for h in trusted]
                known_parts.append(f"{L['high_prob_hypotheses']}：\n" + "\n".join(lines))
        if user_model_data:
            lines = [f"  {m['dimension']}: {m['assessment']}" for m in user_model_data]
            known_parts.append(f"{L['user_model']}：\n" + "\n".join(lines))

        known_text = "\n\n".join(known_parts)

        messages = [
            {"role": "system", "content": get_prompt("cognition.trajectory_analysis", self.language)},
            {"role": "user", "content": f"[system_time: {get_now().strftime('%Y-%m-%dT%H:%M')}]\n\n{L['known_info']}：\n{known_text}\n\n{L['user_input_label']}：{user_input}"},
        ]
        raw = (await call_llm_async(messages, self.config)).strip()

        result = self._parse_trajectory_result(raw)
        if not result:
            return None

        trajectory = result.get("trajectory", "no_data")
        if trajectory in ("on_track", "no_data"):
            return None

        return result

    async def _verify_async(self, user_input: str, perception: dict,
                memory_text: str, response: str,
                chat_history: list[dict] | None = None) -> str:
        L = get_labels("context.labels", self.language)
        verify_memory = self._strip_internal_sections(memory_text, language=self.language)

        session_context = ""
        if chat_history:
            lines = []
            for turn in chat_history:
                lines.append(f"{L['user']}：{turn['user_summary']}")
                lines.append(f"{L['assistant']}：{turn['assistant_summary']}")
            session_context = "\n".join(lines)

        messages = [
            {"role": "system", "content": get_prompt("cognition.verify_system", self.language)},
            {"role": "user", "content": (
                f"[system_time: {get_now().strftime('%Y-%m-%dT%H:%M')}]\n"
                f"{L['memory']}：\n{verify_memory}\n"
                f"{L['current_session']}：\n{session_context if session_context else L['none']}\n"
                f"{L['user_asks']}：{user_input}\n"
                f"{L['ai_reply']}：{response}\n\n"
                f"{L['output']}："
            )},
        ]
        result = (await call_llm_async(messages, self.config)).strip()

        if result.startswith("FAIL:") or result.startswith("FAIL："):
            return result
        return "PASS"

    async def think_async(self, user_input: str, perception: dict,
              memories: dict, use_cloud: bool = False) -> dict:
        messages = [{"role": "system", "content": get_prompt("cognition.system_prompt", self.language)}]

        memory_text = memories.get("memory_text", "")
        if memory_text:
            messages.append({"role": "system", "content": memory_text})

        if self.chat_history:
            L = get_labels("context.labels", self.language)
            history_lines = []
            for turn in self.chat_history:
                history_lines.append(f"{L['user']}：{turn['user_summary']}")
                history_lines.append(f"{L['assistant']}：{turn['assistant_summary']}")
            messages.append({
                "role": "system",
                "content": f"{L['current_session']}：\n" + "\n".join(history_lines),
            })

        messages.append({"role": "user", "content": f"[system_time: {get_now().strftime('%Y-%m-%dT%H:%M')}]\n{user_input}"})

        if use_cloud and self.cloud_configs:
            llm_cfg = self.cloud_configs[0]
            raw_response = await call_llm_async(messages, llm_cfg)
        else:
            raw_response = await call_llm_async(messages, self.config)
            if self._escalation_auto and self.cloud_configs and self._should_escalate(raw_response):
                cloud_cfg = self.cloud_configs[0]
                raw_response = await call_llm_async(messages, cloud_cfg)
        raw_response_at = get_now()

        if perception.get("category") == "personal":
            verification_result = await self._verify_async(
                user_input, perception, memory_text, raw_response,
                self.chat_history,
            )
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

        thinking_notes = self._make_thinking_notes(
            perception, memory_text, raw_response, verification_result, final_response
        )
        thinking_notes_at = get_now()

        self.chat_history.append({
            "user_summary": perception.get("ai_summary", user_input),
            "assistant_summary": self._summarize_response(final_response),
        })

        return {
            "raw_response": raw_response,
            "raw_response_at": raw_response_at,
            "verification_result": verification_result,
            "verification_result_at": verification_at,
            "final_response": final_response,
            "final_response_at": final_response_at,
            "thinking_notes": thinking_notes,
            "thinking_notes_at": thinking_notes_at,
        }
