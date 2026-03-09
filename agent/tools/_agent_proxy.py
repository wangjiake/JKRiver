
import re
import shlex
import subprocess
import requests

from agent.tools import BaseTool, ToolManifest, ToolResult
from agent.config.prompts import get_labels

_SHELL_META_RE = re.compile(r"[;&|`$(){}]")

_MAX_RESULT_LEN = 2000

class AgentProxyTool(BaseTool):

    def __init__(self, agent_config: dict, global_config: dict):
        self._cfg = agent_config
        self._global_config = global_config

    def manifest(self) -> ToolManifest:
        return ToolManifest(
            name=self._cfg["name"],
            description=self._cfg.get("description", ""),
            parameters=self._cfg.get("parameters", {}),
            examples=self._cfg.get("examples", []),
        )

    def is_available(self) -> bool:
        return self._cfg.get("enabled", True)

    def _get_error_labels(self) -> dict:
        return get_labels("errors.tools", self._global_config.get("language", "en"))

    def execute(self, params: dict) -> ToolResult:
        EL = self._get_error_labels()
        agent_type = self._cfg.get("type", "")
        try:
            if agent_type == "http":
                return self._execute_http(params)
            elif agent_type == "command":
                return self._execute_command(params)
            else:
                return ToolResult(success=False, data="",
                                  error=EL["unknown_agent_type"].format(type=agent_type))
        except Exception as e:
            return ToolResult(success=False, data="",
                              error=EL["agent_exec_error"].format(name=self._cfg['name'], error=e))

    def _execute_http(self, params: dict) -> ToolResult:
        EL = self._get_error_labels()
        http_cfg = self._cfg.get("http", {})
        url = http_cfg.get("url", "")
        if not url:
            return ToolResult(success=False, data="", error=EL["agent_no_http_url"])

        url = self._interpolate(url, params)

        method = http_cfg.get("method", "GET").upper()
        headers = dict(http_cfg.get("headers", {}))
        timeout = http_cfg.get("timeout", 15)

        query_params = None
        if http_cfg.get("query_template"):
            query_params = {
                k: self._interpolate(v, params)
                for k, v in http_cfg["query_template"].items()
            }

        body = None
        if http_cfg.get("body_template"):
            body_tpl = http_cfg["body_template"]
            if isinstance(body_tpl, dict):
                body = {
                    k: self._interpolate(v, params) if isinstance(v, str) else v
                    for k, v in body_tpl.items()
                }
            elif isinstance(body_tpl, str):
                body = self._interpolate(body_tpl, params)

        try:
            resp = requests.request(
                method, url,
                headers=headers,
                params=query_params,
                json=body if isinstance(body, dict) else None,
                data=body if isinstance(body, str) else None,
                timeout=timeout,
            )
            resp.raise_for_status()
        except requests.Timeout:
            return ToolResult(success=False, data="",
                              error=EL["http_timeout"].format(timeout=timeout))
        except requests.RequestException as e:
            return ToolResult(success=False, data="",
                              error=EL["http_request_failed"].format(error=e))

        result_path = http_cfg.get("result_path", "")
        data = self._extract_result(resp, result_path)
        return ToolResult(success=True, data=data[:_MAX_RESULT_LEN])

    def _execute_command(self, params: dict) -> ToolResult:
        EL = self._get_error_labels()
        cmd_cfg = self._cfg.get("command", {})
        template = cmd_cfg.get("template", "")
        if not template:
            return ToolResult(success=False, data="",
                              error=EL["agent_no_command_template"])

        timeout = cmd_cfg.get("timeout", 30)
        use_shell = cmd_cfg.get("shell", False)
        allowed = cmd_cfg.get("allowed_params", {})

        for key, value in params.items():
            value_str = str(value)
            if _SHELL_META_RE.search(value_str):
                return ToolResult(
                    success=False, data="",
                    error=EL["param_dangerous_chars"].format(key=key))
            if key in allowed:
                if value_str not in allowed[key]:
                    return ToolResult(
                        success=False, data="",
                        error=EL["param_not_whitelisted"].format(key=key, value=value_str, allowed=allowed[key]))

        cmd = self._interpolate(template, params)

        try:
            run_cmd = cmd if use_shell else shlex.split(cmd)
            result = subprocess.run(
                run_cmd, shell=use_shell,
                capture_output=True, text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, data="",
                              error=EL["command_timeout"].format(timeout=timeout))
        except Exception as e:
            return ToolResult(success=False, data="",
                              error=EL["command_exec_failed"].format(error=e))

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            return ToolResult(
                success=False, data="",
                error=f"{EL['command_return_code'].format(code=result.returncode)}: {stderr[:500]}")

        stdout = (result.stdout or "").strip()
        return ToolResult(success=True, data=stdout[:_MAX_RESULT_LEN])

    @staticmethod
    def _interpolate(template: str, params: dict) -> str:
        result = template
        for key, value in params.items():
            result = result.replace(f"{{{key}}}", str(value))
        result = re.sub(r"\{[a-zA-Z_][a-zA-Z0-9_]*\}", "", result)
        return result

    @staticmethod
    def _extract_result(resp: requests.Response, result_path: str) -> str:
        if not result_path:
            return resp.text

        try:
            data = resp.json()
        except ValueError:
            return resp.text

        for key in result_path.split("."):
            if isinstance(data, dict) and key in data:
                data = data[key]
            else:
                return resp.text

        if isinstance(data, str):
            return data
        import json
        return json.dumps(data, ensure_ascii=False)
