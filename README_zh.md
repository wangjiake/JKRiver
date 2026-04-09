<p align="center">
  <img src="img/binary-wave-logo.svg" width="128" height="128" alt="Riverse Logo">
</p>

# Riverse

**为 AI 打造的个人记忆引擎 — 从每次对话中提取、管理、整理你的记忆。本地运行，兼容任意 LLM。**

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

*两个月前你提到换了工作。刚才你说最近老是头痛。*

<table>
<tr><th>没有 Riverse</th><th>有 Riverse</th></tr>
<tr>
<td>

🤖 很抱歉听到这个。头痛的常见原因：脱水、用眼过度、压力大……

<sub>和你的生活毫无关联。</sub>

</td>
<td>

🤖 你大概两个月前开始带团队了，差不多同一时间睡眠变差了——你好几次提到凌晨一点多才睡。头痛可能和这些有关。最近工作压力怎么样？

<sub>因果链：换工作 → 睡眠变差 → 头痛。有时间线意识，个人权重驱动。</sub>

</td>
</tr>
</table>

---

## 快速开始

```bash
mkdir jkriver && cd jkriver
curl -O https://raw.githubusercontent.com/wangjiake/JKRiver/main/docker/docker-compose.yaml
docker compose pull && docker compose up -d
docker logs jkriver-jkriver-1 2>&1 | grep "Token:"
```

在浏览器打开 `http://localhost:1234`，输入 Token，在 **System** 页面填写 API Key。完成。

| 服务 | 地址 | 功能 |
|------|------|------|
| **JKRiver** | http://localhost:1234 | 网页聊天 + 系统配置 |
| **RiverHistory** | http://localhost:2345 | 用户画像查看 |
| **API 文档** | http://localhost:8400/docs | REST API 参考 |

完整 Docker 指南（机器人、数据导入、Demo）：**[docker/README.md](docker/README.md)**

---

## 记忆引擎

每次对话结束后，Riverse 运行离线整理流水线（Sleep），构建结构化的个人画像：

- **多类型提取** — 事实、人际关系、有时效的事件分别独立追踪，各有自己的生命周期
- **置信度升级** — 事实从 `suspected`（猜测）开始，经多轮验证升级为 `confirmed`（确认）再到 `established`（稳固）
- **时间衰减** — 每条记忆携带 `decay_days` 生命周期，过期记忆自动失效，无需手动清理
- **失效与关闭** — 事实发生变化时，旧记录自动关闭并记录 `end_time`，被新事实取代；完整历史永久保留
- **矛盾检测与仲裁** — 冲突事实自动检测，由 LLM 仲裁解决
- **证据链** — 每条记忆关联产生它的原始对话
- **知识图谱** — 事实之间通过有类型的边连接（因果、时序、层级）

所有数据存储在本地 PostgreSQL，不离开你的设备。

---

## REST API

任意外部系统、Agent 或 LLM 都可以查询记忆：

| 接口 | 说明 |
|------|------|
| `GET /profile` | 当前确认的画像（类别、字段、值） |
| `GET /hypotheses` | 完整画像，含置信度和状态 |
| `POST /chat` | 发送消息；回复使用完整记忆上下文 |
| `POST /sleep` | 手动触发记忆整理 |
| `GET /health` | 服务健康检查 |

认证方式：每个请求携带 `X-Device-Token: <token>` 请求头。

---

## 为什么不用 RAG？

| | RAG / 现有 AI 记忆 | Riverse |
|---|---|---|
| **检索方式** | 向量相似度 — 找"看起来像"的文本 | 个人画像权重 — 按与*你*的相关性排序 |
| **时间线** | 没有时间线 — 3 年前和昨天一样权重 | 时间推移 — 事实有势能和衰减 |
| **推理** | 没有因果推理 — 事实是孤立碎片 | 因果链 — 相关事实自动关联 |
| **置信度** | 所有事实同等权重 | 猜测 → 确认 → 稳固 |
| **失效机制** | 无 — 旧事实永久存在 | 事实会过期、被取代或被否定 |
| **数据归属** | 云端依赖，平台所有 | 本地驱动 — 你的设备，你的数据 |

---

## Demo

Demo 包含 20 段与虚构人物的日常对话。从原始聊天记录：

[![原始对话](https://raw.githubusercontent.com/wangjiake/JKRiver/main/img/demo-raw-data.png)](https://raw.githubusercontent.com/wangjiake/JKRiver/main/img/demo-raw-data.png)

Riverse 提取出结构化的、持续演化的画像：

[![确认的事实](https://raw.githubusercontent.com/wangjiake/JKRiver/main/img/demo-profile-confirmed.png)](https://raw.githubusercontent.com/wangjiake/JKRiver/main/img/demo-profile-confirmed.png)
[![时间线 — 事实如何随时间变化](https://raw.githubusercontent.com/wangjiake/JKRiver/main/img/demo-profile-timeline.png)](https://raw.githubusercontent.com/wangjiake/JKRiver/main/img/demo-profile-timeline.png)
[![人际关系](https://raw.githubusercontent.com/wangjiake/JKRiver/main/img/demo-profile-relationships.png)](https://raw.githubusercontent.com/wangjiake/JKRiver/main/img/demo-profile-relationships.png)

---

## 内置 Agent

Riverse 附带一个完整的个人 AI Agent，直接消费记忆引擎：

- **多渠道** — 网页面板、Telegram、Discord、REST API、CLI
- **多模态** — 文本、语音、图片、文件
- **工具** — 网页搜索、财务追踪、健康同步（Withings）、TTS；在 System 页面可一键开关
- **YAML 技能** — 按关键词或 cron 定时触发自定义行为
- **任务 Agent** — 将复杂多步任务委托给自主子 Agent；执行前预览计划并确认

  [![任务计划预览](https://raw.githubusercontent.com/wangjiake/JKRiver/main/img/demo-outsource-plan.png)](https://raw.githubusercontent.com/wangjiake/JKRiver/main/img/demo-outsource-plan.png)
  [![任务结果](https://raw.githubusercontent.com/wangjiake/JKRiver/main/img/demo-outsource-result.png)](https://raw.githubusercontent.com/wangjiake/JKRiver/main/img/demo-outsource-result.png)

- **MCP 协议** — 接入 Gmail 等 MCP Server
- **外部 Agent** — 通过 `agents_*.yaml` 接入 Home Assistant、n8n、Dify
- **主动关怀** — 跟进重要事件，尊重静默时段

[![聊天界面](https://raw.githubusercontent.com/wangjiake/JKRiver/main/img/demo-chat-empty.png)](https://raw.githubusercontent.com/wangjiake/JKRiver/main/img/demo-chat-empty.png)
[![系统配置](https://raw.githubusercontent.com/wangjiake/JKRiver/main/img/demo-system.png)](https://raw.githubusercontent.com/wangjiake/JKRiver/main/img/demo-system.png)

---

## 从源码安装

```bash
git clone https://github.com/wangjiake/JKRiver.git
cd JKRiver
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

createdb -h localhost -U YOUR_USERNAME Riverse
psql -h localhost -U YOUR_USERNAME -d Riverse -f agent/schema.sql

cp settings.yaml.default settings.yaml
# 编辑 settings.yaml：设置 database.user 和 openai.api_key
python scripts/start_local.py
```

> 完整配置说明：**[wangjiake.github.io/riverse-docs](https://wangjiake.github.io/riverse-docs/zh/getting-started/configuration/)**

---

## 技术栈

| 层 | 技术 |
|---|---|
| 运行时 | Python 3.10+, PostgreSQL 16+ |
| 本地 LLM | Ollama（任意兼容模型） |
| 云端 LLM | 兼容任意 OpenAI 格式 API（OpenAI、DeepSeek、Groq 等） |
| 向量嵌入 | Ollama + 任意嵌入模型（安装 [pgvector](https://github.com/pgvector/pgvector) 后自动加速） |
| REST API | FastAPI + Uvicorn |
| Web 面板 | Flask |
| Telegram / Discord | python-telegram-bot / discord.py |
| 语音 / 图像 | Whisper-1, GPT-4 Vision, LLaVA |
| TTS | Edge TTS |

## 安全提示

Riverse 设计为**单用户本地运行**的应用。Web 面板通过首次启动时自动生成的 Access Token 保护。REST API（端口 8400）没有认证保护，请勿暴露到公网。如需远程访问，请使用反向代理（如 Nginx、Caddy）或 SSH 隧道。

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
