
import json
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from agent.utils.time_context import get_now
from agent.utils.llm_client import call_llm
from agent.config.prompts import get_prompt, get_labels
from agent.storage import (
    load_proactive_log, save_proactive_log,
    load_active_events, load_pending_strategies,
    get_last_interaction_time,
    load_full_current_profile, load_trajectory_summary,
    load_user_model,
)

logger = logging.getLogger(__name__)

_LOG = {
    "en": {
        "no_triggers": "chat_id=%s: no triggers found",
        "quiet_hours": "chat_id=%s: quiet hours, skipped",
        "daily_limit": "chat_id=%s: sent %d today, reached limit",
        "gap_too_short": "chat_id=%s: %.0f min since last < %d, skipped",
        "llm_parse_fail": "LLM response unparseable: %s",
        "llm_call_error": "Proactive LLM call error",
    },
    "zh": {
        "no_triggers": "chat_id=%s: 无触发信号",
        "quiet_hours": "chat_id=%s: 静默时段，跳过",
        "daily_limit": "chat_id=%s: 今日已发%d条，达上限",
        "gap_too_short": "chat_id=%s: 距上次%.0f分钟 < %d，跳过",
        "llm_parse_fail": "LLM 返回无法解析: %s",
        "llm_call_error": "主动推送 LLM 调用异常",
    },
    "ja": {
        "no_triggers": "chat_id=%s: トリガーなし",
        "quiet_hours": "chat_id=%s: 静音時間帯、スキップ",
        "daily_limit": "chat_id=%s: 本日%d件送信済み、上限到達",
        "gap_too_short": "chat_id=%s: 前回から%.0f分 < %d、スキップ",
        "llm_parse_fail": "LLMレスポンス解析不可: %s",
        "llm_call_error": "プロアクティブLLM呼び出しエラー",
    },
}

DEFAULT_MAX_MESSAGES_PER_DAY = 3
DEFAULT_MIN_GAP_MINUTES = 120
DEFAULT_EVENT_MIN_IMPORTANCE = 0.6
DEFAULT_FOLLOWUP_AFTER_HOURS = 24
DEFAULT_EVENT_MAX_AGE_DAYS = 7
DEFAULT_IDLE_HOURS = 48
DEFAULT_STRATEGY_LOG_HOURS = 168
MAX_STRATEGIES_PER_SCAN = 5

def _log(key: str, lang: str = "en") -> str:
    return _LOG.get(lang, _LOG["en"]).get(key, _LOG["en"].get(key, key))

class ProactiveScanner:

    def __init__(self, config: dict):
        self.config = config
        self.language = config.get("language", "en")
        self.proactive_cfg = config.get("proactive", {})
        self.llm_config = config.get("llm", {})
        self.triggers_cfg = self.proactive_cfg.get("triggers", {})

    def scan(self, chat_id: int, session_prefix: str = "tg_") -> dict | None:
        if not self._check_rate_limits(chat_id):
            return None

        triggers = self._gather_triggers(chat_id, session_prefix=session_prefix)
        if not triggers:
            logger.debug(_log("no_triggers", self.language), chat_id)
            return None

        result = self._decide_and_generate(chat_id, triggers)
        if not result:
            return None

        if result.get("send") and result.get("message"):
            save_proactive_log(
                chat_id=chat_id,
                trigger_type=result.get("trigger_used", "unknown"),
                trigger_ref=result.get("reasoning", ""),
                message_text=result["message"],
            )

        return result

    def _check_rate_limits(self, chat_id: int) -> bool:
        now = get_now()

        quiet = self.proactive_cfg.get("quiet_hours", {})
        quiet_start = quiet.get("start", "23:00")
        quiet_end = quiet.get("end", "08:00")
        user_tz_name = self.config.get("timezone", "UTC")
        try:
            user_tz = ZoneInfo(user_tz_name)
        except Exception:
            user_tz = timezone.utc
        local_now = now.astimezone(user_tz)
        current_time_str = local_now.strftime("%H:%M")
        if self._in_quiet_hours(current_time_str, quiet_start, quiet_end):
            logger.debug(_log("quiet_hours", self.language), chat_id)
            return False

        logs_today = load_proactive_log(chat_id, since_hours=24)

        max_per_day = self.proactive_cfg.get("max_messages_per_day", DEFAULT_MAX_MESSAGES_PER_DAY)
        if len(logs_today) >= max_per_day:
            logger.debug(_log("daily_limit", self.language), chat_id, len(logs_today))
            return False

        min_gap = self.proactive_cfg.get("min_gap_minutes", DEFAULT_MIN_GAP_MINUTES)
        if logs_today:
            last_sent = logs_today[0]["sent_at"]
            gap = (now - last_sent).total_seconds() / 60
            if gap < min_gap:
                logger.debug(_log("gap_too_short", self.language),
                             chat_id, gap, min_gap)
                return False

        return True

    @staticmethod
    def _in_quiet_hours(current: str, start: str, end: str) -> bool:
        if start <= end:
            return start <= current <= end
        else:
            return current >= start or current <= end

    def _gather_triggers(self, chat_id: int, session_prefix: str = "tg_") -> list[dict]:
        triggers = []
        now = get_now()

        evt_cfg = self.triggers_cfg.get("event_followup", {})
        if evt_cfg.get("enabled", True):
            min_importance = evt_cfg.get("min_importance", DEFAULT_EVENT_MIN_IMPORTANCE)
            followup_after = evt_cfg.get("followup_after_hours", DEFAULT_FOLLOWUP_AFTER_HOURS)
            max_age = evt_cfg.get("max_age_days", DEFAULT_EVENT_MAX_AGE_DAYS)

            events = load_active_events(top_k=20)
            recent_logs = load_proactive_log(chat_id, since_hours=max_age * 24)
            sent_refs = {
                log["trigger_ref"] for log in recent_logs
                if log.get("trigger_type") == "event_followup"
            }

            for evt in events:
                importance = evt.get("importance", 0)
                if importance < min_importance:
                    continue
                created = evt.get("created_at")
                if not created:
                    continue
                age_hours = (now - created).total_seconds() / 3600
                if age_hours < followup_after:
                    continue
                if age_hours > max_age * 24:
                    continue
                ref_key = f"event_{evt.get('id', '')}"
                if ref_key in sent_refs:
                    continue

                triggers.append({
                    "type": "event_followup",
                    "ref": ref_key,
                    "summary": evt.get("summary", ""),
                    "category": evt.get("category", ""),
                    "importance": importance,
                    "age_hours": round(age_hours),
                })

        strat_cfg = self.triggers_cfg.get("strategy", {})
        if strat_cfg.get("enabled", True):
            strategies = load_pending_strategies()
            recent_logs = load_proactive_log(chat_id, since_hours=DEFAULT_STRATEGY_LOG_HOURS)
            sent_refs = {
                log["trigger_ref"] for log in recent_logs
                if log.get("trigger_type") == "strategy"
            }
            for strat in strategies[:MAX_STRATEGIES_PER_SCAN]:
                ref_key = f"strategy_{strat.get('id', '')}"
                if ref_key in sent_refs:
                    continue
                triggers.append({
                    "type": "strategy",
                    "ref": ref_key,
                    "description": strat.get("description", ""),
                    "approach": strat.get("approach", ""),
                    "subject": strat.get("hypothesis_subject", ""),
                })

        idle_cfg = self.triggers_cfg.get("idle_checkin", {})
        if idle_cfg.get("enabled", True):
            idle_hours = idle_cfg.get("idle_hours", DEFAULT_IDLE_HOURS)
            session_id = f"{session_prefix}{chat_id}"
            last_time = get_last_interaction_time(session_id)
            if last_time:
                gap_hours = (now - last_time).total_seconds() / 3600
                if gap_hours >= idle_hours:
                    recent_idle = load_proactive_log(chat_id, since_hours=idle_hours)
                    already_sent = any(
                        log.get("trigger_type") == "idle_checkin"
                        for log in recent_idle
                    )
                    if not already_sent:
                        triggers.append({
                            "type": "idle_checkin",
                            "ref": "idle_checkin",
                            "idle_hours": round(gap_hours),
                        })

        return triggers

    def _decide_and_generate(self, chat_id: int,
                             triggers: list[dict]) -> dict | None:
        L = get_labels("context.labels", self.language)

        profile = load_full_current_profile()
        trajectory = load_trajectory_summary()
        user_model = load_user_model()
        today_logs = load_proactive_log(chat_id, since_hours=24)

        profile_text = "\n".join(
            f"- [{p.get('layer','?')}] {p.get('category','')}/{p.get('subject','')}: {p.get('value','')}"
            for p in profile[:30]
        ) if profile else L["no_profile_data"]

        trajectory_text = ""
        if trajectory:
            trajectory_text = (
                f"{L['life_phase_label']}: {trajectory.get('life_phase', '?')}\n"
                f"{L['trajectory_direction_label']}: {trajectory.get('trajectory_direction', '?')}\n"
                f"{L['recent_momentum_label']}: {trajectory.get('recent_momentum', '?')}"
            )

        model_text = "\n".join(
            f"- {m.get('dimension','')}: {m.get('assessment','')}"
            for m in user_model[:10]
        ) if user_model else L["no_user_model"]

        today_sent = "\n".join(
            f"- [{log.get('trigger_type','')}] {log.get('message_text','')[:50]}"
            for log in today_logs
        ) if today_logs else L["today_not_sent"]

        triggers_text = json.dumps(triggers, ensure_ascii=False, indent=2)

        system_prompt = get_prompt("proactive.system", self.language)

        user_prompt = get_prompt(
            "proactive.user", self.language,
            profile_text=profile_text,
            trajectory_text=trajectory_text or L["no_data_short"],
            model_text=model_text,
            today_sent=today_sent,
            triggers_text=triggers_text,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            raw = call_llm(messages, self.llm_config)
            result = self._parse_llm_response(raw)
            if result:
                return result
            logger.warning(_log("llm_parse_fail", self.language), raw[:200])
            return None
        except Exception:
            logger.exception(_log("llm_call_error", self.language))
            return None

    @staticmethod
    def _parse_llm_response(raw: str) -> dict | None:
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()

        try:
            data = json.loads(text)
            if isinstance(data, dict) and "send" in data:
                return {
                    "send": bool(data["send"]),
                    "reasoning": data.get("reasoning", ""),
                    "trigger_used": data.get("trigger_used", ""),
                    "message": data.get("message", ""),
                }
        except json.JSONDecodeError:
            pass

        return None
