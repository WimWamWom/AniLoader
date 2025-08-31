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
import threading
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import random


# -------------------- Konfiguration --------------------
BASE_DIR = Path(__file__).resolve().parent
ANIME_TXT = BASE_DIR / "AniLoader.txt"
DOWNLOAD_DIR = BASE_DIR / "Downloads"
DB_PATH = BASE_DIR / "AniLoader.db"
CONFIG_PATH = BASE_DIR / "config.json"
LANGUAGES = ["German Dub", "German Sub", "English Dub", "English Sub"]
MIN_FREE_GB = 2.0
MAX_PATH = 260


def load_config():
    global LANGUAGES, MIN_FREE_GB
    try:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
                LANGUAGES = cfg.get('languages', LANGUAGES)
                MIN_FREE_GB = float(cfg.get('min_free_gb', MIN_FREE_GB))
                log(f"[CONFIG] geladen: languages={LANGUAGES} min_free_gb={MIN_FREE_GB}")
        else:
            save_config()  # create default config
    except Exception as e:
        log(f"[CONFIG-ERROR] load_config: {e}")


def save_config():
    try:
        cfg = {'languages': LANGUAGES, 'min_free_gb': MIN_FREE_GB}
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
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

# -------------------- Flask app --------------------
app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)

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
    conn.commit()
    conn.close()

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
    for key, val in kwargs.items():
        if key == "fehlende_deutsch_folgen":
            val = json.dumps(val)
        fields.append(f"{key} = ?")
        values.append(val)
    values.append(anime_id)
    if fields:
        c.execute(f"UPDATE anime SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()
    conn.close()

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
    """Gibt den verfügbaren Speicherplatz des angegebenen Pfads in MB zurück."""
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
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        title = soup.select_one("div.series-title h1 span")
        if title and title.text.strip():
            return sanitize_title(title.text.strip())
    except Exception as e:
        log(f"[FEHLER] Konnte Serien-Titel nicht abrufen ({url}): {e}")
    return None

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
    lang_suffix = {
        "German Dub": False,
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
    except Exception:
        pass
    # Prüfe freien Speicher vor jedem Download (freier_speicher_mb liefert GB)
    try:
        free_gb = freier_speicher_mb(DOWNLOAD_DIR)
    except Exception as e:
        log(f"[ERROR] Konnte freien Speicher nicht ermitteln: {e}")
        return "FAILED"

    if free_gb < MIN_FREE_GB:
        log(f"[ERROR] Zu wenig freier Speicher ({free_gb} GB < {MIN_FREE_GB} GB) im Download-Ordner ({DOWNLOAD_DIR}) - Abbruch")
        # Status global setzen, damit Web-UI es anzeigen kann
        try:
            with download_lock:
                current_download["status"] = "kein-speicher"
        except Exception:
            pass
        return "NO_SPACE"
    
    series_folder = os.path.join(DOWNLOAD_DIR, series_title)
    if not german_only:
        if episode_already_downloaded(series_folder, season, episode):
            log(f"[SKIP] Episode bereits vorhanden: {series_title} - " + (f"S{season}E{episode}" if season > 0 else f"Film {episode}"))
            return "SKIPPED"

    langs_to_try = ["German Dub"] if german_only else LANGUAGES
    episode_downloaded = False
    german_available = False

    for lang in langs_to_try:
        log(f"[DOWNLOAD] Versuche {lang} -> {episode_url}")
        cmd = ["aniworld", "--language", lang, "-o", str(DOWNLOAD_DIR), "--episode", episode_url]
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
                    free_after_gb = freier_speicher_mb(DOWNLOAD_DIR)
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
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # --- IDs + Titel aller als 'complete' markierten Animes holen ---
        c.execute("SELECT id, title FROM anime WHERE complete = 1")
        complete_animes_in_db = c.fetchall()  # Liste von Tupeln: [(id, title), ...]

        # --- Alle Ordnernamen im Downloads-Verzeichnis lesen (erste Ebene) ---
        local_animes = []
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
    "current_season": None,
    "current_episode": None,
    "current_is_film": None
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
            "current_season": None,
            "current_episode": None,
            "current_is_film": None
        })
    
    try:
        init_db()
        # lade Anime inkl. 'deleted' flag
        anime_list = load_anime()
        log(f"[INFO] Gewählter Modus: {mode}")
        if mode == "german":
            log("=== Modus: Prüfe auf neue deutsche Synchro ===")
            for idx, anime in enumerate(anime_list):
                current_download["current_index"] = idx
                # Überspringen wenn als deleted markiert
                if anime.get("deleted"):
                    log(f"[SKIP] '{anime['title']}' übersprungen (deleted flag gesetzt).")
                    continue
                series_title = anime["title"] or get_series_title(anime["url"])
                anime_id = anime["id"]
                current_download["current_title"] = series_title
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
        elif mode == "new":
            log("=== Modus: Prüfe auf neue Episoden & Filme ===")
            for idx, anime in enumerate(anime_list):
                
                current_download["current_index"] = idx
                if anime.get("deleted"):
                    log(f"[SKIP] '{anime['title']}' übersprungen (deleted flag gesetzt).")
                    continue
                series_title = anime["title"] or get_series_title(anime["url"])
                anime_id = anime["id"]
                base_url = anime["url"]
                current_download["current_title"] = series_title
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

        elif mode == "check-missing":
            log("=== Modus: Prüfe auf fehlende Episoden & Filme ===")
            """
            Prüft alle Anime, die entweder teilweise oder komplett heruntergeladen sind,
            und versucht fehlende Filme oder Episoden erneut zu laden.
            """
            anime_list = load_anime()
            for anime in anime_list:
                
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

        else:
            log("=== Modus: Standard  ===")
            for idx, anime in enumerate(anime_list):
                
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
                    "current_is_film": None
                })
            else:
                # Nur laufende Details zurücksetzen, Status bleibt 'kein-speicher'
                current_download.update({
                    "current_index": None,
                    "current_title": None,
                    "current_season": None,
                    "current_episode": None,
                    "current_is_film": None
                })
    

# -------------------- API Endpoints --------------------
@app.route("/start_download", methods=["POST", "GET"])
def api_start_download():
    body = request.get_json(silent=True) or {}
    mode = request.args.get("mode") or body.get("mode") or "default"
    if mode not in ("default", "german", "new", "check-missing"):
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

    


@app.route("/config", methods=["GET", "POST"])
def api_config():
    global LANGUAGES, MIN_FREE_GB
    if request.method == 'GET':
        try:
            cfg = {'languages': LANGUAGES, 'min_free_gb': MIN_FREE_GB}
            return jsonify(cfg)
        except Exception as e:
            log(f"[ERROR] api_config GET: {e}")
            return jsonify({'error': 'failed'}), 500

    # POST -> save
    data = request.get_json() or {}
    langs = data.get('languages')
    min_free = data.get('min_free_gb')
    changed = False
    try:
        if isinstance(langs, list) and langs:
            LANGUAGES = list(langs)
            changed = True
        if min_free is not None:
            MIN_FREE_GB = float(min_free)
            changed = True
        if changed:
            save_config()
        return jsonify({'status': 'ok'})
    except Exception as e:
        log(f"[ERROR] api_config POST: {e}")
        return jsonify({'status': 'failed', 'error': str(e)}), 400



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
        conn.close()

    return jsonify({"exists": exists})

@app.route("/")
def index():
    return render_template("index.html")

# -------------------- Entrypoint --------------------
if __name__ == "__main__":
    load_config()
    init_db()
    import_anime_txt()
    Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)
    deleted_check()
    log("[SYSTEM] AniLoader API starting...")
    # run Flask WITHOUT reloader so background threads survive page reloads
    app.run(host="0.0.0.0", port=5050, debug=False, threaded=True)
