
import os
import asyncio
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from datetime import time as dt_time

from agent.config import load_config
from agent.config.prompts import get_labels
from agent.core import SessionManager, run_cycle_async
from agent.channel_utils import split_message, safe_remove
from agent.proactive import ProactiveScanner
from agent.skills import SkillRegistry
from agent.skills.executor import execute_skill

logger = logging.getLogger(__name__)

_LOG = {
    "en": {
        "sleep_done": "Sleep done: profile updated",
        "sleep_error": "Sleep execution error",
        "run_cycle_error": "run_cycle error",
        "tts_send_failed": "TTS voice send failed",
        "voice_downloaded": "Voice downloaded: %s (%.1f KB)",
        "photo_downloaded": "Photo downloaded: %s (%.1f KB)",
        "file_downloaded": "File downloaded: %s (%.1f KB)",
        "proactive_sent": "Proactive message → %s: %s",
        "proactive_error": "Proactive message error chat_id=%s",
        "bot_error": "Telegram Bot error:",
        "no_token": "telegram.bot_token not configured. Please set it in settings.yaml",
        "bot_starting": "Telegram Bot starting...",
        "proactive_enabled": "Proactive messaging enabled, interval=%d min",
        "skill_sent": "Scheduled skill '%s' → %s",
        "skill_error": "Scheduled skill '%s' execution error",
        "skill_registered_daily": "Skill registered: %s (daily %s)",
        "skill_registered_weekly": "Skill registered: %s (weekly day=%s %s)",
        "skill_registered_repeat": "Skill registered: %s (every %d sec)",
        "skill_cron_failed": "Skill '%s' cron parse failed: %s",
        "bot_ready": "Bot ready, polling...",
    },
    "zh": {
        "sleep_done": "sleep 完成：画像已更新",
        "sleep_error": "sleep 执行异常",
        "run_cycle_error": "run_cycle 异常",
        "tts_send_failed": "TTS 语音发送失败",
        "voice_downloaded": "语音已下载: %s (%.1f KB)",
        "photo_downloaded": "图片已下载: %s (%.1f KB)",
        "file_downloaded": "文件已下载: %s (%.1f KB)",
        "proactive_sent": "主动推送 → %s: %s",
        "proactive_error": "主动推送异常 chat_id=%s",
        "bot_error": "Telegram Bot 异常:",
        "no_token": "未配置 telegram.bot_token，请在 settings.yaml 中填入 Bot Token",
        "bot_starting": "Telegram Bot 启动中...",
        "proactive_enabled": "主动推送已启用，间隔=%d分钟",
        "skill_sent": "定时技能 '%s' → %s",
        "skill_error": "定时技能 '%s' 执行异常",
        "skill_registered_daily": "定时技能注册: %s (每天 %s)",
        "skill_registered_weekly": "定时技能注册: %s (每周 day=%s %s)",
        "skill_registered_repeat": "定时技能注册: %s (每%d秒)",
        "skill_cron_failed": "定时技能 '%s' cron 解析失败: %s",
        "bot_ready": "Bot 已就绪，开始轮询...",
    },
    "ja": {
        "sleep_done": "Sleep完了：プロフィール更新済み",
        "sleep_error": "Sleep実行エラー",
        "run_cycle_error": "run_cycle エラー",
        "tts_send_failed": "TTS音声送信失敗",
        "voice_downloaded": "音声DL: %s (%.1f KB)",
        "photo_downloaded": "画像DL: %s (%.1f KB)",
        "file_downloaded": "ファイルDL: %s (%.1f KB)",
        "proactive_sent": "プロアクティブ → %s: %s",
        "proactive_error": "プロアクティブエラー chat_id=%s",
        "bot_error": "Telegram Bot エラー:",
        "no_token": "telegram.bot_token が未設定です。settings.yaml に設定してください",
        "bot_starting": "Telegram Bot 起動中...",
        "proactive_enabled": "プロアクティブ有効、間隔=%d分",
        "skill_sent": "定時スキル '%s' → %s",
        "skill_error": "定時スキル '%s' 実行エラー",
        "skill_registered_daily": "スキル登録: %s (毎日 %s)",
        "skill_registered_weekly": "スキル登録: %s (毎週 day=%s %s)",
        "skill_registered_repeat": "スキル登録: %s (%d秒ごと)",
        "skill_cron_failed": "スキル '%s' cron解析失敗: %s",
        "bot_ready": "Bot準備完了、ポーリング開始...",
    },
}

def _log(key: str) -> str:
    lang = _config.get("language", "en")
    return _LOG.get(lang, _LOG["en"]).get(key, _LOG["en"].get(key, key))

def _run_sleep() -> str | None:
    try:
        from agent.sleep import run as sleep_run
        sleep_run()
        logger.info(_log("sleep_done"))
        return "💤 记忆整理完成"
    except Exception:
        logger.exception(_log("sleep_error"))
        return None

_config: dict = {}
_manager: SessionManager | None = None
_tg_config: dict = {}
_proactive: ProactiveScanner | None = None

def _init():
    global _config, _manager, _tg_config, _proactive
    _config = load_config()
    _manager = SessionManager(_config)
    _tg_config = _config.get("telegram", {})

    temp_dir = _tg_config.get("temp_dir", "tmp/telegram")
    os.makedirs(temp_dir, exist_ok=True)

    if _config.get("proactive", {}).get("enabled"):
        _proactive = ProactiveScanner(_config)

def _is_allowed(user_id: int) -> bool:
    allowed = _tg_config.get("allowed_user_ids", [])
    if not allowed:
        return True
    return user_id in allowed

def _get_session(user_id: int):
    session_id = f"tg_{user_id}"
    return _manager.get_or_create(session_id)

MAX_TG_LENGTH = 4096

def _split_message(text: str) -> list[str]:
    return split_message(text, MAX_TG_LENGTH)

async def _process_and_reply(
    update: Update,
    user_input,
    session,
):
    typing_done = asyncio.Event()
    async def _keep_typing():
        while not typing_done.is_set():
            try:
                await update.message.chat.send_action("typing")
            except Exception:
                pass
            await asyncio.sleep(4)
    typing_task = asyncio.ensure_future(_keep_typing())

    try:
        result = await run_cycle_async(user_input, session)
        response_text = result["response"]
    except Exception:
        logger.exception(_log("run_cycle_error"))
        BL = get_labels("bot.messages", _config.get("language", "zh"))
        response_text = BL["error_fallback"]
    finally:
        typing_done.set()
        typing_task.cancel()

    for chunk in _split_message(response_text):
        await update.message.reply_text(chunk)

    tts_cfg = _tg_config.get("tts", {}) or _config.get("tts", {})
    if tts_cfg.get("enabled"):
        from agent.tools.tts import text_to_speech
        audio_path = await text_to_speech(response_text, _config)
        if audio_path:
            try:
                with open(audio_path, "rb") as af:
                    await update.message.reply_voice(af)
            except Exception:
                logger.exception(_log("tts_send_failed"))
            finally:
                _safe_remove(audio_path)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    BL = get_labels("bot.messages", _config.get("language", "zh"))
    if not _is_allowed(update.effective_user.id):
        await update.message.reply_text(BL["no_permission"])
        return

    await update.message.reply_text(
        BL["welcome"].format(reset_command="/new")
    )

async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update.effective_user.id):
        return

    user_id = update.effective_user.id
    session_id = f"tg_{user_id}"
    _manager.remove(session_id)
    BL = get_labels("bot.messages", _config.get("language", "zh"))
    await update.message.reply_text(BL["session_reset"])

    chat_id = update.effective_chat.id
    async def _sleep_and_notify():
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _run_sleep)
        if result:
            await context.bot.send_message(chat_id, result)
    asyncio.ensure_future(_sleep_and_notify())

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update.effective_user.id):
        return

    text = update.message.text
    if not text or not text.strip():
        return

    session = _get_session(update.effective_user.id)
    await _process_and_reply(update, text.strip(), session)

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update.effective_user.id):
        return

    temp_dir = _tg_config.get("temp_dir", "tmp/telegram")
    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)
    file_path = os.path.join(temp_dir, f"{voice.file_unique_id}.ogg")

    await file.download_to_drive(file_path)
    logger.info(_log("voice_downloaded"), file_path, os.path.getsize(file_path) / 1024)

    session = _get_session(update.effective_user.id)
    user_input = {"type": "voice", "file_path": file_path}

    try:
        await _process_and_reply(update, user_input, session)
    finally:
        _safe_remove(file_path)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update.effective_user.id):
        return

    temp_dir = _tg_config.get("temp_dir", "tmp/telegram")
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    file_path = os.path.join(temp_dir, f"{photo.file_unique_id}.jpg")

    await file.download_to_drive(file_path)
    logger.info(_log("photo_downloaded"), file_path, os.path.getsize(file_path) / 1024)

    session = _get_session(update.effective_user.id)
    caption = update.message.caption or ""
    user_input = {"type": "image", "text": caption, "file_path": file_path}

    try:
        await _process_and_reply(update, user_input, session)
    finally:
        _safe_remove(file_path)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update.effective_user.id):
        return

    temp_dir = _tg_config.get("temp_dir", "tmp/telegram")
    doc = update.message.document
    file = await context.bot.get_file(doc.file_id)

    ext = os.path.splitext(doc.file_name or "")[1] if doc.file_name else ""
    file_path = os.path.join(temp_dir, f"{doc.file_unique_id}{ext}")

    await file.download_to_drive(file_path)
    logger.info(_log("file_downloaded"), file_path, os.path.getsize(file_path) / 1024)

    session = _get_session(update.effective_user.id)
    caption = update.message.caption or ""
    user_input = {"type": "file", "text": caption, "file_path": file_path}

    try:
        await _process_and_reply(update, user_input, session)
    finally:
        _safe_remove(file_path)

def _parse_cron_for_jobqueue(cron_str: str) -> dict | None:
    parts = cron_str.strip().split()
    if len(parts) != 5:
        return None

    minute, hour, dom, month, dow = parts

    if minute.startswith("*/") and hour == "*":
        try:
            interval = int(minute[2:])
            return {"type": "repeating", "interval": interval * 60}
        except ValueError:
            return None

    try:
        m = int(minute)
        h = int(hour)
    except ValueError:
        return None

    if dow != "*":
        try:
            day = int(dow)
            py_day = (day - 1) % 7
            if day == 0:
                py_day = 6
            return {"type": "weekly", "time": dt_time(h, m), "days": (py_day,)}
        except ValueError:
            return None

    return {"type": "daily", "time": dt_time(h, m)}

def _safe_remove(path: str):
    safe_remove(path)

async def _proactive_job(context: ContextTypes.DEFAULT_TYPE):
    if not _proactive:
        return
    for user_id in _tg_config.get("allowed_user_ids", []):
        chat_id = user_id
        try:
            result = await asyncio.to_thread(_proactive.scan, chat_id)
            if result and result.get("send") and result.get("message"):
                for chunk in _split_message(result["message"]):
                    await context.bot.send_message(chat_id=chat_id, text=chunk)
                logger.info(_log("proactive_sent"), chat_id, result["message"][:50])
        except Exception:
            logger.exception(_log("proactive_error"), chat_id)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(_log("bot_error"), exc_info=context.error)

def main():
    logging.basicConfig(
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        level=logging.INFO,
    )

    _init()

    token = _tg_config.get("bot_token", "")
    if not token:
        logger.error(_log("no_token"))
        return

    logger.info(_log("bot_starting"))

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("new", cmd_new))

    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.add_error_handler(error_handler)

    proactive_cfg = _config.get("proactive", {})
    if proactive_cfg.get("enabled") and app.job_queue:
        interval = proactive_cfg.get("scan_interval_minutes", 30) * 60
        app.job_queue.run_repeating(_proactive_job, interval=interval, first=60)
        logger.info(_log("proactive_enabled"), interval // 60)

    if _config.get("skills", {}).get("enabled", True) and app.job_queue:
        skill_registry = SkillRegistry(_config)
        schedule_skills = skill_registry.get_schedule_skills()
        for skill in schedule_skills:
            parsed = _parse_cron_for_jobqueue(skill.cron)
            if not parsed:
                logger.warning(_log("skill_cron_failed"), skill.name, skill.cron)
                continue

            def _make_skill_callback(sk):
                async def _skill_job(context: ContextTypes.DEFAULT_TYPE):
                    for user_id in _tg_config.get("allowed_user_ids", []):
                        try:
                            result_text = await asyncio.to_thread(
                                execute_skill, sk, _manager.get_or_create(f"tg_{user_id}").tool_registry,
                                _config.get("llm", {}), _config,
                            )
                            if result_text:
                                for chunk in _split_message(result_text):
                                    await context.bot.send_message(chat_id=user_id, text=chunk)
                                logger.info(_log("skill_sent"), sk.name, user_id)
                        except Exception:
                            logger.exception(_log("skill_error"), sk.name)
                return _skill_job

            callback = _make_skill_callback(skill)

            if parsed["type"] == "daily":
                app.job_queue.run_daily(callback, time=parsed["time"])
                logger.info(_log("skill_registered_daily"), skill.name, parsed["time"])
            elif parsed["type"] == "weekly":
                app.job_queue.run_daily(callback, time=parsed["time"], days=parsed["days"])
                logger.info(_log("skill_registered_weekly"), skill.name, parsed["days"], parsed["time"])
            elif parsed["type"] == "repeating":
                app.job_queue.run_repeating(callback, interval=parsed["interval"], first=60)
                logger.info(_log("skill_registered_repeat"), skill.name, parsed["interval"])

    logger.info(_log("bot_ready"))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
