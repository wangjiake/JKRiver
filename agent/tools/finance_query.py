
from agent.tools import BaseTool, ToolManifest, ToolResult
from agent.config.prompts import get_labels
from agent.storage import load_finance_transactions

_FALLBACK = {
    "en": {
        "description": "Query credit card transaction records (filter by month, merchant). Returns all matching records with totals.",
        "parameters": {"year": "Year (optional)", "month": "Month (optional)", "merchant": "Merchant name keyword (optional)"},
        "examples": ["Recent credit card transactions", "February spending", "How much did I spend last month", "Amazon purchases"],
    },
    "zh": {
        "description": "查询用户信用卡消费记录（支持按月份、商家筛选）。总是返回全部匹配记录和合计金额。",
        "parameters": {"year": "年份（可选）", "month": "月份（可选）", "merchant": "商家名关键词（可选）"},
        "examples": ["最近一笔信用卡消费", "2月份消费情况", "上个月消费了多少", "亚马逊消费记录"],
    },
    "ja": {
        "description": "クレジットカードの取引履歴を検索（月別・加盟店で絞り込み可能）。一致する全記録と合計を返す。",
        "parameters": {"year": "年（任意）", "month": "月（任意）", "merchant": "加盟店名キーワード（任意）"},
        "examples": ["最近のカード利用", "2月の支出", "先月いくら使った", "Amazonの購入履歴"],
    },
}

class FinanceQueryTool(BaseTool):

    def __init__(self, config: dict):
        self.config = config

    def manifest(self) -> ToolManifest:
        lang = self.config.get("language", "en")
        fb = _FALLBACK.get(lang, _FALLBACK["en"])
        m = get_labels("tools.manifests", lang).get("finance_query", {})
        return ToolManifest(
            name="finance_query",
            description=m.get("description", fb["description"]),
            parameters=m.get("parameters", fb["parameters"]),
            examples=m.get("examples", fb["examples"]),
        )

    def execute(self, params: dict) -> ToolResult:
        TL = get_labels("tools.labels", self.config.get("language", "en"))
        merchant = params.get("merchant") or None

        try:
            year = int(params["year"]) if params.get("year") else None
            month = int(params["month"]) if params.get("month") else None
        except (ValueError, TypeError):
            EL = get_labels("errors.tools", self.config.get("language", "en"))
            return ToolResult(success=False, data="",
                              error=EL.get("invalid_date_param", "Invalid year/month parameter"))

        try:
            rows = load_finance_transactions(
                year=year, month=month, merchant=merchant, limit=200,
            )
            if not rows:
                return ToolResult(success=True, data=TL.get("no_transactions", "该期间无消费记录。"))

            total_jpy = 0
            total_other = {}
            lines = []
            for r in rows:
                date_str = r["transaction_date"].strftime("%Y-%m-%d") if r.get("transaction_date") else "?"
                amt = float(r.get("amount", 0))
                cur = r.get("currency", "")
                jpy = r.get("amount_jpy")
                jpy_str = f" (≈{jpy:.0f}JPY)" if jpy and cur != "JPY" else ""
                cat = r.get("category") or ""
                lines.append(f"{date_str} {r.get('merchant','?')} {amt:.0f}{cur}{jpy_str} {cat}")

                if jpy:
                    total_jpy += float(jpy)
                elif cur == "JPY":
                    total_jpy += amt
                else:
                    total_other[cur] = total_other.get(cur, 0) + amt

            summary = TL.get("transaction_summary", "共{count}笔交易，合计: {total} JPY").format(count=len(rows), total=f"{total_jpy:.0f}")
            if total_other:
                for cur, amt in total_other.items():
                    summary += f" + {amt:.2f} {cur}"
            summary += "\n"

            return ToolResult(success=True, data=summary + "\n".join(lines))

        except Exception as e:
            EL = get_labels("errors.tools", self.config.get("language", "en"))
            return ToolResult(success=False, data="", error=EL["finance_query_failed"].format(error=e))
