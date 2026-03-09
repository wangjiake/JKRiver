
import json
import re
import logging

logger = logging.getLogger(__name__)


class LLMPipelineError(Exception):
    """Raised when an LLM error is detected during sleep pipeline processing."""
    pass


def _check_llm_response(raw: str):
    """Raise if raw is an LLM error string, preventing silent data loss."""
    from agent.utils.llm_client import is_llm_error
    if is_llm_error(raw):
        logger.error("LLM error in sleep pipeline: %s", raw[:200])
        raise LLMPipelineError(raw[:200])


def _parse_json_array(raw: str) -> list[dict]:
    _check_llm_response(raw)
    text = raw.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    start = text.find("[")
    end = text.rfind("]") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except (json.JSONDecodeError, ValueError):
            pass
    merged = []
    for m in re.finditer(r'\[.*?\]', text, re.DOTALL):
        try:
            arr = json.loads(m.group())
            if isinstance(arr, list):
                merged.extend(arr)
        except (json.JSONDecodeError, ValueError):
            continue
    return merged


def _parse_json_object(raw: str) -> dict:
    _check_llm_response(raw)
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
        return {}
