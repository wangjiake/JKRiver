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
## System Overview (Current State)

- **Language**: zh
- **Timezone**: ?
- **LLM Provider**: openai
- **Model**: gpt-4o @ https://api.openai.com
- **Remote Fallback (远端兜底)**: ❌ disabled

**Tools status:**
- `web_search`: ✅ enabled (backend: duckduckgo)
- `dispatch_task`: ✅ enabled (mode: strict)
- `shell_exec`: ✅ enabled
- `file_read`: ✅ enabled
- `finance_query`: ❌ disabled
- `health_query`: ❌ disabled
- `image_describe`: ❌ disabled
- `voice_transcribe`: ❌ disabled
- `tts`: ✅ enabled

**Bots:**
- Telegram: ❌ disabled
- Discord: ❌ disabled

**Other features:**
- Proactive messaging: ❌ disabled
- Embedding/vector search: ❌ disabled
- Skills: ✅ enabled
- MCP servers: ❌ disabled
<!-- END AUTO-GENERATED: system_overview -->

<!-- AUTO-GENERATED: tools -->
## Available Tools

### `ask_user` (enabled)
向用户提问并等待回复。当你需要确认才能继续时使用，例如：本地还是远端、用哪个分支、是否覆盖文件等。

Parameters:
- `question` `(string)`: 向用户提出的问题

### `dispatch_task` (enabled)
将复杂任务外包给自主子智能体执行。
必须按两步走：
  第一步：action='preview' + 任务描述 → 生成执行计划。你必须将工具返回内容原样输出给用户，禁止概括、改写或用自己的话替代。
  第二步：用户确认后：action='start' + task_id → 后台开始执行。
禁止跳过预览步骤，禁止未经用户确认就开始执行，禁止改写计划内容。

Parameters:
- `action`: 'preview' 生成计划，'start' 开始执行
- `task`: 任务描述（preview 时必填）
- `task_id`: preview 返回的任务号（start 时必填）

### `file_list` (enabled)
列出目录的直接内容（单层，非递归）。返回子目录（以 / 结尾）和文件（附文件大小，单位 bytes），末尾附汇总行：`N 个目录，M 个文件`。递归列目录或按条件筛选请用 grep 或 shell_exec（find）。

Parameters:
- `path` `(string)`: 要列出的目录路径（string，默认：当前工作目录）

### `file_read` (enabled)
读取本地文本文件内容。支持 .txt/.py/.yaml/.json/.md/.log 等格式，大文件自动截断。

Parameters:
- `path` `(string)`: 文件路径（string，支持绝对路径或相对路径）

### `file_write` (enabled)
将文本内容写入本地文件。文件不存在时自动创建，已存在时直接覆盖（无确认提示）。父级目录不存在时自动创建。写入路径限制在当前工作目录和 /tmp 内。

Parameters:
- `path` `(string)`: 要写入的文件路径（string，绝对路径或相对路径）
- `content` `(string)`: 要写入文件的文本内容（string，UTF-8 编码）

### `finance_query` (disabled)
查询用户信用卡/银行卡消费记录，支持按年月、商家关键词筛选。返回全部匹配记录及合计金额。

Parameters:
- `year` `(int)`: 年份（int，可选，如 2025）
- `month` `(int)`: 月份（int，可选，如 3 表示3月）
- `merchant` `(string)`: 商家名关键词（string，可选，如 Amazon）

### `grep` (enabled)
使用正则表达式在文件中搜索内容。返回格式为 `文件名:行号: 内容`。最多返回 100 行，超出时末尾附加截断提示。建议用 file_glob 限定文件类型（如 '*.py'），避免扫描二进制文件。

Parameters:
- `pattern` `(string)`: 要搜索的正则表达式（必填）
- `path` `(string)`: 搜索目录或文件路径（string，默认：当前工作目录）
- `file_glob` `(string)`: 限定搜索范围的 glob 模式（string，默认：* 匹配所有文件），如 '*.py'、'*.yaml'

### `health_query` (disabled)
查询用户体重、体脂、步数等健康数据，返回最近90天全部记录。

Parameters:
- `data_type` `(string)`: 数据类型（string）：weight（体重）| fat（体脂）| activity（步数/活动）| all（全部）

### `image_describe` (enabled)
分析图片内容并回答问题。支持识别物体、场景、文字、图表、截图等。可提供具体问题以获得针对性分析。

Parameters:
- `file_path` `(string)`: 图片文件路径（支持 jpg/png/gif/webp）
- `question` `(string)`: 关于图片的具体问题（可选，默认描述图片全部内容）

### `shell_exec` (enabled)
执行 shell 命令并返回输出。允许：ls/cat/head/tail/find/grep/wc/date/df/du、git status/log/diff/branch/remote、python/pip/node/npm 版本查看。安装命令（pip install、npm install）需先通过 ask_user 获得用户确认。禁止：rm、sudo、dd、mkfs 及含 ;|&`$> 的命令。

Parameters:
- `command` `(string)`: 要执行的 shell 命令（string）

### `system_manage` (enabled)
管理 AI 系统：查看/开关工具，安装/开关/删除技能，切换智能体，读写配置。

可用操作及参数：
  list_tools       — 无需参数。返回所有工具及其启用状态。
  toggle_tool      — name: 工具名如 'web_search'; enabled: 'true'/'false'。
  list_skills      — 无需参数。
  create_skill     — name: 技能名; content: YAML 技能定义。
  toggle_skill     — name: 技能名; enabled: 'true'/'false'。
  delete_skill     — name: 技能名。
  list_agents      — 无需参数。
  toggle_agent     — name: 智能体名; enabled: 'true'/'false'。
  get_config       — key: 点分路径，如 'tools.web_search.backend'。
  set_config       — key: 点分路径; value: 新值。
                     不可设置: api_key, bot_token, password, secret, token。
  restart          — 无需参数。重启服务使配置生效。
                     修改 settings.yaml 后必须调用此操作。
  update_agent_doc — 无需参数。扫描所有工具/智能体/技能，更新 AGENT.md，
                     让 AI 获得最新的系统能力说明。

Parameters:
- `action` `(string)`: list_tools | toggle_tool | list_skills | create_skill | toggle_skill | delete_skill | list_agents | toggle_agent | get_config | set_config | restart | update_agent_doc
- `name` `(string)`: 工具/技能/智能体名称（toggle/delete/create 时必填）
- `enabled` `(bool)`: 'true' 或 'false'（toggle 操作时必填）
- `content` `(string)`: YAML 格式的技能定义（create_skill 时必填）
- `key` `(string)`: 点分路径配置键，如 'tools.web_search.backend'（get/set_config 时必填）
- `value` `(bool|int|float|string)`: 新的配置值（set_config 时必填）

### `tts` (disabled)
将 AI 文字回复自动合成语音发送给用户。由系统在每次回复后自动调用，无需手动触发。自动识别中英文并切换对应音色。超过 max_chars 的内容会被截断。

### `voice_transcribe` (enabled)
将语音/音频文件转写为文字。支持 mp3/wav/ogg/m4a 等常见格式。

Parameters:
- `file_path` `(string)`: 音频文件路径（string，支持 mp3/wav/ogg/m4a 等）

### `web_search` (enabled)
搜索互联网获取实时信息：当前天气、突发新闻、实时价格、最新事件等。当答案需要最新数据时使用（如今天天气、最新发布、当前汇率）。对于稳定的知识性问题无需搜索。

Parameters:
- `query` `(string)`: 自然语言搜索词（越具体结果越准确）
<!-- END AUTO-GENERATED: tools -->

<!-- AUTO-GENERATED: agents -->
## Available Agents

Switch agents via `system_manage` with `action="toggle_agent"`.

### `weather_query` (disabled)
查询全球任意城市的实时天气（温度、湿度、风速、天气状况）

Example triggers: "东京现在天气怎么样" / "北京今天多少度" / "伦敦下雨了吗"

### `home_lights` (disabled)
控制家里的灯光（开关、亮度、颜色）

Example triggers: "把客厅灯打开" / "关掉卧室的灯" / "把灯调到50%"

### `home_status` (disabled)
查询家中设备状态（温度传感器、门窗、灯光等）

Example triggers: "客厅现在多少度" / "前门关了吗" / "空调开着吗"

### `n8n_email` (disabled)
通过 n8n 工作流发送邮件

Example triggers: "发封邮件给张三" / "帮我发个邮件通知一下"

### `n8n_workflow` (disabled)
触发 n8n 自定义工作流（通用）

Example triggers: "运行数据备份流程" / "执行日报生成"

### `dify_agent` (disabled)
调用 Dify 子 agent 处理复杂任务（研究、分析、写作等）

Example triggers: "帮我研究一下这个话题" / "分析这段数据"

### `system_info` (disabled)
查看本机系统信息（CPU、内存、磁盘使用率）

Example triggers: "查看本机系统信息" / "查看系统信息" / "电脑内存还剩多少"

### `httpbin_echo` (disabled)
HTTP echo 测试工具，将参数原样返回（用于调试 agent 链路）

Example triggers: "测试一下 agent 连通性" / "echo hello"
<!-- END AUTO-GENERATED: agents -->

<!-- AUTO-GENERATED: skills -->
## Available Skills

Skills are auto-detected by the AI based on trigger keywords or schedules.

### `explain_code` (enabled, built-in)
用户发代码时自动提供逐行解释
Trigger keywords: 解释代码, explain code, 这段代码什么意思, 帮我看看这段代码

### `weekly_summary` (enabled, built-in)
每周日晚上发送温馨周末问候
Schedule: `0 20 * * 0`
<!-- END AUTO-GENERATED: skills -->
