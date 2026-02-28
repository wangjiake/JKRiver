
import re
import requests
import httpx

# ── Async versions ──

async def call_llm_async(messages: list[dict], config: dict) -> str:
    if config.get("search"):
        return await _call_responses_api_async(messages, config)
    return await _call_chat_completions_async(messages, config)

async def _call_chat_completions_async(messages: list[dict], config: dict) -> str:
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

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{api_base}/v1/chat/completions",
                headers=headers,
                json={
                    "model": model,
                    "messages": messages,
                    **token_param,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        from agent.config.prompts import get_labels
        EL = get_labels("errors.llm", config.get("language", "zh"))
        return EL["call_failed"].format(error=e)

async def _call_responses_api_async(messages: list[dict], config: dict) -> str:
    api_base = config.get("api_base", "https://api.openai.com")
    model = config.get("model", "")
    api_key = config.get("api_key", "")
    temperature = config.get("temperature", 0.7)
    max_tokens = config.get("max_tokens", 2048)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{api_base}/v1/responses",
                headers=headers,
                json={
                    "model": model,
                    "input": messages,
                    "tools": [{"type": "web_search_preview"}],
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        for item in data.get("output", []):
            if item.get("type") == "message":
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        text = content["text"]
                        annotations = content.get("annotations", [])
                        if annotations:
                            text = _append_citations(text, annotations, label=config.get("_citation_label", "Sources"))
                        return text

        from agent.config.prompts import get_labels
        EL = get_labels("errors.llm", config.get("language", "zh"))
        return EL["responses_no_text"]
    except Exception as e:
        from agent.config.prompts import get_labels
        EL = get_labels("errors.llm", config.get("language", "zh"))
        return EL["call_failed"].format(error=e)

# ── Sync versions (unchanged, for backward compatibility) ──

def call_llm(messages: list[dict], config: dict) -> str:
    if config.get("search"):
        return _call_responses_api(messages, config)
    return _call_chat_completions(messages, config)

def _call_chat_completions(messages: list[dict], config: dict) -> str:
    api_base = config.get("api_base", "http://localhost:11434")
    model = config.get("model", "")
    api_key = config.get("api_key", "")
    temperature = config.get("temperature", 0.7)
    max_tokens = config.get("max_tokens", 2048)

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    # gpt-5/o1/o3 系列：max_completion_tokens + 不支持自定义 temperature
    is_new_model = any(k in model for k in ("gpt-5", "o1", "o3"))
    if is_new_model:
        token_param = {"max_completion_tokens": max_tokens}
    else:
        token_param = {"max_tokens": max_tokens, "temperature": temperature}

    try:
        resp = requests.post(
            f"{api_base}/v1/chat/completions",
            headers=headers,
            json={
                "model": model,
                "messages": messages,
                **token_param,
            },
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        from agent.config.prompts import get_labels
        EL = get_labels("errors.llm", config.get("language", "zh"))
        return EL["call_failed"].format(error=e)

def _call_responses_api(messages: list[dict], config: dict) -> str:
    api_base = config.get("api_base", "https://api.openai.com")
    model = config.get("model", "")
    api_key = config.get("api_key", "")
    temperature = config.get("temperature", 0.7)
    max_tokens = config.get("max_tokens", 2048)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    try:
        resp = requests.post(
            f"{api_base}/v1/responses",
            headers=headers,
            json={
                "model": model,
                "input": messages,
                "tools": [{"type": "web_search_preview"}],
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            },
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()

        for item in data.get("output", []):
            if item.get("type") == "message":
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        text = content["text"]
                        annotations = content.get("annotations", [])
                        if annotations:
                            text = _append_citations(text, annotations, label=config.get("_citation_label", "Sources"))
                        return text

        from agent.config.prompts import get_labels
        EL = get_labels("errors.llm", config.get("language", "zh"))
        return EL["responses_no_text"]
    except Exception as e:
        from agent.config.prompts import get_labels
        EL = get_labels("errors.llm", config.get("language", "zh"))
        return EL["call_failed"].format(error=e)

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
