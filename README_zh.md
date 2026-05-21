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

## 2026 年 5 月更新

### 家庭多账号模式

JKRiver 现在支持单部署里多个家庭成员各自有自己独立的对话历史、画像、记忆、财务/健康数据，共享同一个 Postgres 库。从 **System → 家庭成员** 设置：

- **accounts 表** —— 把内部名（如 `wife`）映射到 `owner_id`。所有业务行（observations / profile / memory / finance 等）都按这个 id 隔离。
- **access_tokens 表** —— 每个设备一个 session token，SHA-256 hash 存库；同一个家庭成员可以同时绑老婆 iPhone、你的 iPad 等多个设备。
- **邀请流程** —— admin 在 System 页生成一次性邀请 URL（可带 QR 码），家人在自己设备打开 → 命名设备 → cookie 自动设好 → 登录完成。可在 settings.yaml 打开 `family.require_admin_approval` 让新设备需要 admin 审批。
- **IM 映射** —— `channel_identities` 把 Telegram/Discord 的 user_id 映射到 owner_id，老婆通过 Telegram 发来的消息自动归到她的账号，不会和你的混。
- **按 owner 跑 sleep** —— sleep 流水线现在按 owner 循环，每个家人有未处理对话就跑一轮，记忆/画像各自独立。
- **按 owner 计 token** —— LLM API 用量按 owner 记录，能看到谁花了多少 token。

### UI 改进

- **居中的 "zero-state" 聊天页** —— 新建会话时输入框居中显示并配蓝色径向光晕（仿 Gemini），不再是底部空空的对话框。
- **Gemini 风格发送按钮** —— 中性灰色药丸，输入框有内容时变蓝，图标用 Material `send`（纸飞机）。流式响应时停止按钮仍为红色。
- **服务端 i18n** —— 语言由服务端根据 `jk_lang` cookie 直接渲染，跨页跳转不再有英文文字闪一下被 JS 替换的现象。
- **首帧零闪烁** —— 侧栏折叠状态、zero-state 模式、亮/暗主题全部通过 `<head>` 同步脚本在首次绘制前就应用完。

### 数据库迁移

`migrations/` 下 12 个 SQL 文件覆盖多账号上线：`005_multi_owner.sql` 给 27 张业务表加 `owner_id` 列（已有数据默认填 1）；006-007 修唯一约束；008 删除遗留的 `hypotheses` 表（功能合并到 `user_profile.layer`）；009 把设备 token 改成 hash 存储 + 加设备元数据；010-012 覆盖 geoip、admin 审批、清理工作。迁移幂等，启动时自动跑。

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

### Sleep 流水线 — 14 步

整条流水线在一个数据库事务中原子执行。任何步骤失败，全部回滚。

| 阶段 | 步骤 | 做什么 |
|------|------|-------|
| **提取** | 1. 加载初始数据 | 加载现有画像和人生轨迹 |
| | 2. 提取会话 | LLM 从每段未处理的对话中提取观察、标签、人际关系和事件 |
| **分析** | 3. 行为分析 | LLM 从观察中推断行为模式（如"深夜发消息"→"夜猫子"）；生成澄清策略 |
| | 4. 分类与整合 | LLM 将每条观察分类为 `support`（支持）、`contradict`（矛盾）、`evidence_against`（反向证据）或 `new`（新发现）；整合进画像 |
| | 5. 交叉验证 | `stated` 来源 + 提及次数 ≥ 2 的猜测事实自动确认；其余猜测事实结合时间线和对话历史进行 LLM 交叉验证 |
| | 6. 矛盾仲裁 | LLM 对矛盾事实对（取代链）进行裁决——接受新事实或驳回新事实 |
| **维护** | 7. 提取边 | 为受影响的事实构建知识图谱边 |
| | 8. 过期处理 | 关闭超过 `expires_at` 的事实；为下次对话生成验证策略 |
| | 9. 成熟度衰减 | 根据事实年龄和证据数量调整 `decay_days`——长期存在且证据充分的事实获得更长寿命（最长 2 年） |
| **输出** | 10. 用户模型 | LLM 从对话中分析沟通风格维度 |
| | 11. 轨迹 | 检测到重大变化时更新人生阶段轨迹 |
| | 12. 整合去重 | 对画像进行去重整理 |
| | 13. 快照 | 预编译记忆快照（画像 + 模型 + 事件 + 关系 + 知识图谱），供下次对话快速加载 |
| | 14. 完成 | 标记对话为已处理 |

事务结束后运行非关键后处理：向量嵌入和记忆聚类。

### 算法先行的设计理念

Riverse 的记忆流水线在架构设计上超前于当前通用 LLM 的能力。14 步 Sleep 整合流程需要在每一步做出精确的结构化判断——观察提取、事实分类、交叉验证、矛盾仲裁——目前准确率的主要瓶颈是 LLM 输出的精度，而非算法本身。

目前没有任何 LLM 是专门为个人记忆整合训练的。理想路径是训练一个专用的记忆 LLM，针对结构化画像提取和多事实推理进行优化。作者对这个模型应该长什么样有清晰的设计，但训练它需要个人开发者无法获得的算力和数据资源。

如果你的公司正在做记忆相关的模型，或者在做个人 AI 方向，有合适的岗位的话，欢迎联系我：[mailwangjk@gmail.com](mailto:mailwangjk@gmail.com)

在此之前，算法运行在通用模型之上，并随着每一代更强模型的出现自动提升，无需改动一行代码。这条流水线也是一个实用的基准：如果提取错误率较高，原因几乎总是 LLM 的能力，而非系统 Bug。换一个更强的模型试试，效果会立竿见影。

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
