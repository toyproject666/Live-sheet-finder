# Live Song + Sheet Finder / 中文版的在下面~

A real-time singing assistant that listens to your voice, identifies the song you're singing, and automatically pulls up the matching sheet music.

## How it works

1. Press **Start** — the app begins listening via your microphone
2. Sing a few words — every 3 seconds it sends what it heard to the server
3. The server matches the transcript against your lyric library
4. When a match is found, the sheet is displayed and the buffer resets
5. Change songs anytime — it keeps listening and detecting continuously

## Features

- **Real-time detection** using the browser's Web Speech API (interim results, no waiting for final)
- **Always-on loop** — never stops after a match, resets cleanly for the next song
- **Sticky sheet display** — last matched sheet stays visible until a new one is found
- **Multi-language support** — Auto, English, Cantonese, Mandarin
- **File-based sheet serving** — drop image or PDF sheets into the `sheets/` folder
- **SQLite sheet database** — optionally store sheet URLs or text via API

## Project structure

```
.
├── app.py              # Flask server
├── songs/              # Lyric library — one .txt file per song
│   └── my_song.txt
├── sheets/             # Sheet music files (images, PDFs, etc.)
│   └── my_song.png
└── sheets.db           # Auto-created SQLite database
```

## Song file format

Each `.txt` file in `songs/` represents one song. The filename is used as the title fallback.

```
Title: My Song
Artist: Artist Name
Lyrics:
Never gonna give you up
Never gonna let you down
...
```

The `Title:`, `Artist:`, and `Lyrics:` headers are optional — the parser will infer them. Lines starting with `#` are treated as comments and ignored.

## Sheet file matching

Drop any file into the `sheets/` folder with the same name as the song title (e.g. `my_song.png`, `my_song.pdf`). The server fuzzy-matches the detected song title against filenames automatically.

Supported image formats for inline display: `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`, `.bmp`

## Setup

### Requirements

- Python 3.11+
- Flask

```bash
pip install flask
```

### Run

```bash
python app.py
```

The app runs on `http://localhost:5000`. Open it in **Chrome or Edge** — Safari does not support the Web Speech API.

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `SHEET_DB_PATH` | `sheets.db` | Path to SQLite database |
| `SONGS_DIR` | `songs` | Directory containing lyric `.txt` files |
| `SHEET_FILES_DIR` | `sheets` | Directory containing sheet music files |

## Sheet database API

You can also store sheets directly in the database instead of the filesystem.

**Add a sheet**
```bash
curl -X POST http://localhost:5000/api/sheets \
  -H "Content-Type: application/json" \
  -d '{"title": "My Song", "artist": "Artist", "sheet_url": "https://..."}'
```

**List all sheets**
```bash
curl http://localhost:5000/api/sheets
```

## Browser support

| Browser | Supported |
|---|---|
| Chrome | ✅ |
| Edge | ✅ |
| Firefox | ❌ |
| Safari | ❌ |

## Notes

- The app uses **interim speech results** for low-latency detection — words are matched as you sing them, not after you stop
- After each detection attempt the recognizer restarts to flush the browser's internal buffer, ensuring a clean slate for the next song
- Detection threshold is 3 words minimum before a request is sent
- Match scoring weighs token overlap, line-level overlap, substring containment, and sequence similarity

---

# 实时歌曲乐谱查找器

一个实时演唱助手，通过监听你的声音识别你正在唱的歌曲，并自动调出对应的乐谱。

## 工作原理

1. 按下 **Start（开始）** — 应用通过麦克风开始监听
2. 唱几个字 — 每隔 3 秒将识别到的内容发送到服务器进行匹配
3. 服务器将语音转录与你的歌词库进行比对
4. 匹配成功后，乐谱自动显示，缓冲区重置
5. 随时换歌 — 应用持续监听与识别，不会中断

## 功能特点

- **实时识别** — 使用浏览器 Web Speech API 的中间结果，无需等待语音确认
- **持续运行** — 识别到结果后不停止，自动重置并等待下一首歌
- **乐谱保留** — 上一张乐谱保持显示，直到找到新的匹配
- **多语言支持** — 自动、英语、粤语、普通话
- **文件式乐谱管理** — 将图片或 PDF 乐谱放入 `sheets/` 文件夹即可
- **SQLite 乐谱数据库** — 也可通过 API 存储乐谱链接或文字内容

## 项目结构

```
.
├── app.py              # Flask 服务器
├── songs/              # 歌词库 — 每首歌一个 .txt 文件
│   └── my_song.txt
├── sheets/             # 乐谱文件（图片、PDF 等）
│   └── my_song.png
└── sheets.db           # 自动创建的 SQLite 数据库
```

## 歌词文件格式

`songs/` 目录中每个 `.txt` 文件代表一首歌，文件名作为歌名的后备值。

```
Title: 我的歌
Artist: 歌手名
Lyrics:
第一行歌词
第二行歌词
...
```

`Title:`、`Artist:`、`Lyrics:` 标头均为可选 — 解析器会自动推断。以 `#` 开头的行视为注释，将被忽略。

## 乐谱文件匹配

将乐谱文件放入 `sheets/` 文件夹，文件名与歌名保持一致（例如 `my_song.png`、`my_song.pdf`）。服务器会自动对检测到的歌名与文件名进行模糊匹配。

支持内嵌显示的图片格式：`.png`、`.jpg`、`.jpeg`、`.webp`、`.gif`、`.bmp`

## 安装与运行

### 环境要求

- Python 3.11+
- Flask

```bash
pip install flask
```

### 运行

```bash
python app.py
```

应用运行在 `http://localhost:5000`。请使用 **Chrome 或 Edge** 打开 — Safari 不支持 Web Speech API。

### 环境变量

| 变量名 | 默认值 | 说明 |
|---|---|---|
| `SHEET_DB_PATH` | `sheets.db` | SQLite 数据库路径 |
| `SONGS_DIR` | `songs` | 歌词 `.txt` 文件目录 |
| `SHEET_FILES_DIR` | `sheets` | 乐谱文件目录 |

## 乐谱数据库 API

也可以将乐谱直接存入数据库，而不是放在文件系统中。

**添加乐谱**
```bash
curl -X POST http://localhost:5000/api/sheets \
  -H "Content-Type: application/json" \
  -d '{"title": "我的歌", "artist": "歌手名", "sheet_url": "https://..."}'
```

**查看所有乐谱**
```bash
curl http://localhost:5000/api/sheets
```

## 浏览器支持

| 浏览器 | 是否支持 |
|---|---|
| Chrome | ✅ |
| Edge | ✅ |
| Firefox | ❌ |
| Safari | ❌ |

## 备注

- 应用使用**语音中间结果**实现低延迟识别 — 边唱边匹配，无需停顿
- 每次识别完成后，语音识别器会重启以清空浏览器内部缓冲区，确保下一首歌从干净状态开始
- 至少需要识别到 3 个词才会发送请求
- 匹配评分综合考虑词语重叠率、逐行重叠率、子串包含情况及序列相似度
