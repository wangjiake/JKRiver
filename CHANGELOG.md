# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [2.3.0] - 2026-03-26

### Added

- **Outsource / Task Agent** — Delegate complex multi-step tasks to an autonomous sub-agent via `dispatch_task` tool; sub-agent uses a ReAct loop with file read/write, shell, grep, and other tools
- **Task preview + confirmation flow** — Agent generates a step-by-step plan and waits for user confirmation before execution begins
- **Real-time task progress** — `/outsource` page shows live step-by-step execution with collapsible params per step
- **Task tray** — Status bar shows active task count and a collapsible tray of running/recent tasks
- **Interactive task questions** (`ask_user` tool) — Sub-agent can pause and ask the user a question mid-task; user replies inline in chat
- **Task cancellation** — Tasks can be cancelled from `/outsource` page or via WebSocket; status correctly set to `cancelled`
- **Soft delete for tasks** — Deleted tasks set `deleted_at` instead of being removed; history preserved for debugging
- **Per-task temp directory** — LLM-created temporary scripts isolated to `/tmp/jkriver_tasks/{task_id}/`, auto-cleaned after task completes
- **DB migration** `003_outsource_fields.sql` — Adds `session_id`, `pending_question`, `deleted_at` to `outsource_tasks`
- **Outsource page mobile layout** — Sidebar/detail toggle, back button, mobile-friendly header matching chat page style
- **Status bar hamburger button** — Moved from header to status bar (before connection dot) on both mobile and desktop
- **Mobile sys-stats 2-row layout** — CPU + Memory on row 1, Disk + Network on row 2 (fixed, not dynamic)

### Changed

- Light mode accent color updated from GitHub blue (`#0969da`) to soft indigo (`#4f5fba`) across all pages
- `dispatch_task.py` / `api.py` — All local `import` statements moved to file top; removed redundant `_get_plan()` wrapper
- i18n: Chinese nav label for "Tasks" renamed to "外包" (outsource); Japanese nav label renamed to "派遣" (dispatch)
- `outsource.yaml` skill — Extended trigger keyword list: added Japanese (`派遣モード`, `派遣して`, `派遣タスク`, `派遣に`) and English variants (`outsource this`, `delegate to agent`, `run as task`, `use task agent`)

### Fixed

- Second `ask_user` question in the same task created duplicate element IDs, making reply button unclickable — fixed with unique IDs per question
- Backend silently dropped `task_answer` WebSocket messages when task was no longer waiting; now sends explicit error response
- Task answer submit button now disables immediately on click with visual feedback and error toast if WebSocket is closed

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
