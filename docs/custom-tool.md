# Custom Tool Development

Riverse uses a drop-in tool system. To add a new tool, create a single `.py` file in `agent/tools/` — no registration code needed.

## Interface

Every tool extends `BaseTool` and implements two methods:

```python
from agent.tools import BaseTool, ToolManifest, ToolResult

class MyTool(BaseTool):

    def __init__(self, config: dict):
        self.config = config

    def manifest(self) -> ToolManifest:
        return ToolManifest(
            name="my_tool",                          # unique ID
            description="One-line description for LLM to decide when to use this tool",
            parameters={
                "param_name": "what this parameter means",
            },
            examples=[
                "natural language trigger example 1",
                "natural language trigger example 2",
            ],
        )

    def execute(self, params: dict) -> ToolResult:
        value = params.get("param_name", "")

        # do your work here...
        result = f"some output for {value}"

        return ToolResult(success=True, data=result)
```

### ToolManifest

| Field | Purpose |
|-------|---------|
| `name` | Unique identifier. The LLM uses this to call the tool. |
| `description` | One line. The LLM reads this to decide **when** to use the tool. |
| `parameters` | Dict of `{param: description}`. The LLM fills these in. |
| `examples` | 2-3 natural language phrases that would trigger this tool. |

### ToolResult

| Field | Purpose |
|-------|---------|
| `success` | `True` / `False` |
| `data` | String injected into the LLM's context as reference material. |
| `error` | Error message (only when `success=False`). |

### Optional: `is_available()`

Override this to disable the tool when dependencies are missing:

```python
def is_available(self) -> bool:
    return self.config.get("tools", {}).get("my_tool", {}).get("enabled", True)
```

## Example: Weather Tool

```python
import requests
from agent.tools import BaseTool, ToolManifest, ToolResult

class WeatherTool(BaseTool):

    def __init__(self, config: dict):
        self.config = config

    def manifest(self) -> ToolManifest:
        return ToolManifest(
            name="weather",
            description="Query current weather for a city",
            parameters={"city": "City name, e.g. Tokyo, London"},
            examples=["What's the weather in Tokyo?", "Is it raining in London?"],
        )

    def execute(self, params: dict) -> ToolResult:
        city = params.get("city", "").strip()
        if not city:
            return ToolResult(success=False, data="", error="Missing city")

        try:
            r = requests.get(f"https://wttr.in/{city}?format=j1", timeout=10)
            data = r.json()["current_condition"][0]
            summary = f"{city}: {data['temp_C']}°C, {data['weatherDesc'][0]['value']}"
            return ToolResult(success=True, data=summary)
        except Exception as e:
            return ToolResult(success=False, data="", error=str(e))
```

Save as `agent/tools/weather.py` — it will be available on next startup.

## How It Works

1. On startup, `ToolRegistry` scans every `.py` in `agent/tools/` (skips files starting with `_`).
2. For each `BaseTool` subclass found, it calls `is_available()`.
3. Available tools are registered by their `manifest().name`.
4. When the user sends a message, the LLM sees all tool manifests and decides which (if any) to call.
5. The tool's `execute()` result is injected into the LLM's context for generating the final response.
