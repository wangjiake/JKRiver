# カスタムツール開発

Riverse はドロップイン方式のツールシステムを採用しています。`agent/tools/` ディレクトリに `.py` ファイルを作成するだけで新しいツールを追加できます。登録コードは不要です。

## インターフェース

各ツールは `BaseTool` を継承し、2つのメソッドを実装します：

```python
from agent.tools import BaseTool, ToolManifest, ToolResult

class MyTool(BaseTool):

    def __init__(self, config: dict):
        self.config = config

    def manifest(self) -> ToolManifest:
        return ToolManifest(
            name="my_tool",                          # 一意の識別子
            description="LLM がこのツールを使うべきか判断するための一行説明",
            parameters={
                "param_name": "パラメータの意味",
            },
            examples=[
                "自然言語トリガー例 1",
                "自然言語トリガー例 2",
            ],
        )

    def execute(self, params: dict) -> ToolResult:
        value = params.get("param_name", "")

        # ここに処理を実装...
        result = f"処理結果: {value}"

        return ToolResult(success=True, data=result)
```

### ToolManifest

| フィールド | 用途 |
|-----------|------|
| `name` | 一意の識別子。LLM はこの名前でツールを呼び出します。 |
| `description` | 一行の説明。LLM はこれを読んで**いつ**使うか判断します。 |
| `parameters` | `{パラメータ名: 説明}` の辞書。LLM が自動的に値を埋めます。 |
| `examples` | このツールをトリガーする自然言語フレーズを 2-3 個。 |

### ToolResult

| フィールド | 用途 |
|-----------|------|
| `success` | `True` / `False` |
| `data` | 参考情報として LLM のコンテキストに注入される文字列。 |
| `error` | エラーメッセージ（`success=False` の場合のみ）。 |

### オプション：`is_available()`

依存関係が不足している場合にツールを無効化するにはこのメソッドをオーバーライドします：

```python
def is_available(self) -> bool:
    return self.config.get("tools", {}).get("my_tool", {}).get("enabled", True)
```

## 例：天気ツール

```python
import requests
from agent.tools import BaseTool, ToolManifest, ToolResult

class WeatherTool(BaseTool):

    def __init__(self, config: dict):
        self.config = config

    def manifest(self) -> ToolManifest:
        return ToolManifest(
            name="weather",
            description="指定した都市の現在の天気を取得する",
            parameters={"city": "都市名（例：東京、ロンドン）"},
            examples=["東京の天気は？", "ロンドンは雨ですか？"],
        )

    def execute(self, params: dict) -> ToolResult:
        city = params.get("city", "").strip()
        if not city:
            return ToolResult(success=False, data="", error="都市名がありません")

        try:
            r = requests.get(f"https://wttr.in/{city}?format=j1", timeout=10)
            data = r.json()["current_condition"][0]
            summary = f"{city}: {data['temp_C']}°C, {data['weatherDesc'][0]['value']}"
            return ToolResult(success=True, data=summary)
        except Exception as e:
            return ToolResult(success=False, data="", error=str(e))
```

`agent/tools/weather.py` として保存すれば、次回起動時から利用可能になります。

## 仕組み

1. 起動時に `ToolRegistry` が `agent/tools/` 内のすべての `.py` ファイルをスキャンします（`_` で始まるファイルはスキップ）。
2. 各 `BaseTool` サブクラスに対して `is_available()` を呼び出します。
3. 利用可能なツールは `manifest().name` で登録されます。
4. ユーザーがメッセージを送信すると、LLM はすべてのツールの manifest を確認し、どれを呼び出すか決定します。
5. ツールの `execute()` 結果が LLM のコンテキストに注入され、最終回答の生成に使われます。
