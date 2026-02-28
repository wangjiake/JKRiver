# Riverse — 河流アルゴリズム（River Algorithm）

**個人デバイスのために設計された AI エージェント — 永続的な記憶、オフライン認知、使うほどあなたを理解する。**

**[English](README.md)** | **[中文](README_zh.md)** | **[日本語](README_ja.md)**

![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white)
![License: AGPL-3.0 + Commercial](https://img.shields.io/badge/License-AGPL--3.0%20%2B%20Commercial-green)

[![X (Twitter)](https://img.shields.io/badge/X-@JKRiverse-000000?logo=x&logoColor=white)](https://x.com/JKRiverse)
[![Discord](https://img.shields.io/badge/Discord-Join-5865F2?logo=discord&logoColor=white)](https://discord.gg/PnAt4Xkt)
[![Docs](https://img.shields.io/badge/ドキュメント-wangjiake.github.io-06b6d4?logo=readthedocs&logoColor=white)](https://wangjiake.github.io/riverse-docs/ja/)

## Docker でクイック体験

Python や PostgreSQL をインストールしたくない方へ。**[Docker で 3 コマンドですぐに体験](https://github.com/wangjiake/Riverse-Docker)** — OpenAI、DeepSeek、Groq、その他の OpenAI 互換 API に対応。

---

## Riverse とは？

長年 AI と会話してきたのに、どの AI もあなたを知りません。プラットフォームを変えればゼロからやり直し。あなたのデータはあちこちのクラウドに散らばり、あなたのものではありません。

Riverse はあなた自身のマシンで動くパーソナル AI エージェントです。Telegram、Discord、その他のインターフェースで会話すると、すべてを記憶し、人間の睡眠のようにオフラインで記憶を整理します — 性格、好み、経験、人間関係を抽出し、継続的に成長するプロフィールを構築します。会話が増えるほど、より深くあなたを理解します。すべてのデータはローカルに保存され、あなたが所有します。

v1.0 の実装済み機能：マルチモーダル入力（テキスト、音声、画像、ファイル）、マルチチャネルアクセス、プラガブルツール（財務追跡、健康同期、Web検索、スマートホーム）、YAML カスタムスキル、外部エージェント連携、MCP プロトコル（Gmail など）、プロアクティブ通知。これは将来、スマートフォンやスマートウォッチなどの個人デバイスで本当のパーソナル AI を実行するための基盤です。

現在のバージョンは beta であり、シングルユーザーでの使用を推奨します。画像、音声、ファイルを扱うため、**Telegram Bot** をメインのチャットインターフェースとして使用し、`settings.yaml` にあなた固有の Telegram User ID を設定してください。

## 河流アルゴリズム（River Algorithm）

Riverse のコア認知モデルは**河流アルゴリズム** — 個人デジタルプロフィール重み付けアルゴリズムです。会話は水の流れ、重要な情報は河床の堆積物のように沈殿し、複数ターンの検証を経て「推測」から「確認」へ、さらに「確立」へと段階的に昇格します。オフライン整理（Sleep）は河の自浄作用です。すべてのデータはローカルに保存され、あなたが所有します。会話が増えるほど AI の理解はより深くなります。

```
会話が流入 ──→ 浸食 ──→ 堆積 ──→ 認知を形成 ──→ 流れ続ける
                │         │         │
                │         │         └─ 確認された認知は深く沈み、安定した岩盤に
                │         └─ 重要な情報が観察・仮説・プロフィールとして堆積
                └─ 矛盾する古い認識は洗い流され、新たな洞察に置き換わる
```

**3つのコアメタファー：**

- **流れ（Flow）** — すべての会話は流れる水。川は止まらず、あなたへの理解は進化し続け、リセットされない
- **堆積（Sediment）** — 会話の重要情報は沈泥のように堆積する：事実はプロフィールに、感情は観察に、パターンは仮説に。繰り返し確認された認知はより深く沈み、より安定する
- **自浄（Purify）** — Sleep プロセスは川の自浄能力：古い情報を洗い流し、矛盾を解消し、断片を統合して一貫した理解へ。整理のたびに河床はより鮮明に、認知はより正確に

既存の AI メモリとの違い：ChatGPT Memory、Claude Memory などは本質的にフラットなリスト — いくつかの事実を保存するだけで、タイムライン、確信度、矛盾検出はありません。データはクラウドに保存され、プラットフォームが所有しています。Riverse は生きた川 — すべての会話が河床を形作り、河床が未来の会話を導き、すべてのデータはあなたのマシンに残ります。

## 特徴

- **永続的な記憶** — セッションを超えて記憶し、あなたと共に進化するタイムラインベースのプロファイルを構築
- **オフライン整理** — 会話終了後に自動処理：洞察の抽出、矛盾の解消、確認済み知識の強化
- **マルチモーダル入力** — テキスト、音声、画像、ファイルをネイティブに理解
- **プラガブルツール** — 財務追跡、健康同期（Withings）、Web検索、画像認識、TTS など
- **YAML スキル** — シンプルな YAML でカスタム動作を作成、キーワードまたはスケジュールでトリガー
- **外部エージェント** — `agents_*.yaml` で Home Assistant、n8n、Dify 等を接続
- **MCP プロトコル** — Model Context Protocol 対応、Gmail 等の MCP Server を接続
- **マルチチャネル** — Telegram、Discord、REST API、WebSocket、CLI、Web ダッシュボード
- **ローカルファースト** — デフォルトは Ollama、必要時に OpenAI / DeepSeek へ自動エスカレーション
- **プロアクティブ** — イベントフォローアップ、アイドルチェックイン、静寂時間帯を尊重
- **セマンティック検索** — BGE-M3 ベクトル埋め込み、意味で関連する記憶を検索
- **多言語プロンプト** — 英語・中国語・日本語のプロンプトを内蔵、設定一つで切り替え

> **精度について：** 現在、個人プロファイル抽出に特化して訓練された LLM は存在しないため、抽出結果に誤りが含まれる場合があります。不正確な内容を見つけた場合は、Web ダッシュボードで誤った記憶を**拒否**するか、古くなった記憶を**クローズ**できます。Riverse は記憶内容の手動編集を意図的にサポートしていません — 誤った記憶は河の中の泥沙のように、水流に洗い流されるべきものであり、人の手で河床を削るべきではありません。会話が蓄積されるにつれ、河流アルゴリズムがマルチターン検証と矛盾検出により継続的に自己修正し、プロファイルはより正確になっていきます。

## Sleep — オフライン記憶統合

Sleep は Riverse が会話を消化し、プロフィールを更新するプロセスです。自動・手動の両方で実行可能：

| トリガー | 方法 |
|---|---|
| **Telegram** | `/new` を送信 — セッションをリセットし、バックグラウンドで Sleep を実行 |
| **CLI** | 終了時に自動実行（`quit` または Ctrl+C） |
| **REST API** | `POST /sleep` |
| **cron（推奨）** | 毎晩の定時ジョブで一日の会話を統合 |

**cron の例** — 毎日 0 時に Sleep を実行：

```bash
# crontab -e
0 0 * * * cd /path/to/JKRiver && /path/to/python -c "from agent.sleep import run; run()"
```

## 技術スタック

| レイヤー | 技術 |
|---|---|
| ランタイム | Python 3.10+, PostgreSQL 16+ |
| ローカル LLM | Ollama（任意の互換モデル） |
| クラウド LLM | OpenAI GPT-4o / DeepSeek（フォールバック）|
| 埋め込み | Ollama + BGE-M3 |
| REST API | FastAPI + Uvicorn |
| Web ダッシュボード | Flask |
| Telegram | python-telegram-bot (async) |
| Discord | discord.py (async) |
| 音声認識 | OpenAI Whisper-1 |
| 画像認識 | GPT-4 Vision / Ollama LLaVA |
| TTS | Edge TTS |

## プロジェクト構成

```
JKRiver/
├── settings.yaml            # メイン設定（DB、LLM、Bot トークン等）
├── agent/
│   ├── main.py              # CLI エントリポイント
│   ├── api.py               # FastAPI REST + WebSocket
│   ├── core.py              # コア会話ループ
│   ├── cognition/           # 認知エンジン
│   ├── sleep.py             # オフライン記憶整理
│   ├── proactive.py         # プロアクティブ通知
│   ├── telegram_bot.py      # Telegram Bot
│   ├── discord_bot.py       # Discord Bot
│   ├── storage/             # データベース層
│   ├── tools/               # ツール（検索、画像、音声、TTS 等）
│   ├── skills/              # スキル（YAML 定義 + 実行エンジン）
│   ├── config/
│   │   ├── agents_*.yaml    #   外部エージェント設定 (zh/en/ja)
│   │   └── prompts/         #   多言語プロンプト (zh/en/ja)
│   └── schema.sql           # データベーススキーマ
├── web.py                   # Flask Web ダッシュボード
├── templates/               # フロントエンドテンプレート
└── requirements.txt         # Python 依存パッケージ
```

---

## インストール

### 1. 前提条件

| 依存 | 説明 |
|---|---|
| Python 3.10+ | ランタイム |
| PostgreSQL 16+ | データ保存 |
| Ollama | ローカル LLM 推論（オプション、クラウドのみも可）|

### 2. クローン & インストール

```bash
git clone https://github.com/wangjiake/JKRiver.git
cd JKRiver
python3 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

pip install -r requirements.txt
```

### 3. PostgreSQL セットアップ

```bash
createdb -h localhost -U your_username Riverse
psql -h localhost -U your_username -d Riverse -f agent/schema.sql
```

> **注意：** Riverse と [River Algorithm — AI会話履歴特別版](https://github.com/wangjiake/RiverHistory) は同じデータベースを共有しています。どちらのプロジェクトからテーブルを作成しても、両方に必要な全テーブルが作成されます。もう一方のプロジェクトで既にテーブル作成済みの場合、このステップはスキップできます。

### 4. 設定

プロジェクトルートの `settings.yaml` を編集。DB、LLM、Bot トークン等すべて一つのファイルで管理。

#### 4.1 データベース

```yaml
database:
    name: "Riverse"
    user: "your_username"     # ← PostgreSQL ユーザー名に変更
    host: "localhost"
```

> macOS の Homebrew PostgreSQL ではユーザー名はシステムユーザー名（`whoami` で確認）。Linux/Windows では通常 `postgres`。

#### 4.2 言語

```yaml
language: "ja"                  # en / zh / ja
```

#### 4.3 LLM

**方式 A：ローカル Ollama（推奨）**

```bash
ollama pull <your-model>         # 例：qwen2.5:14b, llama3, mistral
ollama pull bge-m3              # 埋め込みモデル（オプション）
```

```yaml
llm_provider: "local"

local:
  model: "your-model"            # 例：qwen2.5:14b, llama3, mistral
  api_base: "http://localhost:11434"
```

**方式 B：クラウドのみ（Ollama 不要）**

```yaml
llm_provider: "openai"

openai:
  model: "gpt-4o-mini"
  api_base: "https://api.openai.com"
  api_key: "sk-your-openai-api-key"
```

#### 4.4 クラウド LLM（フォールバック + Web検索）

ローカルモデルの品質が不十分な場合に自動でクラウドへエスカレーション。ローカル使用時でも設定推奨：

```yaml
cloud_llm:
  enabled: true
  providers:
    - name: "openai"
      model: "gpt-4o"
      api_base: "https://api.openai.com"
      api_key: "sk-your-openai-api-key"
      search: true              # Web検索を有効化
      priority: 1
    - name: "deepseek"
      model: "deepseek-chat"
      api_base: "https://api.deepseek.com"
      api_key: "sk-your-deepseek-key"
      priority: 2
```

#### 4.5 Telegram Bot

1. Telegram で [@BotFather](https://t.me/BotFather) に `/newbot` を送信して Bot を作成、トークンを取得
2. user ID を取得（どちらか）：
   - [@userinfobot](https://t.me/userinfobot) に任意のメッセージを送ると、ID が返ってきます
   - または Bot にメッセージを送り、`https://api.telegram.org/bot<TOKEN>/getUpdates` にアクセス
3. `settings.yaml` を編集：

```yaml
telegram:
  bot_token: "123456:ABC-DEF..."
  temp_dir: "tmp/telegram"
  allowed_user_ids: [your_user_id]  # 自分だけに制限
```

#### 4.6 Discord Bot（オプション）

1. [Discord Developer Portal](https://discord.com/developers/applications) でアプリを作成
2. Bot ページでトークンを取得、Message Content Intent を有効化
3. OAuth2 URL で Bot をサーバーに招待

```yaml
discord:
  bot_token: "your-discord-bot-token"
  allowed_user_ids: []           # 空 = 全員許可、ID指定で制限
```

#### 4.7 埋め込み / セマンティック検索（オプション、デフォルト無効）

キーワードではなく意味で記憶を検索できます。Ollama + bge-m3 が必要：

```bash
ollama pull bge-m3
```

`settings.yaml` で有効化：

```yaml
embedding:
  enabled: true
  model: "bge-m3"
  api_base: "http://localhost:11434"
```

#### 4.8 その他のオプション設定

```yaml
# ツール
tools:
  enabled: true
  shell_exec:
    enabled: false               # セキュリティのためデフォルト無効

# TTS（テキスト読み上げ）
tts:
  enabled: false

# MCP プロトコル
mcp:
  enabled: false
  servers: []

# プロアクティブ配信
proactive:
  enabled: true
  quiet_hours:
    start: "23:00"
    end: "08:00"
```

### 5. 起動

```bash
python -m agent.main                                    # CLI
uvicorn agent.api:app --host 0.0.0.0 --port 8400       # REST API
python web.py                                            # Web ダッシュボード
python -m agent.telegram_bot                             # Telegram Bot
python -m agent.discord_bot                              # Discord Bot
```

---

## スキル

`agent/skills/` にYAMLファイルを作成してスキルを定義。

**キーワードトリガー：**

```yaml
name: explain_code
description: コードを送った時に自動で説明
trigger:
  type: keyword
  keywords: ["コード説明", "explain code"]
instruction: |
  コードをステップバイステップで説明してください。
enabled: true
```

**スケジュール：**

```yaml
name: weekly_summary
description: 毎週日曜日に週末の挨拶を送信
trigger:
  type: schedule
  cron: "0 20 * * 0"
steps:
  - respond: |
      短く温かい週末の挨拶を書いてください。
enabled: true
```

Bot に「スキルを作って...」と言うだけでも自動生成されます。

---

## 外部エージェント

`agent/config/agents_ja.yaml` を編集して外部サービスを接続。組み込みテンプレート：

| エージェント | タイプ | 説明 | デフォルト |
|---|---|---|---|
| weather_query | HTTP | wttr.in 天気取得 | 有効 |
| home_lights | HTTP | Home Assistant 照明制御 | 無効 |
| home_status | HTTP | Home Assistant デバイス状態 | 無効 |
| n8n_email | HTTP | n8n メール送信 | 無効 |
| n8n_workflow | HTTP | n8n ワークフロー | 無効 |
| dify_agent | HTTP | Dify サブエージェント | 無効 |
| backup_notes | Command | ローカルバックアップ | 無効 |
| system_info | Command | システム情報取得 | 無効 |

`enabled: true` に変更し、URL/トークンを入力。LLM が自動的にいつ呼び出すかを判断します。

---

## API エンドポイント

| エンドポイント | メソッド | 説明 |
|---|---|---|
| `/chat` | POST | メッセージ送信、返信取得 |
| `/session/new` | POST | 新規セッション作成 |
| `/sleep` | POST | 記憶整理をトリガー |
| `/profile` | GET | 現在のプロファイル取得 |
| `/hypotheses` | GET | 全仮説取得 |
| `/sessions` | GET | アクティブセッション一覧 |
| `/ws/chat` | WebSocket | リアルタイムチャット |

---

## よくある質問

### PostgreSQL 接続失敗

```bash
pg_isready -h localhost
```

ユーザー名が `postgres` でない場合、`settings.yaml` の `database.user` を更新してください。

### Ollama モデルが見つからない

```bash
ollama list
ollama pull <your-model>        # 例：qwen2.5:14b, llama3, mistral
ollama pull bge-m3
```

### Telegram Bot が応答しない

1. `bot_token` が正しいか確認
2. `allowed_user_ids` に自分の Telegram user ID が含まれているか確認
3. ターミナルのログ出力を確認

### Ollama なしでクラウドのみ

`llm_provider: "openai"` に設定、API キーを入力、`embedding.enabled: false` に設定。

---

## ライセンス

本プロジェクトは**デュアルライセンス**です：

| 用途 | ライセンス | 詳細 |
|---|---|---|
| 個人利用 / オープンソース | [AGPL-3.0](LICENSE) | 無料利用可、変更はオープンソース必須 |
| 商用 / クローズドソース | 商用ライセンス | mailwangjk@gmail.com まで連絡 |

個人利用、研究、オープンソース貢献は自由です。クローズドソースでの商用利用や SaaS には商用ライセンスが必要です。

## お問い合わせ

- **X (Twitter):** [@JKRiverse](https://x.com/JKRiverse)
- **Discord:** [参加](https://discord.gg/PnAt4Xkt)
- **Email:** mailwangjk@gmail.com
