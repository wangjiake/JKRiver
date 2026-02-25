
import asyncio
import json
import logging
import threading

from agent.tools import BaseTool, ToolManifest, ToolResult
from agent.config.prompts import get_labels

logger = logging.getLogger(__name__)

class MCPManager:

    def __init__(self, servers_config: list[dict]):
        self._servers_config = servers_config
        self._sessions = {}
        self._tools = {}

        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._loop.run_forever, daemon=True)
        self._thread.start()

        future = asyncio.run_coroutine_threadsafe(
            self._connect_all(), self._loop)
        future.result(timeout=30)

    async def _connect_all(self):
        for srv_cfg in self._servers_config:
            name = srv_cfg.get("name", "")
            if not name:
                continue
            try:
                await self._connect_server(srv_cfg)
                logger.info("[MCP] 已连接 server: %s", name)
            except Exception:
                logger.exception("[MCP] 连接 server '%s' 失败", name)

    async def _connect_server(self, srv_cfg: dict):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        name = srv_cfg["name"]
        command = srv_cfg.get("command", "")
        args = srv_cfg.get("args", [])
        env = srv_cfg.get("env")

        server_params = StdioServerParameters(
            command=command, args=args, env=env)

        transport_cm = stdio_client(server_params)
        read, write = await transport_cm.__aenter__()

        session = ClientSession(read, write)
        await session.__aenter__()
        await session.initialize()

        self._sessions[name] = (session, transport_cm, read, write)

        tools_result = await session.list_tools()
        for tool in tools_result.tools:
            key = f"{name}/{tool.name}"
            self._tools[key] = {
                "name": tool.name,
                "description": tool.description or "",
                "inputSchema": tool.inputSchema if hasattr(tool, "inputSchema") else {},
                "server": name,
            }
            logger.info("[MCP]   工具: %s/%s", name, tool.name)

    def list_tools(self) -> list[dict]:
        return list(self._tools.values())

    def call_tool(self, server_name: str, tool_name: str,
                  arguments: dict) -> str:
        session_info = self._sessions.get(server_name)
        if not session_info:
            EL = get_labels("errors.tools", "zh")
            raise RuntimeError(EL["mcp_server_not_connected"].format(name=server_name))

        session = session_info[0]

        async def _call():
            result = await session.call_tool(tool_name, arguments)
            parts = []
            for content in result.content:
                if hasattr(content, "text"):
                    parts.append(content.text)
                else:
                    parts.append(str(content))
            return "\n".join(parts)

        future = asyncio.run_coroutine_threadsafe(_call(), self._loop)
        return future.result(timeout=60)

    def shutdown(self):
        async def _close():
            for name, (session, transport_cm, _, _) in self._sessions.items():
                try:
                    await transport_cm.__aexit__(None, None, None)
                except Exception:
                    pass
            self._sessions.clear()

        try:
            future = asyncio.run_coroutine_threadsafe(_close(), self._loop)
            future.result(timeout=10)
        except Exception:
            pass
        self._loop.call_soon_threadsafe(self._loop.stop)

class MCPBridgeTool(BaseTool):

    def __init__(self, manager: MCPManager, tool_info: dict, language: str = "zh"):
        self._manager = manager
        self._tool_info = tool_info
        self._server = tool_info["server"]
        self._tool_name = tool_info["name"]
        self._language = language

    def manifest(self) -> ToolManifest:
        schema = self._tool_info.get("inputSchema", {})
        parameters = {}
        props = schema.get("properties", {})
        for pname, pschema in props.items():
            desc = pschema.get("description", pschema.get("type", ""))
            parameters[pname] = desc

        return ToolManifest(
            name=f"mcp_{self._server}_{self._tool_name}",
            description=self._tool_info.get("description", "MCP tool"),
            parameters=parameters,
        )

    def execute(self, params: dict) -> ToolResult:
        try:
            result = self._manager.call_tool(
                self._server, self._tool_name, params)
            return ToolResult(success=True, data=result)
        except Exception as e:
            EL = get_labels("errors.tools", self._language)
            return ToolResult(
                success=False, data="",
                error=EL["mcp_tool_call_failed"].format(error=e))
