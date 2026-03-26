
import os

from agent.tools import BaseTool, ToolManifest, ToolResult

_FALLBACK = {
    "en": {
        "description": "List directory contents (files and subdirectories, one level deep)",
        "parameters": {
            "path": "Directory path to list (default: current working directory)",
        },
        "examples": ["List files in .", "What's in the src/ directory?", "Show me the contents of /tmp"],
    },
    "zh": {
        "description": "列出目录内容（文件和子目录，单层）",
        "parameters": {
            "path": "要列出的目录路径（默认：当前工作目录）",
        },
        "examples": ["列出 . 目录的文件", "src/ 目录里有什么？", "显示 /tmp 的内容"],
    },
    "ja": {
        "description": "ディレクトリの内容を一覧表示する（ファイルとサブディレクトリ、1レベルのみ）",
        "parameters": {
            "path": "一覧表示するディレクトリパス（デフォルト：カレントディレクトリ）",
        },
        "examples": [". の中のファイルを一覧表示", "src/ ディレクトリの中身は？", "/tmp の内容を見せて"],
    },
}


class FileListTool(BaseTool):

    def __init__(self, config: dict):
        self.config = config
        self._tool_cfg = config.get("tools", {}).get("file_list", {})

    def manifest(self) -> ToolManifest:
        lang = self.config.get("language", "en")
        fb = _FALLBACK.get(lang, _FALLBACK["en"])
        return ToolManifest(
            name="file_list",
            description=fb["description"],
            parameters=fb["parameters"],
            examples=fb["examples"],
        )

    def is_available(self) -> bool:
        return self._tool_cfg.get("enabled", True)

    def execute(self, params: dict) -> ToolResult:
        path = params.get("path", ".").strip() or "."
        abs_path = os.path.realpath(os.path.abspath(path))

        if not os.path.exists(abs_path):
            return ToolResult(success=False, data="", error=f"Path not found: {abs_path}")
        if not os.path.isdir(abs_path):
            return ToolResult(success=False, data="", error=f"Not a directory: {abs_path}")

        try:
            entries = os.listdir(abs_path)
        except Exception as e:
            return ToolResult(success=False, data="", error=f"Cannot list directory: {e}")

        entries.sort()
        lines = [f"=== {abs_path} ==="]
        dirs = []
        files = []
        for name in entries:
            full = os.path.join(abs_path, name)
            if os.path.isdir(full):
                dirs.append(name)
            else:
                try:
                    size = os.path.getsize(full)
                    files.append((name, size))
                except OSError:
                    files.append((name, -1))

        for d in dirs:
            lines.append(f"  {d}/")
        for name, size in files:
            if size >= 0:
                lines.append(f"  {name}  ({size} bytes)")
            else:
                lines.append(f"  {name}")

        lines.append(f"\n{len(dirs)} directories, {len(files)} files")
        return ToolResult(success=True, data="\n".join(lines))
