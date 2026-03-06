
import logging
import re
import time
import requests
import httpx

logger = logging.getLogger(__name__)


# ── Shared request/response helpers ──────────────────────


def _build_chat_request(messages: list[dict], config: dict) -> tuple[str, dict, dict]:
    """Build (url, headers, body) for chat completions API."""
    api_base = config.get("api_base", "http://localhost:11434")
    model = config.get("model", "")
    api_key = config.get("api_key", "")
    temperature = config.get("temperature", 0.7)
    max_tokens = config.get("max_tokens", 2048)

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    is_new_model = any(k in model for k in ("gpt-5", "o1", "o3"))
    if is_new_model:
        token_param = {"max_completion_tokens": max_tokens}
    else:
        token_param = {"max_tokens": max_tokens, "temperature": temperature}

    url = f"{api_base}/v1/chat/completions"
    body = {"model": model, "messages": messages, **token_param}
    return url, headers, body


def _parse_chat_response(data: dict) -> str:
    """Extract content text from chat completions response."""
    choices = data.get("choices")
    if not choices:
        return ""
    return choices[0].get("message", {}).get("content", "")


def _build_responses_request(messages: list[dict], config: dict) -> tuple[str, dict, dict]:
    """Build (url, headers, body) for responses API."""
    api_base = config.get("api_base", "https://api.openai.com")
    model = config.get("model", "")
    api_key = config.get("api_key", "")
    temperature = config.get("temperature", 0.7)
    max_tokens = config.get("max_tokens", 2048)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    url = f"{api_base}/v1/responses"
    body = {
        "model": model,
        "input": messages,
        "tools": [{"type": "web_search_preview"}],
        "temperature": temperature,
        "max_output_tokens": max_tokens,
    }
    return url, headers, body


def _parse_responses_response(data: dict, config: dict) -> str | None:
    """Extract content text from responses API output. Returns None if no text found."""
    for item in data.get("output", []):
        if item.get("type") == "message":
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    text = content["text"]
                    annotations = content.get("annotations", [])
                    if annotations:
                        text = _append_citations(
                            text, annotations,
                            label=config.get("_citation_label", "Sources"),
                        )
                    return text
    return None


def _log_success(tag: str, model: str, t0: float, data: dict):
    duration_ms = (time.monotonic() - t0) * 1000
    usage = data.get("usage", {})
    logger.debug("LLM %s ok model=%s duration_ms=%.0f tokens=%s",
                  tag, model, duration_ms, usage.get("total_tokens", "?"))


def _log_failure(tag: str, model: str, t0: float, error: Exception):
    duration_ms = (time.monotonic() - t0) * 1000
    logger.warning("LLM %s fail model=%s duration_ms=%.0f error=%s",
                    tag, model, duration_ms, error)


def is_llm_error(text: str) -> bool:
    """Check if text is an LLM error message."""
    return bool(text) and text.startswith("[LLM ")


def _error_message(config: dict, key: str = "call_failed", **kwargs) -> str:
    from agent.config.prompts import get_labels
    EL = get_labels("errors.llm", config.get("language", "en"))
    return EL[key].format(**kwargs) if kwargs else EL[key]


# ── Sync versions ────────────────────────────────────────


def call_llm(messages: list[dict], config: dict) -> str:
    if config.get("search"):
        return _call_responses_api(messages, config)
    return _call_chat_completions(messages, config)


def _call_chat_completions(messages: list[dict], config: dict) -> str:
    url, headers, body = _build_chat_request(messages, config)
    model = config.get("model", "")
    t0 = time.monotonic()
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        _log_success("chat", model, t0, data)
        return _parse_chat_response(data)
    except Exception as e:
        _log_failure("chat", model, t0, e)
        return _error_message(config, "call_failed", error=e)


def _call_responses_api(messages: list[dict], config: dict) -> str:
    url, headers, body = _build_responses_request(messages, config)
    model = config.get("model", "")
    t0 = time.monotonic()
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        _log_success("responses", model, t0, data)
        text = _parse_responses_response(data, config)
        if text is not None:
            return text
        return _error_message(config, "responses_no_text")
    except Exception as e:
        _log_failure("responses", model, t0, e)
        return _error_message(config, "call_failed", error=e)


# ── Async versions ───────────────────────────────────────


async def call_llm_async(messages: list[dict], config: dict) -> str:
    if config.get("search"):
        return await _call_responses_api_async(messages, config)
    return await _call_chat_completions_async(messages, config)


async def _call_chat_completions_async(messages: list[dict], config: dict) -> str:
    url, headers, body = _build_chat_request(messages, config)
    model = config.get("model", "")
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
            _log_success("chat_async", model, t0, data)
            return _parse_chat_response(data)
    except Exception as e:
        _log_failure("chat_async", model, t0, e)
        return _error_message(config, "call_failed", error=e)


async def _call_responses_api_async(messages: list[dict], config: dict) -> str:
    url, headers, body = _build_responses_request(messages, config)
    model = config.get("model", "")
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
        _log_success("responses_async", model, t0, data)
        text = _parse_responses_response(data, config)
        if text is not None:
            return text
        return _error_message(config, "responses_no_text")
    except Exception as e:
        _log_failure("responses_async", model, t0, e)
        return _error_message(config, "call_failed", error=e)


# ── Citation helper ──────────────────────────────────────


def _append_citations(text: str, annotations: list[dict], label: str = "Sources") -> str:
    citations = []
    seen_urls = set()
    for ann in annotations:
        if ann.get("type") != "url_citation":
            continue
        url = ann.get("url", "")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        clean_url = re.sub(r"[?&]utm_source=openai", "", url)
        title = ann.get("title", clean_url)
        citations.append(f"- {title}: {clean_url}")

    if citations:
        text += f"\n\n{label}:\n" + "\n".join(citations)

    return text
