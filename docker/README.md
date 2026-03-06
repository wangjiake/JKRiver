# Docker Quick Start

## 1. Configure

```bash
cp .env.example .env
```

Edit `.env` — set your API key:

```env
OPENAI_API_KEY=sk-your-key-here
```

## 2. Run

```bash
docker compose up -d
```

- **Web Dashboard:** http://localhost:2345
- **REST API:** http://localhost:8400/docs

## 3. Import your chat history (optional)

Drop your export files into the `data/` folder:

| Platform | Folder | File format |
|----------|--------|-------------|
| ChatGPT | `data/ChatGPT/` | `conversations.json` (from Settings → Export) |
| Claude | `data/Claude/` | JSON export |
| Gemini | `data/Gemini/` | JSON export |

Then restart:

```bash
docker compose restart
```

## Configuration

All settings are in `.env`. Key options:

| Variable | Default | Description |
|----------|---------|-------------|
| `LANGUAGE` | `en` | Prompt language: `en` / `zh` / `ja` |
| `LLM_PROVIDER` | `openai` | `openai` (remote API) or `local` (Ollama) |
| `OPENAI_API_KEY` | — | Required for openai provider |
| `OPENAI_API_BASE` | `https://api.openai.com` | Change for DeepSeek, Groq, etc. |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model name |
| `DEMO_MODE` | `true` | Load demo conversations on startup |
| `DEMO_PROCESS` | `false` | Auto-run River Algorithm on demo data |
| `SLEEP_MODE` | `cron` | Memory consolidation: `cron` / `auto` / `off` |
| `TELEGRAM_BOT_TOKEN` | — | Optional: Telegram bot |
| `DISCORD_BOT_TOKEN` | — | Optional: Discord bot |

## Commands

```bash
docker compose up -d          # Start
docker compose down            # Stop
docker compose logs -f         # View logs
docker compose restart         # Restart after config change
```
