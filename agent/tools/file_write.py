
import os

from agent.tools import BaseTool, ToolManifest, ToolResult

_FALLBACK = {
    "en": {
        "description": (
            "Write text content to a local file. "
            "Creates the file if it does not exist; overwrites it silently if it does. "
            "Parent directories are created automatically. "
            "Writes are restricted to the current working directory and /tmp."
        ),
        "parameters": {
            "path": "File path to write (string, absolute or relative)",
            "content": "Text content to write to the file (string, UTF-8)",
        },
        "examples": [
            "write JSON result to /tmp/output.json",
            "save generated README to ./README.md",
            "create config file at config/settings.yaml",
        ],
    },
    "zh": {
        "description": (
            "将文本内容写入本地文件。"
            "文件不存在时自动创建，已存在时直接覆盖（无确认提示）。"
            "父级目录不存在时自动创建。"
            "写入路径限制在当前工作目录和 /tmp 内。"
        ),
        "parameters": {
            "path": "要写入的文件路径（string，绝对路径或相对路径）",
            "content": "要写入文件的文本内容（string，UTF-8 编码）",
        },
        "examples": [
            "将 JSON 结果写入 /tmp/output.json",
            "将生成的 README 保存到 ./README.md",
            "在 config/settings.yaml 创建配置文件",
        ],
    },
    "ja": {
        "description": (
            "テキストをローカルファイルに書き込みます。"
            "ファイルが存在しない場合は作成し、存在する場合は確認なしで上書きします。"
            "親ディレクトリが存在しない場合は自動的に作成されます。"
            "書き込み先はカレントディレクトリと /tmp に制限されています。"
        ),
        "parameters": {
            "path": "書き込むファイルパス（string、絶対パスまたは相対パス）",
            "content": "ファイルに書き込むテキスト内容（string、UTF-8）",
        },
        "examples": [
            "JSON 結果を /tmp/output.json に書き込む",
            "生成した README を ./README.md に保存する",
            "config/settings.yaml に設定ファイルを作成する",
        ],
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
            parameter_types={"path": "string", "content": "string"},
        )

    def is_available(self) -> bool:
        return self._tool_cfg.get("enabled", True)

    def execute(self, params: dict) -> ToolResult:
        path = params.get("path", "").strip()
        content = params.get("content", "")

        if not path:
            return ToolResult(success=False, data="", error="Missing required parameter: path")

        abs_path = os.path.realpath(os.path.abspath(path))
        abs_path_raw = os.path.abspath(path)
        cwd = os.path.realpath(os.getcwd())

        # Allow writes within cwd (check both resolved and unresolved paths to support symlinks)
        in_cwd = (abs_path.startswith(cwd + os.sep) or abs_path == cwd or
                  abs_path_raw.startswith(cwd + os.sep) or abs_path_raw == cwd)
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
