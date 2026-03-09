<p align="center">
  <img src="img/binary-wave-logo.svg" width="128" height="128" alt="Riverse Logo">
</p>

# Riverse — 河流アルゴリズム（River Algorithm）

**個人デバイスのために設計された AI エージェント — 永続的な記憶、オフライン認知、使うほどあなたを理解する。すべてのデータはローカルに保存。**

**[English](README.md)** | **[中文](README_zh.md)** | **[日本語](README_ja.md)**

[![CI](https://github.com/wangjiake/JKRiver/actions/workflows/ci.yml/badge.svg)](https://github.com/wangjiake/JKRiver/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/riverse?logo=pypi&logoColor=white)](https://pypi.org/project/riverse/)
![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white)
![License: AGPL-3.0 + Commercial](https://img.shields.io/badge/License-AGPL--3.0%20%2B%20Commercial-green)

[![X (Twitter)](https://img.shields.io/badge/X-@JKRiverse-000000?logo=x&logoColor=white)](https://x.com/JKRiverse)
[![Discord](https://img.shields.io/badge/Discord-Join-5865F2?logo=discord&logoColor=white)](https://discord.gg/ZnmFrPvXym)
[![Docs](https://img.shields.io/badge/ドキュメント-wangjiake.github.io-06b6d4?logo=readthedocs&logoColor=white)](https://wangjiake.github.io/riverse-docs/ja/)

📖 **ドキュメント：[wangjiake.github.io/riverse-docs](https://wangjiake.github.io/riverse-docs/ja/)**

---

## RAG メモリ vs. 河流アルゴリズム

なぜ類似度検索ではパーソナル AI に不十分なのか。

| | RAG / 既存 AI メモリ | Riverse / 河流アルゴリズム |
|---|---|---|
| **検索方式** | キーワード / ベクトル類似度 — 「似ている」テキストを検索 | パーソナルプロフィール重み付け — *あなた*との関連性で順位付け |
| **タイムライン** | タイムラインなし — 3年前と昨日が同じ重み | 時間推移 — 最近の出来事は勢いを持ち、古いパターンは自然に固化・消退 |
| **推論** | 因果推論なし — 「頭痛」と「転職」は孤立した断片 | 因果チェーン — 「転職 → ストレス → 睡眠障害 → 頭痛」を自動接続 |
| **確信度** | すべての事実が同じ重み | 観察が段階的に昇格：推測 → 確認 → 確立 |
| **データ所有** | クラウド依存、プラットフォーム所有 | ローカルファースト — あなたのデバイス、あなたのデータ |

### 💬 シナリオ：「最近ずっと頭痛がする」と言った場合

*2ヶ月前、転職したことを話していた。*

<table>
<tr><th>RAG アプローチ</th><th>河流アルゴリズム</th></tr>
<tr>
<td>

🧑 最近ずっと頭痛がするんだ

🤖 それは大変ですね。頭痛の一般的な原因には、脱水、画面の見すぎ、ストレスなどがあります。対処法をお伝えしましょうか？

<sub>ベクトル検索が医療Q&Aで「頭痛」を検出。あなたの生活との関連なし。</sub>

</td>
<td>

🧑 最近ずっと頭痛がするんだ

🤖 2ヶ月ほど前に新しいマネージャー職に就いたよね。ちょうど同じ頃から睡眠が悪くなっていて、深夜1時過ぎまで起きていると何度か話してくれた。頭痛はそれと関連しているかもしれない。最近の仕事のプレッシャーはどう？健康パターンとして追跡しようか？

<sub>因果チェーン：転職 → 睡眠障害 → 頭痛。タイムライン認識、パーソナル重み付け。</sub>

</td>
</tr>
</table>

---

## Riverse とは？

長年 AI と会話してきたのに、どの AI もあなたを知りません。プラットフォームを変えればゼロからやり直し。あなたのデータはあちこちのクラウドに散らばり、あなたのものではありません。

Riverse はあなた自身のマシンで動くパーソナル AI エージェントです。すべての会話を記憶し、人間の睡眠のようにオフラインで記憶を整理 — 性格、好み、経験、人間関係を抽出し、継続的に成長するプロフィールを構築します。会話が増えるほど、より深くあなたを理解します。すべてのデータはローカルに保存。

## 河流アルゴリズム

会話は水の流れ、重要な情報は河床の堆積物のように沈殿し、複数ターンの検証を経て「推測」から「確認」へ、さらに「確立」へと段階的に昇格します。オフライン整理（Sleep）は河の自浄作用です。

```
会話が流入 ──→ 浸食 ──→ 堆積 ──→ 認知を形成 ──→ 流れ続ける
                │         │         │
                │         │         └─ 確認された認知 → 安定した岩盤
                │         └─ 重要な情報 → 観察・仮説・プロフィール
                └─ 矛盾する古い認識は洗い流され、新たな洞察に置き換わる
```

- **流れ（Flow）** — すべての会話は流れる水。川は止まらず、あなたへの理解は進化し続ける
- **堆積（Sediment）** — 重要情報は沈泥のように堆積：事実はプロフィールに、感情は観察に、パターンは仮説に
- **自浄（Purify）** — Sleep は川の自浄能力：古い情報を洗い流し、矛盾を解消し、断片を統合して一貫した理解へ

## 特徴

- **永続的な記憶** — セッションを超えて記憶し、あなたと共に進化するプロファイルを構築
- **オフライン整理（Sleep）** — 洞察の抽出、矛盾の解消、確認済み知識の強化
- **マルチモーダル入力** — テキスト、音声、画像、ファイルをネイティブに理解
- **プラガブルツール** — 財務追跡、健康同期（Withings）、Web検索、TTS など
- **YAML スキル** — キーワードまたはスケジュールでトリガーするカスタム動作
- **外部エージェント** — `agents_*.yaml` で Home Assistant、n8n、Dify 等を接続
- **MCP プロトコル** — Model Context Protocol 対応、Gmail 等の MCP Server を接続
- **マルチチャネル** — Telegram、Discord、REST API、WebSocket、CLI、Web ダッシュボード
- **ローカルファースト** — デフォルトは Ollama、必要時に OpenAI / DeepSeek へ自動エスカレーション
- **プロアクティブ** — イベントフォローアップ、アイドルチェックイン、静寂時間帯を尊重
- **セマンティック検索** — BGE-M3 ベクトル埋め込み、意味で関連する記憶を検索
- **多言語プロンプト** — 英語・中国語・日本語を内蔵、設定一つで切り替え

> **精度について：** 現在、個人プロファイル抽出に特化して訓練された LLM は存在しないため、結果に誤りが含まれる場合があります。Web ダッシュボードで**拒否**または**クローズ**できます。会話が蓄積されるにつれ、河流アルゴリズムがマルチターン検証と矛盾検出により継続的に自己修正します。

---

## クイックスタート

### 方法A：Docker Compose（推奨）

最も簡単な方法です。Python や PostgreSQL のインストールは不要です。

```bash
git clone https://github.com/wangjiake/JKRiver.git
cd JKRiver/docker
cp .env.example .env       # .env を編集 — API キーを設定
docker compose up -d
```

Web ダッシュボード `http://localhost:2345`、API `http://localhost:8400/docs`。

Docker 完全ガイド（チャットボット、データインポート、デモ、設定）：**[docker/README.md](docker/README.md)**

---

### 方法B：ソースから

#### 1. 前提条件

- **Python 3.10+**
- **PostgreSQL 16+** — [インストールガイド](https://www.postgresql.org/download/)
- **Ollama**（オプション）— [ollama.ai](https://ollama.ai)、ローカル LLM モードの場合のみ必要

#### 2. クローンとインストール

```bash
git clone https://github.com/wangjiake/JKRiver.git
cd JKRiver
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

#### 3. PostgreSQL のセットアップ

```bash
# データベースを作成（YOUR_USERNAME を PostgreSQL ユーザー名に置き換えてください）
createdb -h localhost -U YOUR_USERNAME Riverse

# 全テーブルを作成
psql -h localhost -U YOUR_USERNAME -d Riverse -f agent/schema.sql
```

> **ヒント：** macOS/Linux では `whoami` でユーザー名を確認できます。Windows のデフォルト PostgreSQL ユーザーは通常 `postgres` です。

#### 4. 設定

```bash
cp settings.yaml.default settings.yaml
```

`settings.yaml` を編集 — 最低限以下を変更：

```yaml
database:
    user: "YOUR_USERNAME"               # PostgreSQL ユーザー名

llm_provider: "openai"                  # "openai" = クラウド API、"local" = ローカル Ollama
openai:
    api_key: "sk-your-key-here"         # openai プロバイダー使用時は必須
```

> 完全な設定ガイド：**[wangjiake.github.io/riverse-docs](https://wangjiake.github.io/riverse-docs/ja/getting-started/configuration/)**

#### 5. 起動

```bash
python -m agent.main                    # CLI モード
python -m agent.telegram_bot            # Telegram Bot
python -m agent.discord_bot             # Discord Bot
python web.py                           # Web ダッシュボード (http://localhost:1234)
```

### テスト

```bash
# クイックチェック — モジュールインポートとDBスキーマの検証（LLM不要）
python tests/test_imports.py
python tests/test_db.py

# エンドツーエンドパイプラインテスト — LLM + データベースが必要
python tests/test_demo_pipeline.py                          # demo2.json（52セッション、英語）
python tests/test_demo_pipeline.py tests/data/demo.json     # demo.json （50セッション、中国語）
python tests/test_demo_pipeline.py --sessions 3             # クイックスモークテスト（3セッションのみ）

# テストデータをデータベースからクリーンアップ
python tests/test_demo_pipeline.py --clean
```

テストデータは `tests/data/` に含まれています。外部依存は不要です。

## 技術スタック

| レイヤー | 技術 |
|---|---|
| ランタイム | Python 3.10+, PostgreSQL 16+ |
| ローカル LLM | Ollama（任意の互換モデル） |
| クラウド LLM | OpenAI GPT-4o / DeepSeek（フォールバック）|
| 埋め込み | Ollama + BGE-M3（[pgvector](https://github.com/pgvector/pgvector) インストール時に自動高速化） |
| REST API | FastAPI + Uvicorn |
| Web ダッシュボード | Flask |
| Telegram / Discord | python-telegram-bot / discord.py |
| 音声 / 画像 | Whisper-1, GPT-4 Vision, LLaVA |
| TTS | Edge TTS |

## セキュリティに関する注意

Riverse は**シングルユーザー・ローカル実行**を前提とした設計です。REST API と Web ダッシュボードには**認証機能が組み込まれていません**。公開インターネットには絶対に公開しないでください。リモートアクセスが必要な場合は、リバースプロキシ（Nginx、Caddy など）で認証を追加するか、SSH トンネルを使用してください。

---

## ライセンス

| 用途 | ライセンス |
|---|---|
| 個人利用 / オープンソース | [AGPL-3.0](LICENSE) — 無料利用可、変更はオープンソース必須 |
| 商用 / クローズドソース | mailwangjk@gmail.com まで連絡 |

## お問い合わせ

- **X (Twitter):** [@JKRiverse](https://x.com/JKRiverse)
- **Discord:** [参加](https://discord.gg/ZnmFrPvXym)
- **Email:** mailwangjk@gmail.com
