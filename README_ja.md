<p align="center">
  <img src="img/binary-wave-logo.svg" width="128" height="128" alt="Riverse Logo">
</p>

# Riverse

**AI のための個人記憶エンジン — すべての会話から記憶を抽出・管理・整理する。ローカル実行、任意の LLM に対応。**

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

*2ヶ月前、転職したことを話していた。今「最近ずっと頭痛がする」と言った。*

<table>
<tr><th>Riverse なし</th><th>Riverse あり</th></tr>
<tr>
<td>

🤖 それは大変ですね。頭痛の一般的な原因には、脱水、画面の見すぎ、ストレスなどがあります……

<sub>あなたの生活との関連なし。</sub>

</td>
<td>

🤖 2ヶ月ほど前に新しいマネージャー職に就いたよね。ちょうど同じ頃から睡眠が悪くなっていて、深夜1時過ぎまで起きていると何度か話してくれた。頭痛はそれと関連しているかもしれない。最近の仕事のプレッシャーはどう？

<sub>因果チェーン：転職 → 睡眠障害 → 頭痛。タイムライン認識、パーソナル重み付け。</sub>

</td>
</tr>
</table>

---

## クイックスタート

```bash
mkdir jkriver && cd jkriver
curl -O https://raw.githubusercontent.com/wangjiake/JKRiver/main/docker/docker-compose.yaml
docker compose pull && docker compose up -d
docker logs jkriver-jkriver-1 2>&1 | grep "Token:"
```

ブラウザで `http://localhost:1234` を開き、トークンを入力後 **System** ページで API キーを設定。完了。

| サービス | URL | 役割 |
|---------|-----|------|
| **JKRiver** | http://localhost:1234 | Web チャット + システム設定 |
| **RiverHistory** | http://localhost:2345 | プロフィール閲覧 |
| **API ドキュメント** | http://localhost:8400/docs | REST API リファレンス |

Docker 完全ガイド（ボット、データインポート、デモ）：**[docker/README.md](docker/README.md)**

---

## 記憶エンジン

会話のたびにオフライン整理パイプライン（Sleep）が実行され、構造化された個人プロファイルを構築します：

- **マルチタイプ抽出** — 事実・人間関係・期限付きイベントをそれぞれ独立して追跡し、独自のライフサイクルで管理
- **信頼度の昇格** — 事実は `suspected`（推測）から始まり、複数ターンの検証を経て `confirmed`（確認）、`established`（確立）へと昇格
- **時間的な減衰** — 各事実は `decay_days` の TTL を持ち、古くなった事実は自動的に失効。手動クリーンアップ不要
- **無効化と上書き** — 事実が変わると古いレコードに `end_time` が記録され、新しい事実に置き換わる。履歴は完全に保持
- **矛盾の検出と仲裁** — 競合する事実は自動検出され、LLM による仲裁で解消
- **証拠チェーン** — すべての事実はそれを生んだ会話に紐付けられる
- **知識グラフ** — 事実は型付きエッジ（因果・時系列・階層）で互いに接続

すべてのデータはローカルの PostgreSQL に保存。デバイスの外には出ない。

---

## REST API

外部システム・Agent・LLM から記憶をクエリできます：

| エンドポイント | 説明 |
|--------------|------|
| `GET /profile` | 現在の確認済みプロファイル（カテゴリ・フィールド・値） |
| `GET /hypotheses` | 信頼度・ステータス付きの全プロファイル |
| `POST /chat` | メッセージ送信；応答は完全な記憶コンテキストを使用 |
| `POST /sleep` | 記憶整理を手動トリガー |
| `GET /health` | サービスのヘルスチェック |

認証：すべてのリクエストに `X-Device-Token: <token>` ヘッダーを付与。

---

## RAG との違い

| | RAG / 既存 AI メモリ | Riverse |
|---|---|---|
| **検索方式** | ベクトル類似度 — 「似ている」テキストを検索 | プロファイル重み付け — *あなた*との関連性で順位付け |
| **タイムライン** | なし — 3年前と昨日が同じ重み | 時間推移 — 事実は勢いと減衰を持つ |
| **推論** | 因果推論なし — 事実は孤立した断片 | 因果チェーン — 関連事実を自動で接続 |
| **確信度** | すべての事実が同じ重み | 推測 → 確認 → 確立 |
| **無効化** | なし — 古い事実は永続する | 事実は期限切れ・上書き・否定される |
| **データ所有** | クラウド依存、プラットフォーム所有 | ローカルファースト — あなたのデバイス、あなたのデータ |

---

## デモ

架空のキャラクターとの20の日常会話を含むデモ。生の会話記録から：

[![生の会話データ](https://raw.githubusercontent.com/wangjiake/JKRiver/main/img/demo-raw-data.png)](https://raw.githubusercontent.com/wangjiake/JKRiver/main/img/demo-raw-data.png)

Riverse が構造化された進化するプロファイルを抽出：

[![確認済みの事実](https://raw.githubusercontent.com/wangjiake/JKRiver/main/img/demo-profile-confirmed.png)](https://raw.githubusercontent.com/wangjiake/JKRiver/main/img/demo-profile-confirmed.png)
[![タイムライン — 事実の変遷](https://raw.githubusercontent.com/wangjiake/JKRiver/main/img/demo-profile-timeline.png)](https://raw.githubusercontent.com/wangjiake/JKRiver/main/img/demo-profile-timeline.png)
[![人間関係](https://raw.githubusercontent.com/wangjiake/JKRiver/main/img/demo-profile-relationships.png)](https://raw.githubusercontent.com/wangjiake/JKRiver/main/img/demo-profile-relationships.png)

---

## 内蔵エージェント

Riverse には記憶エンジンを活用した個人 AI エージェントが付属しています：

- **マルチチャネル** — Web ダッシュボード、Telegram、Discord、REST API、CLI
- **マルチモーダル** — テキスト、音声、画像、ファイル
- **ツール** — Web 検索、財務追跡、健康同期（Withings）、TTS；System ページで個別に ON/OFF
- **YAML スキル** — キーワードまたは cron スケジュールでトリガーするカスタム動作
- **タスク Agent** — 複雑なマルチステップタスクを自律サブ Agent に委託；実行前に計画をプレビューして確認

  [![タスク計画プレビュー](https://raw.githubusercontent.com/wangjiake/JKRiver/main/img/demo-outsource-plan.png)](https://raw.githubusercontent.com/wangjiake/JKRiver/main/img/demo-outsource-plan.png)
  [![タスク結果](https://raw.githubusercontent.com/wangjiake/JKRiver/main/img/demo-outsource-result.png)](https://raw.githubusercontent.com/wangjiake/JKRiver/main/img/demo-outsource-result.png)

- **MCP プロトコル** — Gmail 等の MCP Server を接続
- **外部エージェント** — `agents_*.yaml` で Home Assistant、n8n、Dify を接続
- **プロアクティブ通知** — 重要イベントをフォローアップ、静寂時間帯を尊重

[![チャット画面](https://raw.githubusercontent.com/wangjiake/JKRiver/main/img/demo-chat-empty.png)](https://raw.githubusercontent.com/wangjiake/JKRiver/main/img/demo-chat-empty.png)
[![システム設定](https://raw.githubusercontent.com/wangjiake/JKRiver/main/img/demo-system.png)](https://raw.githubusercontent.com/wangjiake/JKRiver/main/img/demo-system.png)

---

## ソースからインストール

```bash
git clone https://github.com/wangjiake/JKRiver.git
cd JKRiver
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

createdb -h localhost -U YOUR_USERNAME Riverse
psql -h localhost -U YOUR_USERNAME -d Riverse -f agent/schema.sql

cp settings.yaml.default settings.yaml
# settings.yaml を編集：database.user と openai.api_key を設定
python scripts/start_local.py
```

> 完全な設定ガイド：**[wangjiake.github.io/riverse-docs](https://wangjiake.github.io/riverse-docs/ja/getting-started/configuration/)**

---

## 技術スタック

| レイヤー | 技術 |
|---|---|
| ランタイム | Python 3.10+, PostgreSQL 16+ |
| ローカル LLM | Ollama（任意の互換モデル） |
| クラウド LLM | 任意の OpenAI 互換 API（OpenAI、DeepSeek、Groq など） |
| 埋め込み | Ollama + 任意の埋め込みモデル（[pgvector](https://github.com/pgvector/pgvector) で自動高速化） |
| REST API | FastAPI + Uvicorn |
| Web ダッシュボード | Flask |
| Telegram / Discord | python-telegram-bot / discord.py |
| 音声 / 画像 | Whisper-1, GPT-4 Vision, LLaVA |
| TTS | Edge TTS |

## セキュリティ

Riverse は**シングルユーザー・ローカル実行**を前提とした設計です。Web ダッシュボードは初回起動時に自動生成されるアクセストークンで保護されています。REST API（ポート 8400）には認証がありません。公開インターネットに公開しないでください。リモートアクセスが必要な場合は、リバースプロキシ（Nginx、Caddy など）か SSH トンネルを使用してください。

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
