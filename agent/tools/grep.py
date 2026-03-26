
import fnmatch
import os
import re

from agent.tools import BaseTool, ToolManifest, ToolResult

_MAX_LINES = 100

_FALLBACK = {
    "en": {
        "description": "Search for a pattern in files using regular expressions",
        "parameters": {
            "pattern": "Regular expression pattern to search for",
            "path": "Directory or file to search in (default: current working directory)",
            "file_glob": "Glob pattern to filter files (default: *, matches all files)",
        },
        "examples": [
            "Search for 'def run' in *.py files",
            "Find all TODO comments in src/",
            "Look for 'import asyncio' in the project",
        ],
    },
    "zh": {
        "description": "使用正则表达式在文件中搜索模式",
        "parameters": {
            "pattern": "要搜索的正则表达式模式",
            "path": "要搜索的目录或文件（默认：当前工作目录）",
            "file_glob": "过滤文件的 glob 模式（默认：*，匹配所有文件）",
        },
        "examples": [
            "在 *.py 文件中搜索 'def run'",
            "在 src/ 中查找所有 TODO 注释",
            "在项目中查找 'import asyncio'",
        ],
    },
    "ja": {
        "description": "正規表現を使ってファイル内のパターンを検索する",
        "parameters": {
            "pattern": "検索する正規表現パターン",
            "path": "検索するディレクトリまたはファイル（デフォルト：カレントディレクトリ）",
            "file_glob": "ファイルを絞り込む glob パターン（デフォルト：*、全ファイルにマッチ）",
        },
        "examples": [
            "*.py ファイルで 'def run' を検索",
            "src/ 内の TODO コメントをすべて探す",
            "プロジェクト内で 'import asyncio' を探す",
        ],
    },
}


class GrepTool(BaseTool):

    def __init__(self, config: dict):
        self.config = config
        self._tool_cfg = config.get("tools", {}).get("grep", {})

    def manifest(self) -> ToolManifest:
        lang = self.config.get("language", "en")
        fb = _FALLBACK.get(lang, _FALLBACK["en"])
        return ToolManifest(
            name="grep",
            description=fb["description"],
            parameters=fb["parameters"],
            examples=fb["examples"],
        )

    def is_available(self) -> bool:
        return self._tool_cfg.get("enabled", True)

    def execute(self, params: dict) -> ToolResult:
        pattern = params.get("pattern", "").strip()
        path = params.get("path", ".").strip() or "."
        file_glob = params.get("file_glob", "*").strip() or "*"

        if not pattern:
            return ToolResult(success=False, data="", error="Missing required parameter: pattern")

        try:
            regex = re.compile(pattern)
        except re.error as e:
            return ToolResult(success=False, data="", error=f"Invalid regular expression: {e}")

        abs_path = os.path.realpath(os.path.abspath(path))
        if not os.path.exists(abs_path):
            return ToolResult(success=False, data="", error=f"Path not found: {abs_path}")

        matches = []
        truncated = False

        if os.path.isfile(abs_path):
            files_to_search = [abs_path]
        else:
            files_to_search = []
            for dirpath, _dirnames, filenames in os.walk(abs_path):
                for fname in filenames:
                    if fnmatch.fnmatch(fname, file_glob):
                        files_to_search.append(os.path.join(dirpath, fname))

        for filepath in sorted(files_to_search):
            try:
                with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                    for lineno, line in enumerate(f, start=1):
                        if regex.search(line):
                            rel = os.path.relpath(filepath, abs_path) if os.path.isdir(abs_path) else filepath
                            matches.append(f"{rel}:{lineno}: {line.rstrip()}")
                            if len(matches) >= _MAX_LINES:
                                truncated = True
                                break
            except Exception:
                continue
            if truncated:
                break

        if not matches:
            return ToolResult(success=True, data=f"No matches found for pattern '{pattern}'")

        output = "\n".join(matches)
        if truncated:
            output += f"\n\n[Output truncated at {_MAX_LINES} lines]"

        return ToolResult(success=True, data=output)
