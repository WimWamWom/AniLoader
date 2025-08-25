from flask import Flask, render_template, jsonify, request, Response
from flask_cors import CORS
import sqlite3
import subprocess
import threading
import os
import json
import re
import requests
from bs4 import BeautifulSoup
from pathlib import Path
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "download.db")

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)

# -------------------- Hilfsfunktionen --------------------
def sanitize_filename(name):
    """Entfernt ungültige Zeichen für Dateinamen und DB-Titel."""
    return re.sub(r'[<>:"/\\|?*]', ' ', name)

def get_series_title(url):
    """Versucht, den Serientitel von der Webseite zu extrahieren (Aniworld-Struktur)."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        title_tag = soup.select_one("div.series-title h1 span")
        if title_tag and title_tag.text.strip():
            return sanitize_filename(title_tag.text.strip())
    except Exception as e:
        print(f"[FEHLER] Konnte Serien-Titel nicht abrufen ({url}): {e}")
    return None

# -------------------- DB-Funktionen --------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS anime (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            url TEXT UNIQUE,
            complete BOOLEAN DEFAULT 0,
            deutsch_komplett BOOLEAN DEFAULT 0,
            fehlende_deutsch_folgen TEXT DEFAULT '[]',
            last_film INTEGER DEFAULT 0,
            last_episode INTEGER DEFAULT 0,
            last_season INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def insert_anime(url, title=None):
    """Fügt eine neue Anime-URL in die DB ein, falls nicht vorhanden."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        if not title:
            m = re.search(r"/anime/stream/([^/]+)", url) or re.search(r"/serie/stream/([^/]+)", url)
            fallback = m.group(1).replace("-", " ").title() if m else url
            title = get_series_title(url) or fallback
        c.execute("INSERT OR IGNORE INTO anime (url, title) VALUES (?, ?)", (url, title))
        conn.commit()
        return True
    except Exception as e:
        print(f"[DB-ERROR] {e}")
        return False
    finally:
        conn.close()

def fetch_all_anime():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT id, title, url, complete, deutsch_komplett, fehlende_deutsch_folgen,
               last_film, last_episode, last_season
        FROM anime
        ORDER BY id
    """)
    rows = c.fetchall()
    conn.close()
    data = []
    for r in rows:
        data.append({
            "id": r[0],
            "title": r[1],
            "url": r[2],
            "complete": bool(r[3]),
            "deutsch_komplett": bool(r[4]),
            "fehlende": r[5],
            "last_film": r[6],
            "last_episode": r[7],
            "last_season": r[8]
        })
    return data

# -------------------- Live-Log & Download-Thread --------------------
log_lines = []
log_lock = threading.Lock()
runner_lock = threading.Lock()
current = {"status": "idle", "mode": None, "started_at": None}

def log(msg):
    ts = time.strftime("[%H:%M:%S]")
    line = f"{ts} {msg}"
    with log_lock:
        log_lines.append(line)
        if len(log_lines) > 2000:
            del log_lines[:500]
    # auch in Server-Konsole
    print(line, flush=True)

def run_downloader(mode: str):
    """Startet downloader.py im gegebenen Modus und streamt Logs live in log_lines."""
    env = os.environ.copy()
    # Erzwinge UTF-8 Ausgabe des Subprozesses (fix für Windows Unicode)
    env["PYTHONIOENCODING"] = "utf-8"

    args = ["python", "downloader.py"]
    if mode in ("german", "new"):
        args.append(mode)

    log(f"[START] Downloader gestartet (Modus: {mode})")
    process = subprocess.Popen(
        args,
        cwd=BASE_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        bufsize=1,
        env=env
    )
    try:
        for line in process.stdout:
            with log_lock:
                log_lines.append(line.rstrip("\n"))
                if len(log_lines) > 2000:
                    del log_lines[:500]
    except Exception as e:
        log(f"[FEHLER] Log-Streaming: {e}")
    finally:
        process.wait()
        code = process.returncode
        log(f"[ENDE] Downloader beendet (Code {code})")
        with runner_lock:
            current["status"] = "idle"
            current["mode"] = None
            current["started_at"] = None

# -------------------- API --------------------
@app.route("/start_download", methods=["POST"])
def start_download():
    """
    Startet den Downloader in einem Modus.
    Body: {"mode":"default"|"german"|"new"}
    """
    body = request.get_json(silent=True) or {}
    mode = body.get("mode", "default").lower()
    if mode not in ("default", "german", "new"):
        return jsonify({"status": "error", "message": "Ungültiger Modus"}), 400

    with runner_lock:
        if current["status"] == "running":
            return jsonify({"status": "already_running", "mode": current["mode"]})
        current["status"] = "running"
        current["mode"] = mode
        current["started_at"] = int(time.time())

    t = threading.Thread(target=run_downloader, args=(mode,), daemon=True)
    t.start()
    return jsonify({"status": "started", "mode": mode})

@app.route("/status")
def status():
    return jsonify(current)

@app.route("/logs")
def logs():
    """Gibt die Logs als Text zurück (für einfaches Streaming im Frontend)."""
    with log_lock:
        text = "\n".join(log_lines)
    return Response(text, mimetype="text/plain; charset=utf-8")

@app.route("/database")
def get_database():
    return jsonify(fetch_all_anime())

@app.route("/export", methods=["POST"])
def export_anime():
    """Erhält URL vom Tampermonkey-Skript und fügt sie in DB ein."""
    data = request.get_json() or {}
    url = data.get("url")
    if not url:
        return jsonify({"status": "error", "msg": "Keine URL angegeben"}), 400
    ok = insert_anime(url)
    return jsonify({"status": "ok" if ok else "failed"})

@app.route("/check")
def check_export():
    url = request.args.get("url")
    if not url:
        return jsonify({"exists": False})
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM anime WHERE url = ?", (url,))
    exists = c.fetchone() is not None
    conn.close()
    return jsonify({"exists": exists})

@app.route("/api/state")
def api_state():
    """
    Liefert eine Übersichtsliste für den Download-Tab.
    (Hier nehmen wir DB-Daten; Counts sind Platzhalter, können später erweitert werden.)
    """
    items = []
    for row in fetch_all_anime():
        items.append({
            "id": row["id"],
            "title": row["title"],
            "url": row["url"],
            "complete": row["complete"],
            "deutsch_komplett": row["deutsch_komplett"],
            "count_episodes": row["last_episode"] or 0,
            "count_films": row["last_film"] or 0,
            "estimated_total_episodes": 0,  # unbekannt -> 0
            "episodes": [],
            "films": [],
            "last_season": row["last_season"] or 0,
            "last_episode": row["last_episode"] or 0,
            "last_film": row["last_film"] or 0
        })
    return jsonify({"items": items})

# -------------------- UI --------------------
@app.route("/")
def index():
    return render_template("index.html")

# -------------------- Main --------------------
if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
