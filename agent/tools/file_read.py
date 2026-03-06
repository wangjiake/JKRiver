
import os

from agent.tools import BaseTool, ToolManifest, ToolResult
from agent.config.prompts import get_labels

_DEFAULT_MAX_SIZE = 1_048_576
_MAX_OUTPUT_CHARS = 4000

_FALLBACK = {
    "en": {
        "description": "Read local text file content (.txt/.py/.yaml/.json/.md etc.)",
        "parameters": {"path": "File path (absolute or relative)"},
        "examples": ["Read settings.yaml", "Show the contents of README.md", "What's in src/main.py"],
    },
    "zh": {
        "description": "读取本地文本文件内容（支持 .txt/.py/.yaml/.json/.md 等）",
        "parameters": {"path": "文件路径（绝对路径或相对路径）"},
        "examples": ["读一下 settings.yaml", "查看 README.md 的内容", "帮我看看 src/main.py 里写了什么"],
    },
    "ja": {
        "description": "ローカルテキストファイルの内容を読み取る（.txt/.py/.yaml/.json/.md 等）",
        "parameters": {"path": "ファイルパス（絶対パスまたは相対パス）"},
        "examples": ["settings.yaml を読んで", "README.md の内容を見せて", "src/main.py に何が書いてある"],
    },
}

class FileReadTool(BaseTool):

    def __init__(self, config: dict):
        self.config = config
        self._tool_cfg = config.get("tools", {}).get("file_read", {})

    def manifest(self) -> ToolManifest:
        lang = self.config.get("language", "en")
        fb = _FALLBACK.get(lang, _FALLBACK["en"])
        m = get_labels("tools.manifests", lang).get("file_read", {})
        return ToolManifest(
            name="file_read",
            description=m.get("description", fb["description"]),
            parameters=m.get("parameters", fb["parameters"]),
            examples=m.get("examples", fb["examples"]),
        )

    def is_available(self) -> bool:
        return self._tool_cfg.get("enabled", True)

    def execute(self, params: dict) -> ToolResult:
        TL = get_labels("tools.labels", self.config.get("language", "en"))
        EL = get_labels("errors.tools", self.config.get("language", "en"))
        path = params.get("path", "").strip()
        if not path:
            return ToolResult(success=False, data="", error=EL["missing_path_param"])

        path = os.path.realpath(os.path.abspath(path))

        allowed_dirs = self._tool_cfg.get("allowed_dirs", [])
        if allowed_dirs:
            if not any(path.startswith(os.path.realpath(os.path.abspath(d))) for d in allowed_dirs):
                return ToolResult(
                    success=False, data="",
                    error=EL["path_not_allowed"].format(path=path))

        if not os.path.isfile(path):
            return ToolResult(success=False, data="", error=EL["file_not_found"].format(path=path))

        max_size = self._tool_cfg.get("max_file_size", _DEFAULT_MAX_SIZE)
        file_size = os.path.getsize(path)
        if file_size > max_size:
            return ToolResult(
                success=False, data="",
                error=EL["file_too_large"].format(size=file_size, limit=max_size))

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            return ToolResult(success=False, data="", error=EL["file_read_failed"].format(error=e))

        truncated = ""
        if len(content) > _MAX_OUTPUT_CHARS:
            content = content[:_MAX_OUTPUT_CHARS]
            truncated = "\n\n[" + TL.get("content_truncated", "内容已截断，仅显示前 {limit} 字符").format(limit=_MAX_OUTPUT_CHARS) + "]"

        return ToolResult(
            success=True,
            data=f"=== {path} ===\n{content}{truncated}",
        )
