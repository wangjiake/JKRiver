# Data Directory

[English](#english) | [中文](#中文) | [日本語](#日本語)

---

## English

Place your AI conversation export files in this directory.

### ChatGPT

1. Settings → Data controls → Export data
2. Unzip to get `conversations.json`
3. Place it in this directory

```bash
python import_data.py --chatgpt data/conversations.json
```

### Claude

1. Settings → Account → Export Data
2. Unzip to get `conversations.json`
3. Place it here (rename to `claude.json` if it conflicts with ChatGPT)

```bash
python import_data.py --claude data/claude/conversations.json
```

### Gemini

1. [Google Takeout](https://takeout.google.com/) → Select "Gemini Apps" → Download
2. Unzip to get the `Gemini Apps` folder (contains `My Activity.html`) or JSON file
3. Place the entire folder or JSON file in this directory

```bash
# HTML format
python import_data.py --gemini "data/Gemini Apps/My Activity.html"
# JSON format
python import_data.py --gemini data/gemini.json
```

### Notes

- You don't need all three — import whichever platforms you use
- Duplicate entries are skipped automatically (checksum-based)
- Data files are git-ignored and will not be committed

---

## 中文

将 AI 对话导出文件放在此目录下。

### ChatGPT

1. Settings → Data controls → Export data
2. 解压，得到 `conversations.json`
3. 放到此目录下

```bash
python import_data.py --chatgpt data/conversations.json
```

### Claude

1. Settings → Account → Export Data
2. 解压，得到 `conversations.json`
3. 放到此目录下（如果和 ChatGPT 重名，改名为 `claude.json`）

```bash
python import_data.py --claude data/claude/conversations.json
```

### Gemini

1. [Google Takeout](https://takeout.google.com/) → 选择 "Gemini Apps" → 下载
2. 解压，得到 `Gemini Apps` 文件夹（里面有 `我的活动记录.html`）或 JSON 文件
3. 将整个文件夹或 JSON 文件放到此目录下

```bash
# HTML 格式
python import_data.py --gemini "data/Gemini Apps/我的活动记录.html"
# JSON 格式
python import_data.py --gemini data/gemini.json
```

### 说明

- 不需要三个平台都导入，导入你用过的就行
- 重复数据会自动跳过（基于 checksum 去重）
- 数据文件已被 .gitignore 排除，不会被提交

---

## 日本語

AIの会話エクスポートファイルをこのディレクトリに配置してください。

### ChatGPT

1. Settings → Data controls → Export data
2. 解凍して `conversations.json` を取得
3. このディレクトリに配置

```bash
python import_data.py --chatgpt data/conversations.json
```

### Claude

1. Settings → Account → Export Data
2. 解凍して `conversations.json` を取得
3. このディレクトリに配置（ChatGPTと重複する場合は `claude.json` にリネーム）

```bash
python import_data.py --claude data/claude/conversations.json
```

### Gemini

1. [Google Takeout](https://takeout.google.com/) → "Gemini Apps" を選択 → ダウンロード
2. 解凍して `Gemini Apps` フォルダ（`マイ アクティビティ.html` を含む）またはJSONファイルを取得
3. フォルダまたはJSONファイルをこのディレクトリに配置

```bash
# HTML形式
python import_data.py --gemini "data/Gemini Apps/マイ アクティビティ.html"
# JSON形式
python import_data.py --gemini data/gemini.json
```

### 注意事項

- 3つすべてのプラットフォームをインポートする必要はありません。使用しているものだけで構いません
- 重複データはチェックサムにより自動的にスキップされます
- データファイルは .gitignore で除外されており、コミットされません
