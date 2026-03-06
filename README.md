<p align="center">
  <img src="img/binary-wave-logo.svg" width="128" height="128" alt="Riverse Logo">
</p>

# Riverse — River Algorithm

**A personal AI agent that runs on your own machine — persistent memory, offline cognition, grows with every conversation. All data stays local.**

**[English](README.md)** | **[中文](README_zh.md)** | **[日本語](README_ja.md)**

![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white)
![License: AGPL-3.0 + Commercial](https://img.shields.io/badge/License-AGPL--3.0%20%2B%20Commercial-green)

[![X (Twitter)](https://img.shields.io/badge/X-@JKRiverse-000000?logo=x&logoColor=white)](https://x.com/JKRiverse)
[![Discord](https://img.shields.io/badge/Discord-Join-5865F2?logo=discord&logoColor=white)](https://discord.gg/ZnmFrPvXym)
[![Docs](https://img.shields.io/badge/Docs-wangjiake.github.io-06b6d4?logo=readthedocs&logoColor=white)](https://wangjiake.github.io/riverse-docs/)

📖 **Full documentation: [wangjiake.github.io/riverse-docs](https://wangjiake.github.io/riverse-docs/)**

---

## RAG Memory vs. River Algorithm

Why similarity search isn't enough for a personal AI.

| | RAG / Existing AI Memory | Riverse / River Algorithm |
|---|---|---|
| **Retrieval** | Keyword / vector similarity — finds text that "looks similar" | Personal profile weighting — ranked by relevance to *you* |
| **Timeline** | No timeline — 3 years ago and yesterday weigh the same | Temporal evolution — recent events carry momentum, old patterns solidify or fade |
| **Reasoning** | No causal inference — "headaches" and "job change" stay as isolated fragments | Causal chains — connects "new job → stress → sleep problems → headaches" |
| **Confidence** | All facts have equal weight | Observations progress: suspected → confirmed → established |
| **Data ownership** | Cloud-dependent, platform-owned | Local-first — your device, your data |

### 💬 Scenario: You said "I've been having headaches lately"

*Two months ago, you mentioned changing jobs.*

<table>
<tr><th>RAG Approach</th><th>River Algorithm</th></tr>
<tr>
<td>

🧑 I've been having headaches lately

🤖 I'm sorry to hear that. Here are some common causes of headaches: dehydration, screen time, stress... Would you like some tips?

<sub>Vector search found "headache" in medical Q&A corpus. No connection to your life context.</sub>

</td>
<td>

🧑 I've been having headaches lately

🤖 You started the new management role about two months ago, and around the same time your sleep got worse — you mentioned staying up past 1am several times. The headaches might be linked. How's the work pressure been? Want me to track this as a health pattern?

<sub>Causal chain: job change → sleep disruption → headaches. Timeline-aware, personally weighted.</sub>

</td>
</tr>
</table>

---

## What is Riverse?

You've been talking to AI for years, but no AI actually knows you. Switch platforms and you start from zero. Your data is scattered across clouds you don't control.

Riverse is a personal AI agent that runs on your own machine. It remembers every conversation and consolidates memories offline, like human sleep — extracting your personality, preferences, experiences, and relationships into a continuously growing profile. The more you talk, the deeper it understands you. All data stays local and belongs to you.

## River Algorithm

Conversations flow like water, key information settles like riverbed sediment, progressively upgrading from "suspected" to "confirmed" to "established" through multi-turn verification. Offline consolidation (Sleep) acts as the river's self-purification.

```
Conversation flows in ──→ Erosion ──→ Sedimentation ──→ Shapes cognition ──→ Keeps flowing
                           │              │                   │
                           │              │                   └─ Confirmed knowledge → stable bedrock
                           │              └─ Key info → observations, hypotheses, profiles
                           └─ Outdated beliefs washed away, replaced by new insights
```

- **Flow** — Every conversation is water flowing through. The river never stops; understanding of you evolves continuously
- **Sediment** — Key information settles like silt: facts sink into profiles, emotions into observations, patterns into hypotheses
- **Purify** — Sleep is the river's self-purification: washing away outdated info, resolving contradictions, integrating fragments

## Features

- **Persistent Memory** — Remembers across sessions, builds a timeline-based profile that evolves with you
- **Offline Consolidation (Sleep)** — Extracts insights, resolves contradictions, strengthens confirmed knowledge
- **Multi-Modal Input** — Text, voice, images, files — all understood natively
- **Pluggable Tools** — Finance tracking, health sync (Withings), web search, vision, TTS, and more
- **YAML Skills** — Custom behaviors triggered by keyword or cron schedule
- **External Agents** — Connect Home Assistant, n8n, Dify and more via `agents_*.yaml`
- **MCP Protocol** — Model Context Protocol support for Gmail and other MCP servers
- **Multi-Channel** — Telegram, Discord, REST API, WebSocket, CLI, Web Dashboard
- **Local-First** — Ollama by default, auto-escalates to OpenAI / DeepSeek when needed
- **Proactive Outreach** — Follows up on events, checks in when idle, respects quiet hours
- **Semantic Search** — BGE-M3 embeddings, retrieves relevant memories by meaning
- **Multi-language Prompts** — English, Chinese, Japanese — switch with one setting

> **On accuracy:** No LLM today is specifically trained for personal profile extraction, so results may occasionally be off. You can **reject** incorrect memories or **close** outdated ones in the Web Dashboard. As conversations accumulate, the River Algorithm continuously self-corrects through multi-turn verification and contradiction detection.

---

## Quick Start

### Option A: Docker Compose (Recommended)

The fastest way to get started. No Python or PostgreSQL installation needed.

```bash
git clone https://github.com/wangjiake/JKRiver.git
cd JKRiver/docker
cp .env.example .env
```

Edit `.env` — set your API key:

```env
OPENAI_API_KEY=sk-your-key-here
```

```bash
docker compose up -d
```

Done. Web Dashboard at `http://localhost:2345`, API at `http://localhost:8400/docs`.

> **Import your chat history:** Drop your ChatGPT / Claude / Gemini export files into `docker/data/ChatGPT/`, `docker/data/Claude/`, or `docker/data/Gemini/` and restart.
>
> For Telegram/Discord bots, set `TELEGRAM_BOT_TOKEN` or `DISCORD_BOT_TOKEN` in `.env` and restart.

---

### Option B: From Source

#### 1. Prerequisites

- **Python 3.10+**
- **PostgreSQL 16+** — [Install guide](https://www.postgresql.org/download/)
- **Ollama** (optional) — [ollama.ai](https://ollama.ai), only needed for local LLM mode

#### 2. Clone and install

```bash
git clone https://github.com/wangjiake/JKRiver.git
cd JKRiver
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

#### 3. Set up PostgreSQL

```bash
# Create the database (replace YOUR_USERNAME with your PostgreSQL user)
createdb -h localhost -U YOUR_USERNAME Riverse

# Create all tables
psql -h localhost -U YOUR_USERNAME -d Riverse -f agent/schema.sql
```

> **Tip:** On macOS/Linux, run `whoami` to find your username. On Windows with default PostgreSQL, the user is usually `postgres`.

#### 4. Configure

```bash
cp settings.yaml.default settings.yaml
```

Edit `settings.yaml` — at minimum, change these:

```yaml
database:
    user: "YOUR_USERNAME"               # Your PostgreSQL username

llm_provider: "openai"                  # "openai" for cloud API, "local" for Ollama
openai:
    api_key: "sk-your-key-here"         # Required if using openai provider
```

> Full configuration guide: **[wangjiake.github.io/riverse-docs](https://wangjiake.github.io/riverse-docs/getting-started/configuration/)**

#### 5. Run

```bash
python -m agent.main                    # CLI mode
python -m agent.telegram_bot            # Telegram Bot
python -m agent.discord_bot             # Discord Bot
python web.py                           # Web Dashboard (http://localhost:1234)
```

### Testing

```bash
# Quick checks — verify imports and database schema (no LLM needed)
python tests/test_imports.py
python tests/test_db.py

# End-to-end pipeline test — requires LLM + database
python tests/test_demo_pipeline.py                          # demo2.json (52 sessions, English)
python tests/test_demo_pipeline.py tests/data/demo.json     # demo.json  (50 sessions, Chinese)
python tests/test_demo_pipeline.py --sessions 3             # Quick smoke test (3 sessions only)

# Clean up test data from database
python tests/test_demo_pipeline.py --clean
```

Test data is included in `tests/data/`. No external dependencies needed.

## Tech Stack

| Layer | Technology |
|---|---|
| Runtime | Python 3.10+, PostgreSQL 16+ |
| Local LLM | Ollama (any compatible model) |
| Cloud LLM | OpenAI GPT-4o / DeepSeek (fallback) |
| Embeddings | Ollama + BGE-M3 |
| REST API | FastAPI + Uvicorn |
| Web Dashboard | Flask |
| Telegram / Discord | python-telegram-bot / discord.py |
| Voice / Vision | Whisper-1, GPT-4 Vision, LLaVA |
| TTS | Edge TTS |

---

## License

| Use Case | License |
|---|---|
| Personal / Open Source | [AGPL-3.0](LICENSE) — free to use, modifications must be open-sourced |
| Commercial / Closed Source | Contact mailwangjk@gmail.com |

## Contact

- **X (Twitter):** [@JKRiverse](https://x.com/JKRiverse)
- **Discord:** [Join](https://discord.gg/ZnmFrPvXym)
- **Email:** mailwangjk@gmail.com
