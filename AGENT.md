# JKRiver Agent Context

This file is located at `/app/AGENT.md` (Docker) or `<project_root>/AGENT.md` (local).
It is automatically injected into sub-agent system prompts to provide project-specific context.

> Note: `<!-- HANDWRITTEN -->` and `<!-- AUTO-GENERATED -->` are file structure markers — ignore them.

<!-- HANDWRITTEN: core -->
---

## Directory Layout (Docker Runtime)

| Path | Contents |
|------|----------|
| `/app/` | Application root (working directory) |
| `/app/agent/` | Core AI engine |
| `/app/agent/tools/` | Tool implementations |
| `/app/agent/routers/` | FastAPI route handlers |
| `/app/agent/cognition/` | Perception / thinking / memory |
| `/app/agent/storage/` | Database access layer |
| `/app/agent/skills/` | Skill definitions (YAML + Python) |
| `/app/agent/config/` | Config loader and prompt files |
| `/app/templates/` | HTML templates (Flask UI) |
| `/app/settings.yaml` | **Active config file** — symlink → `/app_config/settings.yaml` |
| `/app_config/` | Persistent config volume (survives restarts) |
| `/app_config/settings.yaml` | Persisted settings (source of truth) |
| `/app_config/skills/` | User-created custom skills (YAML) |

> On a local (non-Docker) install, replace `/app/` with the project root and `/app_config/` with `./`.

---

## Key Concepts

### "远端兜底" / Remote Fallback
Refers to `cloud_llm` in `settings.yaml` — a chain of cloud LLM providers (OpenAI, DeepSeek, etc.) that the system escalates to when the local model gives a poor response. It is **not** a separate service; it is a config section.

To enable: set `cloud_llm.enabled: true` in `/app/settings.yaml`.

### web_search backend
The `tools.web_search.backend` field in `settings.yaml` controls which search engine is used:
- `"duckduckgo"` — local library, no API key needed
- `"openai_responses"` — uses OpenAI's built-in web search (requires OpenAI API key)

> **Important**: The only valid values are `"duckduckgo"` and `"openai_responses"`. Do NOT use `"openai"` — that is wrong.
> This setting is completely separate from `cloud_llm` (远端兜底). "远端兜底" refers to `cloud_llm`, NOT to `web_search.backend`.
> To change: `system_manage` with `action="set_config"`, `key="tools.web_search.backend"`, `value="duckduckgo"` or `value="openai_responses"`.

### "外包" / Outsource / dispatch_task
A two-step flow where the main agent delegates a complex task to an autonomous sub-agent:
1. `action='preview'` — generate a plan (shown to user)
2. `action='start'` — execute in background

The sub-agent (`task_agent.py`) runs its own LLM loop with access to tools.

### strict_mode vs loose_mode (dispatch_task)
- **strict**: sub-agent can only read files, search, run syntax checks
- **loose**: sub-agent can also write files, install packages, run Python scripts

### Telegram / Discord Bot Runtime Status
To check whether the Telegram or Discord bot process is actually running (not just enabled in config):
```bash
shell_exec: ps aux | grep -E "telegram|discord" | grep -v grep
```
- If output is empty → bot process is not running
- If output shows a process → bot is running

`telegram.enabled: true` in settings.yaml means the bot is configured to start, but does NOT guarantee the process is alive. Use the above command to verify actual runtime status.

### Session
A single conversation thread. Each session has a unique `session_id`. Stored in `raw_conversations` and `conversation_turns` tables.

### Memory / River Algorithm
User facts flow through three confidence layers: `observation → suspected → confirmed`. Time-weighted: recent events matter more.

---

## Settings File: `/app/settings.yaml`

This is the live config. **Always use `system_manage` with `action="set_config"` to change a single key** — never rewrite the entire file unless changing 3+ keys at once. Rewriting the whole file risks corrupting API keys and other sensitive values.

**After any change to settings.yaml, always call `system_manage` with `action="restart"` as the final step.**

When calling `set_config`, pass the `value` parameter as follows based on type:
- **bool**: pass exactly `true` or `false` (no quotes, lowercase)
- **int**: pass a plain number string, e.g. `2048`
- **float**: pass a plain decimal string, e.g. `0.7`
- **string**: pass the value as-is, e.g. `gpt-4o-mini`

All configurable keys, their types, and allowed values:

```
# key                                              type     allowed values / notes
language                                           string   "zh" | "en" | "ja"
timezone                                           string   IANA tz, e.g. "Asia/Shanghai", "Asia/Tokyo", "America/New_York"

llm_provider                                       string   "openai" | "local"
openai.model                                       string   e.g. "gpt-4o-mini", "gpt-4o", "deepseek-chat"
openai.api_base                                    string   API endpoint URL
openai.temperature                                 float    0.0 – 1.0
openai.max_tokens                                  int      e.g. 2048

local.model                                        string   Ollama model name, e.g. "qwen2.5:14b"
local.api_base                                     string   Ollama address, e.g. "http://localhost:11434"
local.temperature                                  float    0.0 – 1.0
local.max_tokens                                   int

cloud_llm.enabled                                  bool     true | false   ← "远端兜底开关". NOT the same as web_search backend.
cloud_llm.escalation.auto                          bool     true | false
cloud_llm.escalation.feedback                      bool     true | false
cloud_llm.escalation.min_response_length           int      replies shorter than this = low quality

tools.enabled                                      bool     true | false
tools.web_search.backend                           string   "duckduckgo" | "openai_responses"  (NOT "openai", NOT "远端兜底")
tools.dispatch_task.enabled                        bool     true | false
tools.dispatch_task.strict_mode                    bool     true | false   (true = read-only sub-agent)
tools.dispatch_task.max_steps                      int      e.g. 20
tools.dispatch_task.timeout                        int      seconds, e.g. 300
tools.shell_exec.enabled                           bool     true | false
tools.shell_exec.timeout                           int      seconds
tools.file_read.enabled                            bool     true | false
tools.file_read.max_file_size                      int      bytes, e.g. 1048576 (1MB)
tools.finance_query.enabled                        bool     true | false
tools.health_query.enabled                         bool     true | false
tools.voice_transcribe.model                       string   e.g. "whisper-1"
tools.voice_transcribe.language                    string   e.g. "en", "zh"
tools.image_describe.provider                      string   "openai" | "local"
tools.image_describe.model                         string   e.g. "gpt-4o"

telegram.enabled                                   bool     true | false
telegram.allowed_user_ids                          list     list of integer user IDs (empty = allow all)
# telegram.bot_token — cannot be set via set_config; edit settings.yaml directly with file_read + file_write

discord.enabled                                    bool     true | false
discord.allowed_user_ids                           list     list of integer user IDs (empty = allow all)
# discord.bot_token — cannot be set via set_config; edit settings.yaml directly with file_read + file_write

tts.enabled                                        bool     true | false
tts.max_chars                                      int      max characters before truncation
tts.voices.zh                                      string   e.g. "zh-CN-XiaoxiaoNeural"
tts.voices.en                                      string   e.g. "en-US-AriaNeural"

session_memory.char_budget                         int      total character budget for session context
session_memory.keep_recent                         int      number of recent turns to keep in full
session_memory.summary_ratio                       float    0.0 – 1.0, portion of budget used for summaries
session_memory.recall_max                          int      max vector recall items
session_memory.recall_min_score                    float    0.0 – 1.0, minimum similarity threshold

embedding.enabled                                  bool     true | false
embedding.model                                    string   e.g. "bge-m3"
embedding.api_base                                 string   Ollama address
embedding.search.top_k                             int
embedding.search.min_score                         float    0.0 – 1.0
embedding.clustering.enabled                       bool     true | false
embedding.clustering.show_themes                   bool     true | false

skills.enabled                                     bool     true | false
mcp.enabled                                        bool     true | false

agent_doc_scan.enabled                             bool     true | false   ← "系统能力定时扫描". NOT the same as proactive.enabled.
agent_doc_scan.interval_hours                      int      e.g. 24

proactive.enabled                                  bool     true | false
proactive.scan_interval_minutes                    int
proactive.quiet_hours.start                        string   "HH:MM" format
proactive.quiet_hours.end                          string   "HH:MM" format
proactive.max_messages_per_day                     int
proactive.min_gap_minutes                          int
proactive.triggers.event_followup.enabled          bool     true | false
proactive.triggers.event_followup.min_importance   float    0.0 – 1.0
proactive.triggers.event_followup.followup_after_hours  int
proactive.triggers.event_followup.max_age_days     int
proactive.triggers.strategy.enabled                bool     true | false
proactive.triggers.idle_checkin.enabled            bool     true | false
proactive.triggers.idle_checkin.idle_hours         int
```

Note: `api_key`, `bot_token`, `password`, `secret`, `token` fields cannot be set via `system_manage set_config` — edit settings.yaml directly with `file_read` + `file_write`.

---

## Database

- Engine: PostgreSQL
- Database name: `Riverse`
- Connection: read from `settings.yaml → database` section

Key tables:
| Table | Purpose |
|-------|---------|
| `conversation_turns` | All conversation history with AI summaries |
| `outsource_tasks` | Background task status and results |
| `user_profile` | Confirmed user facts |
| `observations` | Raw observations about the user |
| `finance_transactions` | Credit card / expense data |

<!-- END HANDWRITTEN: core -->

<!-- AUTO-GENERATED: system_overview -->
<!-- END AUTO-GENERATED: system_overview -->

<!-- AUTO-GENERATED: tools -->
<!-- END AUTO-GENERATED: tools -->

<!-- AUTO-GENERATED: agents -->
<!-- END AUTO-GENERATED: agents -->

<!-- AUTO-GENERATED: skills -->
<!-- END AUTO-GENERATED: skills -->
