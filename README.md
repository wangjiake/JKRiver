# Riverse — River Algorithm

**A personal AI agent designed for your own devices — persistent memory, offline cognition, grows with every conversation.**

**[English](README.md)** | **[中文](README_zh.md)** | **[日本語](README_ja.md)**

![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white)
![License: AGPL-3.0 + Commercial](https://img.shields.io/badge/License-AGPL--3.0%20%2B%20Commercial-green)

[![X (Twitter)](https://img.shields.io/badge/X-@JKRiverse-000000?logo=x&logoColor=white)](https://x.com/JKRiverse)
[![Discord](https://img.shields.io/badge/Discord-Join-5865F2?logo=discord&logoColor=white)](https://discord.gg/PnAt4Xkt)
[![Docs](https://img.shields.io/badge/Docs-wangjiake.github.io-06b6d4?logo=readthedocs&logoColor=white)](https://wangjiake.github.io/riverse-docs/)

## Quick Try with Docker

Don't want to install Python or PostgreSQL? **[Run with Docker in 3 commands](https://github.com/wangjiake/Riverse-Docker)** — supports OpenAI, DeepSeek, Groq, or any OpenAI-compatible API.

---

## What is Riverse?

You've been talking to AI for years, but no AI actually knows you. Switch platforms and you start from zero. Your data is scattered across clouds you don't control.

Riverse is a personal AI agent that runs on your own machine. Talk to it through Telegram, Discord, or any interface — it remembers every conversation and consolidates memories offline, like human sleep: extracting your personality, preferences, experiences, and relationships into a continuously growing profile. The more you talk, the deeper it understands you. All data stays local and belongs to you.

v1.0 includes: multi-modal input (text, voice, images, files), multi-channel access, pluggable tools (finance tracking, health sync, web search, smart home), YAML custom skills, external agent integration, MCP protocol (Gmail, etc.), and proactive outreach. This lays the foundation for running a truly personal AI on phones, watches, and other personal devices in the future.

The current version is beta and recommended for single-user use. Since Riverse handles images, voice, and files, we recommend the **Telegram Bot** as the primary chat interface — set your unique Telegram User ID in `settings.yaml`.

## River Algorithm

The core cognition model of Riverse is called the **River Algorithm** — a personal digital profile weighting algorithm. Conversations flow like water, key information settles like riverbed sediment, progressively upgrading from "suspected" to "confirmed" to "established" through multi-turn verification. Offline consolidation (Sleep) acts as the river's self-purification. All data is stored locally and owned by you. The more you talk, the deeper the AI understands you.

```
Conversation flows in ──→ Erosion ──→ Sedimentation ──→ Shapes cognition ──→ Keeps flowing
                           │              │                   │
                           │              │                   └─ Confirmed knowledge sinks deep, becoming stable bedrock
                           │              └─ Key info settles into observations, hypotheses, profiles
                           └─ Contradicted old beliefs are washed away, replaced by new insights
```

**Three core metaphors:**

- **Flow** — Every conversation is water flowing through. The river never stops; understanding of you evolves continuously and never resets
- **Sediment** — Key information from conversations settles like silt: facts sink into profiles, emotions into observations, patterns into hypotheses. Repeatedly confirmed knowledge sinks deeper, becoming more stable
- **Purify** — The Sleep process is the river's self-purification: washing away outdated information, resolving contradictions, integrating fragments into coherent understanding. After each cycle, the riverbed is clearer and cognition more accurate

How this differs from existing AI memory: ChatGPT Memory, Claude Memory and the like are flat lists — a handful of facts with no timeline, no confidence levels, no contradiction detection, stored in the cloud and owned by the platform. Riverse is a living river — every conversation shapes the riverbed, the riverbed guides every future conversation, and all of it stays on your machine.

## Features

- **Persistent Memory** — Remembers across sessions, builds a timeline-based profile that evolves with you
- **Offline Consolidation** — Processes conversations after they end: extracts insights, resolves contradictions, strengthens confirmed knowledge
- **Multi-Modal Input** — Text, voice, images, files — all understood natively
- **Pluggable Tools** — Finance tracking, health sync (Withings), web search, vision, TTS, and more
- **YAML Skills** — Create custom behaviors with simple YAML — trigger by keyword or schedule
- **External Agents** — Connect Home Assistant, n8n, Dify and more via `agents_*.yaml`
- **MCP Protocol** — Model Context Protocol support for Gmail and other MCP servers
- **Multi-Channel** — Telegram, Discord, REST API, WebSocket, CLI, Web Dashboard
- **Local-First** — Ollama by default, auto-escalates to OpenAI / DeepSeek when needed
- **Proactive Outreach** — Follows up on events, checks in when idle, respects quiet hours
- **Semantic Search** — BGE-M3 embeddings, retrieves relevant memories by meaning
- **Multi-language Prompts** — Built-in prompts for English, Chinese, and Japanese — switch with one setting

> **On accuracy:** No LLM today is specifically trained for personal profile extraction, so results may occasionally be off. When you spot something inaccurate, you can **reject** incorrect memories or **close** outdated ones in the Web Dashboard. Riverse intentionally does not allow manual editing of memory content — wrong memories are like sediment in a river, meant to be washed away by the current, not sculpted by hand. As conversations accumulate, the River Algorithm continuously self-corrects through multi-turn verification and contradiction detection — profiles become more accurate over time.

## Sleep — Offline Memory Consolidation

Sleep is the process where Riverse digests conversations and updates your profile. It is triggered automatically or on demand:

| Trigger | How |
|---|---|
| **Telegram** | Send `/new` — resets the session and runs Sleep in the background |
| **CLI** | Runs automatically when you exit (`quit` or Ctrl+C) |
| **REST API** | `POST /sleep` |
| **Cron (recommended)** | Schedule a nightly job to consolidate the day's conversations |

**Cron example** — run Sleep every day at midnight:

```bash
# crontab -e
0 0 * * * cd /path/to/JKRiver && /path/to/python -c "from agent.sleep import run; run()"
```

## Tech Stack

| Layer | Technology |
|---|---|
| Runtime | Python 3.10+, PostgreSQL 16+ |
| Local LLM | Ollama (any compatible model) |
| Cloud LLM | OpenAI GPT-4o / DeepSeek (fallback) |
| Embeddings | Ollama + BGE-M3 |
| REST API | FastAPI + Uvicorn |
| Web Dashboard | Flask |
| Telegram | python-telegram-bot (async) |
| Discord | discord.py (async) |
| Voice | OpenAI Whisper-1 |
| Vision | GPT-4 Vision / Ollama LLaVA |
| TTS | Edge TTS |

## Project Structure

```
JKRiver/
├── settings.yaml            # Main config (database, LLM, bot tokens, etc.)
├── agent/
│   ├── main.py              # CLI entry point
│   ├── api.py               # FastAPI REST + WebSocket
│   ├── core.py              # Core conversation loop
│   ├── cognition/           # Cognition engine
│   ├── sleep.py             # Offline memory consolidation
│   ├── proactive.py         # Proactive messaging
│   ├── telegram_bot.py      # Telegram Bot
│   ├── discord_bot.py       # Discord Bot
│   ├── storage/             # Database layer
│   ├── tools/               # Tool system (search, vision, voice, TTS, etc.)
│   ├── skills/              # Skill system (YAML definitions + execution engine)
│   ├── config/
│   │   ├── agents_*.yaml    #   External agent configs (zh/en/ja)
│   │   └── prompts/         #   Multi-language prompts (zh/en/ja)
│   └── schema.sql           # Database schema
├── web.py                   # Flask web dashboard
├── templates/               # Frontend templates
└── requirements.txt         # Python dependencies
```

---

## Installation

### 1. Prerequisites

| Dependency | Description |
|---|---|
| Python 3.10+ | Runtime |
| PostgreSQL 16+ | Data storage |
| Ollama | Local LLM inference (optional, can use cloud-only) |

### 2. Clone & Install

```bash
git clone https://github.com/wangjiake/JKRiver.git
cd JKRiver
python3 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

pip install -r requirements.txt
```

### 3. Setup PostgreSQL

```bash
createdb -h localhost -U your_username Riverse
psql -h localhost -U your_username -d Riverse -f agent/schema.sql
```

> **Note:** Riverse and [River Algorithm — AI Chat History Edition](https://github.com/wangjiake/RiverHistory) share the same database. Running the schema setup from either project creates all tables needed for both. If you have already run the other project's database setup, you can skip this step.

### 4. Configure

Edit `settings.yaml` in the project root. All settings are in one file — database, LLM, bot tokens, etc.

#### 4.1 Database

```yaml
database:
    name: "Riverse"
    user: "your_username"     # ← your PostgreSQL username
    host: "localhost"
```

> On macOS with Homebrew PostgreSQL, the username is usually your system username (run `whoami` to check). On Linux/Windows, it's usually `postgres`.

#### 4.2 Language

```yaml
language: "en"                  # en / zh / ja
```

#### 4.3 LLM

**Option A: Local Ollama (recommended)**

```bash
ollama pull <your-model>         # e.g. qwen2.5:14b, llama3, mistral
ollama pull bge-m3              # Embedding model (optional)
```

```yaml
llm_provider: "local"

local:
  model: "your-model"            # e.g. qwen2.5:14b, llama3, mistral
  api_base: "http://localhost:11434"
```

**Option B: Cloud-only (no Ollama needed)**

```yaml
llm_provider: "openai"

openai:
  model: "gpt-4o-mini"
  api_base: "https://api.openai.com"
  api_key: "sk-your-openai-api-key"
```

#### 4.4 Cloud LLM (fallback + web search)

Auto-escalates to cloud when local model quality is insufficient. Recommended even when using local:

```yaml
cloud_llm:
  enabled: true
  providers:
    - name: "openai"
      model: "gpt-4o"
      api_base: "https://api.openai.com"
      api_key: "sk-your-openai-api-key"
      search: true              # Enable web search
      priority: 1
    - name: "deepseek"
      model: "deepseek-chat"
      api_base: "https://api.deepseek.com"
      api_key: "sk-your-deepseek-key"
      priority: 2
```

#### 4.5 Telegram Bot

1. Find [@BotFather](https://t.me/BotFather) on Telegram, send `/newbot` to create a bot and get the token
2. Get your user ID (pick one):
   - Send any message to [@userinfobot](https://t.me/userinfobot), it will reply with your ID
   - Or send a message to your bot, then visit `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Edit `settings.yaml`:

```yaml
telegram:
  bot_token: "123456:ABC-DEF..."
  temp_dir: "tmp/telegram"
  allowed_user_ids: [your_user_id]  # Only allow yourself
```

#### 4.6 Discord Bot (optional)

1. Go to [Discord Developer Portal](https://discord.com/developers/applications) and create an application
2. On the Bot page, get the token and enable Message Content Intent
3. Use the OAuth2 URL to invite the bot to your server

```yaml
discord:
  bot_token: "your-discord-bot-token"
  allowed_user_ids: []           # Empty = allow everyone; add IDs to restrict
```

#### 4.7 Embedding / Semantic Search (optional, off by default)

Enables searching memories by meaning instead of keywords. Requires Ollama with bge-m3:

```bash
ollama pull bge-m3
```

Then enable in `settings.yaml`:

```yaml
embedding:
  enabled: true
  model: "bge-m3"
  api_base: "http://localhost:11434"
```

#### 4.8 Other Optional Settings

```yaml
# Tools
tools:
  enabled: true
  shell_exec:
    enabled: false               # Disabled by default for security

# TTS (Text-to-Speech)
tts:
  enabled: false

# MCP Protocol
mcp:
  enabled: false
  servers: []

# Proactive Outreach
proactive:
  enabled: true
  quiet_hours:
    start: "23:00"
    end: "08:00"
```

### 5. Run

```bash
python -m agent.main                                    # CLI
uvicorn agent.api:app --host 0.0.0.0 --port 8400       # REST API
python web.py                                            # Web Dashboard
python -m agent.telegram_bot                             # Telegram Bot
python -m agent.discord_bot                              # Discord Bot
```

---

## Skills

Create `.yaml` files in `agent/skills/` to define custom skills.

**Keyword-triggered:**

```yaml
name: explain_code
description: Auto-explain code when user sends a snippet
trigger:
  type: keyword
  keywords: ["explain code", "what does this do"]
instruction: |
  Explain the code step by step.
enabled: true
```

**Scheduled:**

```yaml
name: weekly_summary
description: Send a warm weekend greeting every Sunday
trigger:
  type: schedule
  cron: "0 20 * * 0"
steps:
  - respond: |
      Write a short, warm weekend greeting.
enabled: true
```

You can also create skills by telling the bot: "Create a skill that..."

---

## External Agents

Edit `agent/config/agents_en.yaml` to connect external services. Built-in templates:

| Agent | Type | Description | Default |
|---|---|---|---|
| weather_query | HTTP | wttr.in weather query | Enabled |
| home_lights | HTTP | Home Assistant light control | Disabled |
| home_status | HTTP | Home Assistant device status | Disabled |
| n8n_email | HTTP | Send email via n8n | Disabled |
| n8n_workflow | HTTP | Trigger n8n workflow | Disabled |
| dify_agent | HTTP | Dify sub-agent | Disabled |
| backup_notes | Command | Local backup script | Disabled |
| system_info | Command | System info query | Disabled |

Set `enabled: true` and fill in your URL/token. The LLM decides when to invoke them automatically.

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/chat` | POST | Send message, get reply |
| `/session/new` | POST | Create new session |
| `/sleep` | POST | Trigger memory consolidation |
| `/profile` | GET | Get current profile |
| `/hypotheses` | GET | Get all hypotheses |
| `/sessions` | GET | List active sessions |
| `/ws/chat` | WebSocket | Real-time chat |

---

## FAQ

### PostgreSQL connection failed

```bash
pg_isready -h localhost
```

If your username is not `postgres`, update `database.user` in `settings.yaml`.

### Ollama model not found

```bash
ollama list
ollama pull <your-model>        # e.g. qwen2.5:14b, llama3, mistral
ollama pull bge-m3
```

### Telegram Bot not responding

1. Check `bot_token` is correct
2. Check `allowed_user_ids` includes your Telegram user ID
3. Check terminal log output

### Cloud-only without Ollama

Set `llm_provider: "openai"`, fill in API key, set `embedding.enabled: false`.

---

## License

This project is **dual-licensed**:

| Use Case | License | Details |
|---|---|---|
| Personal / Open Source | [AGPL-3.0](LICENSE) | Free to use; modifications must be open-sourced |
| Commercial / Closed Source | Commercial License | Contact mailwangjk@gmail.com |

In short: personal use, research, and open-source contributions are free; closed-source commercial use or SaaS requires a commercial license.

## Contact

- **X (Twitter):** [@JKRiverse](https://x.com/JKRiverse)
- **Discord:** [Join](https://discord.gg/PnAt4Xkt)
- **Email:** mailwangjk@gmail.com
