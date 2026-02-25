
import importlib
import os
import pkgutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import yaml

@dataclass
class ToolManifest:
    name: str
    description: str
    parameters: dict
    examples: list[str] = field(default_factory=list)

@dataclass
class ToolResult:
    success: bool
    data: str
    error: str = ""

class BaseTool(ABC):

    @abstractmethod
    def manifest(self) -> ToolManifest:
        ...

    @abstractmethod
    def execute(self, params: dict) -> ToolResult:
        ...

    def is_available(self) -> bool:
        return True

class ToolRegistry:

    def __init__(self, config: dict):
        self.config = config
        self._tools: dict[str, BaseTool] = {}
        self._discover()

    def _discover(self):
        import agent.tools as tools_pkg

        for importer, modname, ispkg in pkgutil.iter_modules(tools_pkg.__path__):
            if modname.startswith("_"):
                continue
            try:
                module = importlib.import_module(f"agent.tools.{modname}")
            except Exception as e:
                continue

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type)
                        and issubclass(attr, BaseTool)
                        and attr is not BaseTool):
                    try:
                        instance = attr(self.config)
                        if instance.is_available():
                            manifest = instance.manifest()
                            self._tools[manifest.name] = instance
                    except Exception as e:
                        pass

        self._discover_agents()

        self._discover_mcp()

    def _discover_mcp(self):
        mcp_cfg = self.config.get("mcp", {})
        if not mcp_cfg.get("enabled"):
            return

        servers = mcp_cfg.get("servers", [])
        if not servers:
            return

        try:
            from agent.tools._mcp_bridge import MCPManager, MCPBridgeTool
        except ImportError as e:
            return

        try:
            manager = MCPManager(servers)
        except Exception as e:
            return

        for tool_info in manager.list_tools():
            try:
                bridge = MCPBridgeTool(manager, tool_info, language=self.config.get("language", "zh"))
                manifest = bridge.manifest()
                if manifest.name not in self._tools:
                    self._tools[manifest.name] = bridge
                else:
                    pass
            except Exception as e:
                pass

    def _discover_agents(self):
        from agent.tools._agent_proxy import AgentProxyTool

        lang = self.config.get("language", "en")
        config_dir = os.path.join(os.path.dirname(__file__), "..", "config")
        agents_path = os.path.join(config_dir, f"agents_{lang}.yaml")
        if not os.path.exists(agents_path):
            agents_path = os.path.join(config_dir, "agents_en.yaml")
        if not os.path.exists(agents_path):
            return

        try:
            with open(agents_path, "r", encoding="utf-8") as f:
                agents_config = yaml.safe_load(f) or {}
        except Exception as e:
            return

        for agent_def in agents_config.get("agents", []):
            name = agent_def.get("name", "")
            if not name:
                continue
            if name in self._tools:
                continue
            try:
                proxy = AgentProxyTool(agent_def, self.config)
                if proxy.is_available():
                    self._tools[name] = proxy
            except Exception as e:
                pass

    def list_available(self) -> list[ToolManifest]:
        return [t.manifest() for t in self._tools.values()]

    def execute(self, name: str, params: dict) -> ToolResult:
        from agent.config.prompts import get_labels
        EL = get_labels("errors.tools", self.config.get("language", "zh"))
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(success=False, data="", error=EL["tool_not_found"].format(name=name))
        try:
            return tool.execute(params)
        except Exception as e:
            return ToolResult(success=False, data="", error=EL["tool_exec_error"].format(name=name, error=e))

    def get_tool(self, name: str) -> BaseTool | None:
        return self._tools.get(name)
