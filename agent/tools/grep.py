
import fnmatch
import os
import re

from agent.tools import BaseTool, ToolManifest, ToolResult

_MAX_LINES = 100

_FALLBACK = {
    "en": {
        "description": (
            "Search for a regex pattern across files. "
            "Returns matching lines in `file:line_number: content` format. "
            "Results are capped at 100 lines; if truncated, a notice is appended. "
            "Use file_glob to narrow the search (e.g. '*.py') and avoid scanning binaries."
        ),
        "parameters": {
            "pattern": "Regular expression pattern to search for (required)",
            "path": "Directory or file to search in (string, default: current working directory)",
            "file_glob": "Glob pattern to restrict which files are searched (string, default: * — all files). Example: '*.py', '*.yaml'",
        },
        "examples": [
            "find all TODO comments across the project",
            "search for 'def run' in *.py files under src/",
            "locate config key 'api_key' in *.yaml files",
            "grep 'import asyncio' in Python files",
        ],
    },
    "zh": {
        "description": (
            "使用正则表达式在文件中搜索内容。"
            "返回格式为 `文件名:行号: 内容`。"
            "最多返回 100 行，超出时末尾附加截断提示。"
            "建议用 file_glob 限定文件类型（如 '*.py'），避免扫描二进制文件。"
        ),
        "parameters": {
            "pattern": "要搜索的正则表达式（必填）",
            "path": "搜索目录或文件路径（string，默认：当前工作目录）",
            "file_glob": "限定搜索范围的 glob 模式（string，默认：* 匹配所有文件），如 '*.py'、'*.yaml'",
        },
        "examples": [
            "在整个项目中查找所有 TODO 注释",
            "在 src/ 下的 *.py 文件中搜索 'def run'",
            "在 *.yaml 文件中定位配置键 'api_key'",
            "在 Python 文件中查找 'import asyncio'",
        ],
    },
    "ja": {
        "description": (
            "正規表現を使ってファイル内のパターンを検索します。"
            "結果は `ファイル名:行番号: 内容` 形式で返されます。"
            "最大100行まで返し、超過した場合は末尾に切り捨て通知が付きます。"
            "file_glob でファイル種別を絞り込むことを推奨します（例: '*.py'）。"
        ),
        "parameters": {
            "pattern": "検索する正規表現パターン（必須）",
            "path": "検索対象のディレクトリまたはファイル（string、デフォルト：カレントディレクトリ）",
            "file_glob": "検索対象ファイルを絞り込む glob パターン（string、デフォルト：* 全ファイル）。例: '*.py'、'*.yaml'",
        },
        "examples": [
            "プロジェクト全体から TODO コメントを探す",
            "src/ 以下の *.py ファイルで 'def run' を検索",
            "*.yaml ファイルで設定キー 'api_key' を探す",
            "Python ファイルで 'import asyncio' を検索",
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
            parameter_types={"pattern": "string", "path": "string", "file_glob": "string"},
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
