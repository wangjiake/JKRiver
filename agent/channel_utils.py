
import os
import logging
import socket
import subprocess
import time
from urllib.parse import urlparse

from agent.config import load_config
from agent.core import SessionManager
from agent.proactive import ProactiveScanner

logger = logging.getLogger(__name__)

_OLLAMA_CHECK_TTL = 300  # re-check after 5 minutes
_ollama_checked: float | None = None


def ensure_ollama(config: dict) -> bool:
    """Ensure Ollama is reachable; auto-start if local provider and not running.

    Uses a module-level timestamp to avoid repeated checks, re-checking
    after _OLLAMA_CHECK_TTL seconds.
    Returns True if reachable or not applicable.
    """
    global _ollama_checked
    if _ollama_checked is not None and (time.monotonic() - _ollama_checked) < _OLLAMA_CHECK_TTL:
        return True

    provider = config.get("llm_provider", "local")
    llm = config.get("llm", {})
    api_base = llm.get("api_base", "")
    if not api_base:
        _ollama_checked = time.monotonic()
        return True

    import requests
    # Already reachable?
    try:
        requests.get(api_base, timeout=3)
        _ollama_checked = time.monotonic()
        return True
    except Exception:
        pass

    # Only auto-start for local provider
    if provider != "local":
        logger.warning("Cannot reach LLM API at %s", api_base)
        _ollama_checked = time.monotonic()
        return False

    parsed = urlparse(api_base)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 11434

    # Port already bound → Ollama is starting up, wait for it
    if _is_port_in_use(host, port):
        logger.info("Ollama port %d in use, waiting for it to become ready...", port)
        for _ in range(10):
            time.sleep(1)
            try:
                requests.get(api_base, timeout=2)
                _ollama_checked = time.monotonic()
                return True
            except Exception:
                pass
        logger.warning("Ollama port %d bound but API not responding", port)
        _ollama_checked = time.monotonic()
        return False

    # Port free → start Ollama
    logger.info("Starting Ollama on port %d...", port)
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        logger.warning("'ollama' not found in PATH; please install Ollama first")
        _ollama_checked = time.monotonic()
        return False

    for _ in range(15):
        time.sleep(1)
        try:
            requests.get(api_base, timeout=2)
            logger.info("Ollama is ready")
            _ollama_checked = time.monotonic()
            return True
        except Exception:
            pass

    logger.warning("Ollama started but not responding at %s", api_base)
    _ollama_checked = time.monotonic()
    return False


def _is_port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex((host, port)) == 0


async def run_sleep_async() -> str | None:
    """Run sleep pipeline. Shared by both bots."""
    try:
        from agent.sleep import run_async as sleep_run_async
        await sleep_run_async()
        return "ok"
    except Exception:
        logger.exception("Sleep execution error")
        return None


def init_bot(channel_key: str) -> tuple[dict, SessionManager, dict, ProactiveScanner | None]:
    """Load config, create SessionManager, setup temp dir, init proactive."""
    config = load_config()
    ensure_ollama(config)
    manager = SessionManager(config)
    channel_config = config.get(channel_key, {})

    temp_dir = channel_config.get("temp_dir", f"tmp/{channel_key}")
    os.makedirs(temp_dir, exist_ok=True)

    proactive = None
    if config.get("proactive", {}).get("enabled"):
        proactive = ProactiveScanner(config)

    return config, manager, channel_config, proactive


def is_allowed(channel_config: dict, user_id: int) -> bool:
    """Check allowed_user_ids list."""
    allowed = channel_config.get("allowed_user_ids", [])
    if not allowed:
        return True
    return user_id in allowed


def get_session(manager: SessionManager, user_id: int, prefix: str):
    """Get or create session with prefix (e.g. 'tg', 'dc')."""
    session_id = f"{prefix}_{user_id}"
    return manager.get_or_create(session_id)

def split_message(text: str, max_length: int = 4096) -> list[str]:
    if len(text) <= max_length:
        return [text]

    chunks = []
    while text:
        if len(text) <= max_length:
            chunks.append(text)
            break

        cut = text.rfind("\n\n", 0, max_length)
        if cut == -1:
            cut = text.rfind("\n", 0, max_length)
        if cut == -1:
            for sep in ("。", "？", "！", ".", "?", "!"):
                cut = text.rfind(sep, 0, max_length)
                if cut != -1:
                    cut += len(sep)
                    break
        if cut <= 0:
            cut = max_length

        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")

    return chunks

def safe_remove(path: str):
    try:
        os.remove(path)
        logger.debug("已删除临时文件: %s", path)
    except OSError:
        pass
