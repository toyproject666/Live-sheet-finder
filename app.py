import os
import re
import sqlite3
from pathlib import Path
from difflib import SequenceMatcher
from typing import Any, Dict, Optional
from urllib.parse import quote

from flask import Flask, abort, jsonify, render_template_string, request, send_from_directory


DB_PATH = os.environ.get("SHEET_DB_PATH", "sheets.db")
SONGS_DIR = os.environ.get("SONGS_DIR", "songs")
SHEET_FILES_DIR = os.environ.get("SHEET_FILES_DIR", "sheets")
SUPPORTED_LANG_HINTS = {"auto", "english", "cantonese", "mandarin"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}

app = Flask(__name__)


HTML_PAGE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Live Song + Sheet Finder</title>
  <style>
    :root {
      --bg: #f5f7fb;
      --ink: #17202a;
      --muted: #5e6b7a;
      --card: #ffffff;
      --accent: #0f766e;
      --line: #dbe3ea;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", "Helvetica Neue", sans-serif;
      background:
        radial-gradient(circle at 10% 10%, #d8eff0 0%, transparent 40%),
        radial-gradient(circle at 90% 20%, #efe2ff 0%, transparent 45%),
        var(--bg);
      color: var(--ink);
    }
    .wrap { max-width: 900px; margin: 2rem auto; padding: 0 1rem; }
    .card {
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 1rem;
      box-shadow: 0 12px 40px rgba(23,32,42,.08);
      margin-bottom: 1rem;
    }
    h1 { margin: 0 0 .5rem; font-size: 1.5rem; }
    p { color: var(--muted); margin: .25rem 0 1rem; }
    button {
      border: 0; border-radius: 10px; padding: .7rem 1.4rem;
      font-weight: 600; cursor: pointer; font-size: 1rem; margin-right: .5rem;
    }
    .btn-start { background: var(--accent); color: #fff; }
    .btn-stop  { background: #334155; color: #fff; }
    button:disabled { opacity: .45; cursor: default; }
    .interim-box {
      border: 1px dashed var(--line); border-radius: 10px;
      padding: .75rem; min-height: 90px; background: #f9fbfe;
      color: var(--muted); white-space: pre-wrap; font-size: .95rem;
    }
    .tag {
      display: inline-block; padding: .2rem .45rem; border-radius: 999px;
      border: 1px solid var(--line); color: var(--muted); font-size: .75rem; margin-bottom: .5rem;
    }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
    @media (max-width: 760px) { .row { grid-template-columns: 1fr; } }
    .result-title { margin: .25rem 0; font-weight: 700; }
    .link { color: #0f3b73; text-decoration: none; border-bottom: 1px dotted #0f3b73; }
    .status { font-size: .9rem; color: var(--muted); margin-top: .75rem; display: flex; align-items: center; gap: .5rem; }
    .dot {
      width: 9px; height: 9px; border-radius: 50%; background: #22c55e;
      animation: pulse 1.2s infinite; flex-shrink: 0;
    }
    .dot.detecting { background: #f59e0b; animation: pulse .6s infinite; }
    .dot.idle      { background: #94a3b8; animation: none; }
    @keyframes pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50%       { opacity: .4; transform: scale(.7); }
    }
    .debug-box {
      background: #0b1220; color: #dbe7ff; border-radius: 10px;
      padding: .75rem; min-height: 120px; max-height: 220px; overflow: auto;
      font-family: Consolas, "Courier New", monospace; font-size: .82rem; white-space: pre-wrap;
    }
  </style>
</head>
<body>
<div class="wrap">
  <div class="card">
    <h1>Live Song + Sheet Finder</h1>
    <p>Detects every 3 seconds from live speech. Clears buffer on sheet found. Change songs anytime.</p>
    <label for="langMode"><strong>Language Mode:</strong></label>
    <select id="langMode" style="margin-right:.75rem">
      <option value="auto">Auto</option>
      <option value="english">English</option>
      <option value="cantonese">Cantonese</option>
      <option value="mandarin">Mandarin</option>
    </select>
    <button id="startBtn" class="btn-start">🎙 Start</button>
    <button id="stopBtn"  class="btn-stop" disabled>⏹ Stop</button>
    <div class="status">
      <div id="dot" class="dot idle"></div>
      <span id="statusText">Idle — press Start</span>
    </div>
  </div>

  <div class="card" style="min-height:70vh;">
    <div class="tag">Sheet Match</div>
    <div id="sheetResult" style="font-size:1.1rem;">—</div>
  </div>

  <div class="card">
    <div class="tag">Debug Logs</div>
    <div id="debugLog" class="debug-box"></div>
  </div>
</div>

<script>
  const startBtn   = document.getElementById('startBtn');
  const stopBtn    = document.getElementById('stopBtn');
  const dot        = document.getElementById('dot');
  const statusText = document.getElementById('statusText');
  const sheetResult= document.getElementById('sheetResult');
  const langMode   = document.getElementById('langMode');
  const debugLog   = document.getElementById('debugLog');

  const DETECT_INTERVAL_MS  = 3000;
  const MIN_WORDS_TO_DETECT = 3;    // must have at least 3 words before firing

  let recognition  = null;
  let started      = false;   // true = should be listening
  let detecting    = false;   // true = fetch in-flight
  let clearing     = false;   // true = restarting recognizer to flush buffer
  let interim      = '';
  let detectTimer  = null;

  // ─── Helpers ─────────────────────────────────────────────────────────────────
  function log(msg, obj) {
    const ts = new Date().toLocaleTimeString();
    debugLog.textContent += obj
      ? `[${ts}] ${msg}\n${JSON.stringify(obj, null, 2)}\n\n`
      : `[${ts}] ${msg}\n`;
    debugLog.scrollTop = debugLog.scrollHeight;
  }

  function setStatus(msg, state = 'listening') {
    statusText.textContent = msg;
    dot.className = 'dot';
    if (state === 'detecting') dot.classList.add('detecting');
    else if (state === 'idle' || state === 'error') dot.classList.add('idle');
  }

  function tokenize(text) {
    return (text || '').toLowerCase().match(/[\u3400-\u9fff]|[a-z0-9']+/g) || [];
  }

  function getSpeechLang(mode) {
    if (mode === 'english')   return 'en-US';
    if (mode === 'cantonese') return 'zh-HK';
    if (mode === 'mandarin')  return 'zh-CN';
    return navigator.language || 'en-US';
  }

  // ─── Full recognizer restart — the only reliable way to flush the browser's
  //     internal speech buffer. Simply setting interim='' isn't enough because
  //     the next onresult fires with the old accumulated text straight away.
  function restartRecognizer(reason) {
    if (!started || !recognition) return;
    clearing = true;
    interim  = '';
    log('Restarting recognizer — ' + reason);
    try { recognition.stop(); } catch (_) {}
    // onend will fire → sees started=true, clearing=true → starts fresh
  }

  // ─── Detect ──────────────────────────────────────────────────────────────────
  async function runDetect() {
    if (detecting) return;
    if (clearing)  return;   // mid-restart, skip this tick
    const transcript = interim.trim();
    if (tokenize(transcript).length < MIN_WORDS_TO_DETECT) return;

    detecting = true;
    setStatus('detecting...', 'detecting');
    log('Detecting', { preview: transcript.slice(0, 60) });

    try {
      const resp = await fetch('/api/detect_song', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ transcript, language_hint: langMode.value }),
      });
      const data = await resp.json();
      log('Response', data.debug || {});
      if (!resp.ok) throw new Error(data.error || 'Server error');

      // Sheet display — update only when found; restart recognizer to flush buffer
      if (data.sheet) {
        const url     = data.sheet.sheet_url || '';
        const isImage = /\.(png|jpe?g|webp|gif|bmp)$/i.test(url);
        sheetResult.innerHTML = `
          <div class="result-title">${data.sheet.title}</div>
          <div>${data.sheet.artist || ''}</div>
          ${url ? `<a class="link" target="_blank" href="${url}">Open Sheet</a>` : '<div>Sheet found (no URL)</div>'}
          ${isImage ? `<div style="margin-top:.5rem"><img src="${url}" alt="Sheet"
              style="max-width:100%;border:1px solid #dbe3ea;border-radius:8px"></div>` : ''}
          ${data.sheet.sheet_text ? `<pre style="margin-top:.5rem;font-size:.85rem">${data.sheet.sheet_text}</pre>` : ''}
        `;
      }

      // Always restart recognizer after a successful detect — flushes browser's internal
      // buffer so the next loop starts completely clean, match or no match.
      restartRecognizer('detect-done');

    } catch (err) {
      log('Detect error', { message: err.message });
      // Don't restart recognizer on error — just release the lock and keep going
    } finally {
      detecting = false;
      if (started && !clearing) setStatus('listening...', 'listening');
    }
  }

  // ─── Ticker ──────────────────────────────────────────────────────────────────
  function startDetectTimer() {
    if (detectTimer) clearInterval(detectTimer);
    detectTimer = setInterval(runDetect, DETECT_INTERVAL_MS);
  }

  function stopDetectTimer() {
    if (detectTimer) { clearInterval(detectTimer); detectTimer = null; }
  }

  // ─── Recognition ─────────────────────────────────────────────────────────────
  function buildRecognition() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return null;

    const r           = new SR();
    r.lang            = getSpeechLang(langMode.value);
    r.interimResults  = true;
    r.continuous      = true;
    r.maxAlternatives = 1;

    r.onstart = () => {
      clearing = false;
      interim  = '';
      log('Recognizer started');
      if (started) setStatus('listening...', 'listening');
    };

    r.onerror = (e) => {
      log('Speech error', { error: e.error });
      if (e.error === 'not-allowed' || e.error === 'service-not-allowed') {
        started = false;
        stopDetectTimer();
        setStatus('Mic denied — reload and allow microphone', 'error');
        startBtn.disabled = false;
        stopBtn.disabled  = true;
      }
    };

    r.onend = () => {
      log('Recognizer ended');
      if (!started) {
        // Deliberate stop
        setStatus('Stopped', 'idle');
        return;
      }
      // Auto-restart: either after sheet-found flush or browser timeout
      setTimeout(() => {
        if (!started) return;
        try { r.start(); }
        catch (err) { log('Restart error', { message: String(err) }); }
      }, 150);
    };

    r.onresult = (event) => {
      if (clearing) return;
      let text = '';
      for (let i = 0; i < event.results.length; i++) {
        text += event.results[i][0].transcript;
      }
      interim = text.trim();
    };

    return r;
  }

  // ─── Start / Stop ────────────────────────────────────────────────────────────
  startBtn.onclick = () => {
    if (started) return;

    if (!recognition) recognition = buildRecognition();
    if (!recognition) {
      setStatus('SpeechRecognition not supported — use Chrome or Edge', 'error');
      return;
    }

    started   = true;
    detecting = false;
    clearing  = false;
    interim   = '';
    debugLog.textContent = '';

    recognition.lang = getSpeechLang(langMode.value);
    try { recognition.start(); }
    catch (err) { log('Start error', { message: String(err) }); }

    startDetectTimer();
    startBtn.disabled = true;
    stopBtn.disabled  = false;
    log('Started', { lang: langMode.value, detectIntervalMs: DETECT_INTERVAL_MS });
  };

  stopBtn.onclick = () => {
    if (!started) return;
    started   = false;
    detecting = false;
    clearing  = false;
    interim   = '';
    stopDetectTimer();
    try { recognition && recognition.stop(); } catch (_) {}
    setStatus('Stopped', 'idle');
    startBtn.disabled = false;
    stopBtn.disabled  = true;
    log('Stopped by user');
  };
</script>
</body>
</html>
"""


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sheets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            artist TEXT,
            sheet_url TEXT,
            sheet_text TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, (a or "").lower(), (b or "").lower()).ratio()


def normalize_language_hint(value: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized in SUPPORTED_LANG_HINTS:
        return normalized
    return "auto"


def contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u3400-\u9FFF]", text or ""))


def tokenize_text(text: str) -> list[str]:
    cleaned = (text or "").lower().strip()
    if not cleaned:
        return []
    if contains_cjk(cleaned):
        return re.findall(r"[\u3400-\u9FFF]", cleaned)
    return re.findall(r"[a-z0-9']+", cleaned)


def normalize_for_match(text: str) -> str:
    src = (text or "").lower()
    src = re.sub(r"[^\w\u3400-\u9FFF]+", " ", src)
    return re.sub(r"\s+", " ", src).strip()


def read_text_file(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "cp936"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def parse_song_txt(path: Path) -> Optional[Dict[str, str]]:
    raw = read_text_file(path)
    if not raw.strip():
        return None
    lines = [
        line.strip()
        for line in raw.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if not lines:
        return None

    title = path.stem
    artist = ""

    first_line = lines[0]
    title_match = re.match(
        r"^(?:title|song|song name|歌名|歌曲)\s*[:：]\s*(.+)$",
        first_line, flags=re.IGNORECASE,
    )
    if title_match:
        title = title_match.group(1).strip()
        lines = lines[1:]

    if lines:
        artist_match = re.match(
            r"^(?:artist|singer|歌手|演唱)\s*[:：]\s*(.+)$",
            lines[0], flags=re.IGNORECASE,
        )
        if artist_match:
            artist = artist_match.group(1).strip()
            lines = lines[1:]

    if lines:
        lyrics_header_match = re.match(
            r"^(?:lyrics|lyric|歌词)\s*[:：]?\s*(.*)$",
            lines[0], flags=re.IGNORECASE,
        )
        if lyrics_header_match:
            first_lyric = lyrics_header_match.group(1).strip()
            lines = lines[1:]
            if first_lyric:
                lines.insert(0, first_lyric)

    lyrics = "\n".join(lines).strip()
    if not lyrics:
        return None

    return {"title": title, "artist": artist, "lyrics": lyrics, "file_name": path.name}


def lyric_match_score(transcript: str, lyrics: str) -> float:
    t_norm = normalize_for_match(transcript)
    l_norm = normalize_for_match(lyrics)
    if not t_norm or not l_norm:
        return 0.0

    t_tokens = tokenize_text(t_norm)
    l_tokens = set(tokenize_text(l_norm))
    if not t_tokens:
        return 0.0

    overlap = sum(1 for token in t_tokens if token in l_tokens) / max(len(t_tokens), 1)
    contains = 1.0 if t_norm in l_norm else 0.0
    seq_ratio = similarity(t_norm, l_norm)

    best_chunk_overlap = 0.0
    for chunk in lyrics.splitlines():
        c_norm = normalize_for_match(chunk)
        if not c_norm:
            continue
        c_tokens = set(tokenize_text(c_norm))
        if not c_tokens:
            continue
        chunk_overlap = sum(
            1 for token in t_tokens if token in c_tokens
        ) / max(len(t_tokens), 1)
        if chunk_overlap > best_chunk_overlap:
            best_chunk_overlap = chunk_overlap

    return (0.35 * overlap) + (0.35 * best_chunk_overlap) + (0.2 * contains) + (0.1 * seq_ratio)


def detect_song_from_library(
    transcript: str, language_hint: str = "auto"
) -> tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    _ = normalize_language_hint(language_hint)
    songs_path = Path(SONGS_DIR)
    if not songs_path.exists() or not songs_path.is_dir():
        return None, {
            "songs_dir": str(songs_path), "exists": False,
            "scanned": 0, "best_score": 0.0, "candidates": [],
        }

    best_song  = None
    best_score = 0.0
    scanned    = 0
    candidates: list[Dict[str, Any]] = []

    for txt_path in songs_path.rglob("*.txt"):
        if txt_path.name.lower().startswith("readme"):
            continue
        scanned += 1
        parsed = parse_song_txt(txt_path)
        if not parsed:
            continue
        score = lyric_match_score(transcript, parsed["lyrics"])
        candidates.append({
            "file":  str(txt_path.relative_to(songs_path)),
            "title": parsed["title"],
            "score": round(score, 3),
        })
        if score > best_score:
            best_score = score
            best_song  = parsed

    candidates.sort(key=lambda x: x["score"], reverse=True)
    debug = {
        "songs_dir":      str(songs_path),
        "exists":         True,
        "scanned":        scanned,
        "best_score":     round(best_score, 3),
        "threshold":      0.28,
        "top_candidates": candidates[:5],
    }

    if not best_song or best_score < 0.28:
        return None, debug

    return {
        "title":        best_song["title"],
        "artist":       best_song["artist"],
        "library_file": best_song["file_name"],
        "match_score":  round(best_score, 3),
    }, debug


def normalize_sheet_key(text: str) -> str:
    src = (text or "").lower().strip()
    src = re.sub(r"[^\w\u3400-\u9FFF]+", "", src)
    return src


def find_sheet_file(song_title: str) -> Optional[Dict[str, Any]]:
    sheets_path = Path(SHEET_FILES_DIR)
    if not sheets_path.exists() or not sheets_path.is_dir():
        return None

    target = normalize_sheet_key(song_title)
    if not target:
        return None

    best_file: Optional[Path] = None
    best_score = 0.0

    for file_path in sheets_path.rglob("*"):
        if not file_path.is_file():
            continue
        stem_key = normalize_sheet_key(file_path.stem)
        if not stem_key:
            continue
        score = 1.0 if stem_key == target else similarity(target, stem_key)
        if score > best_score:
            best_score = score
            best_file  = file_path

    if not best_file or best_score < 0.75:
        return None

    rel_path = best_file.relative_to(sheets_path).as_posix()
    return {
        "id":         None,
        "title":      best_file.stem,
        "artist":     "",
        "sheet_url":  f"/sheet_files/{quote(rel_path)}",
        "sheet_text": "",
        "score":      round(best_score, 3),
        "source":     "file",
        "is_image":   best_file.suffix.lower() in IMAGE_EXTENSIONS,
    }


def find_sheet(song_title: str, artist: str = "") -> Optional[Dict[str, Any]]:
    conn = get_db()
    rows = conn.execute(
        "SELECT id, title, artist, sheet_url, sheet_text FROM sheets"
    ).fetchall()
    conn.close()

    best_row   = None
    best_score = 0.0
    for row in rows:
        title_score  = similarity(song_title, row["title"])
        artist_score = similarity(artist, row["artist"] or "") if artist else 0.0
        score        = (title_score * 0.8) + (artist_score * 0.2)
        if score > best_score:
            best_score = score
            best_row   = row

    if not best_row or best_score < 0.55:
        return find_sheet_file(song_title)

    return {
        "id":         best_row["id"],
        "title":      best_row["title"],
        "artist":     best_row["artist"],
        "sheet_url":  best_row["sheet_url"],
        "sheet_text": best_row["sheet_text"],
        "score":      round(best_score, 3),
        "source":     "db",
        "is_image":   False,
    }


@app.route("/")
def index() -> str:
    return render_template_string(HTML_PAGE)


@app.post("/api/detect_song")
def detect_song():
    payload       = request.get_json(silent=True) or {}
    transcript    = (payload.get("transcript") or "").strip()
    language_hint = normalize_language_hint(payload.get("language_hint") or "auto")
    if len(transcript) < 2:
        return jsonify({"error": "Transcript too short"}), 400

    try:
        song, debug = detect_song_from_library(transcript, language_hint=language_hint)
    except Exception as exc:
        return jsonify({"error": f"Library lookup failed: {exc}"}), 502

    if not song:
        return jsonify({"song": None, "sheet": None, "debug": debug})

    sheet = find_sheet(song.get("title", ""), song.get("artist", ""))
    return jsonify({"song": song, "sheet": sheet, "debug": debug})


@app.post("/api/sheets")
def add_sheet():
    payload    = request.get_json(silent=True) or {}
    title      = (payload.get("title")      or "").strip()
    artist     = (payload.get("artist")     or "").strip()
    sheet_url  = (payload.get("sheet_url")  or "").strip()
    sheet_text = (payload.get("sheet_text") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400

    conn = get_db()
    cur  = conn.cursor()
    cur.execute(
        "INSERT INTO sheets(title, artist, sheet_url, sheet_text) VALUES(?, ?, ?, ?)",
        (title, artist, sheet_url, sheet_text),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return jsonify({"ok": True, "id": row_id})


@app.get("/api/sheets")
def list_sheets():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, title, artist, sheet_url FROM sheets ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return jsonify([
        {"id": r["id"], "title": r["title"], "artist": r["artist"], "sheet_url": r["sheet_url"]}
        for r in rows
    ])


@app.get("/sheet_files/<path:filename>")
def serve_sheet_file(filename: str):
    base   = Path(SHEET_FILES_DIR).resolve()
    target = (base / filename).resolve()
    if not str(target).startswith(str(base)) or not target.is_file():
        abort(404)
    return send_from_directory(str(base), filename, as_attachment=False)


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
