# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [1.1.0] - 2026-03-01

### Added

- Multilingual synonyms YAML for category/subject matching
- PostgreSQL service in CI with storage tests
- OSS community files: contributing, CoC, changelog, security, CI, issue/PR templates

### Fixed

- Perceive JSON output parsing
- Interest category check to use synonyms instead of single-language label
- Web dashboard port in READMEs

## [0.1.0] - 2026-02-25

### Added

- River Algorithm: temporal evolution, causal chains, confidence progression (suspected → confirmed → established)
- Persistent memory with timeline-based profile extraction
- Offline consolidation (Sleep) — insight extraction, contradiction resolution, knowledge strengthening
- Multi-modal input: text, voice (Whisper-1), images (GPT-4 Vision / LLaVA), files
- Pluggable tools: finance tracking, health sync (Withings), web search, vision, TTS
- YAML skills: custom behaviors triggered by keyword or cron schedule
- External agents: Home Assistant, n8n, Dify via `agents_*.yaml`
- MCP Protocol support for Gmail and other MCP servers
- Multi-channel: Telegram, Discord, REST API, WebSocket, CLI, Web Dashboard
- Local-first LLM via Ollama with auto-escalation to OpenAI / DeepSeek
- Proactive outreach: event follow-up, idle check-in, quiet hours
- Semantic search with BGE-M3 embeddings
- Multi-language prompts: English, Chinese, Japanese
- PostgreSQL storage with schema migrations
- Docker Compose deployment
- Chat history import: ChatGPT, Claude, Gemini exports
- FastAPI REST API + Flask Web Dashboard
- Health endpoint (`/health`) and config validation

[Unreleased]: https://github.com/wangjiake/JKRiver/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/wangjiake/JKRiver/compare/v0.1.0...v1.1.0
[0.1.0]: https://github.com/wangjiake/JKRiver/releases/tag/v0.1.0
