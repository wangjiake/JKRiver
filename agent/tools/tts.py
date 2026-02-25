
import os
import uuid
import logging

import edge_tts

logger = logging.getLogger(__name__)

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
