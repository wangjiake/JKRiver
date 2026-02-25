# 自定义工具开发

Riverse 采用即插即用的工具系统。只需在 `agent/tools/` 目录下创建一个 `.py` 文件即可添加新工具，无需额外注册。

## 接口

每个工具继承 `BaseTool`，实现两个方法：

```python
from agent.tools import BaseTool, ToolManifest, ToolResult

class MyTool(BaseTool):

    def __init__(self, config: dict):
        self.config = config

    def manifest(self) -> ToolManifest:
        return ToolManifest(
            name="my_tool",                          # 唯一标识
            description="供 LLM 判断何时使用该工具的一句话描述",
            parameters={
                "param_name": "参数含义说明",
            },
            examples=[
                "自然语言触发示例 1",
                "自然语言触发示例 2",
            ],
        )

    def execute(self, params: dict) -> ToolResult:
        value = params.get("param_name", "")

        # 在这里实现你的逻辑...
        result = f"处理结果: {value}"

        return ToolResult(success=True, data=result)
```

### ToolManifest

| 字段 | 用途 |
|------|------|
| `name` | 唯一标识符，LLM 通过此名称调用工具。 |
| `description` | 一句话描述，LLM 据此判断**何时**使用该工具。 |
| `parameters` | `{参数名: 说明}` 字典，LLM 会自动填入参数值。 |
| `examples` | 2-3 个会触发该工具的自然语言示例。 |

### ToolResult

| 字段 | 用途 |
|------|------|
| `success` | `True` / `False` |
| `data` | 字符串，作为参考信息注入 LLM 上下文。 |
| `error` | 错误信息（仅在 `success=False` 时使用）。 |

### 可选：`is_available()`

重写此方法可在依赖缺失时禁用工具：

```python
def is_available(self) -> bool:
    return self.config.get("tools", {}).get("my_tool", {}).get("enabled", True)
```

## 示例：天气查询工具

```python
import requests
from agent.tools import BaseTool, ToolManifest, ToolResult

class WeatherTool(BaseTool):

    def __init__(self, config: dict):
        self.config = config

    def manifest(self) -> ToolManifest:
        return ToolManifest(
            name="weather",
            description="查询指定城市的当前天气",
            parameters={"city": "城市名，例如 东京、伦敦"},
            examples=["东京今天天气怎么样？", "伦敦在下雨吗？"],
        )

    def execute(self, params: dict) -> ToolResult:
        city = params.get("city", "").strip()
        if not city:
            return ToolResult(success=False, data="", error="缺少城市名")

        try:
            r = requests.get(f"https://wttr.in/{city}?format=j1", timeout=10)
            data = r.json()["current_condition"][0]
            summary = f"{city}: {data['temp_C']}°C, {data['weatherDesc'][0]['value']}"
            return ToolResult(success=True, data=summary)
        except Exception as e:
            return ToolResult(success=False, data="", error=str(e))
```

保存为 `agent/tools/weather.py`，下次启动即可使用。

## 工作原理

1. 启动时，`ToolRegistry` 扫描 `agent/tools/` 下所有 `.py` 文件（跳过 `_` 开头的文件）。
2. 对每个 `BaseTool` 子类调用 `is_available()`。
3. 可用的工具按 `manifest().name` 注册。
4. 用户发送消息时，LLM 会看到所有工具的 manifest，决定调用哪个。
5. 工具的 `execute()` 结果会注入 LLM 上下文，用于生成最终回复。
