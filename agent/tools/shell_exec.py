
import re
import subprocess

from agent.tools import BaseTool, ToolManifest, ToolResult
from agent.config.prompts import get_labels

_DANGEROUS_RE = re.compile(r"[;&|`$(){}><]|\bsudo\b|\brm\b|\bdd\b|\bmkfs\b")

_MAX_OUTPUT_CHARS = 4000

_DEFAULT_WHITELIST = [
    "ls", "dir", "cat", "head", "tail", "find", "grep", "wc",
    "date", "whoami", "hostname", "uname", "df", "du",
    "python --version", "python3 --version", "pip list", "pip3 list",
    "git status", "git log", "git diff", "git branch", "git remote",
    "node --version", "npm --version",
]

_FALLBACK = {
    "en": {
        "description": "Execute safe shell commands (read-only commands like ls/grep/git status)",
        "parameters": {"command": "Shell command to execute"},
        "examples": ["Run git status", "List files in current directory", "Run python --version"],
    },
    "zh": {
        "description": "执行安全的 shell 命令（仅限只读命令，如 ls/grep/git status 等）",
        "parameters": {"command": "要执行的 shell 命令"},
        "examples": ["执行 git status", "查看当前目录文件列表", "运行 python --version"],
    },
    "ja": {
        "description": "安全なシェルコマンドを実行（読み取り専用コマンドのみ: ls/grep/git status 等）",
        "parameters": {"command": "実行するシェルコマンド"},
        "examples": ["git status を実行", "現在のディレクトリのファイル一覧", "python --version を実行"],
    },
}

class ShellExecTool(BaseTool):

    def __init__(self, config: dict):
        self.config = config
        self._tool_cfg = config.get("tools", {}).get("shell_exec", {})

    def manifest(self) -> ToolManifest:
        lang = self.config.get("language", "zh")
        fb = _FALLBACK.get(lang, _FALLBACK["en"])
        m = get_labels("tools.manifests", lang).get("shell_exec", {})
        return ToolManifest(
            name="shell_exec",
            description=m.get("description", fb["description"]),
            parameters=m.get("parameters", fb["parameters"]),
            examples=m.get("examples", fb["examples"]),
        )

    def is_available(self) -> bool:
        return self._tool_cfg.get("enabled", False)

    def execute(self, params: dict) -> ToolResult:
        TL = get_labels("tools.labels", self.config.get("language", "zh"))
        EL = get_labels("errors.tools", self.config.get("language", "zh"))
        command = params.get("command", "").strip()
        if not command:
            return ToolResult(success=False, data="", error=EL["missing_command_param"])

        if _DANGEROUS_RE.search(command):
            return ToolResult(
                success=False, data="",
                error=EL["command_dangerous_chars"].format(command=command))

        whitelist = self._tool_cfg.get("whitelist", _DEFAULT_WHITELIST)
        if not any(command.startswith(prefix) for prefix in whitelist):
            return ToolResult(
                success=False, data="",
                error=EL["command_not_whitelisted"].format(prefixes=', '.join(whitelist[:10]) + '...'))

        timeout = self._tool_cfg.get("timeout", 30)
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False, data="",
                error=EL["command_timeout"].format(timeout=timeout))
        except Exception as e:
            return ToolResult(
                success=False, data="",
                error=EL["command_exec_failed"].format(error=e))

        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()

        if result.returncode != 0:
            error_msg = stderr[:500] if stderr else EL["command_return_code"].format(code=result.returncode)
            return ToolResult(
                success=False,
                data=stdout[:_MAX_OUTPUT_CHARS] if stdout else "",
                error=error_msg)

        output = stdout or TL.get("no_output", "(无输出)")
        if len(output) > _MAX_OUTPUT_CHARS:
            output = output[:_MAX_OUTPUT_CHARS] + "\n\n[" + TL.get("output_truncated", "输出已截断，仅显示前 {limit} 字符").format(limit=_MAX_OUTPUT_CHARS) + "]"

        return ToolResult(success=True, data=output)
