<p align="center">
  <img src="img/binary-wave-logo.svg" width="128" height="128" alt="Riverse Logo">
</p>

# Riverse — 河流算法

**为个人终端设计的 AI Agent — 持久记忆，离线认知，越用越懂你。所有数据存在本地。**

**[English](README.md)** | **[中文](README_zh.md)** | **[日本語](README_ja.md)**

[![CI](https://github.com/wangjiake/JKRiver/actions/workflows/ci.yml/badge.svg)](https://github.com/wangjiake/JKRiver/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/riverse?logo=pypi&logoColor=white)](https://pypi.org/project/riverse/)
![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white)
![License: AGPL-3.0 + Commercial](https://img.shields.io/badge/License-AGPL--3.0%20%2B%20Commercial-green)

[![X (Twitter)](https://img.shields.io/badge/X-@JKRiverse-000000?logo=x&logoColor=white)](https://x.com/JKRiverse)
[![Discord](https://img.shields.io/badge/Discord-Join-5865F2?logo=discord&logoColor=white)](https://discord.gg/ZnmFrPvXym)
[![Docs](https://img.shields.io/badge/文档-wangjiake.github.io-06b6d4?logo=readthedocs&logoColor=white)](https://wangjiake.github.io/riverse-docs/zh/)

📖 **完整文档：[wangjiake.github.io/riverse-docs](https://wangjiake.github.io/riverse-docs/zh/)**

---

## RAG 记忆 vs. 河流算法

为什么相似度检索做不好个人 AI。

| | RAG / 现有 AI 记忆 | Riverse / 河流算法 |
|---|---|---|
| **检索方式** | 关键词 / 向量相似度 — 找"看起来像"的文本 | 个人画像权重 — 按与*你*的相关性排序 |
| **时间线** | 没有时间线 — 3 年前和昨天一样权重 | 时间推移 — 近期事件有势能，旧模式自然固化或消退 |
| **推理** | 没有因果推理 — "头痛"和"换工作"是孤立碎片 | 因果链 — "换工作 → 压力 → 睡眠差 → 头痛"自动关联 |
| **置信度** | 所有事实同等权重 | 观察逐步升级：猜测 → 确认 → 稳固 |
| **数据归属** | 云端依赖，平台所有 | 本地驱动 — 你的设备，你的数据 |

### 💬 场景：你说"最近老是头痛"

*两个月前，你提到过换了工作。*

<table>
<tr><th>RAG 方式</th><th>河流算法</th></tr>
<tr>
<td>

🧑 最近老是头痛

🤖 很抱歉听到这个。头痛的常见原因包括：脱水、用眼过度、压力大……需要一些缓解建议吗？

<sub>向量搜索在医疗问答库中匹配了"头痛"。和你的生活毫无关联。</sub>

</td>
<td>

🧑 最近老是头痛

🤖 你大概两个月前开始带团队了，差不多同一时间睡眠变差了——你好几次提到凌晨一点多才睡。头痛可能和这些有关。最近工作压力怎么样？要不要我把这个记录成一个健康趋势持续追踪？

<sub>因果链：换工作 → 睡眠变差 → 头痛。有时间线意识，个人权重驱动。</sub>

</td>
</tr>
</table>

---

## 什么是 Riverse？

你和 AI 聊了这么久，但每个 AI 都不认识你。换一个平台，一切从零开始。你的数据散落在各个云端，不属于你。

Riverse 是一个运行在你自己机器上的个人 AI Agent。它记住每一次对话，在对话结束后像人类睡眠一样离线整理记忆 — 提取你的性格、偏好、经历、人际关系，构建一个持续成长的你的画像。聊得越多，它越懂你。所有数据存在本地，归你所有。

## 河流算法

对话像水流，关键信息像河床泥沙一样沉淀，经过多轮验证逐步从"猜测"升级为"确认"再到"稳固"。离线整理（Sleep）则是河流的自净过程。

```
对话流入 ──→ 冲刷 ──→ 沉淀 ──→ 塑造认知 ──→ 继续流动
              │         │         │
              │         │         └─ 确认的认知 → 稳固的河床
              │         └─ 重要信息 → 观察记录、假设、画像
              └─ 矛盾的旧认知被冲走，新的洞察取而代之
```

- **水流（Flow）** — 每次对话都是流经的水。河流永不停歇，对你的理解持续演化，从不重置
- **沉淀（Sediment）** — 关键信息像泥沙一样沉淀：事实沉入画像，情绪沉入观察，规律沉入假设
- **自净（Purify）** — Sleep 像河流的自净能力：冲走过时的信息，解决矛盾，将碎片整合为完整理解

## 特性

- **持久记忆** — 跨会话记忆，构建随你演化的用户画像
- **离线整理（Sleep）** — 对话结束后自动提炼认知、解决矛盾
- **多模态输入** — 文本、语音、图片、文件，原生理解
- **可插拔工具** — 网页搜索、财务追踪、健康同步（Withings）、TTS 等
- **YAML 技能** — 按关键词或 cron 定时触发自定义行为
- **外部 Agent** — 通过 `agents_*.yaml` 接入 Home Assistant、n8n、Dify 等
- **MCP 协议** — 支持 Model Context Protocol，接入 Gmail 等 MCP Server
- **多渠道** — Telegram、Discord、REST API、WebSocket、CLI、Web 仪表盘
- **本地优先** — 默认 Ollama，质量不足时自动升级到 OpenAI / DeepSeek
- **主动关怀** — 跟进重要事件、空闲问候、策略提醒，尊重静默时段
- **语义搜索** — BGE-M3 向量嵌入，按语义而非关键词检索相关记忆
- **多语言提示词** — 内置中文、英文、日文提示词，一键切换

> **关于准确性：** 目前没有任何 LLM 是专门为个人画像提取训练的，提取结果可能偶尔偏差。发现不准确时可以在 Web 面板中**拒绝**或**关闭**。随着对话积累，河流算法会通过多轮验证和矛盾检测不断自我修正。

---

## 快速开始

### 方式一：Docker Compose（推荐）

最快上手方式，不需要安装 Python 和 PostgreSQL。

```bash
git clone https://github.com/wangjiake/JKRiver.git
cd JKRiver/docker
cp .env.example .env       # 编辑 .env — 填入 API 密钥
docker compose up -d
```

Web 面板 `http://localhost:2345`，API 地址 `http://localhost:8400/docs`。

完整 Docker 指南（聊天机器人、数据导入、Demo、配置说明）：**[docker/README.md](docker/README.md)**

---

### 方式二：从源码安装

#### 1. 前置要求

- **Python 3.10+**
- **PostgreSQL 16+** — [安装指南](https://www.postgresql.org/download/)
- **Ollama**（可选）— [ollama.ai](https://ollama.ai)，仅本地模型模式需要

#### 2. 克隆并安装依赖

```bash
git clone https://github.com/wangjiake/JKRiver.git
cd JKRiver
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

#### 3. 配置 PostgreSQL

```bash
# 创建数据库（把 YOUR_USERNAME 替换为你的 PostgreSQL 用户名）
createdb -h localhost -U YOUR_USERNAME Riverse

# 创建所有表
psql -h localhost -U YOUR_USERNAME -d Riverse -f agent/schema.sql
```

> **提示：** macOS/Linux 终端运行 `whoami` 查看用户名。Windows 默认 PostgreSQL 用户通常是 `postgres`。

#### 4. 编辑配置

```bash
cp settings.yaml.default settings.yaml
```

编辑 `settings.yaml`，至少修改以下内容：

```yaml
database:
    user: "YOUR_USERNAME"               # 你的 PostgreSQL 用户名

llm_provider: "openai"                  # "openai" 用云端 API，"local" 用本地 Ollama
openai:
    api_key: "sk-your-key-here"         # 使用 openai 时必填
```

> 完整配置说明：**[wangjiake.github.io/riverse-docs](https://wangjiake.github.io/riverse-docs/zh/getting-started/configuration/)**

#### 5. 启动

```bash
python -m agent.main                    # CLI 模式
python -m agent.telegram_bot            # Telegram Bot
python -m agent.discord_bot             # Discord Bot
python web.py                           # Web 面板 (http://localhost:1234)
```

### 测试

```bash
# 快速检查 — 验证模块导入和数据库表结构（不需要 LLM）
python tests/test_imports.py
python tests/test_db.py

# 端到端流水线测试 — 需要 LLM + 数据库
python tests/test_demo_pipeline.py                          # demo2.json（52 组会话，英文）
python tests/test_demo_pipeline.py tests/data/demo.json     # demo.json （50 组会话，中文）
python tests/test_demo_pipeline.py --sessions 3             # 快速冒烟测试（仅 3 组会话）

# 清理测试数据
python tests/test_demo_pipeline.py --clean
```

测试数据已包含在 `tests/data/` 中，无需额外依赖。

## 技术栈

| 层 | 技术 |
|---|---|
| 运行时 | Python 3.10+, PostgreSQL 16+ |
| 本地 LLM | Ollama（任意兼容模型） |
| 云端 LLM | OpenAI GPT-4o / DeepSeek（兜底） |
| 向量嵌入 | Ollama + BGE-M3（安装 [pgvector](https://github.com/pgvector/pgvector) 后自动加速） |
| REST API | FastAPI + Uvicorn |
| Web 仪表盘 | Flask |
| Telegram / Discord | python-telegram-bot / discord.py |
| 语音 / 图像 | Whisper-1, GPT-4 Vision, LLaVA |
| TTS | Edge TTS |

## 安全提示

Riverse 设计为**单用户本地运行**的应用。REST API 和 Web 面板**没有内置认证**，请勿将其暴露到公网。如需远程访问，请通过反向代理（如 Nginx、Caddy）添加认证，或使用 SSH 隧道。

---

## 许可证

| 用途 | 协议 |
|---|---|
| 个人使用 / 开源项目 | [AGPL-3.0](LICENSE) — 免费使用，修改后必须开源 |
| 商业使用 / 闭源集成 | 联系 mailwangjk@gmail.com |

## 联系方式

- **X (Twitter):** [@JKRiverse](https://x.com/JKRiverse)
- **Discord:** [加入](https://discord.gg/ZnmFrPvXym)
- **Email:** mailwangjk@gmail.com
