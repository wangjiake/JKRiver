
import os

from agent.tools import BaseTool, ToolManifest, ToolResult

_FALLBACK = {
    "en": {
        "description": "Write content to a local file (restricted to current working directory and /tmp)",
        "parameters": {
            "path": "File path to write (absolute or relative)",
            "content": "Text content to write to the file",
        },
        "examples": ["Write 'hello' to output.txt", "Save the result to /tmp/result.json"],
    },
    "zh": {
        "description": "将内容写入本地文件（限制在当前工作目录和 /tmp 内）",
        "parameters": {
            "path": "要写入的文件路径（绝对路径或相对路径）",
            "content": "要写入文件的文本内容",
        },
        "examples": ["将 'hello' 写入 output.txt", "将结果保存到 /tmp/result.json"],
    },
    "ja": {
        "description": "ローカルファイルにコンテンツを書き込む（カレントディレクトリと /tmp に制限）",
        "parameters": {
            "path": "書き込むファイルパス（絶対パスまたは相対パス）",
            "content": "ファイルに書き込むテキスト内容",
        },
        "examples": ["output.txt に 'hello' を書き込む", "結果を /tmp/result.json に保存する"],
    },
}


class FileWriteTool(BaseTool):

    def __init__(self, config: dict):
        self.config = config
        self._tool_cfg = config.get("tools", {}).get("file_write", {})

    def manifest(self) -> ToolManifest:
        lang = self.config.get("language", "en")
        fb = _FALLBACK.get(lang, _FALLBACK["en"])
        return ToolManifest(
            name="file_write",
            description=fb["description"],
            parameters=fb["parameters"],
            examples=fb["examples"],
        )

    def is_available(self) -> bool:
        return self._tool_cfg.get("enabled", True)

    def execute(self, params: dict) -> ToolResult:
        path = params.get("path", "").strip()
        content = params.get("content", "")

        if not path:
            return ToolResult(success=False, data="", error="Missing required parameter: path")

        abs_path = os.path.realpath(os.path.abspath(path))
        cwd = os.path.realpath(os.getcwd())

        # Allow writes only within cwd or /tmp
        in_cwd = abs_path.startswith(cwd + os.sep) or abs_path == cwd
        in_tmp = abs_path.startswith("/tmp" + os.sep) or abs_path == "/tmp"
        if not (in_cwd or in_tmp):
            return ToolResult(
                success=False, data="",
                error=f"Path not allowed: {abs_path}. Writes are restricted to the current working directory and /tmp.")

        try:
            parent = os.path.dirname(abs_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            return ToolResult(success=False, data="", error=f"File write failed: {e}")

        return ToolResult(
            success=True,
            data=f"Written {len(content)} characters to {abs_path}",
        )
