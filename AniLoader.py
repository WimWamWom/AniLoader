#!/usr/bin/env python3
# AniLoader.py by WimWamWom
import os
import subprocess
import time
import requests
from bs4 import BeautifulSoup
from pathlib import Path
import re
import sqlite3
import json
import sys
import shutil
import stat
import threading
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import random
import socket
from urllib.parse import urlparse


# -------------------- Konfiguration --------------------
BASE_DIR = Path(__file__).resolve().parent
ANIME_TXT = BASE_DIR / "AniLoader.txt"
# Default downloads directory; can be overridden via config.json (download_path)
DEFAULT_DOWNLOAD_DIR = BASE_DIR / "Downloads"
# Effective downloads directory used at runtime
DOWNLOAD_DIR = DEFAULT_DOWNLOAD_DIR
# Neue Speichermodus-Variablen
STORAGE_MODE = "standard"  # 'standard' oder 'separate'
MOVIES_PATH = ""  # Nur für separate Mode (wird nicht mehr verwendet)
SERIES_PATH = ""  # Nur für separate Mode (wird nicht mehr verwendet)
# Neue Content-Type basierte Pfade
ANIME_PATH = ""  # Pfad für Animes (aniworld.to)
SERIEN_PATH = ""  # Pfad für Serien (s.to)
# Film/Staffel Organisation
ANIME_SEPARATE_MOVIES = False  # Filme getrennt von Staffeln bei Animes
SERIEN_SEPARATE_MOVIES = False  # Filme getrennt von Staffeln bei Serien
# Server port (configurable only via config.json)
SERVER_PORT = 5050

# Define paths for the data folder
# Will be loaded from config.json if set, otherwise defaults to ./data
DEFAULT_DATA_FOLDER = os.path.join(os.path.dirname(__file__), 'data')
data_folder = DEFAULT_DATA_FOLDER
config_path = os.path.join(data_folder, 'config.json')
db_path = os.path.join(data_folder, 'AniLoader.db')
log_path = os.path.join(data_folder, 'last_run.log')

# Ensure the data folder exists
os.makedirs(data_folder, exist_ok=True)

# Function to save the last log
def save_last_log(log_content):
    with open(log_path, 'w') as log_file:
        log_file.write(log_content)

# Function to read the last log
def read_last_log():
    if os.path.exists(log_path):
        with open(log_path, 'r') as log_file:
            return log_file.read()
    return "No previous log available."

CONFIG_PATH = Path(config_path)
DB_PATH = Path(db_path)

LANGUAGES = ["German Dub", "German Sub", "English Dub", "English Sub"]
MIN_FREE_GB = 2.0
MAX_PATH = 260
AUTOSTART_MODE = None  # 'default'|'german'|'new'|'check-missing' or None
REFRESH_TITLES = True  # Titelaktualisierung beim Start zulassen


def update_data_paths(new_data_folder):
    """Updates the global data folder paths when the data_folder_path config changes."""
    global data_folder, config_path, db_path, log_path, CONFIG_PATH, DB_PATH
    data_folder = new_data_folder
    config_path = os.path.join(data_folder, 'config.json')
    db_path = os.path.join(data_folder, 'AniLoader.db')
    log_path = os.path.join(data_folder, 'last_run.log')
    CONFIG_PATH = Path(config_path)
    DB_PATH = Path(db_path)
    # Ensure the new data folder exists
    os.makedirs(data_folder, exist_ok=True)


def load_config():
    global LANGUAGES, MIN_FREE_GB, AUTOSTART_MODE, DOWNLOAD_DIR, SERVER_PORT, REFRESH_TITLES, STORAGE_MODE, MOVIES_PATH, SERIES_PATH, ANIME_PATH, SERIEN_PATH, ANIME_SEPARATE_MOVIES, SERIEN_SEPARATE_MOVIES, data_folder
    try:
        # First, check if there's a data_folder_path override in the config
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
                # Check for data_folder_path first
                data_folder_path = cfg.get('data_folder_path')
                if data_folder_path and isinstance(data_folder_path, str) and data_folder_path.strip():
                    try:
                        new_folder = Path(data_folder_path).expanduser()
                        try:
                            new_folder = new_folder.resolve()
                        except Exception:
                            pass
                        if str(new_folder) != data_folder:
                            update_data_paths(str(new_folder))
                            # Reload config from new location
                            if CONFIG_PATH.exists():
                                with open(CONFIG_PATH, 'r', encoding='utf-8') as f2:
                                    cfg = json.load(f2)
                    except Exception as e:
                        log(f"[CONFIG-WARN] Ungültiger data_folder_path: {e}, verwende Standard")
                
                # languages
                langs = cfg.get('languages')
                if isinstance(langs, list) and langs:
                    LANGUAGES = langs
                # min_free_gb
                try:
                    MIN_FREE_GB = float(cfg.get('min_free_gb', MIN_FREE_GB))
                except Exception:
                    pass
                # autostart_mode (normalize, validate)
                raw_mode = cfg.get('autostart_mode')
                allowed = {None, 'default', 'german', 'new', 'check-missing'}
                if isinstance(raw_mode, str):
                    raw_mode_norm = raw_mode.strip().lower()
                    if raw_mode_norm in {'', 'none', 'off', 'disabled'}:
                        AUTOSTART_MODE = None
                    elif raw_mode_norm in allowed:
                        AUTOSTART_MODE = raw_mode_norm
                    else:
                        AUTOSTART_MODE = None
                elif raw_mode is None:
                    AUTOSTART_MODE = None
                else:
                    AUTOSTART_MODE = None
                # download_path (add default if missing)
                changed = False
                dl_path = cfg.get('download_path')
                if isinstance(dl_path, str) and dl_path.strip():
                    try:
                        DOWNLOAD_DIR = Path(dl_path).expanduser()
                        try:
                            DOWNLOAD_DIR = DOWNLOAD_DIR.resolve()
                        except Exception:
                            # keep as provided if resolve fails
                            pass
                    except Exception:
                        DOWNLOAD_DIR = DEFAULT_DOWNLOAD_DIR
                else:
                    DOWNLOAD_DIR = DEFAULT_DOWNLOAD_DIR
                    cfg['download_path'] = str(DOWNLOAD_DIR)
                    changed = True
                # storage_mode, movies_path, series_path
                storage_mode = cfg.get('storage_mode', 'standard')
                if storage_mode in ['standard', 'separate']:
                    STORAGE_MODE = storage_mode
                else:
                    STORAGE_MODE = 'standard'
                    cfg['storage_mode'] = 'standard'
                    changed = True
                
                MOVIES_PATH = cfg.get('movies_path', '')
                if 'movies_path' not in cfg:
                    # Standardmäßig Unterordner "Filme" im Download-Verzeichnis
                    cfg['movies_path'] = str(DOWNLOAD_DIR / 'Filme')
                    MOVIES_PATH = str(DOWNLOAD_DIR / 'Filme')
                    changed = True
                    
                SERIES_PATH = cfg.get('series_path', '')
                if 'series_path' not in cfg:
                    # Standardmäßig Unterordner "Serien" im Download-Verzeichnis
                    cfg['series_path'] = str(DOWNLOAD_DIR / 'Serien')
                    SERIES_PATH = str(DOWNLOAD_DIR / 'Serien')
                    changed = True
                
                # Neue Content-Type basierte Pfade
                ANIME_PATH = cfg.get('anime_path', '')
                if 'anime_path' not in cfg:
                    cfg['anime_path'] = str(DOWNLOAD_DIR / 'Animes')
                    ANIME_PATH = str(DOWNLOAD_DIR / 'Animes')
                    changed = True
                    
                SERIEN_PATH = cfg.get('serien_path', '')
                if 'serien_path' not in cfg:
                    cfg['serien_path'] = str(DOWNLOAD_DIR / 'Serien')
                    SERIEN_PATH = str(DOWNLOAD_DIR / 'Serien')
                    changed = True
                
                # Film/Staffel Organisation
                ANIME_SEPARATE_MOVIES = cfg.get('anime_separate_movies', False)
                if 'anime_separate_movies' not in cfg:
                    cfg['anime_separate_movies'] = False
                    changed = True
                    
                SERIEN_SEPARATE_MOVIES = cfg.get('serien_separate_movies', False)
                if 'serien_separate_movies' not in cfg:
                    cfg['serien_separate_movies'] = False
                    changed = True
                # port (only from config; keep default if invalid)
                try:
                    port_val = cfg.get('port', SERVER_PORT)
                    if isinstance(port_val, str) and port_val.isdigit():
                        port_val = int(port_val)
                    if isinstance(port_val, int) and 1 <= port_val <= 65535:
                        SERVER_PORT = port_val
                    else:
                        cfg['port'] = SERVER_PORT
                        changed = True
                except Exception:
                    cfg['port'] = SERVER_PORT
                    changed = True
                # refresh_titles flag (default True)
                try:
                    if 'refresh_titles' in cfg:
                        REFRESH_TITLES = bool(cfg.get('refresh_titles'))
                    else:
                        cfg['refresh_titles'] = True
                        REFRESH_TITLES = True
                        changed = True
                except Exception:
                    REFRESH_TITLES = True
                    cfg['refresh_titles'] = True
                    changed = True
                # data_folder_path - add if missing but don't change global var during load
                if 'data_folder_path' not in cfg:
                    cfg['data_folder_path'] = data_folder
                    changed = True
                # persist if we added defaults
                if changed:
                    if _write_config_atomic(cfg):
                        log("[CONFIG] fehlende Schlüssel ergänzt und gespeichert")
                    else:
                        log("[CONFIG-ERROR] Ergänzung konnte nicht gespeichert werden (Datei evtl. gesperrt)")
                log(f"[CONFIG] geladen: languages={LANGUAGES} min_free_gb={MIN_FREE_GB} autostart_mode={AUTOSTART_MODE} data_folder={data_folder}")
        else:
            save_config()  # create default config
    except Exception as e:
        log(f"[CONFIG-ERROR] load_config: {e}")


def save_config():
    try:
        cfg = {
            'languages': LANGUAGES,
            'min_free_gb': MIN_FREE_GB,
            'download_path': str(DOWNLOAD_DIR),
            'storage_mode': STORAGE_MODE,
            'movies_path': MOVIES_PATH,
            'series_path': SERIES_PATH,
            'anime_path': ANIME_PATH,
            'serien_path': SERIEN_PATH,
            'anime_separate_movies': ANIME_SEPARATE_MOVIES,
            'serien_separate_movies': SERIEN_SEPARATE_MOVIES,
            'port': SERVER_PORT,
            'autostart_mode': AUTOSTART_MODE,
            'refresh_titles': REFRESH_TITLES,
            'data_folder_path': data_folder
        }
        # atomic write to avoid partial files
        tmp_path = str(CONFIG_PATH) + ".tmp"
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, CONFIG_PATH)
        log(f"[CONFIG] gespeichert")
        return True
    except Exception as e:
        log(f"[CONFIG-ERROR] save_config: {e}")
        return False

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 Edg/116.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_3_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36 OPR/102.0.0.0"
]

# -------------------- Logging-System --------------------
log_lines = []
log_lock = threading.Lock()
MAX_LOG_LINES = 2000
# Separate lock to serialize config writes on Windows
CONFIG_WRITE_LOCK = threading.Lock()

def log(msg):
    """Thread-safe log buffer + print."""
    ts = time.strftime("[%Y-%m-%d %H:%M:%S]")
    line = f"{ts} {msg}"
    with log_lock:
        log_lines.append(line)
        if len(log_lines) > MAX_LOG_LINES:
            del log_lines[: len(log_lines) - MAX_LOG_LINES]
    try:
        print(line, flush=True)
    except Exception:
        try:
            sys.stdout.write(line + "\n")
            sys.stdout.flush()
        except Exception:
            pass
def _write_config_atomic(cfg: dict) -> bool:
    """Write config.json with retries and atomic replace where possible.
    Handles transient PermissionError on Windows by retrying and finally
    falling back to a direct write if needed.
    """
    try:
        with CONFIG_WRITE_LOCK:
            dir_path = os.path.dirname(str(CONFIG_PATH))
            os.makedirs(dir_path, exist_ok=True)
            tmp_path = str(CONFIG_PATH) + ".tmp"
            # make sure target file is writable (remove read-only)
            try:
                if os.path.exists(CONFIG_PATH):
                    os.chmod(CONFIG_PATH, stat.S_IWRITE | stat.S_IREAD)
            except Exception:
                pass
            for attempt in range(5):
                try:
                    with open(tmp_path, 'w', encoding='utf-8') as wf:
                        json.dump(cfg, wf, indent=2, ensure_ascii=False)
                    os.replace(tmp_path, CONFIG_PATH)
                    return True
                except PermissionError:
                    # Clean temp and backoff
                    try:
                        if os.path.exists(tmp_path):
                            os.remove(tmp_path)
                    except Exception:
                        pass
                    time.sleep(0.3 * (attempt + 1))
                    continue
                except Exception:
                    # Cleanup and break to fallback
                    try:
                        if os.path.exists(tmp_path):
                            os.remove(tmp_path)
                    except Exception:
                        pass
                    break
            # Fallback: non-atomic write
            try:
                with open(CONFIG_PATH, 'w', encoding='utf-8') as wf:
                    json.dump(cfg, wf, indent=2, ensure_ascii=False)
                return True
            except Exception as e:
                log(f"[CONFIG-ERROR] final write failed: {e}")
                return False
    except Exception as e:
        log(f"[CONFIG-ERROR] _write_config_atomic: {e}")
        return False

# -------------------- Flask app --------------------
app = Flask(__name__, template_folder="templates", static_folder="static")
# CORS für Tampermonkey-Skript von HTTPS-Seiten (aniworld.to, s.to)
CORS(app, resources={r"/*": {"origins": "*", "allow_headers": "*", "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"]}})

# -------------------- DB-Funktionen --------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS anime (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            url TEXT UNIQUE,
            complete INTEGER DEFAULT 0,
            deutsch_komplett INTEGER DEFAULT 0,
            deleted INTEGER DEFAULT 0,
            fehlende_deutsch_folgen TEXT DEFAULT '[]',
            last_film INTEGER DEFAULT 0,
            last_episode INTEGER DEFAULT 0,
            last_season INTEGER DEFAULT 0
        )
    """)

    # Queue-Tabelle für "Als nächstes downloaden"
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            anime_id INTEGER,
            anime_url TEXT UNIQUE,
            added_at INTEGER DEFAULT (strftime('%s','now'))
        )
        """
    )

    # Migration: ensure 'position' column exists to support manual ordering
    try:
        c.execute("PRAGMA table_info(queue)")
        cols = [r[1] for r in c.fetchall()]
        if 'position' not in cols:
            c.execute("ALTER TABLE queue ADD COLUMN position INTEGER")
            # initialize position values in current order
            c.execute("SELECT id FROM queue ORDER BY added_at ASC, id ASC")
            qids = [r[0] for r in c.fetchall()]
            for idx, qid in enumerate(qids, start=1):
                c.execute("UPDATE queue SET position = ? WHERE id = ?", (idx, qid))
            conn.commit()
            log("[DB] queue.position Spalte hinzugefügt und initialisiert")
    except Exception as e:
        log(f"[DB-ERROR] Migration queue.position: {e}")

    # Recalculate IDs to ensure they are sequential
    c.execute("CREATE TEMPORARY TABLE anime_backup AS SELECT * FROM anime;")
    c.execute("DROP TABLE anime;")
    c.execute("""
        CREATE TABLE anime (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            url TEXT UNIQUE,
            complete INTEGER DEFAULT 0,
            deutsch_komplett INTEGER DEFAULT 0,
            deleted INTEGER DEFAULT 0,
            fehlende_deutsch_folgen TEXT DEFAULT '[]',
            last_film INTEGER DEFAULT 0,
            last_episode INTEGER DEFAULT 0,
            last_season INTEGER DEFAULT 0
        )
    """)
    c.execute("INSERT INTO anime (title, url, complete, deutsch_komplett, deleted, fehlende_deutsch_folgen, last_film, last_episode, last_season) SELECT title, url, complete, deutsch_komplett, deleted, fehlende_deutsch_folgen, last_film, last_episode, last_season FROM anime_backup;")
    c.execute("DROP TABLE anime_backup;")

    conn.commit()
    conn.close()

# -------------------- Title-Refresh beim Start --------------------
def refresh_titles_on_start():
    """Geht alle DB-Einträge mit https:// URL durch und aktualisiert den Titel, falls aus der URL-Seite ein anderer Name ermittelt wird."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, url, title FROM anime")
        rows = c.fetchall()
        updated = 0
        for aid, url, old_title in rows:
            try:
                if not isinstance(url, str) or not url.startswith("https://"):
                    continue
                new_title = get_series_title(url)
                if new_title and new_title != old_title:
                    c.execute("UPDATE anime SET title = ? WHERE id = ?", (new_title, aid))
                    updated += 1
                    log(f"[DB] Titel aktualisiert (ID {aid}): '{old_title}' -> '{new_title}'")
            except Exception as e:
                log(f"[WARN] Titel-Check fehlgeschlagen (ID {aid}): {e}")
        conn.commit()
        conn.close()
        log(f"[DB] Titel-Refresh abgeschlossen. Aktualisiert: {updated}")
    except Exception as e:
        log(f"[ERROR] Title refresh on start: {e}")

# -------------------- Import / Insert --------------------
def import_anime_txt():
    """Liest alle Links aus AniLoader.txt, fügt sie in die DB ein und leert die Datei anschließend."""
    if not ANIME_TXT.exists():
        log(f"[WARN] AniLoader.txt nicht gefunden: {ANIME_TXT}")
        return

    # Datei auslesen
    with open(ANIME_TXT, "r", encoding="utf-8") as f:
        links = [line.strip() for line in f if line.strip()]

    # Links in DB einfügen
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for url in links:
        insert_anime(url=url)
    conn.commit()
    conn.close()

    # AniLoader.txt leeren
    try:
        with open(ANIME_TXT, "w", encoding="utf-8") as f:
            f.truncate(0)
    except Exception as e:
        log(f"[ERROR] Konnte AniLoader.txt nicht leeren: {e}")


def insert_anime(url, title=None):
    """
    Fügt einen Anime in die DB ein.
    Wenn der Anime bereits existiert und als deleted markiert ist, wird deleted auf 0 gesetzt.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        if not title:
            # Serien-Titel abrufen oder aus URL ableiten (Best-Effort)
            try:
                title = get_series_title(url)
            except Exception:
                title = None
            if not title:
                m = re.search(r"/anime/stream/([^/]+)", url)
                if m:
                    title = m.group(1).replace("-", " ").title()
                else:
                    title = url

        # Prüfen, ob der Anime existiert
        c.execute("SELECT id, deleted FROM anime WHERE url = ?", (url,))
        row = c.fetchone()
        if row:
            anime_id, deleted_flag = row
            if deleted_flag == 1:
                # Wieder aktivieren: deleted -> 0, evtl. Titel aktualisieren
                c.execute("UPDATE anime SET deleted = 0, title = ? WHERE id = ?", (title, anime_id))
                conn.commit()
                log(f"[DB] Anime reaktiviert: {title} (ID {anime_id})")
            else:
                log(f"[DB] Anime existiert bereits: {title} (ID {anime_id})")
        else:
            # Neuer Eintrag
            c.execute("INSERT INTO anime (url, title) VALUES (?, ?)", (url, title))
            conn.commit()
            log(f"[DB] Neuer Anime eingefügt: {title}")
        return True
    except Exception as e:
        log(f"[DB-ERROR] {e}")
        return False
    finally:
        conn.close()

def update_anime(anime_id, **kwargs):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    fields = []
    values = []
    will_complete = False
    for key, val in kwargs.items():
        if key == "fehlende_deutsch_folgen":
            val = json.dumps(val)
        fields.append(f"{key} = ?")
        values.append(val)
        if key == 'complete' and bool(val):
            will_complete = True
    values.append(anime_id)
    if fields:
        c.execute(f"UPDATE anime SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()
    conn.close()
    # Entferne aus Queue, wenn jetzt komplett
    if will_complete:
        try:
            queue_delete_by_anime_id(anime_id)
            queue_prune_completed()
        except Exception as e:
            log(f"[QUEUE] Entfernen nach Abschluss fehlgeschlagen: {e}")

def load_anime():
    """
    Lädt alle Anime-Einträge aus der DB und gibt sie als Liste von Dicts zurück.
    Enthält jetzt auch das Feld 'deleted' damit caller entscheiden kann.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, title, url, complete, deutsch_komplett, deleted, fehlende_deutsch_folgen, last_film, last_episode, last_season FROM anime ORDER BY id")
    rows = c.fetchall()
    conn.close()
    anime_list = []
    for row in rows:
        entry = {
            "id": row[0],
            "title": row[1],
            "url": row[2],
            "complete": bool(row[3]),
            "deutsch_komplett": bool(row[4]),
            "deleted": bool(row[5]),
            "fehlende_deutsch_folgen": json.loads(row[6] or "[]"),
            "last_film": row[7],
            "last_episode": row[8],
            "last_season": row[9]
        }
        anime_list.append(entry)
    return anime_list

def queue_add(anime_id: int) -> bool:
    """Fügt eine Anime-ID zur Warteschlange hinzu (einzigartig)."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # ensure anime exists
        c.execute("SELECT id, url, complete FROM anime WHERE id = ?", (anime_id,))
        row = c.fetchone()
        if not row:
            return False
        _, aurl, complete_flag = row
        if complete_flag:
            # Bereits komplett -> nicht zur Queue hinzufügen
            log(f"[QUEUE] Anime {anime_id} ist bereits komplett – nicht zur Warteschlange hinzugefügt.")
            return False
        # schon vorhanden?
        c.execute("SELECT id FROM queue WHERE anime_url = ?", (aurl,))
        if c.fetchone():
            conn.close()
            return True
        # nächste Position bestimmen
        c.execute("SELECT COALESCE(MAX(position), 0) FROM queue")
        next_pos = (c.fetchone() or [0])[0] + 1
        c.execute("INSERT INTO queue (anime_id, anime_url, position) VALUES (?, ?, ?)", (anime_id, aurl, next_pos))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        log(f"[DB-ERROR] queue_add: {e}")
        return False

def queue_list():
    """Gibt die Queue als Liste von Dicts mit id, anime_id, title zurück (sortiert)."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            """
            SELECT q.id, a.id as anime_id, a.title, COALESCE(q.position, 0) as position
            FROM queue q
            LEFT JOIN anime a ON a.url = q.anime_url
            ORDER BY position ASC, q.added_at ASC, q.id ASC
            """
        )
        rows = c.fetchall()
        conn.close()
        return [{"id": r[0], "anime_id": r[1], "title": r[2], "position": r[3]} for r in rows]
    except Exception as e:
        log(f"[DB-ERROR] queue_list: {e}")
        return []

def queue_clear():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM queue")
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        log(f"[DB-ERROR] queue_clear: {e}")
        return False

def queue_pop_next():
    """Entnimmt das erste Queue-Element und gibt anime_id zurück, sonst None."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, anime_url FROM queue ORDER BY position ASC, added_at ASC, id ASC LIMIT 1")
        row = c.fetchone()
        if not row:
            conn.close()
            return None
        qid, aurl = row
        c.execute("DELETE FROM queue WHERE id = ?", (qid,))
        conn.commit()
        conn.close()
        # map url to current anime id (IDs could be recalculated in init_db)
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT id FROM anime WHERE url = ?", (aurl,))
            r2 = c.fetchone()
            conn.close()
            return r2[0] if r2 else None
        except Exception:
            return None
    except Exception as e:
        log(f"[DB-ERROR] queue_pop_next: {e}")
        return None

def queue_prune_completed():
    """Entfernt alle Queue-Einträge, deren Anime bereits als komplett markiert ist (oder nicht mehr existiert)."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # lösche alle, deren URL zu einem complete=1 Anime gehört
        c.execute(
            "DELETE FROM queue WHERE anime_url IN (SELECT url FROM anime WHERE complete = 1)"
        )
        # optional: verwaiste Einträge (ohne zugehörigen Anime) entfernen
        c.execute(
            "DELETE FROM queue WHERE anime_url NOT IN (SELECT url FROM anime)"
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        log(f"[DB-ERROR] queue_prune_completed: {e}")
        return False

def queue_delete_by_anime_id(anime_id: int) -> bool:
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM queue WHERE anime_id = ?", (anime_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        log(f"[DB-ERROR] queue_delete_by_anime_id: {e}")
        return False

def queue_delete(qid: int) -> bool:
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM queue WHERE id = ?", (qid,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        log(f"[DB-ERROR] queue_delete: {e}")
        return False

def queue_reorder(order_ids):
    """Setzt die Reihenfolge der Queue über die Liste von Queue-IDs (id aus /queue GET)."""
    try:
        if not isinstance(order_ids, list) or not all(isinstance(x, int) for x in order_ids):
            return False
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # Weisen die übergebenen Positionen zu
        for pos, qid in enumerate(order_ids, start=1):
            c.execute("UPDATE queue SET position = ? WHERE id = ?", (pos, qid))
        # Restliche (nicht genannte) hinten anhängen in aktueller Reihenfolge
        placeholders = ",".join(["?"] * len(order_ids)) if order_ids else None
        if placeholders:
            c.execute(f"SELECT id FROM queue WHERE id NOT IN ({placeholders}) ORDER BY position ASC, added_at ASC, id ASC", order_ids)
        else:
            c.execute("SELECT id FROM queue ORDER BY position ASC, added_at ASC, id ASC")
        start_pos = len(order_ids) + 1
        rest = [r[0] for r in c.fetchall()]
        for idx, qid in enumerate(rest, start=start_pos):
            c.execute("UPDATE queue SET position = ? WHERE id = ?", (idx, qid))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        log(f"[DB-ERROR] queue_reorder: {e}")
        return False

def check_deutsch_komplett(anime_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT fehlende_deutsch_folgen FROM anime WHERE id = ?", (anime_id,))
    row = c.fetchone()
    conn.close()
    fehlende = json.loads(row[0]) if row and row[0] else []
    if not fehlende:
        update_anime(anime_id, deutsch_komplett=1)
        log(f"[INFO] Serien-ID {anime_id} komplett auf Deutsch markiert")
        return True
    return False

# -------------------- Hilfsfunktionen --------------------
def get_headers():
    return {"User-Agent": random.choice(USER_AGENTS)}

def sanitize_title(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = re.sub(r'\.', '#', name)
    return name

def check_length(dest_folder: Path, base_name: str, title: str, lang_suffix: str, extension: str = ".mp4") -> str:
    """
    Kürzt den Titel, falls der komplette Pfad sonst die Windows MAX_PATH-Grenze überschreiten würde.
    Berücksichtigt den Sprach-Suffix!
    """
    # Finaler Dateiname
    simulated_name = f"{base_name}"
    if title:
        simulated_name += f" - {title}"
    if lang_suffix:
        simulated_name += f" {lang_suffix}"
    simulated_name += extension

    full_path = dest_folder / simulated_name

    # Prüfen, ob alles okay ist
    if len(str(full_path)) <= MAX_PATH:
        return title

    # Berechne erlaubte Titel-Länge dynamisch
    reserved = len(str(dest_folder)) + len(base_name) + len(extension) + len(lang_suffix) + 10
    max_title_length = MAX_PATH - reserved
    if max_title_length < 0:
        max_title_length = 0

    shortened_title = title[:max_title_length]

    if shortened_title != title:
        log(f"[INFO] Titel gekürzt: '{title}' -> '{shortened_title}'")

    return shortened_title

def sanitize_episode_title(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    return name

def freier_speicher_mb(pfad: str) -> float:
    """Gibt den verfügbaren Speicherplatz des angegebenen Pfads in GB zurück."""
    try:
        gesamt, belegt, frei = shutil.disk_usage(pfad)
        return round(frei / (1024 ** 3), 1)
    except FileNotFoundError:
        raise ValueError(f"Pfad nicht gefunden: {pfad}")
    except PermissionError:
        raise PermissionError(f"Zugriff verweigert auf: {pfad}")


def get_episode_title(url):
    try:
        headers = get_headers()
        host = urlparse(url).hostname
        ips = resolve_ips_via_cloudflare(host)
        with DnsOverride(host, ips):
            r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        german_title = soup.select_one("span.episodeGermanTitle")
        if german_title and german_title.text.strip():
            title = sanitize_episode_title(german_title.text.strip())
            return title
        english_title = soup.select_one("small.episodeEnglishTitle") 
        if english_title and english_title.text.strip():
            title = sanitize_episode_title(english_title.text.strip())
            return title
    except Exception as e:
        log(f"[FEHLER] Konnte Episodentitel nicht abrufen ({url}): {e}")
    return None

def get_series_title(url):
    try:
        headers = get_headers()
        host = urlparse(url).hostname
        ips = resolve_ips_via_cloudflare(host)
        with DnsOverride(host, ips):
            r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        title = soup.select_one("div.series-title h1 span")
        if title and title.text.strip():
            return sanitize_title(title.text.strip())
    except Exception as e:
        log(f"[FEHLER] Konnte Serien-Titel nicht abrufen ({url}): {e}")
    return None

# -------------------- DNS über 1.1.1.1 nur für Titelabfragen --------------------
def resolve_ips_via_cloudflare(hostname: str):
    """DNS-Auflösung über Cloudflare (1.1.1.1). Gibt Liste von IPs zurück oder None bei Fehler."""
    if not hostname:
        return None
    try:
        import dns.resolver  # type: ignore
        resolver = dns.resolver.Resolver(configure=False)
        resolver.nameservers = ["1.1.1.1"]
        ips = []
        for rrtype in ("A", "AAAA"):
            try:
                ans = resolver.resolve(hostname, rrtype, lifetime=2.0)
                for rdata in ans:
                    ips.append(rdata.address)
            except Exception:
                pass
        return ips or None
    except Exception:
        return None


class DnsOverride:
    """Kontextmanager, der socket.getaddrinfo temporär patcht, um den angegebenen Host
    mit vorgegebenen IPs (via 1.1.1.1 aufgelöst) zu beantworten."""
    def __init__(self, hostname: str, ips):
        self.hostname = hostname
        self.ips = ips or []
        self._orig = None

    def __enter__(self):
        if not self.hostname or not self.ips:
            return self
        self._orig = socket.getaddrinfo

        def _patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
            try:
                if host == self.hostname:
                    results = []
                    for ip in self.ips:
                        if ":" in ip:
                            fam = socket.AF_INET6
                            sockaddr = (ip, port, 0, 0)
                        else:
                            fam = socket.AF_INET
                            sockaddr = (ip, port)
                        results.append((fam, socket.SOCK_STREAM, proto or 0, "", sockaddr))
                    return results
            except Exception:
                pass
            return self._orig(host, port, family, type, proto, flags)

        socket.getaddrinfo = _patched_getaddrinfo
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._orig:
            try:
                socket.getaddrinfo = self._orig
            except Exception:
                pass
        return False

def get_base_path_for_content(is_film=False):
    """
    Gibt den Basis-Pfad für Downloads zurück, basierend auf storage_mode.
    - 'standard': Verwendet DOWNLOAD_DIR für alles
    - 'separate': Verwendet MOVIES_PATH für Filme, SERIES_PATH für Serien
    """
    if STORAGE_MODE == 'separate':
        if is_film and MOVIES_PATH:
            path = Path(MOVIES_PATH)
            path.mkdir(parents=True, exist_ok=True)
            return path
        elif not is_film and SERIES_PATH:
            path = Path(SERIES_PATH)
            path.mkdir(parents=True, exist_ok=True)
            return path
    # Fallback zu DOWNLOAD_DIR (standard mode oder wenn separate Pfade nicht gesetzt sind)
    return DOWNLOAD_DIR

def episode_already_downloaded(series_folder, season, episode):
    if not os.path.exists(series_folder):
        return False
    if season > 0:
        pattern = f"S{season:02d}E{episode:03d}"
    else:
        pattern = f"Film{episode:02d}"
    for file in Path(series_folder).rglob("*.mp4"):
        if pattern.lower() in file.name.lower():
            return True
    return False

def delete_old_non_german_versions(series_folder, season, episode):
    if isinstance(series_folder, str):
        base = Path(series_folder)
    else:
        base = Path(DOWNLOAD_DIR) / series_folder
    pattern = f"S{season:02d}E{episode:03d}" if season > 0 else f"Film{episode:02d}"
    for file in base.rglob("*.mp4"):
        if pattern.lower() in file.name.lower():
            if "[sub]" in file.name.lower() or "[english dub]" in file.name.lower() or "[english sub]" in file.name.lower():
                try:
                    os.remove(file)
                    log(f"[DEL] Alte Version gelöscht: {file.name}")
                except Exception as e:
                    log(f"[FEHLER] Konnte Datei nicht löschen: {file.name} -> {e}")

def rename_downloaded_file(series_folder, season, episode, title, language):
    # Always use a string suffix to avoid len() TypeError in check_length
    lang_suffix = {
        "German Dub": "",
        "German Sub": "[Sub]",
        "English Dub": "[English Dub]",
        "English Sub": "[English Sub]"
    }.get(language, "")

    if season > 0:
        pattern = f"S{season:02d}E{episode:03d}"
        matching_files = [f for f in Path(series_folder).rglob("*.mp4") if pattern.lower() in f.name.lower()]
        if not matching_files:
            print(f"[WARN] Keine Datei gefunden für {pattern}")
            return False
        file_to_rename = matching_files[0]
    else:
        pattern = f"Movie {episode:03d}"
        matching_files = [f for f in Path(series_folder).rglob("*.mp4") if pattern.lower() in f.name.lower()]
        if not matching_files:
            print(f"[WARN] Keine Datei gefunden für Film {episode}")
            return False
        file_to_rename = matching_files[0]
        pattern = f"Film{episode:02d}"

    safe_title = sanitize_episode_title(title) if title else ""

    # Im separate Modus keinen "Filme" Unterordner erstellen, da wir bereits im Filme-Ordner sind
    if STORAGE_MODE == 'separate' and season == 0:
        dest_folder = Path(series_folder)
    else:
        dest_folder = Path(series_folder) / ("Filme" if season == 0 else f"Staffel {season}")
    dest_folder.mkdir(parents=True, exist_ok=True)

    safe_title = check_length(dest_folder, pattern, safe_title, lang_suffix)

    new_name = f"{pattern}"
    if safe_title:
        new_name += f" - {safe_title}"
    if lang_suffix:
        new_name += f" {lang_suffix}"
    new_name += ".mp4"

    new_path = dest_folder / new_name

    try:
        shutil.move(file_to_rename, new_path)
        log(f"[OK] Umbenannt: {file_to_rename.name} -> {new_name}")
        return True
    except Exception as e:
        log(f"[FEHLER] Umbenennen fehlgeschlagen: {e}")
        return False

def run_download(cmd):
    """Startet externes CLI-Tool (aniworld) und interpretiert Ausgabe."""
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        outs, _ = process.communicate()
        out = outs or ""
        if "No streams available for episode" in out:
            return "NO_STREAMS"
        if "No provider found for language" in out:
            return "LANGUAGE_ERROR"
        return "OK" if process.returncode == 0 else "FAILED"
    except Exception as e:
        log(f"[FEHLER] run_download: {e}")
        return "FAILED"

# -------------------- Download-Funktionen --------------------
def download_episode(series_title, episode_url, season, episode, anime_id, german_only=False):
    
    # Aktuellen Downloadstatus (Staffel/Episode/Film) für das UI setzen
    try:
        with download_lock:
            current_download["current_season"] = int(season)
            current_download["current_episode"] = int(episode)
            current_download["current_is_film"] = (int(season) == 0)
            current_download["episode_started_at"] = time.time()
    except Exception:
        pass
    
    # Bestimme den richtigen Basis-Pfad basierend auf Inhalt (Film vs. Serie)
    is_film = (season == 0)
    base_path = get_base_path_for_content(is_film)
    
    # Prüfe freien Speicher vor jedem Download (freier_speicher_mb liefert GB)
    try:
        free_gb = freier_speicher_mb(base_path)
    except Exception as e:
        log(f"[ERROR] Konnte freien Speicher nicht ermitteln: {e}")
        return "FAILED"

    if free_gb < MIN_FREE_GB:
        log(f"[ERROR] Zu wenig freier Speicher ({free_gb} GB < {MIN_FREE_GB} GB) im Download-Ordner ({base_path}) - Abbruch")
        # Status global setzen, damit Web-UI es anzeigen kann
        try:
            with download_lock:
                current_download["status"] = "kein-speicher"
        except Exception:
            pass
        return "NO_SPACE"
    
    series_folder = os.path.join(base_path, series_title)
    if not german_only:
        if episode_already_downloaded(series_folder, season, episode):
            log(f"[SKIP] Episode bereits vorhanden: {series_title} - " + (f"S{season}E{episode}" if season > 0 else f"Film {episode}"))
            try:
                with download_lock:
                    current_download["episode_started_at"] = None
            except Exception:
                pass
            return "SKIPPED"

    langs_to_try = ["German Dub"] if german_only else LANGUAGES
    episode_downloaded = False
    german_available = False

    for lang in langs_to_try:
        log(f"[DOWNLOAD] Versuche {lang} -> {episode_url}")
        cmd = ["aniworld", "--language", lang, "-o", str(base_path), "--episode", episode_url]
        result = run_download(cmd)
        
        if result == "NO_STREAMS":
            log(f"[INFO] Kein Stream verfügbar: {episode_url} -> Abbruch")
            return "NO_STREAMS"
        elif result == "OK":
            title = get_episode_title(episode_url)
            rename_downloaded_file(series_folder, season, episode, title, lang)
            if lang == "German Dub":
                german_available = True
                if german_only == True:
                    delete_old_non_german_versions(series_folder=series_folder, season=season, episode=episode)
            episode_downloaded = True
            log(f"[OK] {lang} erfolgreich geladen: {episode_url}")
            break
        elif result == "LANGUAGE_ERROR":
            log(f"[INFO] Sprache {lang} nicht gefunden für {episode_url}, prüfe nächste Sprache.")
            continue

    if not german_available:
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT fehlende_deutsch_folgen FROM anime WHERE id = ?", (anime_id,))
            row = c.fetchone()
            fehlende = json.loads(row[0]) if row and row[0] else []
            if episode_url not in fehlende:
                # Nur in DB schreiben, wenn noch genug Speicher zur Verfügung steht
                try:
                    free_after_gb = freier_speicher_mb(base_path)
                except Exception:
                    free_after_gb = 0
                if free_after_gb >= MIN_FREE_GB:
                    fehlende.append(episode_url)
                    update_anime(anime_id, fehlende_deutsch_folgen=fehlende)
                    log(f"[INFO] Episode zu fehlende_deutsch_folgen hinzugefügt: {episode_url}")
                else:
                    log(f"[WARN] DB nicht aktualisiert wegen zu wenig Speicher: {episode_url}")
        except Exception as e:
            log(f"[DB-ERROR] beim Aktualisieren fehlende_deutsch_folgen: {e}")
        finally:
            try:
                conn.close()
            except:
                pass
    return "OK" if episode_downloaded else "FAILED"

def download_films(series_title, base_url, anime_id, german_only=False, start_film=1):
    film_num = start_film
    log(f"[INFO] Starte Filmprüfung ab Film {start_film}")
    while True:
        film_url = f"{base_url}/filme/film-{film_num}"
        result = download_episode(series_title, film_url, 0, film_num, anime_id, german_only)
        
        if result == "NO_SPACE":
            log(f"[ERROR] Abbruch aller Film-Downloads wegen fehlendem Speicher.")
            return "NO_SPACE"
        if result in ["NO_STREAMS", "FAILED"]:
            log(f"[INFO] Keine weiteren Filme gefunden bei Film {film_num}.")
            break
        update_anime(anime_id, last_film=film_num)
        film_num += 1
        time.sleep(1)

def download_seasons(series_title, base_url, anime_id, german_only=False, start_season=1, start_episode=1):
    season = start_season if start_season > 0 else 1
    consecutive_empty_seasons = 0

    while True:
        episode = start_episode
        found_episode_in_season = False
        log(f"[DOWNLOAD] Prüfe Staffel {season} von '{series_title}'")
        while True:
            episode_url = f"{base_url}/staffel-{season}/episode-{episode}"
            result = download_episode(series_title, episode_url, season, episode, anime_id, german_only)
            
            if result == "NO_SPACE":
                log(f"[ERROR] Abbruch aller Staffel-Downloads wegen fehlendem Speicher.")
                return "NO_SPACE"
            if result in ["NO_STREAMS", "FAILED"]:
                if episode == start_episode:
                    log(f"[INFO] Keine Episoden gefunden in Staffel {season}.")
                    break
                else:
                    log(f"[INFO] Staffel {season} beendet nach {episode-1} Episoden.")
                    break
            found_episode_in_season = True
            update_anime(anime_id, last_episode=episode, last_season=season)
            episode += 1
            time.sleep(1)

        if not found_episode_in_season:
            consecutive_empty_seasons += 1
        else:
            consecutive_empty_seasons = 0

        if consecutive_empty_seasons >= 2:
            log(f"[INFO] Keine weiteren Staffeln gefunden. '{series_title}' scheint abgeschlossen zu sein.")
            break

        season += 1
        start_episode = 1


# -------------------- deleted_check --------------------
def deleted_check():
    """
    Prüft, welche Animes in der DB als complete markiert sind,
    aber nicht mehr im Downloads-Ordner existieren.
    Setzt diese Animes anschließend auf Initialwerte zurück und markiert deleted = 1.
    Berücksichtigt beide Pfade wenn separate Mode aktiv ist.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # --- IDs + Titel aller als 'complete' markierten Animes holen ---
        c.execute("SELECT id, title FROM anime WHERE complete = 1")
        complete_animes_in_db = c.fetchall() # Liste von Tupeln: [(id, title), ...]

        # --- Alle Ordnernamen im Downloads-Verzeichnis lesen (erste Ebene) ---
        local_animes = []
        
        # Sammle alle lokalen Anime-Ordner aus allen relevanten Pfaden
        # Standard-Pfad oder Serien-Pfad prüfen
        if STORAGE_MODE == 'separate' and SERIES_PATH:
            series_path = Path(SERIES_PATH)
            if series_path.exists():
                local_animes.extend([folder.name for folder in series_path.iterdir() if folder.is_dir()])
        
        # Film-Pfad im separate Mode prüfen
        if STORAGE_MODE == 'separate' and MOVIES_PATH:
            movies_path = Path(MOVIES_PATH)
            if movies_path.exists():
                local_animes.extend([folder.name for folder in movies_path.iterdir() if folder.is_dir()])
        
        # Im standard Mode nur DOWNLOAD_DIR prüfen
        if STORAGE_MODE == 'standard':
            downloads_path = Path(DOWNLOAD_DIR)
            if downloads_path.exists():
                local_animes = [folder.name for folder in downloads_path.iterdir() if folder.is_dir()]

        log(f"[CHECK] Gefundene complete-Animes in DB: {len(complete_animes_in_db)}")
        log(f"[CHECK] Gefundene lokale Animes: {len(local_animes)}")

        deleted_anime = []

        # --- Überprüfen, welche Animes gelöscht wurden ---
        for anime_id, anime_title in complete_animes_in_db:
            if anime_title not in local_animes:
                deleted_anime.append(anime_title)

                # Anime in der DB auf Initialwerte zurücksetzen, aber Titel + URL + ID behalten
                c.execute("""
                    UPDATE anime
                    SET complete = 0,
                        deutsch_komplett = 0,
                        deleted = 1,
                        fehlende_deutsch_folgen = '[]',
                        last_film = 0,
                        last_episode = 0,
                        last_season = 0
                    WHERE id = ?
                """, (anime_id,))

        # Änderungen speichern
        conn.commit()
        conn.close()

        log(f"[INFO] Gelöschte Animes: {deleted_anime}")

        return deleted_anime

    except Exception as e:
        log(f"[ERROR] deleted_check: {e}")
        return []

# -------------------- Haupt-Runner (wird im Thread ausgeführt) --------------------
current_download = {
    "status": "idle",  # idle, running, finished
    "mode": None,
    "current_index": None,
    "current_title": None,
    "started_at": None,
    "anime_started_at": None,
    "episode_started_at": None,
    "current_season": None,
    "current_episode": None,
    "current_is_film": None,
    "current_id": None,
    "current_url": None
}
download_lock = threading.Lock()

def run_mode(mode="default"):
    global current_download
    with download_lock:
        if current_download["status"] == "running":
            log("[INFO] Download bereits laufend — start abgebrochen.")
            return
        current_download.update({
            "status": "running",
            "mode": mode,
            "current_index": 0,
            "current_title": None,
            "started_at": time.time(),
            "anime_started_at": None,
            "episode_started_at": None,
            "current_season": None,
            "current_episode": None,
            "current_is_film": None,
            "current_id": None,
            "current_url": None
        })
    
    try:
        init_db()
        # lade Anime inkl. 'deleted' flag
        anime_list = load_anime()
        # Prüfe Queue und bilde Prioritätenliste
        queue_prune_completed()
        queued = queue_list()
        queued_ids = [q['anime_id'] for q in queued]
        priority_map = {aid: idx for idx, aid in enumerate(queued_ids)}
        if queued_ids:
            log(f"[QUEUE] {len(queued_ids)} Einträge werden priorisiert verarbeitet.")
        log(f"[INFO] Gewählter Modus: {mode}")
        if mode == "german":
            log("=== Modus: Prüfe auf neue deutsche Synchro ===")
            # 1) Zuerst Queue (falls vorhanden)
            if queued_ids:
                work_list = [a for a in anime_list if a['id'] in queued_ids]
                work_list.sort(key=lambda a: priority_map.get(a['id'], 1_000_000))
                log(f"[QUEUE] Starte mit {len(work_list)} Einträgen aus der Warteschlange (German)")
                for idx, anime in enumerate(work_list):
                    current_download["current_index"] = idx
                    # Überspringen wenn als deleted markiert
                    if anime.get("deleted"):
                        log(f"[SKIP] '{anime['title']}' übersprungen (deleted flag gesetzt).")
                        continue
                    series_title = anime["title"] or get_series_title(anime["url"])
                    anime_id = anime["id"]
                    current_download["current_title"] = series_title
                    current_download["anime_started_at"] = time.time()
                    current_download["current_id"] = anime_id
                    current_download["current_url"] = anime["url"]
                    current_download["episode_started_at"] = None
                    fehlende = anime.get("fehlende_deutsch_folgen", [])
                    if not fehlende:
                        log(f"[GERMAN] '{series_title}': Keine neuen deutschen Folgen")
                        continue
                    log(f"[GERMAN] '{series_title}': {len(fehlende)} Folgen zu testen.")
                    verbleibend = fehlende.copy()
                    for url in fehlende:
                        match = re.search(r"/staffel-(\d+)/episode-(\d+)", url)
                        if match:
                            season = int(match.group(1))
                            episode = int(match.group(2))
                        else:
                            m2 = re.search(r"/film-(\d+)", url)
                            season = 0
                            episode = int(m2.group(1)) if m2 else 1
                        result = download_episode(series_title, url, season, episode, anime_id, german_only=True)
                        if result == "OK" and url in verbleibend:
                            verbleibend.remove(url)
                            update_anime(anime_id, fehlende_deutsch_folgen=verbleibend)
                            log(f"[GERMAN] '{url}' erfolgreich auf deutsch.")
                            delete_old_non_german_versions(series_folder=os.path.join(DOWNLOAD_DIR, series_title), season=season, episode=episode)
                    check_deutsch_komplett(anime_id)
                    # Entferne diesen Eintrag aus der Queue (falls vorhanden)

            # 2) Danach restliche DB-Einträge
            rest_list = [a for a in anime_list if not queued_ids or a['id'] not in queued_ids]
            for idx, anime in enumerate(rest_list):
                current_download["current_index"] = idx
                # Überspringen wenn als deleted markiert
                if anime.get("deleted"):
                    log(f"[SKIP] '{anime['title']}' übersprungen (deleted flag gesetzt).")
                    continue
                series_title = anime["title"] or get_series_title(anime["url"])
                anime_id = anime["id"]
                current_download["current_title"] = series_title
                current_download["anime_started_at"] = time.time()
                current_download["current_id"] = anime_id
                current_download["current_url"] = anime["url"]
                current_download["episode_started_at"] = None
                fehlende = anime.get("fehlende_deutsch_folgen", [])
                if not fehlende:
                    log(f"[GERMAN] '{series_title}': Keine neuen deutschen Folgen")
                    continue
                log(f"[GERMAN] '{series_title}': {len(fehlende)} Folgen zu testen.")
                verbleibend = fehlende.copy()
                for url in fehlende:
                    match = re.search(r"/staffel-(\d+)/episode-(\d+)", url)
                    if match:
                        season = int(match.group(1))
                        episode = int(match.group(2))
                    else:
                        m2 = re.search(r"/film-(\d+)", url)
                        season = 0
                        episode = int(m2.group(1)) if m2 else 1
                    result = download_episode(series_title, url, season, episode, anime_id, german_only=True)
                    
                    if result == "OK" and url in verbleibend:
                        verbleibend.remove(url)
                        update_anime(anime_id, fehlende_deutsch_folgen=verbleibend)
                        log(f"[GERMAN] '{url}' erfolgreich auf deutsch.")
                        delete_old_non_german_versions(series_folder=os.path.join(DOWNLOAD_DIR, series_title), season=season, episode=episode)
                check_deutsch_komplett(anime_id)
                # Nach jedem DB-Eintrag: Queue erneut prüfen und sofort abarbeiten
                try:
                    queue_prune_completed()
                    queued_now = queue_list()
                    if queued_now:
                        amap = {a['id']: a for a in load_anime()}
                        work_q = [amap[q['anime_id']] for q in queued_now if q.get('anime_id') in amap]
                        work_q.sort(key=lambda a: next((i for i,q in enumerate(queued_now) if q['anime_id']==a['id']), 999999))
                        log(f"[QUEUE] {len(work_q)} neue Einträge – abarbeiten (German)")
                        for q_anime in work_q:
                            if q_anime.get('deleted'):
                                log(f"[SKIP] '{q_anime['title']}' übersprungen (deleted flag gesetzt).")
                                queue_delete_by_anime_id(q_anime['id'])
                                continue
                            q_series_title = q_anime['title'] or get_series_title(q_anime['url'])
                            q_anime_id = q_anime['id']
                            current_download["current_title"] = q_series_title
                            current_download["anime_started_at"] = time.time()
                            current_download["current_id"] = q_anime_id
                            current_download["current_url"] = q_anime['url']
                            current_download["episode_started_at"] = None
                            fehlende = q_anime.get('fehlende_deutsch_folgen', [])
                            if not fehlende:
                                log(f"[GERMAN] '{q_series_title}': Keine neuen deutschen Folgen")
                                queue_delete_by_anime_id(q_anime_id)
                                continue
                            verbleibend = fehlende.copy()
                            for url in fehlende:
                                m = re.search(r"/staffel-(\d+)/episode-(\d+)", url)
                                if m:
                                    s = int(m.group(1)); e = int(m.group(2))
                                else:
                                    m2 = re.search(r"/film-(\d+)", url)
                                    s = 0; e = int(m2.group(1)) if m2 else 1
                                r = download_episode(q_series_title, url, s, e, q_anime_id, german_only=True)
                                if r == 'OK' and url in verbleibend:
                                    verbleibend.remove(url)
                                    update_anime(q_anime_id, fehlende_deutsch_folgen=verbleibend)
                                    delete_old_non_german_versions(series_folder=os.path.join(DOWNLOAD_DIR, q_series_title), season=s, episode=e)
                            check_deutsch_komplett(q_anime_id)
                            queue_delete_by_anime_id(q_anime_id)
                except Exception as _e:
                    log(f"[QUEUE] Re-Check Fehler (German): {_e}")
        elif mode == "new":
            log("=== Modus: Prüfe auf neue Episoden & Filme ===")
            # 1) Zuerst Queue
            if queued_ids:
                work_list = [a for a in anime_list if a['id'] in queued_ids]
                work_list.sort(key=lambda a: priority_map.get(a['id'], 1_000_000))
                log(f"[QUEUE] Starte mit {len(work_list)} Einträgen aus der Warteschlange (New)")
                for idx, anime in enumerate(work_list):
                    current_download["current_index"] = idx
                    if anime.get("deleted"):
                        log(f"[SKIP] '{anime['title']}' übersprungen (deleted flag gesetzt).")
                        continue
                    series_title = anime["title"] or get_series_title(anime["url"])
                    anime_id = anime["id"]
                    base_url = anime["url"]
                    current_download["current_title"] = series_title
                    current_download["anime_started_at"] = time.time()
                    current_download["current_id"] = anime_id
                    current_download["current_url"] = base_url
                    current_download["episode_started_at"] = None
                    start_film = (anime.get("last_film") or 1)
                    start_season = anime.get("last_season") or 1
                    start_episode = (anime.get("last_episode") or 1) if start_season > 0 else 1
                    log(f"[NEW] Prüfe '{series_title}' ab Film {start_film} und Staffel {start_season}, Episode {start_episode}")
                    r = download_films(series_title, base_url, anime_id, start_film=start_film)
                    if r == "NO_SPACE":
                        log("[ERROR] Downloadlauf abgebrochen wegen fehlendem Speicher (new mode).")
                        return
                    r2 = download_seasons(series_title, base_url, anime_id, start_season=start_season, start_episode=start_episode)
                    if r2 == "NO_SPACE":
                        log("[ERROR] Downloadlauf abgebrochen wegen fehlendem Speicher (new mode).")
                        return
                    check_deutsch_komplett(anime_id)
                    # Entferne aus Queue
                    queue_delete_by_anime_id(anime_id)

            # 2) Danach restliche DB-Einträge
            rest_list = [a for a in anime_list if not queued_ids or a['id'] not in queued_ids]
            for idx, anime in enumerate(rest_list):
                
                current_download["current_index"] = idx
                if anime.get("deleted"):
                    log(f"[SKIP] '{anime['title']}' übersprungen (deleted flag gesetzt).")
                    continue
                series_title = anime["title"] or get_series_title(anime["url"])
                anime_id = anime["id"]
                base_url = anime["url"]
                current_download["current_title"] = series_title
                current_download["anime_started_at"] = time.time()
                current_download["current_id"] = anime_id
                current_download["current_url"] = base_url
                current_download["episode_started_at"] = None
                start_film = (anime.get("last_film") or 1)
                start_season = anime.get("last_season") or 1
                start_episode = (anime.get("last_episode") or 1) if start_season > 0 else 1
                log(f"[NEW] Prüfe '{series_title}' ab Film {start_film} und Staffel {start_season}, Episode {start_episode}")
                r = download_films(series_title, base_url, anime_id, start_film=start_film)
                if r == "NO_SPACE":
                    log("[ERROR] Downloadlauf abgebrochen wegen fehlendem Speicher (new mode).")
                    return
                r2 = download_seasons(series_title, base_url, anime_id, start_season=start_season, start_episode=start_episode)
                if r2 == "NO_SPACE":
                    log("[ERROR] Downloadlauf abgebrochen wegen fehlendem Speicher (new mode).")
                    return
                check_deutsch_komplett(anime_id)
                # Nach jedem DB-Eintrag: Queue erneut prüfen und abarbeiten
                try:
                    queue_prune_completed()
                    queued_now = queue_list()
                    if queued_now:
                        amap = {a['id']: a for a in load_anime()}
                        work_q = [amap[q['anime_id']] for q in queued_now if q.get('anime_id') in amap]
                        work_q.sort(key=lambda a: next((i for i,q in enumerate(queued_now) if q['anime_id']==a['id']), 999999))
                        log(f"[QUEUE] {len(work_q)} neue Einträge – abarbeiten (New)")
                        for q_anime in work_q:
                            if q_anime.get('deleted'):
                                log(f"[SKIP] '{q_anime['title']}' übersprungen (deleted flag gesetzt).")
                                queue_delete_by_anime_id(q_anime['id'])
                                continue
                            q_series_title = q_anime['title'] or get_series_title(q_anime['url'])
                            q_anime_id = q_anime['id']
                            base_url = q_anime['url']
                            current_download["current_title"] = q_series_title
                            current_download["anime_started_at"] = time.time()
                            current_download["current_id"] = q_anime_id
                            current_download["current_url"] = base_url
                            current_download["episode_started_at"] = None
                            start_film = (q_anime.get('last_film') or 1)
                            start_season = q_anime.get('last_season') or 1
                            start_episode = (q_anime.get('last_episode') or 1) if start_season > 0 else 1
                            r = download_films(q_series_title, base_url, q_anime_id, start_film=start_film)
                            if r == 'NO_SPACE':
                                return
                            r2 = download_seasons(q_series_title, base_url, q_anime_id, start_season=start_season, start_episode=start_episode)
                            if r2 == 'NO_SPACE':
                                return
                            check_deutsch_komplett(q_anime_id)
                            queue_delete_by_anime_id(q_anime_id)
                except Exception as _e:
                    log(f"[QUEUE] Re-Check Fehler (New): {_e}")

        elif mode == "check-missing":
            log("=== Modus: Prüfe auf fehlende Episoden & Filme ===")
            """
            Prüft alle Anime, die entweder teilweise oder komplett heruntergeladen sind,
            und versucht fehlende Filme oder Episoden erneut zu laden.
            """
            anime_list = load_anime()
            # 1) Zuerst Queue
            if queued_ids:
                work_list = [a for a in anime_list if a['id'] in queued_ids]
                work_list.sort(key=lambda a: priority_map.get(a['id'], 1_000_000))
                log(f"[QUEUE] Starte mit {len(work_list)} Einträgen aus der Warteschlange (Check-Missing)")
                for anime in work_list:
                    # Deleted ignorieren
                    if anime.get("deleted"):
                        log(f"[SKIP] '{anime['title']}' übersprungen (deleted flag).")
                        continue
                    # Nur Anime berücksichtigen, die bereits Downloads haben oder als komplett markiert sind
                    if anime["last_film"] == 0 and anime["last_season"] == 0 and anime["last_episode"] == 0 and not anime["complete"]:
                        continue

                    series_title = anime["title"] or get_series_title(anime["url"])
                    base_url = anime["url"]
                    anime_id = anime["id"]
                    current_download["current_title"] = series_title
                    current_download["anime_started_at"] = time.time()
                    current_download["current_id"] = anime_id
                    current_download["current_url"] = base_url
                    current_download["episode_started_at"] = None

                    log(f"[CHECK-MISSING] Prüfe '{series_title}' auf fehlende Downloads.")

                    # Alle Filme von 1 bis last_film prüfen
                    film_num = 1
                    while True:
                        film_url = f"{base_url}/filme/film-{film_num}"
                        if episode_already_downloaded(os.path.join(DOWNLOAD_DIR, series_title), 0, film_num):
                            log(f"[OK] Film {film_num} bereits vorhanden.")
                        else:
                            log(f"[INFO] Film {film_num} fehlt -> erneuter Versuch")
                            result = download_episode(series_title, film_url, 0, film_num, anime_id, german_only=False)
                            if result == "NO_STREAMS":
                                break  # Keine weiteren Filme vorhanden
                        film_num += 1
                    # Start mit Staffel 1 und zähle leere Staffeln
                    season = 1
                    consecutive_empty_seasons = 0
                    while True:
                        episode = 1
                        found_episode = False
                        while True:
                            episode_url = f"{base_url}/staffel-{season}/episode-{episode}"
                            if episode_already_downloaded(os.path.join(DOWNLOAD_DIR, series_title), season, episode):
                                log(f"[OK] Staffel {season} Episode {episode} vorhanden.")
                                episode += 1
                                continue

                            log(f"[INFO] Staffel {season} Episode {episode} fehlt -> erneuter Versuch")
                            result = download_episode(series_title, episode_url, season, episode, anime_id, german_only=False)

                            if result == "NO_STREAMS":
                                if episode == 1:
                                    # Staffel existiert nicht -> Abbruchkandidat
                                    break
                                else:
                                    log(f"[INFO] Staffel {season} beendet nach {episode-1} Episoden.")
                                    break
                            else:
                                found_episode = True
                                episode += 1

                        if not found_episode:
                            consecutive_empty_seasons += 1
                        else:
                            consecutive_empty_seasons = 0

                        if consecutive_empty_seasons >= 2:
                            log(f"[CHECK-MISSING] '{series_title}' hat keine weiteren Staffeln.")
                            break

                        season += 1

                    # Finaler Statuscheck
                    check_deutsch_komplett(anime_id)
                    log(f"[CHECK-MISSING] Kontrolle für '{series_title}' abgeschlossen.")
                    # Entferne aus Queue
                    queue_delete_by_anime_id(anime_id)

            # 2) Danach restliche DB-Einträge
            rest_list = [a for a in anime_list if not queued_ids or a['id'] not in queued_ids]
            for anime in rest_list:
                # Deleted ignorieren
                if anime.get("deleted"):
                    log(f"[SKIP] '{anime['title']}' übersprungen (deleted flag).")
                    continue
                # Nur Anime berücksichtigen, die bereits Downloads haben oder als komplett markiert sind
                if anime["last_film"] == 0 and anime["last_season"] == 0 and anime["last_episode"] == 0 and not anime["complete"]:
                    continue
                series_title = anime["title"] or get_series_title(anime["url"])
                base_url = anime["url"]
                anime_id = anime["id"]
                current_download["current_title"] = series_title
                current_download["anime_started_at"] = time.time()
                current_download["current_id"] = anime_id
                current_download["current_url"] = base_url
                current_download["episode_started_at"] = None
                log(f"[CHECK-MISSING] Prüfe '{series_title}' auf fehlende Downloads.")
                # Filme
                film_num = 1
                while True:
                    film_url = f"{base_url}/filme/film-{film_num}"
                    if episode_already_downloaded(os.path.join(DOWNLOAD_DIR, series_title), 0, film_num):
                        log(f"[OK] Film {film_num} bereits vorhanden.")
                    else:
                        log(f"[INFO] Film {film_num} fehlt -> erneuter Versuch")
                        result = download_episode(series_title, film_url, 0, film_num, anime_id, german_only=False)
                        if result == "NO_STREAMS":
                            break
                    film_num += 1
                # Staffeln
                season = 1
                consecutive_empty_seasons = 0
                while True:
                    episode = 1
                    found_episode = False
                    while True:
                        episode_url = f"{base_url}/staffel-{season}/episode-{episode}"
                        if episode_already_downloaded(os.path.join(DOWNLOAD_DIR, series_title), season, episode):
                            log(f"[OK] Staffel {season} Episode {episode} vorhanden.")
                            episode += 1
                            continue
                        log(f"[INFO] Staffel {season} Episode {episode} fehlt -> erneuter Versuch")
                        result = download_episode(series_title, episode_url, season, episode, anime_id, german_only=False)
                        if result == "NO_STREAMS":
                            if episode == 1:
                                break
                            else:
                                log(f"[INFO] Staffel {season} beendet nach {episode-1} Episoden.")
                                break
                        else:
                            found_episode = True
                            episode += 1
                    if not found_episode:
                        consecutive_empty_seasons += 1
                    else:
                        consecutive_empty_seasons = 0
                    if consecutive_empty_seasons >= 2:
                        log(f"[CHECK-MISSING] '{series_title}' hat keine weiteren Staffeln.")
                        break
                    season += 1
                check_deutsch_komplett(anime_id)
                log(f"[CHECK-MISSING] Kontrolle für '{series_title}' abgeschlossen.")
                # Nach jedem DB-Eintrag: Queue erneut prüfen und abarbeiten
                try:
                    queue_prune_completed()
                    queued_now = queue_list()
                    if queued_now:
                        amap = {a['id']: a for a in load_anime()}
                        work_q = [amap[q['anime_id']] for q in queued_now if q.get('anime_id') in amap]
                        work_q.sort(key=lambda a: next((i for i,q in enumerate(queued_now) if q['anime_id']==a['id']), 999999))
                        log(f"[QUEUE] {len(work_q)} neue Einträge – abarbeiten (Check-Missing)")
                        for q_anime in work_q:
                            if q_anime.get('deleted'):
                                log(f"[SKIP] '{q_anime['title']}' übersprungen (deleted flag).")
                                queue_delete_by_anime_id(q_anime['id'])
                                continue
                            if q_anime['last_film'] == 0 and q_anime['last_season'] == 0 and q_anime['last_episode'] == 0 and not q_anime['complete']:
                                queue_delete_by_anime_id(q_anime['id'])
                                continue
                            q_series_title = q_anime['title'] or get_series_title(q_anime['url'])
                            base_url = q_anime['url']
                            q_anime_id = q_anime['id']
                            current_download["current_title"] = q_series_title
                            current_download["anime_started_at"] = time.time()
                            current_download["current_id"] = q_anime_id
                            current_download["current_url"] = base_url
                            current_download["episode_started_at"] = None
                            # Filme
                            film_num = 1
                            while True:
                                film_url = f"{base_url}/filme/film-{film_num}"
                                if episode_already_downloaded(os.path.join(DOWNLOAD_DIR, q_series_title), 0, film_num):
                                    pass
                                else:
                                    result = download_episode(q_series_title, film_url, 0, film_num, q_anime_id, german_only=False)
                                    if result == 'NO_STREAMS':
                                        break
                                film_num += 1
                            # Staffeln
                            season = 1
                            consecutive_empty_seasons = 0
                            while True:
                                episode = 1
                                found_episode = False
                                while True:
                                    episode_url = f"{base_url}/staffel-{season}/episode-{episode}"
                                    if episode_already_downloaded(os.path.join(DOWNLOAD_DIR, q_series_title), season, episode):
                                        episode += 1
                                        continue
                                    result = download_episode(q_series_title, episode_url, season, episode, q_anime_id, german_only=False)
                                    if result == 'NO_STREAMS':
                                        if episode == 1:
                                            break
                                        else:
                                            break
                                    else:
                                        found_episode = True
                                        episode += 1
                                if not found_episode:
                                    consecutive_empty_seasons += 1
                                else:
                                    consecutive_empty_seasons = 0
                                if consecutive_empty_seasons >= 2:
                                    break
                                season += 1
                            check_deutsch_komplett(q_anime_id)
                            queue_delete_by_anime_id(q_anime_id)
                except Exception as _e:
                    log(f"[QUEUE] Re-Check Fehler (Check-Missing): {_e}")

        elif mode == "full-check":
            log("=== Modus: Kompletter Check (alle Animes von Anfang an prüfen) ===")
            # 1) Zuerst Queue (falls vorhanden)
            if queued_ids:
                work_list = [a for a in anime_list if a['id'] in queued_ids]
                work_list.sort(key=lambda a: priority_map.get(a['id'], 1_000_000))
                log(f"[QUEUE] Starte mit {len(work_list)} Einträgen aus der Warteschlange (Full-Check)")
                for idx, anime in enumerate(work_list):
                    current_download["current_index"] = idx
                    if anime.get("deleted"):
                        log(f"[SKIP] '{anime['title']}' übersprungen (deleted flag gesetzt).")
                        continue
                    series_title = anime["title"] or get_series_title(anime["url"])
                    anime_id = anime["id"]
                    base_url = anime["url"]
                    current_download["current_title"] = series_title
                    current_download["anime_started_at"] = time.time()
                    current_download["current_id"] = anime_id
                    current_download["current_url"] = base_url
                    current_download["episode_started_at"] = None
                    # Start immer bei 1 (Filme und Staffeln)
                    r = download_films(series_title, base_url, anime_id, start_film=1)
                    if r == "NO_SPACE":
                        log("[ERROR] Downloadlauf abgebrochen wegen fehlendem Speicher (full-check).")
                        return
                    r2 = download_seasons(series_title, base_url, anime_id, start_season=1, start_episode=1)
                    if r2 == "NO_SPACE":
                        log("[ERROR] Downloadlauf abgebrochen wegen fehlendem Speicher (full-check).")
                        return
                    check_deutsch_komplett(anime_id)
                    # Entferne aus Queue
                    queue_delete_by_anime_id(anime_id)

            # 2) Danach restliche DB-Einträge
            rest_list = [a for a in anime_list if not queued_ids or a['id'] not in queued_ids]
            for idx, anime in enumerate(rest_list):
                current_download["current_index"] = idx
                if anime.get("deleted"):
                    log(f"[SKIP] '{anime['title']}' übersprungen (deleted flag gesetzt).")
                    continue
                series_title = anime["title"] or get_series_title(anime["url"])
                anime_id = anime["id"]
                base_url = anime["url"]
                current_download["current_title"] = series_title
                current_download["anime_started_at"] = time.time()
                current_download["current_id"] = anime_id
                current_download["current_url"] = base_url
                current_download["episode_started_at"] = None
                r = download_films(series_title, base_url, anime_id, start_film=1)
                if r == "NO_SPACE":
                    log("[ERROR] Downloadlauf abgebrochen wegen fehlendem Speicher (full-check).")
                    return
                r2 = download_seasons(series_title, base_url, anime_id, start_season=1, start_episode=1)
                if r2 == "NO_SPACE":
                    log("[ERROR] Downloadlauf abgebrochen wegen fehlendem Speicher (full-check).")
                    return
                check_deutsch_komplett(anime_id)
                # Nach jedem DB-Eintrag: Queue erneut prüfen und abarbeiten
                try:
                    queue_prune_completed()
                    queued_now = queue_list()
                    if queued_now:
                        amap = {a['id']: a for a in load_anime()}
                        work_q = [amap[q['anime_id']] for q in queued_now if q.get('anime_id') in amap]
                        work_q.sort(key=lambda a: next((i for i,q in enumerate(queued_now) if q['anime_id']==a['id']), 999999))
                        log(f"[QUEUE] {len(work_q)} neue Einträge – abarbeiten (Full-Check)")
                        for q_anime in work_q:
                            if q_anime.get('deleted'):
                                log(f"[SKIP] '{q_anime['title']}' übersprungen (deleted flag gesetzt).")
                                queue_delete_by_anime_id(q_anime['id'])
                                continue
                            q_series_title = q_anime['title'] or get_series_title(q_anime['url'])
                            q_anime_id = q_anime['id']
                            base_url = q_anime['url']
                            current_download["current_title"] = q_series_title
                            current_download["anime_started_at"] = time.time()
                            current_download["current_id"] = q_anime_id
                            current_download["current_url"] = base_url
                            current_download["episode_started_at"] = None
                            r = download_films(q_series_title, base_url, q_anime_id, start_film=1)
                            if r == 'NO_SPACE':
                                return
                            r2 = download_seasons(q_series_title, base_url, q_anime_id, start_season=1, start_episode=1)
                            if r2 == 'NO_SPACE':
                                return
                            check_deutsch_komplett(q_anime_id)
                            queue_delete_by_anime_id(q_anime_id)

                except Exception as _e:
                    log(f"[QUEUE] Re-Check Fehler (Full-Check): {_e}")

        else:
            log("=== Modus: Standard  ===")
            # 1) Zuerst Queue
            if queued_ids:
                work_list = [a for a in anime_list if a['id'] in queued_ids]
                work_list.sort(key=lambda a: priority_map.get(a['id'], 1_000_000))
                log(f"[QUEUE] Starte mit {len(work_list)} Einträgen aus der Warteschlange (Default)")
                for idx, anime in enumerate(work_list):
                    
                    current_download["current_index"] = idx
                    if anime.get("deleted"):
                        log(f"[SKIP] '{anime['title']}' übersprungen (deleted flag gesetzt).")
                        continue
                    if anime["complete"]:
                        log(f"[SKIP] '{anime['title']}' bereits komplett.")
                        continue
                    series_title = anime["title"] or get_series_title(anime["url"])
                    anime_id = anime["id"]
                    base_url = anime["url"]
                    current_download["current_title"] = series_title
                    current_download["anime_started_at"] = time.time()
                    current_download["current_id"] = anime_id
                    current_download["current_url"] = base_url
                    current_download["episode_started_at"] = None
                    start_film = (anime.get("last_film") or 1)
                    start_season = anime.get("last_season") or 1
                    start_episode = (anime.get("last_episode") or 1) if start_season > 0 else 1
                    log(f"[START] Starte Download für: '{series_title}' ab Film {start_film} / Staffel {start_season}, Episode {start_episode}")
                    r = download_films(series_title, base_url, anime_id, start_film=start_film)
                    if r == "NO_SPACE":
                        log("[ERROR] Downloadlauf abgebrochen wegen fehlendem Speicher (default mode).")
                        return
                    r2 = download_seasons(series_title, base_url, anime_id, start_season=max(1, start_season), start_episode=start_episode)
                    if r2 == "NO_SPACE":
                        log("[ERROR] Downloadlauf abgebrochen wegen fehlendem Speicher (default mode).")
                        return
                    check_deutsch_komplett(anime_id)
                    update_anime(anime_id, complete=1)
                    log(f"[OK] Download abgeschlossen für: '{series_title}'")
                    # Entferne aus Queue
                    queue_delete_by_anime_id(anime_id)
            # 2) Danach restliche DB-Einträge
            rest_list = [a for a in anime_list if not queued_ids or a['id'] not in queued_ids]
            for idx, anime in enumerate(rest_list):
                
                current_download["current_index"] = idx
                if anime.get("deleted"):
                    log(f"[SKIP] '{anime['title']}' übersprungen (deleted flag gesetzt).")
                    continue
                if anime["complete"]:
                    log(f"[SKIP] '{anime['title']}' bereits komplett.")
                    continue
                series_title = anime["title"] or get_series_title(anime["url"])
                anime_id = anime["id"]
                base_url = anime["url"]
                current_download["current_title"] = series_title
                current_download["anime_started_at"] = time.time()
                current_download["current_id"] = anime_id
                current_download["current_url"] = base_url
                current_download["episode_started_at"] = None
                start_film = (anime.get("last_film") or 1)
                start_season = anime.get("last_season") or 1
                start_episode = (anime.get("last_episode") or 1) if start_season > 0 else 1
                log(f"[START] Starte Download für: '{series_title}' ab Film {start_film} / Staffel {start_season}, Episode {start_episode}")
                r = download_films(series_title, base_url, anime_id, start_film=start_film)
                if r == "NO_SPACE":
                    log("[ERROR] Downloadlauf abgebrochen wegen fehlendem Speicher (default mode).")
                    return
                r2 = download_seasons(series_title, base_url, anime_id, start_season=max(1, start_season), start_episode=start_episode)
                if r2 == "NO_SPACE":
                    log("[ERROR] Downloadlauf abgebrochen wegen fehlendem Speicher (default mode).")
                    return
                check_deutsch_komplett(anime_id)
                update_anime(anime_id, complete=1)
                log(f"[OK] Download abgeschlossen für: '{series_title}'")
                # Nach jedem DB-Eintrag: Queue erneut prüfen und abarbeiten
                try:
                    queue_prune_completed()
                    queued_now = queue_list()
                    if queued_now:
                        amap = {a['id']: a for a in load_anime()}
                        work_q = [amap[q['anime_id']] for q in queued_now if q.get('anime_id') in amap]
                        work_q.sort(key=lambda a: next((i for i,q in enumerate(queued_now) if q['anime_id']==a['id']), 999999))
                        log(f"[QUEUE] {len(work_q)} neue Einträge – abarbeiten (Default)")
                        for q_anime in work_q:
                            if q_anime.get('deleted'):
                                log(f"[SKIP] '{q_anime['title']}' übersprungen (deleted flag gesetzt).")
                                queue_delete_by_anime_id(q_anime['id'])
                                continue
                            if q_anime['complete']:
                                queue_delete_by_anime_id(q_anime['id'])
                                continue
                            q_series_title = q_anime['title'] or get_series_title(q_anime['url'])
                            q_anime_id = q_anime['id']
                            base_url = q_anime['url']
                            current_download["current_title"] = q_series_title
                            current_download["anime_started_at"] = time.time()
                            current_download["current_id"] = q_anime_id
                            current_download["current_url"] = base_url
                            current_download["episode_started_at"] = None
                            start_film = (q_anime.get('last_film') or 1)
                            start_season = q_anime.get('last_season') or 1
                            start_episode = (q_anime.get('last_episode') or 1) if start_season > 0 else 1
                            r = download_films(q_series_title, base_url, q_anime_id, start_film=start_film)
                            if r == 'NO_SPACE':
                                return
                            r2 = download_seasons(q_series_title, base_url, q_anime_id, start_season=max(1, start_season), start_episode=start_episode)
                            if r2 == 'NO_SPACE':
                                return
                            check_deutsch_komplett(q_anime_id)
                            update_anime(q_anime_id, complete=1)
                            log(f"[OK] Download abgeschlossen für: '{q_series_title}'")
                            queue_delete_by_anime_id(q_anime_id)
                except Exception as _e:
                    log(f"[QUEUE] Re-Check Fehler (Default): {_e}")
        # Falls wir ausschließlich Queue-Items verarbeitet haben, leeren wir die verarbeiteten aus der Queue
        if queued_ids:
            # alle abgearbeitet -> Queue bereinigen (Pop pro Eintrag)
            # Wir löschen alle IDs, die in queued_ids enthalten waren
            try:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute(
                    f"DELETE FROM queue WHERE anime_id IN ({','.join(['?']*len(queued_ids))})",
                    queued_ids
                )
                conn.commit()
                conn.close()
                log("[QUEUE] Verarbeitete Einträge aus der Warteschlange entfernt.")
            except Exception as e:
                log(f"[DB-ERROR] queue cleanup: {e}")
        log("[INFO] Alle Aufgaben abgeschlossen.")
    except Exception as e:
        log(f"[ERROR] Unhandled exception in run_mode: {e}")
    finally:
        # Wenn der Status bereits auf 'kein-speicher' gesetzt wurde, nicht überschreiben.
        with download_lock:
            if current_download.get("status") != "kein-speicher":
                current_download.update({
                    "status": "finished",
                    "current_index": None,
                    "current_title": None,
                    "current_season": None,
                    "current_episode": None,
                    "current_is_film": None,
                    "anime_started_at": None,
                    "episode_started_at": None,
                    "current_id": None,
                    "current_url": None
                })
            else:
                # Nur laufende Details zurücksetzen, Status bleibt 'kein-speicher'
                current_download.update({
                    "current_index": None,
                    "current_title": None,
                    "current_season": None,
                    "current_episode": None,
                    "current_is_film": None,
                    "anime_started_at": None,
                    "episode_started_at": None,
                    "current_id": None,
                    "current_url": None
                })
@app.route("/upload_txt", methods=["POST"])
def api_upload_txt():
    """Nimmt eine hochgeladene TXT-Datei entgegen und verarbeitet sie wie AniLoader.txt beim Start."""
    try:
        if 'file' not in request.files:
            return jsonify({"status": "error", "msg": "Keine Datei hochgeladen"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"status": "error", "msg": "Keine Datei ausgewählt"}), 400
        
        if not file.filename.endswith('.txt'):
            return jsonify({"status": "error", "msg": "Nur TXT-Dateien erlaubt"}), 400
        
        # Datei lesen
        content = file.read().decode('utf-8')
        links = [line.strip() for line in content.split('\n') if line.strip()]
        
        if not links:
            return jsonify({"status": "error", "msg": "Keine URLs in der Datei gefunden"}), 400
        
        # URLs in die Datenbank importieren
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        imported = 0
        for url in links:
            if insert_anime(url=url):
                imported += 1
        conn.commit()
        conn.close()
        
        log(f"[UPLOAD] {imported} Anime-URLs aus hochgeladener Datei '{file.filename}' importiert")
        return jsonify({
            "status": "ok",
            "msg": f"{imported} URLs erfolgreich importiert",
            "count": imported
        })
    except Exception as e:
        log(f"[ERROR] api_upload_txt: {e}")
        return jsonify({"status": "error", "msg": str(e)}), 500


# -------------------- API Endpoints --------------------
@app.route("/start_download", methods=["POST", "GET"])
def api_start_download():
    body = request.get_json(silent=True) or {}
    mode = request.args.get("mode") or body.get("mode") or "default"
    if mode not in ("default", "german", "new", "check-missing", "full-check"):
        return jsonify({"status": "error", "msg": "Ungültiger Mode"}), 400
    with download_lock:
        if current_download["status"] == "running":
            return jsonify({"status": "already_running"}), 409
    
    thread = threading.Thread(target=run_mode, args=(mode,), daemon=True)
    thread.start()
    return jsonify({"status": "started", "mode": mode})

@app.route("/status")
def api_status():
    with download_lock:
        data = dict(current_download)
    return jsonify(data)

    

@app.route("/health")
def api_health():
    """Lightweight health check endpoint used by the userscript."""
    return jsonify({"ok": True}), 200


@app.route("/config", methods=["GET", "POST"])
def api_config():
    global LANGUAGES, MIN_FREE_GB, AUTOSTART_MODE, DOWNLOAD_DIR, SERVER_PORT, REFRESH_TITLES, STORAGE_MODE, MOVIES_PATH, SERIES_PATH, ANIME_PATH, SERIEN_PATH, ANIME_SEPARATE_MOVIES, SERIEN_SEPARATE_MOVIES, data_folder
    if request.method == 'GET':
        try:
            # Reload to reflect persisted file state
            load_config()
            cfg = {
                'languages': LANGUAGES,
                'min_free_gb': MIN_FREE_GB,
                'download_path': str(DOWNLOAD_DIR),
                'storage_mode': STORAGE_MODE,
                'movies_path': MOVIES_PATH,
                'series_path': SERIES_PATH,
                'anime_path': ANIME_PATH,
                'serien_path': SERIEN_PATH,
                'anime_separate_movies': ANIME_SEPARATE_MOVIES,
                'serien_separate_movies': SERIEN_SEPARATE_MOVIES,
                'port': SERVER_PORT,
                'autostart_mode': AUTOSTART_MODE,
                'refresh_titles': REFRESH_TITLES,
                'data_folder_path': data_folder
            }
            return jsonify(cfg)
        except Exception as e:
            log(f"[ERROR] api_config GET: {e}")
            return jsonify({'error': 'failed'}), 500

    # POST -> save
    data = request.get_json() or {}
    langs = data.get('languages')
    min_free = data.get('min_free_gb')
    new_download_path = data.get('download_path')
    storage_mode = data.get('storage_mode')
    movies_path = data.get('movies_path')
    series_path = data.get('series_path')
    anime_path = data.get('anime_path')
    serien_path = data.get('serien_path')
    anime_separate_movies = data.get('anime_separate_movies')
    serien_separate_movies = data.get('serien_separate_movies')
    refresh_titles_val = data.get('refresh_titles')
    new_data_folder = data.get('data_folder_path')
    # Support both 'autostart_mode' and 'autostart' as input
    autostart_key_present = ('autostart_mode' in data) or ('autostart' in data)
    autostart = data.get('autostart_mode') if ('autostart_mode' in data) else data.get('autostart')
    changed = False
    try:
        log(f"[CONFIG] POST incoming: languages={langs}, min_free_gb={min_free}, download_path={new_download_path}, storage_mode={storage_mode}, autostart={autostart}, data_folder_path={new_data_folder}")
        if isinstance(langs, list) and langs:
            LANGUAGES = list(langs)
            changed = True
        if min_free is not None:
            MIN_FREE_GB = float(min_free)
            changed = True
        if isinstance(new_download_path, str) and new_download_path.strip():
            try:
                new_path = Path(new_download_path).expanduser()
                try:
                    resolved = new_path.resolve()
                except Exception:
                    resolved = new_path
                resolved.mkdir(parents=True, exist_ok=True)
                DOWNLOAD_DIR = resolved
                changed = True
            except Exception as e:
                return jsonify({'status': 'failed', 'error': f'Ungültiger Speicherort: {e}'}), 400
        
        # Data Folder Path
        if isinstance(new_data_folder, str) and new_data_folder.strip():
            try:
                new_folder = Path(new_data_folder).expanduser()
                try:
                    new_folder = new_folder.resolve()
                except Exception:
                    pass
                # Create the new data folder
                new_folder.mkdir(parents=True, exist_ok=True)
                # Update paths globally
                update_data_paths(str(new_folder))
                changed = True
                log(f"[CONFIG] Data-Ordner geändert zu: {data_folder}")
            except Exception as e:
                return jsonify({'status': 'failed', 'error': f'Ungültiger Data-Ordner: {e}'}), 400
        
        # Storage Mode
        if storage_mode is not None and storage_mode in ['standard', 'separate']:
            STORAGE_MODE = storage_mode
            changed = True
        
        # Movies Path
        if movies_path is not None:
            MOVIES_PATH = movies_path.strip()
            changed = True
        
        # Series Path
        if series_path is not None:
            SERIES_PATH = series_path.strip()
            changed = True
        
        # Anime Path
        if anime_path is not None:
            ANIME_PATH = anime_path.strip()
            changed = True
        
        # Serien Path
        if serien_path is not None:
            SERIEN_PATH = serien_path.strip()
            changed = True
        
        # Anime Separate Movies
        if anime_separate_movies is not None:
            ANIME_SEPARATE_MOVIES = bool(anime_separate_movies)
            changed = True
        
        # Serien Separate Movies
        if serien_separate_movies is not None:
            SERIEN_SEPARATE_MOVIES = bool(serien_separate_movies)
            changed = True
            
        if autostart_key_present:
            allowed = {'default', 'german', 'new', 'check-missing'}
            if autostart is None:
                # explicit null -> clear
                AUTOSTART_MODE = None
                changed = True
            elif isinstance(autostart, str):
                mode_norm = autostart.strip().lower()
                if mode_norm in {'', 'none', 'off', 'disabled'}:
                    AUTOSTART_MODE = None
                    changed = True
                elif mode_norm in allowed:
                    AUTOSTART_MODE = mode_norm
                    changed = True
                else:
                    return jsonify({'status': 'failed', 'error': 'invalid autostart_mode'}), 400
            else:
                return jsonify({'status': 'failed', 'error': 'invalid autostart_mode'}), 400
        # refresh_titles toggle
        if refresh_titles_val is not None:
            try:
                REFRESH_TITLES = bool(refresh_titles_val)
                changed = True
            except Exception:
                pass

        if changed:
            save_ok = save_config()
            # Reload from disk to ensure persistence and normalization
            try:
                load_config()
            except Exception as _e:
                log(f"[CONFIG-ERROR] reload after save: {_e}")
            log(f"[CONFIG] POST saved: storage_mode={STORAGE_MODE}, anime_path={ANIME_PATH}, serien_path={SERIEN_PATH}, anime_separate_movies={ANIME_SEPARATE_MOVIES}, serien_separate_movies={SERIEN_SEPARATE_MOVIES}")
            return jsonify({'status': 'ok' if save_ok else 'failed', 'config': {
                'languages': LANGUAGES,
                'min_free_gb': MIN_FREE_GB,
                'download_path': str(DOWNLOAD_DIR),
                'storage_mode': STORAGE_MODE,
                'movies_path': MOVIES_PATH,
                'series_path': SERIES_PATH,
                'anime_path': ANIME_PATH,
                'serien_path': SERIEN_PATH,
                'anime_separate_movies': ANIME_SEPARATE_MOVIES,
                'serien_separate_movies': SERIEN_SEPARATE_MOVIES,
                'port': SERVER_PORT,
                'autostart_mode': AUTOSTART_MODE,
                'refresh_titles': REFRESH_TITLES,
                'data_folder_path': data_folder
            }})
        return jsonify({'status': 'nochange', 'config': {
            'languages': LANGUAGES,
            'min_free_gb': MIN_FREE_GB,
            'download_path': str(DOWNLOAD_DIR),
            'storage_mode': STORAGE_MODE,
            'movies_path': MOVIES_PATH,
            'series_path': SERIES_PATH,
            'anime_path': ANIME_PATH,
            'serien_path': SERIEN_PATH,
            'anime_separate_movies': ANIME_SEPARATE_MOVIES,
            'serien_separate_movies': SERIEN_SEPARATE_MOVIES,
            'port': SERVER_PORT,
            'autostart_mode': AUTOSTART_MODE,
            'refresh_titles': REFRESH_TITLES,
            'data_folder_path': data_folder
        }})
    except Exception as e:
        log(f"[ERROR] api_config POST: {e}")
        return jsonify({'status': 'failed', 'error': str(e)}), 400


@app.route("/pick_folder", methods=["GET"])
def api_pick_folder():
    """Öffnet eine native Ordnerauswahl (Windows-Explorer/OS-Dialog) auf dem Server-Host und liefert den gewählten Pfad zurück.
    Hinweis: Erfordert eine Desktop-Umgebung und tkinter. Bei fehlender GUI/Tk wird ein Fehler zurückgegeben.
    """
    try:
        # Import on demand, um Serverstart ohne GUI zu ermöglichen
        try:
            import tkinter as tk
            from tkinter import filedialog
        except Exception as e:
            log(f"[ERROR] tkinter nicht verfügbar: {e}")
            return jsonify({'status': 'failed', 'selected': None, 'error': 'tkinter nicht verfügbar'}), 500

        root = tk.Tk()
        root.withdraw()
        # Nach vorn holen, damit der Dialog nicht hinter Fenstern erscheint
        try:
            root.attributes("-topmost", True)
        except Exception:
            pass
        try:
            path = filedialog.askdirectory(title="Download-Verzeichnis wählen")
        finally:
            try:
                root.destroy()
            except Exception:
                pass

        if not path:
            return jsonify({'status': 'canceled', 'selected': None}), 200
        return jsonify({'status': 'ok', 'selected': path}), 200
    except Exception as e:
        log(f"[ERROR] api_pick_folder: {e}")
        return jsonify({'status': 'failed', 'selected': None, 'error': str(e)}), 500


@app.route('/queue', methods=['GET', 'POST', 'DELETE'])
def api_queue():
    """GET: Liste der Queue, POST: {'anime_id': id} hinzufügen, DELETE: leeren"""
    try:
        if request.method == 'GET':
            queue_prune_completed()
            return jsonify(queue_list())
        elif request.method == 'POST':
            data = request.get_json() or {}
            # reorder: {"order": [queue_id1, queue_id2, ...]}
            if 'order' in data:
                try:
                    ids = [int(x) for x in data.get('order') or []]
                except Exception:
                    return jsonify({'status': 'failed', 'error': 'invalid order list'}), 400
                ok = queue_reorder(ids)
                return jsonify({'status': 'ok' if ok else 'failed'})
            # add entry
            aid = data.get('anime_id')
            if not isinstance(aid, int):
                try:
                    aid = int(str(aid))
                except Exception:
                    return jsonify({'status': 'failed', 'error': 'invalid anime_id'}), 400
            ok = queue_add(aid)
            return jsonify({'status': 'ok' if ok else 'failed'})
        elif request.method == 'DELETE':
            # einzelnes Element entfernen oder komplette Queue leeren
            payload = request.get_json(silent=True) or {}
            qid = request.args.get('id') or payload.get('id')
            aid = request.args.get('anime_id') or payload.get('anime_id')
            if qid is not None:
                try:
                    ok = queue_delete(int(str(qid)))
                except Exception:
                    return jsonify({'status': 'failed', 'error': 'invalid id'}), 400
                return jsonify({'status': 'ok' if ok else 'failed'})
            if aid is not None:
                try:
                    ok = queue_delete_by_anime_id(int(str(aid)))
                except Exception:
                    return jsonify({'status': 'failed', 'error': 'invalid anime_id'}), 400
                return jsonify({'status': 'ok' if ok else 'failed'})
            ok = queue_clear()
            return jsonify({'status': 'ok' if ok else 'failed'})
    except Exception as e:
        log(f"[ERROR] api_queue: {e}")
        return jsonify({'status': 'failed', 'error': str(e)}), 500



@app.route('/disk')
def api_disk():
    try:
        free_gb = freier_speicher_mb(DOWNLOAD_DIR)
        return jsonify({'free_gb': free_gb})
    except Exception as e:
        log(f"[ERROR] api_disk: {e}")
        return jsonify({'free_gb': None, 'error': str(e)}), 500

@app.route("/logs")
def api_logs():
    with log_lock:
        return jsonify(list(log_lines)) 

@app.route("/database")
def api_database():
    """
    DB endpoint with optional filtering:
      q=search string
      complete=0|1
      deleted=0|1
            deutsch=0|1 (filter on deutsch_komplett)
      sort_by, order, limit, offset
    """
    q = request.args.get("q")
    complete = request.args.get("complete")
    deleted = request.args.get("deleted")
    deutsch = request.args.get("deutsch")
    sort_by = request.args.get("sort_by", "id")
    order = request.args.get("order", "asc").lower()
    limit = request.args.get("limit")
    offset = request.args.get("offset", 0)

    allowed_sort = {"id", "title", "last_film", "last_episode", "last_season"}
    if sort_by not in allowed_sort:
        sort_by = "id"
    order_sql = "ASC" if order != "desc" else "DESC"

    sql = "SELECT id, title, url, complete, deutsch_komplett, deleted, fehlende_deutsch_folgen, last_film, last_episode, last_season FROM anime"
    params = []
    where_clauses = []

    if q:
        where_clauses.append("(title LIKE ? OR url LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])
    if complete in ("0", "1"):
        where_clauses.append("complete = ?")
        params.append(int(complete))
    if deleted in ("0", "1"):
        where_clauses.append("deleted = ?")
        params.append(int(deleted))
    if deutsch in ("0", "1"):
        where_clauses.append("deutsch_komplett = ?")
        params.append(int(deutsch))

    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)

    sql += f" ORDER BY {sort_by} {order_sql}"

    if limit:
        try:
            lim = int(limit)
            off = int(offset)
            sql += f" LIMIT {lim} OFFSET {off}"
        except:
            pass

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(sql, params)
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
            "deleted": bool(row[5]),
            "fehlende": json.loads(row[6] or "[]"),
            "last_film": row[7],
            "last_episode": row[8],
            "last_season": row[9]
        })
    return jsonify(db_data)

@app.route("/counts")
def api_counts():
    """
    Liefert Zählwerte für eine Serie aus dem Dateisystem:
      - per_season: { "1": epCount, ... }
      - total_seasons, total_episodes, films
    Parameter: id (DB id) oder title (Serien-Titel, Ordnername unter Downloads)
    """
    try:
        anime_id = request.args.get("id")
        title = request.args.get("title")
        series_title = None
        if anime_id and anime_id.isdigit():
            try:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("SELECT title FROM anime WHERE id = ?", (int(anime_id),))
                row = c.fetchone()
                if row and row[0]:
                    series_title = row[0]
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
        if not series_title:
            series_title = title
        if not series_title:
            return jsonify({
                'per_season': {},
                'total_seasons': 0,
                'total_episodes': 0,
                'films': 0
            })

        base = Path(DOWNLOAD_DIR) / series_title
        per_season = {}
        total_eps = 0
        films = 0
        if base.exists() and base.is_dir():
            # Filme zählen
            filme_dir = base / 'Filme'
            if filme_dir.exists() and filme_dir.is_dir():
                films = sum(1 for f in filme_dir.glob('*.mp4'))
            # Staffeln zählen
            for d in base.iterdir():
                if d.is_dir():
                    m = re.match(r'^Staffel\s+(\d+)$', d.name, re.IGNORECASE)
                    if m:
                        s = m.group(1)
                        cnt = sum(1 for f in d.glob('*.mp4'))
                        per_season[s] = cnt
                        total_eps += cnt
        return jsonify({
            'per_season': per_season,
            'total_seasons': len(per_season),
            'total_episodes': total_eps,
            'films': films,
            'title': series_title
        })
    except Exception as e:
        log(f"[ERROR] api_counts: {e}")
        return jsonify({'error': str(e), 'per_season': {}, 'total_seasons': 0, 'total_episodes': 0, 'films': 0}), 500

@app.route("/export", methods=["POST"])
def api_export():
    data = request.get_json() or {}
    url = data.get("url")
    if not url:
        return jsonify({"status": "error", "msg": "Keine URL angegeben"}), 400
    ok = insert_anime(url)
    return jsonify({"status": "ok" if ok else "failed"})

@app.route("/anime", methods=["DELETE"])
def api_anime_delete():
    """Löscht einen Anime-Eintrag dauerhaft aus der Datenbank (und aus der Queue). Parameter: id (DB ID)."""
    try:
        anime_id = request.args.get("id") or (request.get_json(silent=True) or {}).get("id")
        if anime_id is None:
            return jsonify({"status": "failed", "error": "missing id"}), 400
        try:
            aid = int(str(anime_id))
        except Exception:
            return jsonify({"status": "failed", "error": "invalid id"}), 400

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # Find URL for extra cleanup
        c.execute("SELECT url, title FROM anime WHERE id = ?", (aid,))
        row = c.fetchone()
        if not row:
            conn.close()
            return jsonify({"status": "failed", "error": "not found"}), 404
        aurl, atitle = row[0], row[1]
        # Clean queue by anime_id and anime_url
        try:
            c.execute("DELETE FROM queue WHERE anime_id = ?", (aid,))
            c.execute("DELETE FROM queue WHERE anime_url = ?", (aurl,))
        except Exception as e:
            log(f"[DB-ERROR] queue cleanup on delete: {e}")
        # Delete anime itself
        c.execute("DELETE FROM anime WHERE id = ?", (aid,))
        conn.commit()
        conn.close()
        log(f"[DB] Anime gelöscht: ID {aid} • '{atitle}'")
        return jsonify({"status": "ok"})
    except Exception as e:
        log(f"[ERROR] api_anime_delete: {e}")
        return jsonify({"status": "failed", "error": str(e)}), 500

@app.route("/anime/restore", methods=["POST"])
def api_anime_restore():
    """Setzt einen als gelöscht markierten Anime zurück (deleted=0, Fortschritt zurücksetzen) und fügt ihn optional der Queue hinzu."""
    try:
        data = request.get_json(silent=True) or {}
        anime_id = data.get("id") or request.args.get("id")
        add_to_queue = bool(data.get("queue", True))
        if anime_id is None:
            return jsonify({"status": "failed", "error": "missing id"}), 400
        try:
            aid = int(str(anime_id))
        except Exception:
            return jsonify({"status": "failed", "error": "invalid id"}), 400

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, title FROM anime WHERE id = ?", (aid,))
        row = c.fetchone()
        if not row:
            conn.close()
            return jsonify({"status": "failed", "error": "not found"}), 404
        # Reset state and clear deleted flag
        c.execute(
            """
            UPDATE anime SET
                complete = 0,
                deutsch_komplett = 0,
                deleted = 0,
                fehlende_deutsch_folgen = '[]',
                last_film = 0,
                last_episode = 0,
                last_season = 0
            WHERE id = ?
            """,
            (aid,)
        )
        conn.commit()
        conn.close()
        log(f"[DB] Anime reaktiviert für erneuten Download: ID {aid}")
        queued = False
        if add_to_queue:
            try:
                queued = queue_add(aid)
            except Exception as e:
                log(f"[QUEUE] queue_add on restore: {e}")
        return jsonify({"status": "ok", "queued": bool(queued)})
    except Exception as e:
        log(f"[ERROR] api_anime_restore: {e}")
        return jsonify({"status": "failed", "error": str(e)}), 500

@app.route("/check")
def api_check():
    url = request.args.get("url")
    if not url:
        return jsonify({"exists": False})

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # Prüfen, ob der Anime existiert UND nicht als gelöscht markiert ist
        c.execute("SELECT 1 FROM anime WHERE url = ? AND deleted = 0", (url,))
        exists = c.fetchone() is not None
    except Exception as e:
        log(f"[ERROR] api_check: {e}")
        exists = False
    finally:
        try:
            conn.close()
        except Exception:
            pass

    return jsonify({"exists": exists})

@app.route("/")
def index():
    return render_template("index.html")

# -------------------- Entrypoint --------------------
def AniLoader():
    load_config()
    init_db()
    import_anime_txt()
    Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)
    deleted_check()
    if REFRESH_TITLES:
        refresh_titles_on_start()
    log("[SYSTEM] AniLoader API starting...")
    # Autostart-Modus, falls in der Config gesetzt
    try:
        if AUTOSTART_MODE in ("default", "german", "new", "check-missing"):
            with download_lock:
                already = (current_download.get("status") == "running")
            if not already:
                threading.Thread(target=run_mode, args=(AUTOSTART_MODE,), daemon=True).start()
                log(f"[SYSTEM] Autostart gestartet: {AUTOSTART_MODE}")
    except Exception as e:
        log(f"[CONFIG-ERROR] Autostart fehlgeschlagen: {e}")

AniLoader()

if __name__ == "__main__":
    # ensure we load config so SERVER_PORT is honored when launched directly
    try:
        load_config()
    except Exception:
        pass
    app.run(host="0.0.0.0", port=SERVER_PORT, debug=False, threaded=True)
