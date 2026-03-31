
import logging
from agent.tools import BaseTool, ToolManifest, ToolResult
from agent.config.prompts import get_prompt, get_labels
from agent.utils.llm_client import call_llm, is_llm_error

logger = logging.getLogger(__name__)

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

_DISCLAIMER = {
    "zh": "\n\n> ⚠️ 以上信息来自互联网搜索，内容可能不准确，请仔细甄别。",
    "en": "\n\n> ⚠️ The above information is from internet search results and may not be accurate. Please verify carefully.",
    "ja": "\n\n> ⚠️ 上記の情報はインターネット検索結果であり、正確でない場合があります。慎重にご確認ください。",
}


def _search_duckduckgo(query: str, max_results: int = 5) -> str:
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS
    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            title = r.get("title", "")
            body = r.get("body", "")
            href = r.get("href", "")
            results.append(f"**{title}**\n{body}\n{href}")
    return "\n\n".join(results) if results else ""


def _search_jina(query: str, max_chars: int = 8000) -> str:
    import requests
    import urllib.parse
    url = f"https://s.jina.ai/{urllib.parse.quote(query)}"
    resp = requests.get(url, headers={"Accept": "text/plain", "X-No-Cache": "true"}, timeout=20)
    resp.raise_for_status()
    text = resp.text.strip()
    return text[:max_chars] if len(text) > max_chars else text


class WebSearchTool(BaseTool):

    def __init__(self, config: dict):
        self.config = config
        self.language = config.get("language", "en")
        search_cfgs = [c for c in config.get("cloud_llm_configs", []) if c.get("search")]
        self._search_config = search_cfgs[0] if search_cfgs else None
        tool_cfg = config.get("tools", {}).get("web_search", {})
        self._backend = tool_cfg.get("backend", "openai_responses")

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
        if self._backend == "duckduckgo":
            try:
                try:
                    import ddgs  # noqa
                except ImportError:
                    import duckduckgo_search  # noqa
                return True
            except ImportError:
                return False
        if self._backend == "jina":
            return True
        return self._search_config is not None

    def execute(self, params: dict) -> ToolResult:
        EL = get_labels("errors.tools", self.config.get("language", "en"))
        query = params.get("query", "")
        if not query:
            return ToolResult(success=False, data="", error=EL["missing_search_query"])

        if self._backend == "duckduckgo":
            return self._execute_duckduckgo(query)
        if self._backend == "jina":
            return self._execute_jina(query)
        return self._execute_openai(query)

    def _execute_duckduckgo(self, query: str) -> ToolResult:
        logger.info("[web_search] DDG query: %s", query)
        try:
            raw = _search_duckduckgo(query)
        except Exception as e:
            logger.error("[web_search] DDG error: %s", e)
            return ToolResult(success=False, data="", error=str(e))

        if not raw:
            lang = self.config.get("language", "en")
            EL = get_labels("errors.tools", lang)
            logger.warning("[web_search] DDG no results for: %s", query)
            return ToolResult(success=False, data="", error=EL.get("search_no_results", "No results found."))

        logger.info("[web_search] DDG raw length: %d chars", len(raw))
        system_prompt = get_prompt("tools.web_search_system", self.language)
        _lang_prefix = {"zh": "搜索结果如下，请用中文回答", "ja": "検索結果は以下の通りです。日本語で回答してください"}.get(self.language, "Search results below, reply in English")
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{_lang_prefix}:\n\nQuery: {query}\n\n{raw}"},
        ]
        llm_cfg = dict(self.config.get("llm", self.config))
        llm_cfg["_source"] = "web_search"
        llm_cfg["temperature"] = 0  # factual summarization — no randomness
        response = call_llm(messages, llm_cfg)
        disclaimer = _DISCLAIMER.get(self.language, _DISCLAIMER["en"])
        if is_llm_error(response):
            logger.warning("[web_search] LLM summarization failed, returning raw")
            # LLM summarization failed — pass raw results so main LLM can still use them
            return ToolResult(success=True, data=f"{system_prompt}\n\n{raw}{disclaimer}")
        logger.info("[web_search] DDG success, response length: %d chars", len(response))
        return ToolResult(success=True, data=response + disclaimer)

    def _execute_jina(self, query: str) -> ToolResult:
        logger.info("[web_search] Jina query: %s", query)
        try:
            raw = _search_jina(query)
        except Exception as e:
            logger.error("[web_search] Jina error: %s", e)
            return ToolResult(success=False, data="", error=str(e))

        if not raw:
            lang = self.config.get("language", "en")
            EL = get_labels("errors.tools", lang)
            return ToolResult(success=False, data="", error=EL.get("search_no_results", "No results found."))

        system_prompt = get_prompt("tools.web_search_system", self.language)
        _lang_prefix = {"zh": "搜索结果如下，请用中文回答", "ja": "検索結果は以下の通りです。日本語で回答してください"}.get(self.language, "Search results below, reply in English")
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{_lang_prefix}:\n\nQuery: {query}\n\n{raw}"},
        ]
        llm_cfg = dict(self.config.get("llm", self.config))
        llm_cfg["_source"] = "web_search"
        llm_cfg["temperature"] = 0  # factual summarization — no randomness
        response = call_llm(messages, llm_cfg)
        disclaimer = _DISCLAIMER.get(self.language, _DISCLAIMER["en"])
        if is_llm_error(response):
            return ToolResult(success=True, data=f"{raw[:3000]}{disclaimer}")
        return ToolResult(success=True, data=response + disclaimer)

    def _execute_openai(self, query: str) -> ToolResult:
        EL = get_labels("errors.tools", self.config.get("language", "en"))
        if not self._search_config:
            return ToolResult(success=False, data="", error=EL.get("search_unavailable", "Search not configured."))

        messages = [
            {"role": "system", "content": get_prompt("tools.web_search_openai_system", self.language)},
            {"role": "user", "content": query},
        ]
        L = get_labels("context.labels", self.config.get("language", "en"))
        cfg = dict(self._search_config)
        cfg["_citation_label"] = L.get("citation_header", "Sources")
        cfg["_source"] = "web_search"
        response = call_llm(messages, cfg)

        if is_llm_error(response):
            return ToolResult(success=False, data="", error=response)

        return ToolResult(success=True, data=response)
