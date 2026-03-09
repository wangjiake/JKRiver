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

This lets you run the complete Riverse AI system using Docker — no need to install Python, PostgreSQL, or any dependencies. Just configure your AI model API key and run one command.

**Two services start automatically:**

| Service | URL | What it does |
|---------|-----|--------------|
| **RiverHistory** | http://localhost:2345 | Web profile viewer — see the extracted personality, preferences, experiences, and life timeline |
| **JKRiver** | http://localhost:8400/docs | AI core engine — REST API, chat bots, memory consolidation scheduler |

### How to Chat

JKRiver provides **three ways** to chat with the AI. All conversations are analyzed by the River Algorithm and contribute to your personal profile:

| Method | Setup | Best for |
|--------|-------|----------|
| **Telegram Bot** | Set `TELEGRAM_BOT_TOKEN` in `.env`, get token from [@BotFather](https://t.me/BotFather) | Daily mobile use, most convenient |
| **Discord Bot** | Set `DISCORD_BOT_TOKEN` in `.env`, get token from [Developer Portal](https://discord.com/developers/applications) | Community / group use |
| **Command Line** | No extra setup needed | Quick test, no bot token required |

**Telegram Bot** — Create a bot via @BotFather, copy the token to `.env`. To restrict access, set `TELEGRAM_ALLOWED_USERS` to your user ID (send any message to [@userinfobot](https://t.me/userinfobot) to get it). **Do not add brackets** — just the number, e.g. `TELEGRAM_ALLOWED_USERS=123456789`. After `docker compose up`, message your bot directly.

**Discord Bot** — Create an application in Discord Developer Portal, add a bot, copy the token to `.env`. Invite the bot to your server. After `docker compose up`, mention the bot or DM it.

**Command Line** — Open a terminal and run:
```bash
docker compose exec jkriver bash -c "cd /app_work && python -m agent.main"
```
Type your message at the `>` prompt, type `quit` to exit. Memory consolidation runs automatically on exit.

> REST API is also available at `http://localhost:8400/docs` for developers who want to integrate programmatically.

### Requirements

- [Docker Desktop](https://docs.docker.com/get-docker/) (includes Docker Compose)

### Quick Start

```bash
# 1. Get the files
git clone https://github.com/wangjiake/JKRiver.git
cd JKRiver/docker

# 2. Create your config file
cp .env.example .env

# 3. Edit .env — add your API key (see "Supported AI Models" below)
#    At minimum, set: OPENAI_API_KEY=sk-your-key-here
#    Set LANGUAGE=zh/en/ja — controls the language of LLM prompts (not the web UI)
#    For chat: set TELEGRAM_BOT_TOKEN or DISCORD_BOT_TOKEN (or use command line)

# 4. Start everything
docker compose up
```

Open http://localhost:2345 to view profiles. Chat via Telegram / Discord / command line.

### Supported AI Models

Works with any OpenAI-compatible API. Edit `.env` to switch providers:

| Provider | `OPENAI_API_BASE` | `OPENAI_MODEL` | Notes |
|----------|-------------------|----------------|-------|
| **OpenAI** | `https://api.openai.com` | `gpt-4o-mini` | Default, good quality |
| **DeepSeek** | `https://api.deepseek.com` | `deepseek-chat` | Cheapest, fast for Chinese |
| **Groq** | `https://api.groq.com` | `llama-3.3-70b-versatile` | Free tier available |
| **Ollama** (local) | — | — | Set `LLM_PROVIDER=local`, no API key needed |

For Ollama, install it on your computer first (`https://ollama.ai`), then run `ollama pull qwen2.5:14b`.

### Try the Demo

Demo conversations are loaded automatically. To process them with the River Algorithm and see the extracted profile:

```bash
docker compose exec riverhistory bash -c "cd /app_work && python run.py demo max"
```

This takes a few minutes (calls your AI model). Then open http://localhost:2345 to see the result — a complete personality profile extracted from 20 conversations.

After processing, the AI **takes on the demo character's identity**. When you chat (via command line, Telegram, or Discord), the AI already knows the character — their career changes, relationships, personality, and life timeline. You can ask "What's my job?" or "Tell me about my ex" and get answers based on the extracted profile.

Through follow-up conversations in command line or Telegram/Discord, you can experience the real-time perception and memory features — the AI will continuously update the profile as you chat. If you want to test more memory capabilities, you can edit the demo JSON to add more life events and extend the timeline.

### Import Your Own Data

You can import your real conversation history from ChatGPT, Claude, or Gemini.

> **Recommended:** Try the demo first to experience the speed and quality. Processing large amounts of real data can take hours depending on how many conversations you have. After trying the demo, run `docker compose down -v` to clear the database, then start importing your own data.
>
> **Cost warning (remote LLM API):** Each conversation consumes tokens. Conversations with lots of code or very long messages use significantly more tokens. Smarter models (e.g. GPT-4o) produce better profiles but cost more; cheaper models (e.g. GPT-4o-mini, DeepSeek) are faster and cheaper but may miss nuances. You can also use local Ollama models to process for free, just slower. Review your export data before processing — remove conversations you don't need (e.g. pure coding sessions). **Monitor your API billing.**

**Step 1: Export your data**

| Platform | How to export |
|----------|---------------|
| **ChatGPT** | Settings → Data controls → Export data → unzip to get `conversations.json` |
| **Claude** | Settings → Account → Export Data → unzip to get `conversations.json` |
| **Gemini** | [Google Takeout](https://takeout.google.com/) → select Gemini Apps → unzip |

**Step 2: Place files in the `data/` folder**

Create a `data/` folder next to your `docker-compose.yml` and put the exported files inside:

```
JKRiver/docker/
├── docker-compose.yml
├── .env
└── data/                      ← already included
    ├── ChatGPT/               ← put conversations.json here
    ├── Claude/                ← put conversations.json here
    └── Gemini/                ← put Takeout files here
```

**Step 3: Import and process**

```bash
# Import (choose one or more)
docker compose exec riverhistory bash -c "cd /app_work && python import_data.py --chatgpt data/ChatGPT/conversations.json"
docker compose exec riverhistory bash -c "cd /app_work && python import_data.py --claude data/Claude/conversations.json"
docker compose exec riverhistory bash -c "cd /app_work && python import_data.py --gemini 'data/Gemini/My Activity.html'"

# Process all imported data
docker compose exec riverhistory bash -c "cd /app_work && python run.py all max"
```

Open http://localhost:2345 to see your extracted profile.

### Configuration Reference

| Variable | Default | What it does |
|----------|---------|--------------|
| `LANGUAGE` | `en` | LLM prompt language: `zh` Chinese / `en` English / `ja` Japanese (does not affect web UI) |
| `LLM_PROVIDER` | `openai` | `openai` = remote API / `local` = Ollama on your machine |
| `OPENAI_API_KEY` | | Your API key (required for remote API) |
| `OPENAI_API_BASE` | `https://api.openai.com` | API endpoint URL (change for DeepSeek, Groq, etc.) |
| `OPENAI_MODEL` | `gpt-4o-mini` | Which AI model to use |
| `OLLAMA_MODEL` | `qwen2.5:14b` | Which Ollama model (when `LLM_PROVIDER=local`) |
| `DEMO_MODE` | `true` | Load demo conversations on startup |
| `DEMO_PROCESS` | `false` | Auto-process demo on startup (uses AI, takes minutes) |
| `SLEEP_MODE` | `cron` | Memory consolidation: `cron` = daily / `auto` = after each chat / `off` = manual |
| `SLEEP_CRON_HOUR` | `0` | What hour to run daily consolidation (0-23) |
| `TELEGRAM_BOT_TOKEN` | | Telegram bot token (get from [@BotFather](https://t.me/BotFather)) |
| `TELEGRAM_ALLOWED_USERS` | | Telegram user IDs, comma-separated, **no brackets** (empty = everyone). Get ID: message [@userinfobot](https://t.me/userinfobot) |
| `DISCORD_BOT_TOKEN` | | Discord bot token (get from [Developer Portal](https://discord.com/developers/applications)) |

### Common Commands

```bash
# Start / Stop
docker compose up                  # Start (foreground, see logs)
docker compose up -d               # Start (background)
docker compose down                # Stop (data preserved)
docker compose down -v             # Stop and DELETE all data

# Chat (command line)
docker compose exec jkriver bash -c "cd /app_work && python -m agent.main"

# Process data: run.py <source> <count>
#   source: demo / chatgpt / claude / gemini / all (all = chatgpt+claude+gemini, excludes demo)
#   count:  max = process all, or a number like 50 = process oldest 50 first (good for testing cost)
#   Safe to interrupt — next run automatically skips already processed conversations
docker compose exec riverhistory bash -c "cd /app_work && python run.py demo max"
docker compose exec riverhistory bash -c "cd /app_work && python run.py all max"
docker compose exec riverhistory bash -c "cd /app_work && python run.py chatgpt 50"

# Manually trigger Sleep (organizes and consolidates memories from conversations)
curl -X POST http://localhost:8400/sleep

# Clear all extracted profiles and memories, keep original conversations (including demo)
docker compose exec riverhistory bash -c "cd /app_work && python reset_db.py"

# Logs
docker compose logs -f             # All services
docker compose logs -f jkriver     # One service

# Update to latest version
docker compose pull && docker compose up -d

# Full reset (delete everything including database)
docker compose down -v && docker compose up
```

### What Does the Demo Show?

The demo character has a contradictory life trajectory that tests the River Algorithm:

| Challenge | Standard RAG | River Algorithm |
|-----------|-------------|-----------------|
| Says "senior engineer", later admits "QA tester" | Stores both | Supersedes lie with truth |
| 4 different cities, 4 different jobs | Returns all equally | Tracks timeline, knows current state |
| Lies differently to parents, girlfriend, coworkers | Treats lies as facts | Distinguishes real vs stated |
| Ex-girlfriend → breakup → new girlfriend | Mixes up both | Marks ex as ended, tracks current |
| "Delivery is embarrassing" → "it was the best thing" | Contradictory | Tracks attitude evolution |

---

## 中文

### 这是什么？

通过 Docker 一键运行完整的 Riverse AI 系统 — 不需要安装 Python、PostgreSQL 或任何依赖。只需配置 AI 模型的 API 密钥，一条命令即可启动。

**自动启动两个服务：**

| 服务 | 地址 | 功能说明 |
|------|------|----------|
| **RiverHistory** | http://localhost:2345 | 网页画像查看器 — 查看提取的性格、偏好、经历和人生时间线 |
| **JKRiver** | http://localhost:8400/docs | AI 核心引擎 — REST API、聊天机器人、记忆整理调度 |

### 如何聊天

JKRiver 提供 **三种方式** 与 AI 聊天。所有对话都会被河流算法分析，持续丰富你的个人画像：

| 方式 | 配置 | 适合场景 |
|------|------|----------|
| **Telegram 机器人** | 在 `.env` 中设置 `TELEGRAM_BOT_TOKEN`，从 [@BotFather](https://t.me/BotFather) 获取 token | 日常手机使用，最方便 |
| **Discord 机器人** | 在 `.env` 中设置 `DISCORD_BOT_TOKEN`，从 [Developer Portal](https://discord.com/developers/applications) 获取 token | 社区/群组使用 |
| **命令行** | 无需额外配置 | 快速测试，不需要机器人 token |

**Telegram 机器人** — 在 @BotFather 创建机器人，将 token 复制到 `.env`。如需限制访问，设置 `TELEGRAM_ALLOWED_USERS` 为你的用户 ID（给 [@userinfobot](https://t.me/userinfobot) 发任意消息即可获取）。**不要加括号** — 直接填数字，如 `TELEGRAM_ALLOWED_USERS=123456789`。`docker compose up` 后直接给机器人发消息即可。

**Discord 机器人** — 在 Discord Developer Portal 创建应用和机器人，将 token 复制到 `.env`，邀请机器人加入你的服务器。`docker compose up` 后 @机器人 或私信它。

**命令行** — 打开终端运行：
```bash
docker compose exec jkriver bash -c "cd /app_work && python -m agent.main"
```
在 `>` 提示符后输入消息，输入 `quit` 退出。退出时会自动运行记忆整理。

> REST API 也可用于开发者集成，接口文档见 `http://localhost:8400/docs`。

### 前置要求

- 安装 [Docker Desktop](https://docs.docker.com/get-docker/)（已自带 Docker Compose）

### 快速开始

```bash
# 1. 获取文件
git clone https://github.com/wangjiake/JKRiver.git
cd JKRiver/docker

# 2. 创建配置文件
cp .env.example .env

# 3. 编辑 .env — 填入你的 API 密钥（参考下方"支持的 AI 模型"）
#    至少设置：OPENAI_API_KEY=sk-你的密钥
#    设置 LANGUAGE=zh/en/ja — 控制 LLM 提示词的语言（不影响网页界面）
#    聊天功能：设置 TELEGRAM_BOT_TOKEN 或 DISCORD_BOT_TOKEN（或使用命令行）

# 4. 启动所有服务
docker compose up
```

打开 http://localhost:2345 查看画像。通过 Telegram / Discord / 命令行聊天。

### 支持的 AI 模型

支持所有 OpenAI 兼容接口。编辑 `.env` 切换提供商：

| 提供商 | `OPENAI_API_BASE` | `OPENAI_MODEL` | 说明 |
|--------|-------------------|----------------|------|
| **OpenAI** | `https://api.openai.com` | `gpt-4o-mini` | 默认，质量好 |
| **DeepSeek** | `https://api.deepseek.com` | `deepseek-chat` | 最便宜，中文处理快 |
| **Groq** | `https://api.groq.com` | `llama-3.3-70b-versatile` | 有免费额度 |
| **Ollama**（本地） | — | — | 设置 `LLM_PROVIDER=local`，不需要 API 密钥 |

使用 Ollama 需要先在你的电脑上安装（`https://ollama.ai`），然后运行 `ollama pull qwen2.5:14b`。

### 体验 Demo

Demo 对话会在启动时自动导入。运行河流算法处理并查看提取的画像：

```bash
docker compose exec riverhistory bash -c "cd /app_work && python run.py demo max"
```

处理需要几分钟（会调用 AI 模型）。完成后打开 http://localhost:2345 查看结果 — 从 20 段对话中提取的完整人格画像。

处理完成后，AI 会**拥有 Demo 主人公的身份**。当你通过命令行、Telegram 或 Discord 聊天时，AI 已经了解这个角色 — 职业变迁、感情经历、性格特点和人生时间线。你可以问"我现在做什么工作？"或"说说我前女友"，AI 会根据提取的画像来回答。

在后续的命令行或 Telegram/Discord 聊天中，你可以体验实时的感知和记忆功能 — AI 会在对话中持续更新画像。如果想测试更多记忆能力，可以编辑 demo JSON 文件，添加更多人生事件、拉长时间线。

### 导入自己的数据

你可以导入自己在 ChatGPT、Claude 或 Gemini 上的真实对话记录。

> **建议：** 先用 Demo 体验一下速度和效果。处理大量真实数据可能需要几小时甚至更久。体验完 Demo 后，运行 `docker compose down -v` 清空数据库，再开始导入自己的数据。
>
> **费用提醒（远端 LLM API）：** 每条对话都会消耗 token。包含大量代码或超长消息的对话会消耗更多。越智能的模型（如 GPT-4o）画像质量越好，但费用越高；便宜的模型（如 GPT-4o-mini、DeepSeek）更快更省，但可能遗漏细节。也可以使用本地 Ollama 模型慢慢跑，完全免费。建议处理前检查导出数据，删除不需要的对话（如纯编程会话）。**请关注你的 API 账单。**

**第一步：导出数据**

| 平台 | 导出方式 |
|------|----------|
| **ChatGPT** | Settings → Data controls → Export data → 解压得到 `conversations.json` |
| **Claude** | Settings → Account → Export Data → 解压得到 `conversations.json` |
| **Gemini** | [Google Takeout](https://takeout.google.com/) → 选择 Gemini Apps → 解压 |

**第二步：放入 `data/` 文件夹**

在 `docker-compose.yml` 同级目录下创建 `data/` 文件夹，把导出文件放进去：

```
JKRiver/docker/
├── docker-compose.yml
├── .env
└── data/                      ← 已包含
    ├── ChatGPT/               ← 把 conversations.json 放这里
    ├── Claude/                ← 把 conversations.json 放这里
    └── Gemini/                ← 把 Takeout 文件放这里
```

**第三步：导入并处理**

```bash
# 导入（选一个或多个）
docker compose exec riverhistory bash -c "cd /app_work && python import_data.py --chatgpt data/ChatGPT/conversations.json"
docker compose exec riverhistory bash -c "cd /app_work && python import_data.py --claude data/Claude/conversations.json"
docker compose exec riverhistory bash -c "cd /app_work && python import_data.py --gemini 'data/Gemini/我的活动记录.html'"

# 处理所有导入的数据
docker compose exec riverhistory bash -c "cd /app_work && python run.py all max"
```

打开 http://localhost:2345 查看你的个人画像。

### 配置说明

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `LANGUAGE` | `en` | LLM 提示词语言：`zh` 中文 / `en` 英文 / `ja` 日文（不影响网页界面） |
| `LLM_PROVIDER` | `openai` | `openai` = 远端 API / `local` = 本机 Ollama |
| `OPENAI_API_KEY` | | 你的 API 密钥（使用远端 API 时必填） |
| `OPENAI_API_BASE` | `https://api.openai.com` | API 地址（换 DeepSeek、Groq 等改这里） |
| `OPENAI_MODEL` | `gpt-4o-mini` | 使用哪个 AI 模型 |
| `OLLAMA_MODEL` | `qwen2.5:14b` | Ollama 模型名（当 `LLM_PROVIDER=local`） |
| `DEMO_MODE` | `true` | 启动时导入演示对话 |
| `DEMO_PROCESS` | `false` | 启动时自动处理演示数据（会调用 AI，需要几分钟） |
| `SLEEP_MODE` | `cron` | 记忆整理方式：`cron` = 每天定时 / `auto` = 每次聊天后 / `off` = 手动 |
| `SLEEP_CRON_HOUR` | `0` | 每天几点运行记忆整理（0-23） |
| `TELEGRAM_BOT_TOKEN` | | Telegram 机器人 token（从 [@BotFather](https://t.me/BotFather) 获取） |
| `TELEGRAM_ALLOWED_USERS` | | 允许使用机器人的 Telegram 用户 ID，逗号分隔，**不要加括号**（留空 = 所有人）。获取 ID：给 [@userinfobot](https://t.me/userinfobot) 发消息 |
| `DISCORD_BOT_TOKEN` | | Discord 机器人 token（从 [Developer Portal](https://discord.com/developers/applications) 获取） |

### 常用命令

```bash
# 启动 / 停止
docker compose up                  # 启动（前台运行，可看日志）
docker compose up -d               # 启动（后台运行）
docker compose down                # 停止（数据保留）
docker compose down -v             # 停止并删除所有数据

# 命令行聊天
docker compose exec jkriver bash -c "cd /app_work && python -m agent.main"

# 处理 Demo 数据
docker compose exec riverhistory bash -c "cd /app_work && python run.py demo max"

# 处理数据：run.py <来源> <数量>
#   来源：demo / chatgpt / claude / gemini / all（all = chatgpt+claude+gemini，不含 demo）
#   数量：max = 全部处理，或填数字如 50 = 从最早开始处理 50 条（适合先试水看费用）
#   可以随时中断，下次运行会自动跳过已处理的对话
docker compose exec riverhistory bash -c "cd /app_work && python run.py demo max"
docker compose exec riverhistory bash -c "cd /app_work && python run.py all max"
docker compose exec riverhistory bash -c "cd /app_work && python run.py chatgpt 50"

# 手动触发 Sleep（整理对话中的记忆，沉淀为画像）
curl -X POST http://localhost:8400/sleep

# 清空所有画像和记忆，保留原始对话数据（含 demo）
docker compose exec riverhistory bash -c "cd /app_work && python reset_db.py"

# 查看日志
docker compose logs -f             # 所有服务
docker compose logs -f jkriver     # 单个服务

# 更新到最新版本
docker compose pull && docker compose up -d

# 彻底重置（删除所有数据包括数据库）
docker compose down -v && docker compose up
```

### Demo 演示什么？

Demo 角色拥有充满矛盾的人生轨迹，用来测试河流算法的能力：

| 挑战 | 普通 RAG | 河流算法 |
|------|---------|----------|
| 先说"高级工程师"，后来承认是"测试" | 两个都存 | 用真相取代谎言 |
| 换了 4 个城市、4 份工作 | 全部返回 | 追踪时间线，知道当前状态 |
| 对父母、女朋友、同事说不同的谎 | 把谎话当事实 | 区分真实 vs 表述 |
| 前女友 → 分手 → 新女友 | 混在一起 | 标记前任为已结束，追踪现任 |
| "跑外卖丢人" → "那是人生最重要的几个月" | 矛盾 | 追踪态度演变 |

---

## 日本語

### これは何ですか？

Docker を使って Riverse AI システム全体をワンクリックで実行できます。Python、PostgreSQL、その他の依存関係のインストールは不要です。AI モデルの API キーを設定して、1 つのコマンドを実行するだけです。

**2 つのサービスが自動的に起動します：**

| サービス | URL | 機能 |
|----------|-----|------|
| **RiverHistory** | http://localhost:2345 | Web プロフィールビューアー — 抽出された性格、好み、経験、人生タイムラインを確認 |
| **JKRiver** | http://localhost:8400/docs | AI コアエンジン — REST API、チャットボット、記憶整理スケジューラー |

### チャット方法

JKRiver は **3 つの方法** で AI とチャットできます。すべての会話は River Algorithm で分析され、パーソナルプロフィールに反映されます：

| 方法 | 設定 | 最適な用途 |
|------|------|-----------|
| **Telegram Bot** | `.env` で `TELEGRAM_BOT_TOKEN` を設定、[@BotFather](https://t.me/BotFather) でトークン取得 | 日常のモバイル利用、最も便利 |
| **Discord Bot** | `.env` で `DISCORD_BOT_TOKEN` を設定、[Developer Portal](https://discord.com/developers/applications) でトークン取得 | コミュニティ / グループ利用 |
| **コマンドライン** | 追加設定不要 | クイックテスト、ボットトークン不要 |

**Telegram Bot** — @BotFather でボットを作成し、トークンを `.env` にコピー。アクセスを制限するには、`TELEGRAM_ALLOWED_USERS` にユーザー ID を設定（[@userinfobot](https://t.me/userinfobot) に任意のメッセージを送ると取得できます）。**括弧は付けない** — 数字のみ、例：`TELEGRAM_ALLOWED_USERS=123456789`。`docker compose up` 後、ボットに直接メッセージを送信。

**Discord Bot** — Discord Developer Portal でアプリケーションとボットを作成、トークンを `.env` にコピー。ボットをサーバーに招待。`docker compose up` 後、ボットにメンションまたは DM。

**コマンドライン** — ターミナルを開いて実行：
```bash
docker compose exec jkriver bash -c "cd /app_work && python -m agent.main"
```
`>` プロンプトでメッセージを入力、`quit` で終了。終了時に自動的に記憶整理が実行されます。

> REST API も利用可能です。開発者向けドキュメント：`http://localhost:8400/docs`。

### 前提条件

- [Docker Desktop](https://docs.docker.com/get-docker/) をインストール（Docker Compose 含む）

### クイックスタート

```bash
# 1. ファイルを取得
git clone https://github.com/wangjiake/JKRiver.git
cd JKRiver/docker

# 2. 設定ファイルを作成
cp .env.example .env

# 3. .env を編集 — API キーを入力（下の「対応 AI モデル」を参照）
#    最低限：OPENAI_API_KEY=sk-あなたのキー
#    LANGUAGE=zh/en/ja を設定 — LLM プロンプトの言語を制御（Web UIには影響しません）
#    チャット：TELEGRAM_BOT_TOKEN または DISCORD_BOT_TOKEN を設定（またはコマンドラインを使用）

# 4. すべてのサービスを起動
docker compose up
```

http://localhost:2345 を開いてプロフィールを確認。Telegram / Discord / コマンドラインでチャット。

### 対応 AI モデル

OpenAI 互換 API すべてに対応。`.env` を編集してプロバイダーを切り替え：

| プロバイダー | `OPENAI_API_BASE` | `OPENAI_MODEL` | 備考 |
|-------------|-------------------|----------------|------|
| **OpenAI** | `https://api.openai.com` | `gpt-4o-mini` | デフォルト、高品質 |
| **DeepSeek** | `https://api.deepseek.com` | `deepseek-chat` | 最安値、中国語が高速 |
| **Groq** | `https://api.groq.com` | `llama-3.3-70b-versatile` | 無料枠あり |
| **Ollama**（ローカル） | — | — | `LLM_PROVIDER=local` に設定、API キー不要 |

Ollama を使用するには、まずコンピュータにインストール（`https://ollama.ai`）し、`ollama pull qwen2.5:14b` を実行してください。

### デモを体験

デモ会話は起動時に自動インポートされます。River Algorithm で処理してプロフィールを確認：

```bash
docker compose exec riverhistory bash -c "cd /app_work && python run.py demo max"
```

処理には数分かかります（AI モデルを呼び出します）。完了後、http://localhost:2345 を開いて結果を確認 — 20 の会話から抽出された完全なプロフィール。

処理完了後、AI は**デモキャラクターのアイデンティティを持ちます**。コマンドライン、Telegram、Discord でチャットすると、AI はすでにこのキャラクターを知っています — 職歴の変遷、恋愛関係、性格特徴、人生のタイムライン。「今の仕事は？」や「元カノについて教えて」と聞けば、抽出されたプロフィールに基づいて回答します。

コマンドラインや Telegram/Discord での後続チャットでは、リアルタイムの感知と記憶機能を体験できます — AI は会話の中でプロフィールを継続的に更新します。より多くの記憶機能をテストしたい場合は、デモ JSON ファイルを編集して、より多くの人生イベントやタイムラインを追加できます。

### 自分のデータをインポート

ChatGPT、Claude、Gemini の実際の会話履歴をインポートできます。

> **推奨：** まずデモで速度と品質を体験してください。大量の実データ処理には数時間以上かかる場合があります。デモ体験後、`docker compose down -v` でデータベースをクリアし、自分のデータのインポートを開始してください。
>
> **費用に関する注意（リモート LLM API）：** 各会話はトークンを消費します。大量のコードや非常に長いメッセージを含む会話はより多く消費します。高性能モデル（GPT-4o など）はプロフィール品質が高いですがコストも高く、安価なモデル（GPT-4o-mini、DeepSeek など）は高速で安価ですが細部を見逃す可能性があります。ローカル Ollama モデルを使えば完全無料でゆっくり処理できます。処理前にエクスポートデータを確認し、不要な会話（純粋なコーディングセッション等）を削除してください。**API の請求額を確認してください。**

**ステップ 1：データをエクスポート**

| プラットフォーム | エクスポート方法 |
|-----------------|-----------------|
| **ChatGPT** | Settings → Data controls → Export data → 解凍して `conversations.json` を取得 |
| **Claude** | Settings → Account → Export Data → 解凍して `conversations.json` を取得 |
| **Gemini** | [Google Takeout](https://takeout.google.com/) → Gemini Apps を選択 → 解凍 |

**ステップ 2：`data/` フォルダに配置**

`docker-compose.yml` と同じディレクトリに `data/` フォルダを作成し、エクスポートファイルを配置：

```
JKRiver/docker/
├── docker-compose.yml
├── .env
└── data/                      ← 同梱済み
    ├── ChatGPT/               ← conversations.json をここに配置
    ├── Claude/                ← conversations.json をここに配置
    └── Gemini/                ← Takeout ファイルをここに配置
```

**ステップ 3：インポートと処理**

```bash
# インポート（1つまたは複数選択）
docker compose exec riverhistory bash -c "cd /app_work && python import_data.py --chatgpt data/ChatGPT/conversations.json"
docker compose exec riverhistory bash -c "cd /app_work && python import_data.py --claude data/Claude/conversations.json"
docker compose exec riverhistory bash -c "cd /app_work && python import_data.py --gemini 'data/Gemini/マイ アクティビティ.html'"

# インポートしたデータをすべて処理
docker compose exec riverhistory bash -c "cd /app_work && python run.py all max"
```

http://localhost:2345 を開いてプロフィールを確認。

### 設定リファレンス

| 設定項目 | デフォルト | 説明 |
|----------|-----------|------|
| `LANGUAGE` | `en` | LLM プロンプト言語：`zh` 中国語 / `en` 英語 / `ja` 日本語（Web UI には影響しません） |
| `LLM_PROVIDER` | `openai` | `openai` = リモート API / `local` = ローカル Ollama |
| `OPENAI_API_KEY` | | API キー（リモート API 使用時に必須） |
| `OPENAI_API_BASE` | `https://api.openai.com` | API エンドポイント（DeepSeek、Groq 等はここを変更） |
| `OPENAI_MODEL` | `gpt-4o-mini` | 使用する AI モデル |
| `OLLAMA_MODEL` | `qwen2.5:14b` | Ollama モデル名（`LLM_PROVIDER=local` の場合） |
| `DEMO_MODE` | `true` | 起動時にデモ会話をインポート |
| `DEMO_PROCESS` | `false` | 起動時にデモを自動処理（AI を使用、数分かかる） |
| `SLEEP_MODE` | `cron` | 記憶整理：`cron` = 毎日定時 / `auto` = チャット毎 / `off` = 手動 |
| `SLEEP_CRON_HOUR` | `0` | 毎日何時に記憶整理を実行（0-23） |
| `TELEGRAM_BOT_TOKEN` | | Telegram ボットトークン（[@BotFather](https://t.me/BotFather) で取得） |
| `TELEGRAM_ALLOWED_USERS` | | ボット使用を許可する Telegram ユーザー ID、カンマ区切り、**括弧不要**（空 = 全員）。ID 取得：[@userinfobot](https://t.me/userinfobot) にメッセージ |
| `DISCORD_BOT_TOKEN` | | Discord ボットトークン（[Developer Portal](https://discord.com/developers/applications) で取得） |

### よく使うコマンド

```bash
# 起動 / 停止
docker compose up                  # 起動（フォアグラウンド、ログ表示）
docker compose up -d               # 起動（バックグラウンド）
docker compose down                # 停止（データ保持）
docker compose down -v             # 停止してすべてのデータを削除

# コマンドラインチャット
docker compose exec jkriver bash -c "cd /app_work && python -m agent.main"

# データ処理：run.py <ソース> <件数>
#   ソース：demo / chatgpt / claude / gemini / all（all = chatgpt+claude+gemini、デモ除外）
#   件数：max = すべて処理、または数字（例: 50）= 最も古い 50 件から処理（コスト確認に最適）
#   中断しても安全 — 次回実行時に処理済み会話は自動スキップ
docker compose exec riverhistory bash -c "cd /app_work && python run.py demo max"
docker compose exec riverhistory bash -c "cd /app_work && python run.py all max"
docker compose exec riverhistory bash -c "cd /app_work && python run.py chatgpt 50"

# Sleep を手動トリガー（会話から記憶を整理し、プロフィールに沈殿）
curl -X POST http://localhost:8400/sleep

# すべてのプロフィールと記憶をクリア、元の会話データは保持（デモ含む）
docker compose exec riverhistory bash -c "cd /app_work && python reset_db.py"

# ログ確認
docker compose logs -f             # 全サービス
docker compose logs -f jkriver     # 単一サービス

# 最新バージョンに更新
docker compose pull && docker compose up -d

# 完全リセット（データベースを含むすべてを削除）
docker compose down -v && docker compose up
```

### デモは何を示していますか？

デモキャラクターは矛盾に満ちた人生軌跡を持ち、River Algorithm の能力をテストします：

| 課題 | 通常の RAG | River Algorithm |
|------|-----------|-----------------|
| 「シニアエンジニア」と言い、後に「テスター」と認める | 両方保存 | 嘘を真実で上書き |
| 4 つの都市、4 つの仕事を転々 | すべて同等に返す | タイムライン追跡、現在の状態を把握 |
| 親、彼女、同僚に違う嘘をつく | 嘘を事実として扱う | 実際 vs 発言を区別 |
| 元カノ → 別れ → 新しい彼女 | 混同 | 元カノを終了済みにし、現在を追跡 |
| 「配達は恥ずかしい」→「人生で最も大切な数ヶ月」 | 矛盾 | 態度の変化を追跡 |

---

## Architecture

```
docker compose up
┌──────────────────────────────────────────────────────────┐
│                                                          │
│  ┌──────────┐  ┌────────────────┐  ┌───────────────────┐│
│  │ postgres │  │  riverhistory  │  │     jkriver       ││
│  │  :5432   │←─│  :2345 (web)   │  │  :8400 (api)      ││
│  │          │  │  init schema   │  │  telegram bot      ││
│  │ Riverse  │←─│  load demo     │←─│  discord bot       ││
│  │   (DB)   │  │  process data  │  │  sleep scheduler   ││
│  └──────────┘  └────────────────┘  └───────────────────┘│
│                                                          │
└──────────────────────────────────────────────────────────┘
```
