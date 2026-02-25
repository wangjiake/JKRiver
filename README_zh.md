# Riverse — 河流算法

**为个人终端设计的 AI Agent — 持久记忆，离线认知，越用越懂你。**

**[English](README.md)** | **[中文](README_zh.md)** | **[日本語](README_ja.md)**

![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white)
![License: AGPL-3.0 + Commercial](https://img.shields.io/badge/License-AGPL--3.0%20%2B%20Commercial-green)

[![X (Twitter)](https://img.shields.io/badge/X-@JKRiverse-000000?logo=x&logoColor=white)](https://x.com/JKRiverse)
[![Discord](https://img.shields.io/badge/Discord-Join-5865F2?logo=discord&logoColor=white)](https://discord.gg/PnAt4Xkt)

## 什么是 Riverse？

你和 AI 聊了这么久，但每个 AI 都不认识你。换一个平台，一切从零开始。你的数据散落在各个云端，不属于你。

Riverse 是一个运行在你自己机器上的个人 AI Agent。你通过 Telegram、Discord 或其他接口和它对话，它会记住每一次交流，在对话结束后像人类睡眠一样离线整理记忆 — 提取你的性格、偏好、经历、人际关系，构建一个持续成长的你的画像。聊得越多，它越懂你。所有数据存在本地，归你所有。

v1.0 已实现：多模态输入（文本、语音、图片、文件）、多渠道接入、可插拔工具（财务追踪、健康同步、网页搜索、智能家居）、YAML 自定义技能、外部 Agent 接入、MCP 协议（Gmail 等）、主动关怀。这是为未来在手机、手表等个人设备上运行真正的个人 AI 打基础。

当前版本为 beta，推荐单用户使用。由于需要处理图片、语音和文件，建议使用 **Telegram Bot** 作为主要聊天入口，在 `settings.yaml` 中填入你唯一的 Telegram User ID。

## 河流算法（River Algorithm）

Riverse 的核心认知模型称为**河流算法** — 一套关于个人数字画像权重的算法。对话像水流，关键信息像河床泥沙一样沉淀，经过多轮验证逐步从"猜测"升级为"确认"再到"稳固"。离线整理（Sleep）则是河流的自净过程。所有数据存在本地，归你所有。对话越多，AI 对你的理解就越深，越用越懂你。

```
对话流入 ──→ 冲刷 ──→ 沉淀 ──→ 塑造认知 ──→ 继续流动
              │         │         │
              │         │         └─ 确认的认知沉入深层，成为稳固的河床
              │         └─ 重要信息沉淀为观察记录、假设、画像
              └─ 矛盾的旧认知被冲走，新的洞察取而代之
```

**三个核心隐喻：**

- **水流（Flow）** — 每次对话都是流经的水，携带新的信息。河流永不停歇，对你的理解持续演化，从不重置
- **沉淀（Sediment）** — 对话中的关键信息像泥沙一样沉淀：事实沉入画像，情绪沉入观察，规律沉入假设。反复确认的认知越沉越深，越来越稳固
- **自净（Purify）** — Sleep 过程像河流的自净能力：冲走过时的信息，解决矛盾的认知，将碎片整合为完整的理解。每次整理后，河床更清晰，认知更准确

与现有 AI 记忆的区别：ChatGPT Memory、Claude Memory 等本质上是平面列表 — 存几条事实，没有时间线，没有置信度，没有矛盾检测，数据存在云端、归平台所有。Riverse 是一条活的河流 — 每段对话都在塑造河床，河床引导未来的每一次对话，而所有数据始终留在你自己的机器上。

## 特性

- **持久记忆** — 跨会话记忆，构建随你演化的用户画像
- **离线整理（Sleep）** — 对话结束后自动整理记忆、提炼认知
- **多模态输入** — 文本、语音（Whisper）、图片（GPT-4 Vision / LLaVA）、文件，原生理解
- **可插拔工具** — 网页搜索、天气查询、财务追踪、健康同步（Withings）、TTS 等
- **YAML 技能** — 用简单的 YAML 创建自定义行为，按关键词或 cron 定时触发
- **外部 Agent** — 通过 `agents_*.yaml` 接入 Home Assistant、n8n、Dify 等外部服务
- **MCP 协议** — 支持 Model Context Protocol，接入 Gmail 等 MCP Server
- **多渠道** — Telegram、Discord、REST API、WebSocket、CLI、Web 仪表盘
- **本地优先** — 默认 Ollama，质量不足时自动升级到 OpenAI / DeepSeek
- **主动关怀** — 跟进重要事件、空闲问候、策略提醒，尊重静默时段
- **语义搜索** — BGE-M3 向量嵌入，按语义而非关键词检索相关记忆
- **多语言提示词** — 内置中文、英文、日文提示词，一键切换

## Sleep — 离线记忆整合

Sleep 是 Riverse 消化对话、更新画像的过程。支持自动触发和手动触发：

| 触发方式 | 说明 |
|---|---|
| **Telegram** | 发送 `/new` — 重置会话并在后台运行 Sleep |
| **CLI** | 退出时自动执行（`quit` 或 Ctrl+C） |
| **REST API** | `POST /sleep` |
| **定时任务（推荐）** | 用 cron 设定每晚定时跑，整合一天的对话 |

**cron 示例** — 每天凌晨 0 点运行 Sleep：

```bash
# crontab -e
0 0 * * * cd /path/to/Riverse && /path/to/python -c "from agent.sleep import run; run()"
```

## 技术栈

| 层 | 技术 |
|---|---|
| 运行时 | Python 3.10+, PostgreSQL 16+ |
| 本地 LLM | Ollama + Qwen 2.5 14B |
| 云端 LLM | OpenAI GPT-4o / DeepSeek（兜底） |
| 向量嵌入 | Ollama + BGE-M3 |
| REST API | FastAPI + Uvicorn |
| Web 仪表盘 | Flask |
| Telegram | python-telegram-bot (async) |
| Discord | discord.py (async) |
| 语音识别 | OpenAI Whisper-1 |
| 图像理解 | GPT-4 Vision / Ollama LLaVA |
| TTS | Edge TTS |

## 项目结构

```
Riverse/
├── settings.yaml            # 主配置文件（数据库、LLM、Bot Token 等）
├── agent/
│   ├── main.py              # CLI 入口
│   ├── api.py               # FastAPI REST + WebSocket 服务
│   ├── core.py              # 核心对话循环
│   ├── cognition/           # 认知引擎
│   ├── sleep.py             # 离线记忆整理
│   ├── proactive.py         # 主动推送
│   ├── telegram_bot.py      # Telegram Bot
│   ├── discord_bot.py       # Discord Bot
│   ├── storage/             # 数据库层
│   ├── tools/               # 工具系统（搜索、图像、语音、TTS 等）
│   ├── skills/              # 技能系统（YAML 定义 + 执行引擎）
│   ├── config/
│   │   ├── agents_*.yaml    #   外部 Agent 配置 (zh/en/ja)
│   │   └── prompts/         #   多语言提示词 (zh/en/ja)
│   └── schema.sql           # 数据库建表脚本
├── web.py                   # Flask Web 仪表盘
├── templates/               # 前端页面模板
├── requirements.txt         # Python 依赖
└── README_zh.md             # 本文档
```

---

## 安装与启动

### 1. 前置要求

| 依赖 | 说明 |
|---|---|
| Python 3.10+ | 运行时 |
| PostgreSQL 16+ | 数据存储 |
| Ollama | 本地 LLM 推理（可选，也可纯云端） |

### 2. 克隆项目

```bash
git clone https://github.com/wangjiake/JKRiver.git
cd Riverse
```

### 3. 创建虚拟环境并安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

pip install -r requirements.txt
```

如需定时技能支持（Telegram Job Queue）：

```bash
pip install "python-telegram-bot[job-queue]"
```

### 4. 配置 PostgreSQL

确保 PostgreSQL 正在运行，然后创建数据库并建表：

```bash
# 创建数据库（根据你的 PostgreSQL 用户名调整）
createdb -h localhost -U your_username Riverse

# 建表
psql -h localhost -U your_username -d Riverse -f agent/schema.sql
```

> **注意：** Riverse 和 [河流算法 — AI 对话历史特别篇](https://github.com/wangjiake/RiverHistory) 共享同一个数据库。任一项目的建表命令都会创建两个项目所需的全部表。如果你已经运行过另一个项目的建表命令，可以跳过此步骤。

验证建表成功：

```bash
psql -h localhost -U your_username -d Riverse -c "\dt"
```

应看到 `conversation_turns`、`user_profile`、`observations` 等十余张表。

### 5. 编辑配置文件

所有配置统一在项目根目录的 `settings.yaml` 中管理，包括数据库、LLM、Bot Token 等。

#### 5.1 数据库

```yaml
database:
    name: "Riverse"
    user: "your_username"     # ← 改为你的 PostgreSQL 用户名
    host: "localhost"
```

> macOS Homebrew 安装的 PostgreSQL 用户名通常是你的系统用户名（终端执行 `whoami` 查看）；Linux/Windows 安装通常是 `postgres`。

#### 5.2 语言

```yaml
language: "zh"                  # zh / en / ja
```

#### 5.3 LLM 配置

**方式 A：使用本地 Ollama（推荐）**

先安装 Ollama 并拉取模型：

```bash
# 安装 Ollama: https://ollama.ai
ollama pull qwen2.5:14b         # 主对话模型
ollama pull bge-m3              # 向量嵌入模型（可选）
```

配置保持默认即可：

```yaml
llm_provider: "local"

local:
  model: "qwen2.5:14b"
  api_base: "http://localhost:11434"
```

**方式 B：纯云端（不需要 Ollama）**

```yaml
llm_provider: "openai"

openai:
  model: "gpt-4o-mini"
  api_base: "https://api.openai.com"
  api_key: "sk-your-openai-api-key"
```

#### 5.4 云端 LLM（兜底 + 网页搜索）

本地模型回答质量不足时自动升级到云端。即使用本地模型也建议配置：

```yaml
cloud_llm:
  enabled: true
  providers:
    - name: "openai"
      model: "gpt-4o"
      api_base: "https://api.openai.com"
      api_key: "sk-your-openai-api-key"
      search: true              # 启用网页搜索能力
      priority: 1
    - name: "deepseek"
      model: "deepseek-chat"
      api_base: "https://api.deepseek.com"
      api_key: "sk-your-deepseek-key"
      priority: 2
```

#### 5.5 Telegram Bot

1. 在 Telegram 找 [@BotFather](https://t.me/BotFather)，发 `/newbot` 创建 Bot，获取 Token
2. 获取你的 user ID（二选一）：
   - 给 [@userinfobot](https://t.me/userinfobot) 发任意消息，它会回复你的 ID
   - 或给 Bot 发一条消息，然后访问 `https://api.telegram.org/bot<TOKEN>/getUpdates` 查看
3. 填入配置：

```yaml
telegram:
  bot_token: "123456:ABC-DEF..."
  temp_dir: "tmp/telegram"
  allowed_user_ids: [your_user_id]  # 只允许你自己使用
```

#### 5.6 Discord Bot（可选）

1. 前往 [Discord Developer Portal](https://discord.com/developers/applications) 创建应用
2. 在 Bot 页面获取 Token，开启 Message Content Intent
3. 用 OAuth2 URL 邀请 Bot 到你的服务器

```yaml
discord:
  bot_token: "your-discord-bot-token"
  allowed_user_ids: []           # 空 = 允许所有人；填 ID 则限制
```

#### 5.7 向量嵌入（可选，默认关闭）

启用后可按语义搜索记忆（而非关键词匹配）。需要 Ollama 运行 bge-m3 模型：

```bash
ollama pull bge-m3
```

然后在 `settings.yaml` 中开启：

```yaml
embedding:
  enabled: true
  model: "bge-m3"
  api_base: "http://localhost:11434"
```

#### 5.8 其他可选配置

```yaml
# 工具
tools:
  enabled: true
  shell_exec:
    enabled: false               # 安全考虑默认禁用

# TTS 文字转语音
tts:
  enabled: false

# MCP 协议
mcp:
  enabled: false
  servers: []

# 主动推送
proactive:
  enabled: true
  quiet_hours:
    start: "23:00"
    end: "08:00"
```

### 6. 启动

激活虚拟环境后，根据需要选择启动方式：

```bash
source .venv/bin/activate
```

#### CLI 交互模式

```bash
python -m agent.main
```

终端中直接输入文字对话，输入 `quit` 退出。退出时会自动触发 Sleep 整理记忆。

#### Telegram Bot

```bash
python -m agent.telegram_bot
```

支持文本、语音消息、图片、文件。发送 `/sleep` 手动触发记忆整理。

#### Discord Bot

```bash
python -m agent.discord_bot
```

#### REST API

```bash
uvicorn agent.api:app --host 0.0.0.0 --port 8400
```

接口列表：

| 端点 | 方法 | 说明 |
|---|---|---|
| `/chat` | POST | 发送消息，获取回复 |
| `/session/new` | POST | 创建新会话 |
| `/sleep` | POST | 触发记忆整理 |
| `/profile` | GET | 获取当前画像 |
| `/hypotheses` | GET | 获取所有假设 |
| `/sessions` | GET | 列出活跃会话 |
| `/ws/chat` | WebSocket | 实时对话 |

#### Web 仪表盘

```bash
python web.py                          # 默认端口 1234
python web.py --port 8401              # 指定端口
```

浏览器访问 `http://localhost:1234`，可查看：

- 画像总览（分类、时间线、确认/待确认状态）
- 人际关系图
- 人物轨迹分析
- 观察记录
- 人工审核（编辑、确认、驳回、解决矛盾）
- 财务数据、健康数据

#### 手动触发 Sleep

CLI 退出时自动触发。也可以单独运行：

```bash
python -c "from agent.sleep import run; run()"
```

---

## 技能系统

在 `agent/skills/` 目录下创建 `.yaml` 文件即可定义技能。

### 简单技能（指令型）

```yaml
name: explain_code
description: 用户发代码时自动提供逐行解释
trigger:
  type: keyword
  keywords: ["解释代码", "explain code"]
instruction: |
  用户希望你解释代码。请：
  1. 先用一句话概括这段代码的功能
  2. 逐行或逐块解释关键逻辑
  3. 指出可能的改进点
enabled: true
```

### 工作流技能（定时型）

```yaml
name: weekly_summary
description: 每周日晚上发送温馨周末问候
trigger:
  type: schedule
  cron: "0 20 * * 0"            # 每周日 20:00
steps:
  - respond: |
      写一条简短温馨的周末问候。
enabled: true
```

### 对话中创建技能

直接对 Bot 说"创建一个技能..."或"帮我做一个定时提醒..."，Bot 会自动生成 YAML 并保存。

---

## 外部 Agent 配置

编辑 `agent/config/agents_zh.yaml` 可接入外部服务。已内置的模板：

| Agent | 类型 | 说明 | 默认状态 |
|---|---|---|---|
| weather_query | HTTP | wttr.in 天气查询 | 启用 |
| home_lights | HTTP | Home Assistant 灯控 | 禁用 |
| home_status | HTTP | Home Assistant 设备状态 | 禁用 |
| n8n_email | HTTP | n8n 发送邮件 | 禁用 |
| n8n_workflow | HTTP | n8n 通用工作流 | 禁用 |
| dify_agent | HTTP | Dify 子 Agent | 禁用 |
| backup_notes | Command | 本地备份脚本 | 禁用 |
| system_info | Command | 查看系统信息 | 禁用 |

将 `enabled` 改为 `true` 并填入你的地址/Token 即可使用。LLM 会自动判断何时调用。

---

## 常见问题

### PostgreSQL 连接失败

确认 PostgreSQL 正在运行：

```bash
pg_isready -h localhost
```

如果用户名不是默认的 `postgres`，需要修改项目根目录 `settings.yaml` 中的 `database.user`。

### Ollama 模型未找到

```bash
ollama list                     # 查看已安装模型
ollama pull qwen2.5:14b         # 安装对话模型
ollama pull bge-m3              # 安装嵌入模型
```

### Telegram Bot 无响应

1. 确认 `bot_token` 正确
2. 确认 `allowed_user_ids` 包含你的 Telegram user ID
3. 查看终端输出的日志信息

### 如何只用云端不用 Ollama

将 `llm_provider` 改为 `"openai"`，填入 API Key，将 `embedding.enabled` 设为 `false`。

---

## 许可证

本项目采用**双协议**授权：

| 用途 | 协议 | 说明 |
|---|---|---|
| 个人使用 / 开源项目 | [AGPL-3.0](LICENSE) | 免费使用，修改后必须开源 |
| 商业使用 / 闭源集成 | 商业授权 | 联系 mailwangjk@gmail.com |

简单来说：个人学习、研究、开源贡献随便用；想闭源商用或做成 SaaS 卖钱，需要商业授权。

## 联系方式

- **X (Twitter):** [@JKRiverse](https://x.com/JKRiverse)
- **Discord:** [加入](https://discord.gg/PnAt4Xkt)
- **Email:** mailwangjk@gmail.com
