<p align="center">
  <img src="https://raw.githubusercontent.com/wangjiake/JKRiver/main/img/binary-wave-logo.svg" width="128" height="128" alt="Riverse Logo">
</p>

# Riverse — Docker

**[English](#english)** | **[中文](#中文)** | **[日本語](#日本語)**

![License: AGPL-3.0 + Commercial](https://img.shields.io/badge/License-AGPL--3.0%20%2B%20Commercial-green)
[![X (Twitter)](https://img.shields.io/badge/X-@JKRiverse-000000?logo=x&logoColor=white)](https://x.com/JKRiverse)
[![Discord](https://img.shields.io/badge/Discord-Join-5865F2?logo=discord&logoColor=white)](https://discord.gg/ZnmFrPvXym)
[![Docs](https://img.shields.io/badge/Docs-wangjiake.github.io-06b6d4?logo=readthedocs&logoColor=white)](https://wangjiake.github.io/riverse-docs/)

---

## English

### What is this?

Run the complete Riverse AI system using Docker — no Python, PostgreSQL, or config files needed. Three commands and you're in.

**Three services start automatically:**

| Service | URL | What it does |
|---------|-----|--------------|
| **JKRiver** | http://localhost:1234 | Web chat + system config |
| **RiverHistory** | http://localhost:2345 | Profile viewer |
| **API Docs** | http://localhost:8400/docs | REST API reference |

### Quick Start

```bash
# 1. Get the compose file
mkdir jkriver && cd jkriver
curl -O https://raw.githubusercontent.com/wangjiake/JKRiver/main/docker/docker-compose.yaml

# 2. Start everything
docker compose pull && docker compose up -d

# 3. Get your access token (generated automatically on first start)
docker logs jkriver-jkriver-1 2>&1 | grep "Token:"
```

Open `http://localhost:1234`, enter the token, then go to **System** to configure your API key. Done.

> Token is saved in `./config/settings.yaml`. As long as `config/` exists, you won't need to look it up again.

### System Page Configuration

All settings are configured through the **System** page at http://localhost:1234 — no config file editing required.

| Section | What you can configure |
|---------|----------------------|
| **LLM** | AI provider (OpenAI / DeepSeek / Groq / Ollama), model, API key, API base URL |
| **Language & Timezone** | LLM prompt language (zh / en / ja), your local timezone |
| **Telegram** | Bot token, allowed user IDs |
| **Discord** | Bot token |
| **Memory (Sleep)** | Consolidation mode (daily cron / after each chat / manual), cron hour |
| **Tools** | Enable or disable individual tools (web search, finance, health, etc.) |
| **Cloud LLM** | Additional providers for web search and fallback |

Settings are saved immediately to `./config/settings.yaml` and take effect after restart.

### How to Chat

| Method | Setup | Best for |
|--------|-------|----------|
| **Web Chat** | Built-in — open http://localhost:1234 | Quick browser access |
| **Telegram Bot** | Set token in System page, get from [@BotFather](https://t.me/BotFather) | Daily mobile use |
| **Discord Bot** | Set token in System page, get from [Developer Portal](https://discord.com/developers/applications) | Community / group use |
| **Command Line** | No extra setup | Quick test |

**Command Line:**
```bash
docker compose exec jkriver bash -c "cd /app && python -m agent.main"
```

### Supported AI Models

Configure in the **System** page, or set environment variables before first start:

| Provider | `OPENAI_API_BASE` | `OPENAI_MODEL` | Notes |
|----------|-------------------|----------------|-------|
| **OpenAI** | `https://api.openai.com` | `gpt-4o-mini` | Default |
| **DeepSeek** | `https://api.deepseek.com` | `deepseek-chat` | Cheapest |
| **Groq** | `https://api.groq.com` | `llama-3.3-70b-versatile` | Free tier |
| **Ollama** (local) | — | — | Set `LLM_PROVIDER=local` |

### Try the Demo

Demo conversations load automatically. Process them:

```bash
docker compose exec riverhistory bash -c "cd /app_work && python run.py demo max"
```

Open http://localhost:2345 to see the extracted profile.

### Import Your Own Data

Place exported files in a `data/` folder:

```
jkriver/
├── docker-compose.yaml
├── config/                    ← auto-created (your settings)
└── data/
    ├── ChatGPT/               ← conversations.json
    ├── Claude/                ← conversations.json
    └── Gemini/                ← Takeout files
```

| Platform | How to export |
|----------|---------------|
| **ChatGPT** | Settings → Data controls → Export data → unzip → `conversations.json` |
| **Claude** | Settings → Account → Export Data → unzip → `conversations.json` |
| **Gemini** | [Google Takeout](https://takeout.google.com/) → select Gemini Apps → unzip |

```bash
docker compose exec riverhistory bash -c "cd /app_work && python import_data.py --chatgpt data/ChatGPT/conversations.json"
docker compose exec riverhistory bash -c "cd /app_work && python import_data.py --claude data/Claude/conversations.json"
docker compose exec riverhistory bash -c "cd /app_work && python import_data.py --gemini 'data/Gemini/My Activity.html'"
docker compose exec riverhistory bash -c "cd /app_work && python run.py all max"
```

### Common Commands

```bash
docker compose up -d               # Start (background)
docker compose down                # Stop (data preserved)
docker compose down -v             # Stop and DELETE all data
docker compose pull && docker compose up -d   # Update to latest

docker compose exec jkriver bash -c "cd /app && python -m agent.main"   # CLI chat
curl -X POST http://localhost:8400/sleep                                 # Trigger Sleep manually

docker compose logs -f jkriver     # View logs
```

### Security Notice

- **Port 8400 (API) and 2345 (RiverHistory) have no authentication.** On a remote server, bind them to `127.0.0.1` or use a reverse proxy.
- **Port 5432 (PostgreSQL) uses trust auth.** Do not expose it to the internet.
- **Set `TELEGRAM_ALLOWED_USERS`** if using a Telegram bot, or anyone who finds it can use it.

---

## 中文

### 这是什么？

通过 Docker 一键运行完整的 Riverse AI 系统 — 不需要 Python、PostgreSQL 或编辑配置文件。三条命令即可启动。

**自动启动三个服务：**

| 服务 | 地址 | 功能说明 |
|------|------|----------|
| **JKRiver** | http://localhost:1234 | 网页聊天 + 系统配置 |
| **RiverHistory** | http://localhost:2345 | 用户画像查看器 |
| **API 文档** | http://localhost:8400/docs | 开发者 REST API 参考 |

### 快速开始

```bash
# 1. 获取 compose 文件
mkdir jkriver && cd jkriver
curl -O https://raw.githubusercontent.com/wangjiake/JKRiver/main/docker/docker-compose.yaml

# 2. 启动所有服务
docker compose pull && docker compose up -d

# 3. 获取访问 Token（首次启动时自动生成）
docker logs jkriver-jkriver-1 2>&1 | grep "Token:"
```

在浏览器打开 `http://localhost:1234`，输入 Token 后进入 **System** 页面配置 API Key 即可。

> Token 保存在 `./config/settings.yaml`，只要 `config/` 目录存在就无需再次查找。

### System 页面配置

登录后在 **System** 页面（http://localhost:1234）完成所有配置，无需手动编辑文件。

| 配置区域 | 可配置内容 |
|---------|-----------|
| **LLM** | AI 提供商（OpenAI / DeepSeek / Groq / Ollama）、模型名、API Key、API 地址 |
| **语言与时区** | LLM 提示词语言（zh / en / ja）、本地时区 |
| **Telegram** | 机器人 Token、允许使用的用户 ID |
| **Discord** | 机器人 Token |
| **记忆整理（Sleep）** | 整理模式（每日定时 / 每次聊天后 / 手动）、定时小时 |
| **工具** | 各工具的开关（网络搜索、财务、健康等） |
| **云端 LLM** | 用于网络搜索和兜底的额外提供商 |

配置立即保存到 `./config/settings.yaml`，重启后生效。

### 如何聊天

| 方式 | 配置 | 适合场景 |
|------|------|----------|
| **网页聊天** | 内置，直接打开 http://localhost:1234 | 浏览器随时访问 |
| **Telegram 机器人** | 在 System 页面设置 token，从 [@BotFather](https://t.me/BotFather) 获取 | 日常手机使用 |
| **Discord 机器人** | 在 System 页面设置 token，从 [Developer Portal](https://discord.com/developers/applications) 获取 | 社区/群组使用 |
| **命令行** | 无需额外配置 | 快速测试 |

**命令行：**
```bash
docker compose exec jkriver bash -c "cd /app && python -m agent.main"
```

### 支持的 AI 模型

在 **System** 页面配置，或在首次启动前通过环境变量设置：

| 提供商 | `OPENAI_API_BASE` | `OPENAI_MODEL` | 说明 |
|--------|-------------------|----------------|------|
| **OpenAI** | `https://api.openai.com` | `gpt-4o-mini` | 默认 |
| **DeepSeek** | `https://api.deepseek.com` | `deepseek-chat` | 最便宜 |
| **Groq** | `https://api.groq.com` | `llama-3.3-70b-versatile` | 有免费额度 |
| **Ollama**（本地） | — | — | 设置 `LLM_PROVIDER=local` |

### 体验 Demo

Demo 对话启动时自动导入，运行处理：

```bash
docker compose exec riverhistory bash -c "cd /app_work && python run.py demo max"
```

打开 http://localhost:2345 查看提取的画像。

### 导入自己的数据

在 `data/` 文件夹放入导出文件：

```
jkriver/
├── docker-compose.yaml
├── config/                    ← 自动创建（存储配置）
└── data/
    ├── ChatGPT/               ← conversations.json
    ├── Claude/                ← conversations.json
    └── Gemini/                ← Takeout 文件
```

| 平台 | 导出方式 |
|------|----------|
| **ChatGPT** | Settings → Data controls → Export data → 解压 → `conversations.json` |
| **Claude** | Settings → Account → Export Data → 解压 → `conversations.json` |
| **Gemini** | [Google Takeout](https://takeout.google.com/) → 选择 Gemini Apps → 解压 |

```bash
docker compose exec riverhistory bash -c "cd /app_work && python import_data.py --chatgpt data/ChatGPT/conversations.json"
docker compose exec riverhistory bash -c "cd /app_work && python import_data.py --claude data/Claude/conversations.json"
docker compose exec riverhistory bash -c "cd /app_work && python import_data.py --gemini 'data/Gemini/我的活动记录.html'"
docker compose exec riverhistory bash -c "cd /app_work && python run.py all max"
```

### 常用命令

```bash
docker compose up -d               # 启动（后台）
docker compose down                # 停止（数据保留）
docker compose down -v             # 停止并删除所有数据
docker compose pull && docker compose up -d   # 更新到最新版本

docker compose exec jkriver bash -c "cd /app && python -m agent.main"   # 命令行聊天
curl -X POST http://localhost:8400/sleep                                 # 手动触发记忆整理

docker compose logs -f jkriver     # 查看日志
```

### 安全须知

- **端口 8400（API）和 2345（RiverHistory）没有认证。** 在远程服务器上，绑定到 `127.0.0.1` 或使用反向代理。
- **端口 5432（PostgreSQL）使用 trust 认证，没有密码。** 不要暴露到公网。
- **使用 Telegram 机器人时设置 `TELEGRAM_ALLOWED_USERS`**，否则任何人都能使用。

---

## 日本語

### これは何ですか？

Docker を使って Riverse AI システム全体を実行できます。Python、PostgreSQL、設定ファイルの編集も不要。3 つのコマンドで起動します。

**3 つのサービスが自動的に起動します：**

| サービス | URL | 機能 |
|----------|-----|------|
| **JKRiver** | http://localhost:1234 | Web チャット + システム設定 |
| **RiverHistory** | http://localhost:2345 | プロフィールビューアー |
| **API ドキュメント** | http://localhost:8400/docs | 開発者向け REST API |

### クイックスタート

```bash
# 1. compose ファイルを取得
mkdir jkriver && cd jkriver
curl -O https://raw.githubusercontent.com/wangjiake/JKRiver/main/docker/docker-compose.yaml

# 2. 全サービスを起動
docker compose pull && docker compose up -d

# 3. アクセストークンを確認（初回起動時に自動生成）
docker logs jkriver-jkriver-1 2>&1 | grep "Token:"
```

ブラウザで `http://localhost:1234` を開き、トークンを入力後 **System** ページで API キーを設定するだけです。

> トークンは `./config/settings.yaml` に保存されます。`config/` が存在する限り再確認は不要です。

### System ページの設定

ログイン後、**System** ページ（http://localhost:1234）ですべての設定が行えます。設定ファイルの手動編集は不要です。

| 設定セクション | 設定できる内容 |
|--------------|--------------|
| **LLM** | AI プロバイダー（OpenAI / DeepSeek / Groq / Ollama）、モデル名、API キー、エンドポイント |
| **言語・タイムゾーン** | LLM プロンプト言語（zh / en / ja）、ローカルタイムゾーン |
| **Telegram** | ボットトークン、許可ユーザー ID |
| **Discord** | ボットトークン |
| **記憶整理（Sleep）** | 整理モード（毎日定時 / チャット毎 / 手動）、定時時刻 |
| **ツール** | 各ツールのオン/オフ（Web 検索、財務、健康など） |
| **クラウド LLM** | Web 検索・フォールバック用の追加プロバイダー |

設定は即座に `./config/settings.yaml` に保存され、再起動後に反映されます。

### チャット方法

| 方法 | 設定 | 最適な用途 |
|------|------|-----------|
| **Web チャット** | 内蔵 — http://localhost:1234 を開くだけ | ブラウザからすぐアクセス |
| **Telegram Bot** | System ページでトークンを設定 [@BotFather](https://t.me/BotFather) | 日常のモバイル利用 |
| **Discord Bot** | System ページでトークンを設定 [Developer Portal](https://discord.com/developers/applications) | コミュニティ利用 |
| **コマンドライン** | 追加設定不要 | クイックテスト |

**コマンドライン：**
```bash
docker compose exec jkriver bash -c "cd /app && python -m agent.main"
```

### 対応 AI モデル

**System** ページで設定するか、初回起動前に環境変数で指定：

| プロバイダー | `OPENAI_API_BASE` | `OPENAI_MODEL` | 備考 |
|-------------|-------------------|----------------|------|
| **OpenAI** | `https://api.openai.com` | `gpt-4o-mini` | デフォルト |
| **DeepSeek** | `https://api.deepseek.com` | `deepseek-chat` | 最安値 |
| **Groq** | `https://api.groq.com` | `llama-3.3-70b-versatile` | 無料枠あり |
| **Ollama**（ローカル） | — | — | `LLM_PROVIDER=local` に設定 |

### デモを体験

デモ会話は起動時に自動インポートされます：

```bash
docker compose exec riverhistory bash -c "cd /app_work && python run.py demo max"
```

http://localhost:2345 を開いてプロフィールを確認。

### 自分のデータをインポート

`data/` フォルダにエクスポートファイルを配置：

```
jkriver/
├── docker-compose.yaml
├── config/                    ← 自動作成（設定を保存）
└── data/
    ├── ChatGPT/               ← conversations.json
    ├── Claude/                ← conversations.json
    └── Gemini/                ← Takeout ファイル
```

| プラットフォーム | エクスポート方法 |
|-----------------|-----------------|
| **ChatGPT** | Settings → Data controls → Export data → 解凍 → `conversations.json` |
| **Claude** | Settings → Account → Export Data → 解凍 → `conversations.json` |
| **Gemini** | [Google Takeout](https://takeout.google.com/) → Gemini Apps → 解凍 |

```bash
docker compose exec riverhistory bash -c "cd /app_work && python import_data.py --chatgpt data/ChatGPT/conversations.json"
docker compose exec riverhistory bash -c "cd /app_work && python import_data.py --claude data/Claude/conversations.json"
docker compose exec riverhistory bash -c "cd /app_work && python import_data.py --gemini 'data/Gemini/マイ アクティビティ.html'"
docker compose exec riverhistory bash -c "cd /app_work && python run.py all max"
```

### よく使うコマンド

```bash
docker compose up -d               # 起動（バックグラウンド）
docker compose down                # 停止（データ保持）
docker compose down -v             # 停止してすべてのデータを削除
docker compose pull && docker compose up -d   # 最新バージョンに更新

docker compose exec jkriver bash -c "cd /app && python -m agent.main"   # CLI チャット
curl -X POST http://localhost:8400/sleep                                 # Sleep を手動トリガー

docker compose logs -f jkriver     # ログ確認
```

### セキュリティに関する注意

- **ポート 8400（API）と 2345（RiverHistory）には認証がありません。** リモートサーバーでは `127.0.0.1` にバインドするかリバースプロキシを使用してください。
- **ポート 5432（PostgreSQL）はパスワードなし（trust 認証）。** インターネットに公開しないでください。
- **Telegram Bot を使う場合は `TELEGRAM_ALLOWED_USERS` を設定**してください。未設定だと誰でも使えます。
