# Live-sheet-finder

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
