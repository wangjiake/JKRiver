
import requests
from agent.config.prompts import get_prompt, get_failure_keywords, get_labels

class LLMCapability:

    def __init__(self, config: dict):
        self.local_config = config.get("llm", {})
        self.language = config.get("language", "zh")
        self.cloud_config = config.get("cloud_llm", {})
        self.escalation_config = self.cloud_config.get("escalation", {})

    def execute(self, messages: list[dict], allow_escalation: bool = True) -> str:
        response = self._call_local(messages)

        if not allow_escalation or not self._is_cloud_enabled():
            return response

        if not self._needs_escalation(response):
            return response

        cloud_response = self._call_cloud(messages)
        if not cloud_response:
            return response

        if self.escalation_config.get("feedback", True):
            return self._feedback_to_local(messages, cloud_response)

        return cloud_response

    def call_local(self, messages: list[dict]) -> str:
        return self._call_local(messages)

    def _call_local(self, messages: list[dict]) -> str:
        api_base = self.local_config.get("api_base", "http://localhost:11434")
        model = self.local_config.get("model", "")
        temperature = self.local_config.get("temperature", 0.7)
        max_tokens = self.local_config.get("max_tokens", 2048)

        try:
            resp = requests.post(
                f"{api_base}/v1/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            EL = get_labels("errors.llm", self.language)
            return EL["local_call_failed"].format(error=e)

    def _call_cloud(self, messages: list[dict]) -> str | None:
        providers = self.cloud_config.get("providers", [])
        if not providers:
            return None

        sorted_providers = sorted(providers, key=lambda p: p.get("priority", 99))

        for provider in sorted_providers:
            result = self._call_single_cloud(messages, provider)
            if result and not result.startswith("["):
                return result

        return None

    def _call_single_cloud(self, messages: list[dict], provider: dict) -> str | None:
        api_base = provider.get("api_base", "")
        api_key = provider.get("api_key", "")
        model = provider.get("model", "")
        name = provider.get("name", "unknown")

        if not api_base or not api_key:
            return None

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            resp = requests.post(
                f"{api_base}/v1/chat/completions",
                headers=headers,
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 4096,
                },
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return None

    def _feedback_to_local(self, original_messages: list[dict],
                           cloud_response: str) -> str:
        L = get_labels("context.labels", self.language)
        user_msg = ""
        for m in reversed(original_messages):
            if m["role"] == "user":
                user_msg = m["content"]
                break

        feedback_messages = [
            {"role": "system", "content": get_prompt("capabilities.feedback_system", self.language)},
            {"role": "user", "content": (
                f"{L['user_question']}：{user_msg}\n\n"
                f"{L['expert_answer']}：{cloud_response}"
            )},
        ]
        return self._call_local(feedback_messages)

    def _is_cloud_enabled(self) -> bool:
        return bool(
            self.cloud_config.get("enabled", False)
            and self.cloud_config.get("providers")
        )

    def _needs_escalation(self, response: str) -> bool:
        if not self.escalation_config.get("auto", True):
            return False

        config_keywords = self.escalation_config.get("failure_keywords")
        failure_keywords = get_failure_keywords(self.language, overrides=config_keywords)
        for kw in failure_keywords:
            if kw in response:
                return True

        min_length = self.escalation_config.get("min_response_length", 20)
        if len(response.strip()) < min_length and "[" not in response:
            return True

        EL = get_labels("errors.llm", self.language)
        if response.startswith("[") and EL["failure_marker"] in response:
            return True

        return False
