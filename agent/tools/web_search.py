
from agent.tools import BaseTool, ToolManifest, ToolResult
from agent.config.prompts import get_prompt, get_labels
from agent.utils.llm_client import call_llm, is_llm_error

_FALLBACK = {
    "en": {
        "description": "Search the internet for real-time info: weather, news, prices, etc.",
        "parameters": {"query": "Search keywords"},
        "examples": ["Weather in Tokyo today", "Latest iPhone price", "Flights from NYC to London"],
    },
    "zh": {
        "description": "搜索互联网获取实时信息、天气、新闻、价格等",
        "parameters": {"query": "搜索关键词"},
        "examples": ["今天东京天气", "iPhone最新价格", "北京飞日本机票"],
    },
    "ja": {
        "description": "インターネットでリアルタイム情報を検索：天気、ニュース、価格など",
        "parameters": {"query": "検索キーワード"},
        "examples": ["東京の今日の天気", "iPhone最新価格", "東京からロンドンへのフライト"],
    },
}

class WebSearchTool(BaseTool):

    def __init__(self, config: dict):
        self.config = config
        self.language = config.get("language", "en")
        self._search_config = None
        for cfg in config.get("cloud_llm_configs", []):
            if cfg.get("search"):
                self._search_config = cfg
                break

    def manifest(self) -> ToolManifest:
        lang = self.config.get("language", "en")
        fb = _FALLBACK.get(lang, _FALLBACK["en"])
        m = get_labels("tools.manifests", lang).get("web_search", {})
        return ToolManifest(
            name="web_search",
            description=m.get("description", fb["description"]),
            parameters=m.get("parameters", fb["parameters"]),
            examples=m.get("examples", fb["examples"]),
        )

    def is_available(self) -> bool:
        return self._search_config is not None

    def execute(self, params: dict) -> ToolResult:
        EL = get_labels("errors.tools", self.config.get("language", "en"))
        query = params.get("query", "")
        if not query:
            return ToolResult(success=False, data="", error=EL["missing_search_query"])

        messages = [
            {"role": "system", "content": get_prompt("tools.web_search_system", self.language)},
            {"role": "user", "content": query},
        ]

        L = get_labels("context.labels", self.config.get("language", "en"))
        cfg = dict(self._search_config)
        cfg["_citation_label"] = L.get("citation_header", "Sources")
        response = call_llm(messages, cfg)

        if is_llm_error(response):
            return ToolResult(success=False, data="", error=response)

        return ToolResult(success=True, data=response)
