
import os
import asyncio
import logging


import discord
from discord.ext import commands, tasks

from agent.config.prompts import get_labels
from agent.core import run_cycle_async
from agent.channel_utils import (
    split_message, safe_remove, run_sleep_async, init_bot, is_allowed, get_session,
)
from agent.skills import SkillRegistry
from agent.skills.executor import execute_skill

logger = logging.getLogger(__name__)

_LOG = {
    "en": {
        "sleep_done": "Sleep done: profile updated",
        "sleep_error": "Sleep execution error",
        "run_cycle_error": "run_cycle error",
        "tts_send_failed": "TTS voice send failed",
        "bot_ready": "Discord Bot ready: %s (ID: %s)",
        "attachment_downloaded": "Attachment downloaded: %s (%.1f KB)",
        "proactive_sent": "Proactive message → %s: %s",
        "proactive_error": "Proactive message error user_id=%s",
        "no_token": "discord.bot_token not configured. Please set it in settings.yaml",
        "bot_starting": "Discord Bot starting...",
    },
    "zh": {
        "sleep_done": "sleep 完成：画像已更新",
        "sleep_error": "sleep 执行异常",
        "run_cycle_error": "run_cycle 异常",
        "tts_send_failed": "TTS 语音发送失败",
        "bot_ready": "Discord Bot 已就绪: %s (ID: %s)",
        "attachment_downloaded": "附件已下载: %s (%.1f KB)",
        "proactive_sent": "主动推送 → %s: %s",
        "proactive_error": "主动推送异常 user_id=%s",
        "no_token": "未配置 discord.bot_token，请在 settings.yaml 中填入 Bot Token",
        "bot_starting": "Discord Bot 启动中...",
    },
    "ja": {
        "sleep_done": "Sleep完了：プロフィール更新済み",
        "sleep_error": "Sleep実行エラー",
        "run_cycle_error": "run_cycle エラー",
        "tts_send_failed": "TTS音声送信失敗",
        "bot_ready": "Discord Bot 準備完了: %s (ID: %s)",
        "attachment_downloaded": "添付ファイルDL: %s (%.1f KB)",
        "proactive_sent": "プロアクティブ → %s: %s",
        "proactive_error": "プロアクティブエラー user_id=%s",
        "no_token": "discord.bot_token が未設定です。settings.yaml に設定してください",
        "bot_starting": "Discord Bot 起動中...",
    },
}

def _log(key: str) -> str:
    lang = _config.get("language", "en")
    return _LOG.get(lang, _LOG["en"]).get(key, _LOG["en"].get(key, key))

async def _run_sleep_async() -> str | None:
    result = await run_sleep_async()
    if result:
        logger.info(_log("sleep_done"))
        return "💤 记忆整理完成"
    return None

_config: dict = {}
_manager = None
_dc_config: dict = {}
_proactive = None

MAX_DC_LENGTH = 2000

def _init():
    global _config, _manager, _dc_config, _proactive
    _config, _manager, _dc_config, _proactive = init_bot("discord")

def _is_allowed(user_id: int) -> bool:
    return is_allowed(_dc_config, user_id)

def _get_session(user_id: int):
    return get_session(_manager, user_id, "dc")

def _split_dc_message(text: str) -> list[str]:
    return split_message(text, MAX_DC_LENGTH)

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

async def _process_and_reply(message: discord.Message, user_input, session):
    async with message.channel.typing():
        try:
            result = await run_cycle_async(user_input, session)
            response_text = result["response"]
        except Exception:
            logger.exception(_log("run_cycle_error"))
            BL = get_labels("bot.messages", _config.get("language", "en"))
            response_text = BL["error_fallback"]

    for chunk in _split_dc_message(response_text):
        await message.reply(chunk, mention_author=False)

    tts_cfg = _dc_config.get("tts", {}) or _config.get("tts", {})
    if tts_cfg.get("enabled"):
        from agent.tools.tts import text_to_speech
        audio_path = await text_to_speech(response_text, _config)
        if audio_path:
            try:
                await message.reply(
                    file=discord.File(audio_path),
                    mention_author=False)
            except Exception:
                logger.exception(_log("tts_send_failed"))
            finally:
                safe_remove(audio_path)

def _classify_attachment(attachment: discord.Attachment) -> str:
    ct = attachment.content_type or ""
    if ct.startswith("image/"):
        return "image"
    if ct.startswith("audio/") or ct.startswith("video/ogg"):
        return "voice"

    ext = os.path.splitext(attachment.filename or "")[1].lower()
    if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
        return "image"
    if ext in (".ogg", ".mp3", ".wav", ".m4a", ".flac"):
        return "voice"

    return "file"

@bot.event
async def on_ready():
    logger.info(_log("bot_ready"), bot.user.name, bot.user.id)

    proactive_cfg = _config.get("proactive", {})
    if proactive_cfg.get("enabled") and not proactive_loop.is_running():
        proactive_loop.change_interval(
            minutes=proactive_cfg.get("scan_interval_minutes", 30))
        proactive_loop.start()

@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return

    await bot.process_commands(message)

    ctx = await bot.get_context(message)
    if ctx.valid:
        return

    if not _is_allowed(message.author.id):
        return

    session = _get_session(message.author.id)
    temp_dir = _dc_config.get("temp_dir", "tmp/discord")

    if message.attachments:
        for attachment in message.attachments:
            att_type = _classify_attachment(attachment)
            ext = os.path.splitext(attachment.filename or "")[1] or ".bin"
            file_path = os.path.join(temp_dir, f"{attachment.id}{ext}")

            try:
                await attachment.save(file_path)
                logger.info(_log("attachment_downloaded"),
                            file_path, os.path.getsize(file_path) / 1024)

                caption = message.content or ""
                if att_type == "image":
                    user_input = {"type": "image", "text": caption,
                                  "file_path": file_path}
                elif att_type == "voice":
                    user_input = {"type": "voice", "file_path": file_path}
                else:
                    user_input = {"type": "file", "text": caption,
                                  "file_path": file_path}

                await _process_and_reply(message, user_input, session)
            finally:
                safe_remove(file_path)
        return

    text = message.content
    if not text or not text.strip():
        return

    await _process_and_reply(message, text.strip(), session)

@bot.command(name="start")
async def cmd_start(ctx: commands.Context):
    BL = get_labels("bot.messages", _config.get("language", "en"))
    if not _is_allowed(ctx.author.id):
        await ctx.reply(BL["no_permission"])
        return

    await ctx.reply(BL["welcome"].format(reset_command="`!new`"))

@bot.command(name="new")
async def cmd_new(ctx: commands.Context):
    if not _is_allowed(ctx.author.id):
        return

    session_id = f"dc_{ctx.author.id}"
    _manager.remove(session_id)
    BL = get_labels("bot.messages", _config.get("language", "en"))
    await ctx.reply(BL["session_reset"])

    async def _sleep_and_notify():
        result = await _run_sleep_async()
        if result:
            await ctx.send(result)
    asyncio.ensure_future(_sleep_and_notify())

@tasks.loop(minutes=30)
async def proactive_loop():
    if not _proactive:
        return

    for user_id in _dc_config.get("allowed_user_ids", []):
        try:
            user = await bot.fetch_user(user_id)
            if not user:
                continue
            dm = await user.create_dm()

            result = await asyncio.to_thread(_proactive.scan, user_id, "dc_")
            if result and result.get("send") and result.get("message"):
                for chunk in _split_dc_message(result["message"]):
                    await dm.send(chunk)
                logger.info(_log("proactive_sent"), user_id,
                            result["message"][:50])
        except Exception:
            logger.exception(_log("proactive_error"), user_id)

@proactive_loop.before_loop
async def _before_proactive():
    await bot.wait_until_ready()

def main():
    logging.basicConfig(
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        level=logging.INFO,
    )

    _init()

    token = _dc_config.get("bot_token", "")
    if not token:
        logger.error(_log("no_token"))
        return

    logger.info(_log("bot_starting"))
    bot.run(token, log_handler=None)

if __name__ == "__main__":
    main()
