from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import sqlite3
import subprocess
import threading
import os
import json
import re
import requests
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "download.db")

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)

# -------------------- Hilfsfunktionen --------------------
def sanitize_filename(name):
    """Entfernt ungültige Zeichen für Dateinamen und DB-Titel."""
    return re.sub(r'[<>:"/\\|?*]', ' ', name)

def get_series_title(url):
    """Versucht, den Serientitel von der Webseite zu extrahieren."""
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
            title = get_series_title(url) or re.search(r"/anime/stream/([^/]+)", url).group(1).replace("-", " ").title()
        c.execute("INSERT OR IGNORE INTO anime (url, title) VALUES (?, ?)", (url, title))
        conn.commit()
        return True
    except Exception as e:
        print(f"[DB-ERROR] {e}")
        return False
    finally:
        conn.close()

# -------------------- Live-Log --------------------
log_lines = []

def stream_logs():
    """Startet den Downloader und speichert die Logs live."""
    global log_lines
    process = subprocess.Popen(
        ["python", "downloader.py"], 
        stdout=subprocess.PIPE,
        encoding="utf-8",  # UTF-8 erzwingen
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    for line in process.stdout:
        log_lines.append(line.strip())
        if len(log_lines) > 200:
            log_lines.pop(0)

@app.route("/start_download")
def start_download():
    threading.Thread(target=stream_logs, daemon=True).start()
    return jsonify({"status": "started"})

@app.route("/logs")
def get_logs():
    return jsonify(log_lines)

# -------------------- DB Übersicht --------------------
@app.route("/database")
def get_database():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, title, url, complete, deutsch_komplett, fehlende_deutsch_folgen, last_film, last_episode, last_season FROM anime")
    rows = c.fetchall()
    conn.close()

    db_data = []
    for row in rows:
        db_data.append({
            "id": row[0],
            "title": row[1],
            "url": row[2],
            "complete": bool(row[3]),
            "deutsch_komplett": bool(row[4]),
            "fehlende": row[5],
            "last_film": row[6],
            "last_episode": row[7],
            "last_season": row[8]
        })
    return jsonify(db_data)

# -------------------- Anime exportieren --------------------
@app.route("/export", methods=["POST"])
def export_anime():
    """Fügt Anime-URL aus Tampermonkey-Skript in DB ein."""
    data = request.get_json()
    url = data.get("url")
    if not url:
        return jsonify({"status": "error", "msg": "Keine URL angegeben"}), 400
    success = insert_anime(url)
    return jsonify({"status": "ok" if success else "failed"})

@app.route("/check")
def check_export():
    url = request.args.get("url")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM anime WHERE url = ?", (url,))
    exists = c.fetchone() is not None
    conn.close()
    return jsonify({"exists": exists})

# -------------------- Index --------------------
@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)


