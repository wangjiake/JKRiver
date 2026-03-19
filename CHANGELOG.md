# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [2.1.0] - 2026-03-19

### Added

- System page: toggle ON/OFF and delete tools/skills directly from the web dashboard
- System page: install skills from SkillHub by name or by pasting YAML / SKILL.md content
- System page: source badges distinguish bundled / file-installed / SkillHub skills
- Chat page: rename and pin sessions for better conversation organization
- File-based tool registry (`tools.yaml`) — tools are now dynamically loaded and removable without code changes
- `session_meta` table for storing session custom names and pinned state

### Fixed

- Tool toggle badges (ON/OFF) now respond to clicks correctly (switched to direct onclick handler)
- Skill toggle failing for files without an `enabled` field (auto-inserted on first toggle)
- Skill delete failing when directory name differs from skill name (e.g. SkillHub installs)
- Install skill modal buttons not translated in non-English UI languages
- Install skill modal height overflowing the browser viewport
- SkillHub tab now auto-detects pasted SKILL.md content and redirects to paste tab
- `weekly_summary` skill missing delete button (fixed skill loading priority: individual files > SkillHub > bundled)

## [1.2.0] - 2026-03-06

### Added

- Centralized `is_llm_error()` to detect LLM error strings across all languages
- Guard `_save_turn_data` to prevent LLM errors from being saved to database
- Synced `is_llm_error()` to riverse and RiverHistory projects

### Changed

- Unified version to 1.2.0 across JKRiver, riverse (PyPI), Docker images
- Simplified `_should_escalate` and web_search error check using `is_llm_error()`

### Removed

- Unused `local_call_failed` error keys from YAML prompts

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

[Unreleased]: https://github.com/wangjiake/JKRiver/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/wangjiake/JKRiver/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/wangjiake/JKRiver/compare/v0.1.0...v1.1.0
[0.1.0]: https://github.com/wangjiake/JKRiver/releases/tag/v0.1.0
