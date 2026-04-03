
from agent.tools import BaseTool, ToolManifest, ToolResult
from agent.config.prompts import get_labels
from agent.storage import (
    load_withings_measures,
    load_withings_activity,
)

_FALLBACK = {
    "en": {
        "description": "Query health data: weight, body fat, daily steps/activity. Returns last 90 days of data.",
        "parameters": {"data_type": "weight | fat | activity | all"},
        "examples": ["My recent weight", "Steps in the last 30 days", "Body fat trend"],
    },
    "zh": {
        "description": "查询用户健康数据：体重、体脂、每日步数/活动量。总是返回最近90天全部数据。",
        "parameters": {"data_type": "weight(体重) | fat(体脂) | activity(步数/活动) | all(全部)"},
        "examples": ["我最近体重多少", "最近30天步数", "体脂变化趋势"],
    },
    "ja": {
        "description": "健康データを取得：体重、体脂肪、歩数/活動量。直近90日分のデータを返す。",
        "parameters": {"data_type": "weight | fat | activity | all"},
        "examples": ["最近の体重", "過去30日の歩数", "体脂肪の推移"],
    },
}

class HealthQueryTool(BaseTool):

    def __init__(self, config: dict):
        self.config = config
        self._tool_cfg = config.get("tools", {}).get("health_query", {})

    def is_available(self) -> bool:
        return self._tool_cfg.get("enabled", True)

    def manifest(self) -> ToolManifest:
        lang = self.config.get("language", "en")
        fb = _FALLBACK.get(lang, _FALLBACK["en"])
        m = get_labels("tools.manifests", lang).get("health_query", {})
        return ToolManifest(
            name="health_query",
            description=m.get("description", fb["description"]),
            parameters=m.get("parameters", fb["parameters"]),
            examples=m.get("examples", fb["examples"]),
            parameter_types={"data_type": "string"},
        )

    def execute(self, params: dict) -> ToolResult:
        TL = get_labels("tools.labels", self.config.get("language", "en"))
        data_type = params.get("data_type", "all")

        try:
            parts = []

            if data_type in ("weight", "all"):
                rows = load_withings_measures(measure_type=1, days=90)
                if rows:
                    lines = [TL.get("weight_records", "Weight records ({count} entries):").format(count=len(rows))]
                    for r in rows:
                        lines.append(f"{r['measured_at'].strftime('%Y-%m-%d')} {float(r['value']):.1f}kg")
                    parts.append("\n".join(lines))

            if data_type in ("fat", "all"):
                rows = load_withings_measures(measure_type=6, days=90)
                if rows:
                    lines = [TL.get("fat_records", "Body fat records ({count} entries):").format(count=len(rows))]
                    for r in rows:
                        lines.append(f"{r['measured_at'].strftime('%Y-%m-%d')} {float(r['value']):.1f}%")
                    parts.append("\n".join(lines))

            if data_type in ("activity", "all"):
                rows = load_withings_activity(days=90)
                if rows:
                    lines = [TL.get("activity_records", "Activity records ({count} days):").format(count=len(rows))]
                    for r in rows:
                        d = r["activity_date"]
                        date_str = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)
                        steps = r.get("steps") or 0
                        cal = r.get("calories") or 0
                        lines.append(f"{date_str} {steps}{TL.get('steps_unit', 'steps')} {cal:.0f}kcal")
                    parts.append("\n".join(lines))

            if not parts:
                return ToolResult(success=True, data=TL.get("no_health_data", "No health data available."))

            return ToolResult(success=True, data="\n\n".join(parts))

        except Exception as e:
            EL = get_labels("errors.tools", self.config.get("language", "en"))
            return ToolResult(success=False, data="", error=EL["health_query_failed"].format(error=e))
