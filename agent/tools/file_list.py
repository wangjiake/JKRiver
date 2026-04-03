
import os

from agent.tools import BaseTool, ToolManifest, ToolResult

_FALLBACK = {
    "en": {
        "description": (
            "List the immediate contents of a directory (one level deep, non-recursive). "
            "Returns subdirectories (with trailing /) and files with their sizes in bytes, "
            "followed by a summary line: `N directories, M files`. "
            "Use grep or shell_exec (find) for recursive or filtered listings."
        ),
        "parameters": {
            "path": "Directory path to list (string, default: current working directory)",
        },
        "examples": [
            "list files in the current project root",
            "what's inside the src/ directory?",
            "show contents of /tmp",
        ],
    },
    "zh": {
        "description": (
            "列出目录的直接内容（单层，非递归）。"
            "返回子目录（以 / 结尾）和文件（附文件大小，单位 bytes），"
            "末尾附汇总行：`N 个目录，M 个文件`。"
            "递归列目录或按条件筛选请用 grep 或 shell_exec（find）。"
        ),
        "parameters": {
            "path": "要列出的目录路径（string，默认：当前工作目录）",
        },
        "examples": [
            "列出项目根目录的文件",
            "src/ 目录里有什么？",
            "显示 /tmp 的内容",
        ],
    },
    "ja": {
        "description": (
            "ディレクトリの直下の内容を一覧表示します（1レベルのみ、再帰なし）。"
            "サブディレクトリ（末尾 /）とファイル（サイズ bytes 付き）を返し、"
            "末尾に `N directories, M files` のサマリ行が付きます。"
            "再帰的な一覧や条件絞り込みは grep または shell_exec（find）を使ってください。"
        ),
        "parameters": {
            "path": "一覧表示するディレクトリパス（string、デフォルト：カレントディレクトリ）",
        },
        "examples": [
            "プロジェクトルートのファイルを一覧表示",
            "src/ ディレクトリの中身は？",
            "/tmp の内容を見せて",
        ],
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
            parameter_types={"path": "string"},
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
