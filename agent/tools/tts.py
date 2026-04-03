
import os
import uuid
import logging

import edge_tts

from agent.tools import BaseTool, ToolManifest, ToolResult

logger = logging.getLogger(__name__)


class TTSTool(BaseTool):

    def __init__(self, config: dict):
        self._config = config
        self._tts_cfg = config.get("tts", {})
        lang = config.get("language", "en")
        self._desc = {
            "zh": (
                "将 AI 文字回复自动合成语音发送给用户。"
                "由系统在每次回复后自动调用，无需手动触发。"
                "自动识别中英文并切换对应音色。超过 max_chars 的内容会被截断。"
            ),
            "en": (
                "Automatically synthesizes AI text replies into speech. "
                "Called by the system after each reply — do not invoke manually. "
                "Auto-detects Chinese vs English and switches voice accordingly."
            ),
            "ja": (
                "AI のテキスト返答を自動的に音声合成してユーザーに送信します。"
                "毎回の返答後にシステムが自動呼び出しします。手動呼び出し不要。"
            ),
        }.get(lang, "Convert AI replies to speech (requires Edge TTS)")

    def manifest(self) -> ToolManifest:
        return ToolManifest(
            name="tts",
            description=self._desc,
            parameters={},
            examples=[],
        )

    def is_available(self) -> bool:
        return self._tts_cfg.get("enabled", False)

    def execute(self, params: dict) -> ToolResult:
        return ToolResult(success=False, data="", error="TTS is called internally, not via execute()")

def _detect_voice(text: str, voices: dict) -> str:
    chinese_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    total = len(text.strip()) or 1
    if chinese_count / total > 0.3:
        return voices.get("zh", "zh-CN-XiaoxiaoNeural")
    return voices.get("en", "en-US-AriaNeural")

async def text_to_speech(text: str, config: dict) -> str | None:
    tts_cfg = config.get("tts", {})
    voices = tts_cfg.get("voices", {})
    voice = _detect_voice(text, voices)
    temp_dir = tts_cfg.get("temp_dir", "tmp/tts")
    max_chars = tts_cfg.get("max_chars", 500)

    if len(text) > max_chars:
        text = text[:max_chars]

    if not text.strip():
        return None

    os.makedirs(temp_dir, exist_ok=True)
    output_path = os.path.join(temp_dir, f"tts_{uuid.uuid4().hex[:8]}.mp3")

    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)
        logger.info("TTS 合成完成: %s (%.1f KB)", output_path,
                     os.path.getsize(output_path) / 1024)
        return output_path
    except Exception:
        logger.exception("TTS 合成失败")
        try:
            os.remove(output_path)
        except OSError:
            pass
        return None
