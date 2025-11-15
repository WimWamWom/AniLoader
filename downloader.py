#!/usr/bin/env python3
# AniLoader.py by WimWamWom
import os
import socket
import subprocess
import time
import random
import threading
import requests
from bs4 import BeautifulSoup
from pathlib import Path
import re
import sqlite3
import json
import sys
import shutil
from urllib.parse import urlparse

# -------------------- Konfiguration --------------------
BASE_DIR = Path(__file__).resolve().parent
ANIME_TXT = BASE_DIR / "AniLoader.txt"
# Standard-Download-Ordner; kann via config.json (download_path) überschrieben werden
DEFAULT_DOWNLOAD_DIR = BASE_DIR / "Downloads"
# Effektiver Download-Ordner zur Laufzeit (wird in load_config gesetzt)
DOWNLOAD_DIR = DEFAULT_DOWNLOAD_DIR
# Neue Speichermodus-Variablen
STORAGE_MODE = "standard"  # 'standard' oder 'separate'
MOVIES_PATH = ""  # Nur für separate Mode (deprecated)
SERIES_PATH = ""  # Nur für separate Mode (deprecated)
# Neue Content-Type basierte Pfade
ANIME_PATH = ""  # Pfad für Animes (aniworld.to)
SERIEN_PATH = ""  # Pfad für Serien (s.to)
# Film/Staffel Organisation
ANIME_SEPARATE_MOVIES = False  # Filme getrennt von Staffeln bei Animes
SERIEN_SEPARATE_MOVIES = False  # Filme getrennt von Staffeln bei Serien
# Port-Schlüssel wird nur in der Config gepflegt (hier ohne Nutzung, für Kompatibilität)
SERVER_PORT = 5050
data_folder = os.path.join(os.path.dirname(__file__), 'data')
config_path = os.path.join(data_folder, 'config.json')
db_path = os.path.join(data_folder, 'AniLoader.db')
log_path = os.path.join(data_folder, 'last_run.log')
LANGUAGES = ["German Dub", "German Sub", "English Dub", "English Sub"]
MIN_FREE_GB = 2.0
REFRESH_TITLES = True

# Ensure the data folder exists
os.makedirs(data_folder, exist_ok=True)

# Update existing paths
CONFIG_PATH = Path(config_path)
DB_PATH = Path(db_path)

# -------------------- Datenbankfunktionen --------------------
def get_content_type_from_url(url):
    """
    Bestimmt den Content-Type basierend auf der URL.
    Returns: 'anime' für aniworld.to, 'serie' für s.to, None für unbekannt
    """
    try:
        hostname = urlparse(url).hostname
        if hostname:
            hostname = hostname.lower()
            if 'aniworld.to' in hostname:
                return 'anime'
            elif 's.to' in hostname:
                return 'serie'
    except Exception:
        pass
    return None

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

def import_anime_txt():
    if not ANIME_TXT.exists():
        print(f"[FEHLER] Anime-Datei nicht gefunden: {ANIME_TXT}")
        return

    with open(ANIME_TXT, "r", encoding="utf-8") as f:
        anime_links = [line.strip() for line in f if line.strip()]

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    for url in anime_links:
        try:
            title = get_series_title(url)
            c.execute("INSERT OR IGNORE INTO anime (url, title) VALUES (?, ?)", (url, title))
        except Exception as e:
            print(f"[FEHLER] DB Insert: {e}")

    conn.commit()
    conn.close()

def load_anime():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, title, url, complete, deutsch_komplett, fehlende_deutsch_folgen, last_film, last_episode, last_season FROM anime ORDER BY id")
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
            "fehlende_deutsch_folgen": json.loads(row[5]),
            "last_film": row[6],
            "last_episode": row[7],
            "last_season": row[8]
        }

        if not entry["title"]:
            new_title = get_series_title(entry["url"])
            if new_title:
                update_anime(entry["id"], title=new_title)
                entry["title"] = new_title

        anime_list.append(entry)
    return anime_list

def refresh_titles_on_start():
    """Aktualisiert Serien-Titel aus den Quellseiten. Läuft schnell durch und
    aktualisiert nur, wenn ein neuer Titel ermittelt werden kann und er sich geändert hat.
    """
    try:
        items = load_anime()
        changed = 0
        for entry in items:
            url = entry.get("url")
            if not url:
                continue
            new_title = get_series_title(url)
            if new_title and new_title != entry.get("title"):
                update_anime(entry["id"], title=new_title)
                changed += 1
                print(f"[TITLE] Aktualisiert: '{entry.get('title')}' -> '{new_title}'")
        if changed:
            print(f"[TITLE] {changed} Titel aktualisiert.")
    except Exception as e:
        print(f"[TITLE-ERROR] {e}")

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
    c.execute(f"UPDATE anime SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()
    conn.close()

def check_deutsch_komplett(anime_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT fehlende_deutsch_folgen FROM anime WHERE id = ?", (anime_id,))
    row = c.fetchone()
    conn.close()
    fehlende = json.loads(row[0]) if row else []
    if not fehlende:
        update_anime(anime_id, deutsch_komplett=True)
        return True
    return False

# -------------------- Hilfsfunktionen --------------------
def sanitize_filename(name):
    return re.sub(r'[<>:"/\\|?*]', ' ', name)

def get_episode_title(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        # DNS nur für diese Anfrage über 1.1.1.1 leiten
        host = urlparse(url).hostname
        ips = resolve_ips_via_cloudflare(host)
        with DnsOverride(host, ips):
            r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        german_title = soup.select_one("span.episodeGermanTitle")
        if german_title and german_title.text.strip():
            return german_title.text.strip()
        english_title = soup.select_one("small.episodeEnglishTitle")
        if english_title and english_title.text.strip():
            return english_title.text.strip()
    except Exception as e:
        print(f"[FEHLER] Konnte Episodentitel nicht abrufen ({url}): {e}")
    return None

def _write_config_atomic(cfg: dict) -> bool:
    """Schreibt config.json schön formatiert, mit einfachem Retry und atomarem Replace, wo möglich."""
    try:
        tmp = str(CONFIG_PATH) + ".tmp"
        # Versuche bis zu 3x zu schreiben/ersetzen (Windows/AV kann sperren)
        for attempt in range(3):
            try:
                with open(tmp, 'w', encoding='utf-8') as f:
                    json.dump(cfg, f, indent=2, ensure_ascii=False)
                os.replace(tmp, CONFIG_PATH)
                return True
            except PermissionError:
                time.sleep(0.2 * (attempt + 1))
        # Fallback: direkt schreiben (nicht atomar)
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[CONFIG-ERROR] Schreiben fehlgeschlagen: {e}")
        return False


def load_config():
    global LANGUAGES, MIN_FREE_GB, DOWNLOAD_DIR, SERVER_PORT, REFRESH_TITLES, STORAGE_MODE, MOVIES_PATH, SERIES_PATH, ANIME_PATH, SERIEN_PATH, ANIME_SEPARATE_MOVIES, SERIEN_SEPARATE_MOVIES
    try:
        cfg = {}
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                try:
                    cfg = json.load(f) or {}
                except Exception:
                    cfg = {}
        # Defaults setzen/erweitern
        changed = False
        if 'languages' in cfg:
            LANGUAGES = cfg.get('languages', LANGUAGES)
        else:
            cfg['languages'] = LANGUAGES
            changed = True
        if 'min_free_gb' in cfg:
            try:
                MIN_FREE_GB = float(cfg.get('min_free_gb', MIN_FREE_GB))
            except Exception:
                MIN_FREE_GB = 2.0
                cfg['min_free_gb'] = MIN_FREE_GB
                changed = True
        else:
            cfg['min_free_gb'] = MIN_FREE_GB
            changed = True

        # Neuer Schlüssel: download_path
        dlp = cfg.get('download_path')
        if not dlp:
            dlp = str(DEFAULT_DOWNLOAD_DIR)
            cfg['download_path'] = dlp
            changed = True
        DOWNLOAD_DIR = Path(dlp)
        Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)

        # Neue Schlüssel: storage_mode, movies_path, series_path
        if 'storage_mode' in cfg:
            mode = cfg.get('storage_mode', 'standard')
            STORAGE_MODE = mode if mode in ['standard', 'separate'] else 'standard'
        else:
            cfg['storage_mode'] = 'standard'
            STORAGE_MODE = 'standard'
            changed = True
        
        if 'movies_path' in cfg:
            MOVIES_PATH = cfg.get('movies_path', '')
        else:
            # Standardmäßig Unterordner "Filme" im Download-Verzeichnis
            cfg['movies_path'] = str(DOWNLOAD_DIR / 'Filme')
            MOVIES_PATH = str(DOWNLOAD_DIR / 'Filme')
            changed = True
            
        if 'series_path' in cfg:
            SERIES_PATH = cfg.get('series_path', '')
        else:
            # Standardmäßig Unterordner "Serien" im Download-Verzeichnis
            cfg['series_path'] = str(DOWNLOAD_DIR / 'Serien')
            SERIES_PATH = str(DOWNLOAD_DIR / 'Serien')
            changed = True
        
        # Neue Content-Type basierte Pfade
        if 'anime_path' in cfg:
            ANIME_PATH = cfg.get('anime_path', '')
        else:
            cfg['anime_path'] = str(DOWNLOAD_DIR / 'Animes')
            ANIME_PATH = str(DOWNLOAD_DIR / 'Animes')
            changed = True
            
        if 'serien_path' in cfg:
            SERIEN_PATH = cfg.get('serien_path', '')
        else:
            cfg['serien_path'] = str(DOWNLOAD_DIR / 'Serien')
            SERIEN_PATH = str(DOWNLOAD_DIR / 'Serien')
            changed = True
        
        # Film/Staffel Organisation
        if 'anime_separate_movies' in cfg:
            ANIME_SEPARATE_MOVIES = cfg.get('anime_separate_movies', False)
        else:
            cfg['anime_separate_movies'] = False
            ANIME_SEPARATE_MOVIES = False
            changed = True
            
        if 'serien_separate_movies' in cfg:
            SERIEN_SEPARATE_MOVIES = cfg.get('serien_separate_movies', False)
        else:
            cfg['serien_separate_movies'] = False
            SERIEN_SEPARATE_MOVIES = False
            changed = True

        # Neuer Schlüssel: port (nur in Config genutzt)
        prt = cfg.get('port')
        try:
            SERVER_PORT = int(prt) if prt is not None else SERVER_PORT
        except Exception:
            SERVER_PORT = 5050
        if 'port' not in cfg:
            cfg['port'] = SERVER_PORT
            changed = True

        # Neuer Schlüssel: refresh_titles (Titelaktualisierung beim Start)
        if 'refresh_titles' in cfg:
            try:
                REFRESH_TITLES = bool(cfg.get('refresh_titles'))
            except Exception:
                REFRESH_TITLES = True
                cfg['refresh_titles'] = True
                changed = True
        else:
            cfg['refresh_titles'] = True
            REFRESH_TITLES = True
            changed = True

        if changed:
            _write_config_atomic(cfg)
    except Exception as e:
        print(f"[CONFIG-ERROR] {e}")

def save_config():
    try:
        # Behalte unbekannte Schlüssel (z.B. autostart_mode), um sie nicht zu löschen
        base = {}
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, 'r', encoding='utf-8') as rf:
                    base = json.load(rf) or {}
            except Exception:
                base = {}
        base['languages'] = LANGUAGES
        base['min_free_gb'] = MIN_FREE_GB
        base['download_path'] = str(DOWNLOAD_DIR)
        base['storage_mode'] = STORAGE_MODE
        base['movies_path'] = MOVIES_PATH
        base['series_path'] = SERIES_PATH
        base['anime_path'] = ANIME_PATH
        base['serien_path'] = SERIEN_PATH
        base['anime_separate_movies'] = ANIME_SEPARATE_MOVIES
        base['serien_separate_movies'] = SERIEN_SEPARATE_MOVIES
        base['port'] = base.get('port', SERVER_PORT)
        base['refresh_titles'] = REFRESH_TITLES
        return _write_config_atomic(base)
    except Exception as e:
        print(f"[CONFIG-ERROR] save_config: {e}")
        return False

def freier_speicher_mb(pfad: str) -> float:
    """Gibt den verfügbaren Speicherplatz des angegebenen Pfads in GB zurück."""
    try:
        # Unterstützt str oder Path
        p = str(pfad)
        gesamt, belegt, frei = shutil.disk_usage(p)
        return round(frei / (1024 ** 3), 1)
    except FileNotFoundError:
        raise ValueError(f"Pfad nicht gefunden: {pfad}")
    except PermissionError:
        raise PermissionError(f"Zugriff verweigert auf: {pfad}")

def get_series_title(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        host = urlparse(url).hostname
        ips = resolve_ips_via_cloudflare(host)
        with DnsOverride(host, ips):
            r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        title = soup.select_one("div.series-title h1 span")
        if title and title.text.strip():
            return sanitize_filename(title.text.strip())
    except Exception as e:
        print(f"[FEHLER] Konnte Serien-Titel nicht abrufen ({url}): {e}")
    return None

# -------------------- DNS über 1.1.1.1 nur für Titelabfragen --------------------
def resolve_ips_via_cloudflare(hostname: str):
    """Löst Host über Cloudflare DNS (1.1.1.1) auf und gibt Liste von IPs zurück.
    Fällt auf None zurück, wenn dnspython nicht verfügbar oder Auflösung fehlschlägt.
    """
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
        # dnspython nicht installiert oder Fehler -> Standard-DNS verwenden
        return None


class DnsOverride:
    """Kontextmanager, der socket.getaddrinfo temporär patcht, um eine
    bestimmte Hostauflösung mit vorgegebenen IPs (von 1.1.1.1) zu erzwingen.
    """
    def __init__(self, hostname: str, ips: list | None):
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

def get_base_path_for_content(content_type='anime', is_film=False):
    """
    Gibt den Basis-Pfad für Downloads zurück, basierend auf storage_mode, content_type und is_film.
    
    Args:
        content_type: 'anime' für aniworld.to, 'serie' für s.to
        is_film: True wenn es sich um einen Film handelt (Season 0)
    
    Returns:
        Path object für den Download-Pfad
    """
    if STORAGE_MODE == 'separate':
        # Content-Type basierte Pfade
        if content_type == 'anime' and ANIME_PATH:
            base_path = Path(ANIME_PATH)
            # Wenn Film-Separation aktiviert ist
            if is_film and ANIME_SEPARATE_MOVIES:
                base_path = base_path / 'Filme'
            base_path.mkdir(parents=True, exist_ok=True)
            return base_path
        elif content_type == 'serie' and SERIEN_PATH:
            base_path = Path(SERIEN_PATH)
            # Wenn Film-Separation aktiviert ist
            if is_film and SERIEN_SEPARATE_MOVIES:
                base_path = base_path / 'Filme'
            base_path.mkdir(parents=True, exist_ok=True)
            return base_path
        # Fallback zu alten MOVIES_PATH/SERIES_PATH (deprecated, für Kompatibilität)
        elif is_film and MOVIES_PATH:
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
    pattern = f"S{season:02d}E{episode:03d}" if season > 0 else f"Film{episode:02d}"
    for file in Path(series_folder).rglob("*.mp4"):
        if pattern.lower() in file.name.lower():
            return True
    return False

def delete_old_non_german_versions(series_folder, season, episode):
    pattern = f"S{season:02d}E{episode:03d}" if season > 0 else f"Film{episode:02d}"
    for file in Path(series_folder).rglob("*.mp4"):
        if pattern.lower() in file.name.lower() and "dub" not in file.name.lower():
            try:
                os.remove(file)
                print(f"[DEL] Alte Version gelöscht: {file.name}")
            except Exception as e:
                print(f"[FEHLER] Konnte Datei nicht löschen: {file.name} -> {e}")

def rename_downloaded_file(series_folder, season, episode, title, language, content_type='anime'):
    """
    Benennt heruntergeladene Datei um und verschiebt sie in den richtigen Ordner.
    
    Args:
        series_folder: Basis-Ordner für die Serie/Anime
        season: Staffel-Nummer (0 = Film)
        episode: Episoden-Nummer
        title: Titel der Episode
        language: Sprache (German Dub, etc.)
        content_type: 'anime' oder 'serie'
    """
    lang_suffix = {
        "German Dub": False,
        "German Sub": "Sub",
        "English Dub": "English Dub",
        "English Sub": "English Sub"
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

    safe_title = sanitize_filename(title) if title else ""
    new_name = f"{pattern}"
    if safe_title:
        new_name += f" - {safe_title}"
    if lang_suffix:
        new_name += f" [{lang_suffix}]"
    new_name += ".mp4"

    # Bestimme Zielordner basierend auf STORAGE_MODE und Film-Separation
    is_film = (season == 0)
    
    # Prüfe ob Film-Separation für diesen Content-Type aktiv ist
    separate_movies = False
    if content_type == 'anime' and ANIME_SEPARATE_MOVIES:
        separate_movies = True
    elif content_type == 'serie' and SERIEN_SEPARATE_MOVIES:
        separate_movies = True
    
    if STORAGE_MODE == 'separate' and is_film and separate_movies:
        # Filme sind bereits im separaten Filme-Ordner, keine weitere Unterteilung
        dest_folder = Path(series_folder)
    elif not separate_movies and is_film:
        # Filme in "Filme" Unterordner innerhalb der Serie
        dest_folder = Path(series_folder) / "Filme"
    elif season > 0:
        # Staffeln in eigenen Unterordnern
        dest_folder = Path(series_folder) / f"Staffel {season}"
    else:
        dest_folder = Path(series_folder)
    
    dest_folder.mkdir(parents=True, exist_ok=True)
    new_path = dest_folder / new_name

    try:
        shutil.move(file_to_rename, new_path)
        print(f"[OK] Umbenannt: {file_to_rename.name} -> {new_name}")
        return True
    except Exception as e:
        print(f"[FEHLER] Umbenennen fehlgeschlagen: {e}")
        return False

def run_download(cmd):
    try:
        process = subprocess.run(cmd, capture_output=True, text=True)
        out = process.stdout + process.stderr
        if "No streams available for episode" in out:
            return "NO_STREAMS"
        if "No provider found for language" in out:
            return "LANGUAGE_ERROR"
        return "OK" if process.returncode == 0 else "FAILED"
    except Exception as e:
        print(f"[FEHLER] {e}")
        return "FAILED"

# -------------------- Downloadfunktionen --------------------
def download_episode(series_title, episode_url, season, episode, anime_id, german_only=False):
    # Content-Type aus URL bestimmen
    content_type = get_content_type_from_url(episode_url)
    if not content_type:
        content_type = 'anime'  # Default zu anime wenn unbekannt
    
    # Bestimme den richtigen Basis-Pfad basierend auf Content-Type und Film-Status
    is_film = (season == 0)
    base_path = get_base_path_for_content(content_type, is_film)
    series_folder = os.path.join(str(base_path), series_title)
    
    # Prüfe freien Speicher vor jedem Download
    try:
        free_gb = freier_speicher_mb(base_path)
    except Exception as e:
        print(f"[ERROR] Konnte freien Speicher nicht ermitteln: {e}")
        return "FAILED"

    if free_gb < MIN_FREE_GB:
        print(f"[ERROR] Zu wenig freier Speicher ({free_gb} GB < {MIN_FREE_GB} GB) - Abbruch")
        return "NO_SPACE"
    if german_only == False:
        if episode_already_downloaded(series_folder, season, episode):
            print(f"[SKIP] Episode bereits vorhanden: {series_title} - " + (f"S{season}E{episode}" if season > 0 else f"Film {episode}"))
            return "SKIPPED"

    langs_to_try = ["German Dub"] if german_only else LANGUAGES
    episode_downloaded = False
    german_available = False

    for lang in langs_to_try:
        print(f"[DOWNLOAD] Versuche {lang} -> {episode_url}")
        cmd = ["aniworld", "--language", lang, "-o", str(base_path), "--episode", episode_url]
        result = run_download(cmd)
        if result == "NO_STREAMS":
            print(f"[INFO] Kein Stream verfügbar: {episode_url} -> Abbruch")
            return "NO_STREAMS"
        elif result == "OK":
            title = get_episode_title(episode_url)
            rename_downloaded_file(series_folder, season, episode, title, lang, content_type)
            if lang == "German Dub":
                german_available = True
                delete_old_non_german_versions(series_folder, season, episode)
            episode_downloaded = True
            print(f"[SUCCESS] {lang} erfolgreich geladen: {episode_url}")
            break
        elif result == "LANGUAGE_ERROR":
            continue

    # Wenn German Dub nicht verfügbar -> in fehlende_deutsch_folgen speichern
    if not german_available:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT fehlende_deutsch_folgen FROM anime WHERE id = ?", (anime_id,))
        row = c.fetchone()
        fehlende = json.loads(row[0]) if row else []
        if episode_url not in fehlende:
            fehlende.append(episode_url)
            update_anime(anime_id, fehlende_deutsch_folgen=fehlende)
            print(f"[INFO] Episode zu fehlende_deutsch_folgen hinzugefügt: {episode_url}")

    # Nach jedem Versuch prüfen, ob deutsch_komplett gesetzt werden muss
    check_deutsch_komplett(anime_id)

    return "OK" if episode_downloaded else "FAILED"

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

        c.execute("SELECT id, title FROM anime WHERE complete = 1")
        complete_animes_in_db = c.fetchall()

        # Sammle alle lokalen Anime-Ordner aus allen relevanten Pfaden
        local_animes = []
        
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

        deleted_anime = []
        for anime_id, anime_title in complete_animes_in_db:
            if anime_title not in local_animes:
                deleted_anime.append(anime_title)
                # reset fields
                c.execute("UPDATE anime SET deleted = 1, complete = 0, last_film = 0, last_episode = 0, last_season = 0 WHERE id = ?", (anime_id,))

        conn.commit()
        conn.close()
        if deleted_anime:
            print(f"[INFO] Gelöschte Animes: {deleted_anime}")
        return deleted_anime
    except Exception as e:
        print(f"[ERROR] deleted_check: {e}")
        return []

def download_films(series_title, base_url, anime_id, german_only=False, start_film=1):
    film_num = start_film
    print(f"[INFO] Starte Filmprüfung ab Film {start_film}")
    while True:
        film_url = f"{base_url}/filme/film-{film_num}"
        result = download_episode(series_title, film_url, 0, film_num, anime_id, german_only)
        if result in ["NO_STREAMS", "FAILED"]:
            print(f"[INFO] Keine weiteren Filme gefunden bei Film {film_num}.")
            break
        update_anime(anime_id, last_film=film_num)
        film_num += 1
        time.sleep(1)

def download_seasons(series_title, base_url, anime_id, german_only=False, start_season=1, start_episode=1):
    season = start_season if start_season > 0 else 1
    consecutive_empty_seasons = 0  # Zählt aufeinanderfolgende leere Staffeln

    while True:
        episode = start_episode
        found_episode_in_season = False
        print(f"[CHECK] Prüfe Staffel {season} von '{series_title}'")
        
        while True:
            episode_url = f"{base_url}/staffel-{season}/episode-{episode}"
            result = download_episode(series_title, episode_url, season, episode, anime_id, german_only)

            if result in ["NO_STREAMS", "FAILED"]:
                if episode == start_episode:
                    print(f"[INFO] Keine Episoden gefunden in Staffel {season}.")
                    break  # Staffel überspringen und nächste prüfen
                else:
                    print(f"[INFO] Staffel {season} beendet nach {episode-1} Episoden.")
                    break

            found_episode_in_season = True
            update_anime(anime_id, last_episode=episode, last_season=season)
            episode += 1
            time.sleep(1)

        if not found_episode_in_season:
            consecutive_empty_seasons += 1
        else:
            consecutive_empty_seasons = 0

        # Wenn 2 leere Staffeln in Folge -> Serie abgeschlossen
        if consecutive_empty_seasons >= 2:
            print(f"[INFO] Keine weiteren Staffeln gefunden. '{series_title}' scheint abgeschlossen zu sein.")
            update_anime(anime_id, complete=True)
            break

        # Nächste Staffel prüfen
        season += 1
        start_episode = 1

# -------------------- Hauptprogramm --------------------
def main():
    # load config and ensure DB + folders exist
    load_config()
    init_db()
    import_anime_txt()
    if REFRESH_TITLES:
        refresh_titles_on_start()
    Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)
    # Detect deleted series in filesystem and mark in DB
    deleted_check()

    anime_list = load_anime()

    mode = str(sys.argv[1].lower() if len(sys.argv) > 1 else "default")
    print(f"[INFO] Gewählter Modus: {mode}")

    if mode == "german":
        print("\n=== Modus: Prüfe auf neue deutsche Synchro ===")
        for anime in anime_list:
            fehlende = anime.get("fehlende_deutsch_folgen", [])
            series_title = anime["title"] or get_series_title(anime["url"])
            anime_id = anime["id"]
            if not fehlende:
                print(f"[GERMAN] '{series_title}': Keine neuen deutschen Folgen")
                check_deutsch_komplett(anime_id)
                continue
            print(f"[GERMAN] '{series_title}': {len(fehlende)} Folgen zu testen.")
            verbleibend = fehlende.copy()
            for url in fehlende:
                match = re.search(r"/staffel-(\d+)/episode-(\d+)", url)
                season = int(match.group(1)) if match else 0
                episode = int(match.group(2)) if match else int(re.search(r"/film-(\d+)", url).group(1))
                result = download_episode(series_title, url, season, episode, anime_id, german_only=True)
                if result == "OK" and url in verbleibend:
                    verbleibend.remove(url)
                    update_anime(anime_id, fehlende_deutsch_folgen=verbleibend)
            print(f"[GERMAN] '{url}' erfolgreich auf deutsch.")
            # Korrigierter Pfad: vollständigen Serienordner übergeben
            delete_old_non_german_versions(series_folder=os.path.join(str(DOWNLOAD_DIR), series_title), season=season, episode=episode)
            check_deutsch_komplett(anime_id)

    elif mode == "new":
        print("\n=== Modus: Prüfe auf neue Episoden & Filme ===")
        for anime in anime_list:
            series_title = anime["title"] or get_series_title(anime["url"])
            anime_id = anime["id"]
            base_url = anime["url"]
            start_film = anime["last_film"] + 1
            start_season = anime["last_season"]
            start_episode = anime["last_episode"] + 1 if start_season > 0 else 1
            print(f"\n[NEW] Prüfe '{series_title}' ab Film {start_film} und Staffel {start_season}, Episode {start_episode}")
            download_films(series_title, base_url, anime_id, start_film=start_film)
            download_seasons(series_title, base_url, anime_id, start_season=start_season, start_episode=start_episode)
            check_deutsch_komplett(anime_id)

    elif mode == "check-missing":
        print("\n=== Modus: Prüfe auf fehlende Episoden & Filme ===")
        for anime in anime_list:
            series_title = anime["title"] or get_series_title(anime["url"])
            anime_id = anime["id"]
            base_url = anime["url"]
            # First re-try any entries in fehlende_deutsch_folgen (german-only)
            fehlende = anime.get("fehlende_deutsch_folgen", []) or []
            if fehlende:
                print(f"[MISSING] '{series_title}': {len(fehlende)} fehlende deutsche Folgen werden geprüft.")
                verbleibend = fehlende.copy()
                for url in fehlende:
                    match = re.search(r"/staffel-(\d+)/episode-(\d+)", url)
                    season = int(match.group(1)) if match else 0
                    episode = int(match.group(2)) if match else int(re.search(r"/film-(\d+)", url).group(1))
                    result = download_episode(series_title, url, season, episode, anime_id, german_only=True)
                    if result == "OK" and url in verbleibend:
                        verbleibend.remove(url)
                        update_anime(anime_id, fehlende_deutsch_folgen=verbleibend)
                        print(f"[MISSING] '{url}' jetzt auf deutsch vorhanden.")
            # Next, check files up to last known indices and try to restore missing files
            series_folder = os.path.join(DOWNLOAD_DIR, series_title)
            # Films
            last_film = anime.get("last_film", 0) or 0
            for fnum in range(1, last_film + 1):
                if not episode_already_downloaded(series_folder, 0, fnum):
                    print(f"[MISSING] Film {fnum} fehlt, versuche Download...")
                    download_episode(series_title, f"{base_url}/filme/film-{fnum}", 0, fnum, anime_id)
                    time.sleep(1)
            # Seasons
            last_season = anime.get("last_season", 0) or 0
            last_episode = anime.get("last_episode", 0) or 0
            for s in range(1, max(1, last_season) + 1):
                # Conservative approach: check episodes 1..last_episode for each season,
                # preferring to re-download anything missing up to the recorded last_episode.
                for e in range(1, last_episode + 1):
                    if not episode_already_downloaded(series_folder, s, e):
                        print(f"[MISSING] S{s}E{e} fehlt, versuche Download...")
                        download_episode(series_title, f"{base_url}/staffel-{s}/episode-{e}", s, e, anime_id)
                        time.sleep(1)
            check_deutsch_komplett(anime_id)

    elif mode == "full-check":
        print("\n=== Modus: Kompletter Check (alle Animes von Anfang an prüfen) ===")
        for anime in anime_list:
            series_title = anime["title"] or get_series_title(anime["url"])
            anime_id = anime["id"]
            base_url = anime["url"]
            # Zuerst fehlende deutsche Folgen erneut versuchen (wie in check-missing)
            fehlende = anime.get("fehlende_deutsch_folgen", []) or []
            if fehlende:
                print(f"[FULL-CHECK] '{series_title}': {len(fehlende)} fehlende deutsche Folgen werden geprüft.")
                verbleibend = fehlende.copy()
                for url in fehlende:
                    match = re.search(r"/staffel-(\d+)/episode-(\d+)", url)
                    season = int(match.group(1)) if match else 0
                    episode = int(match.group(2)) if match else int(re.search(r"/film-(\d+)", url).group(1))
                    result = download_episode(series_title, url, season, episode, anime_id, german_only=True)
                    if result == "OK" and url in verbleibend:
                        verbleibend.remove(url)
                        update_anime(anime_id, fehlende_deutsch_folgen=verbleibend)
                        print(f"[FULL-CHECK] '{url}' jetzt auf deutsch vorhanden.")
            # Danach vollständige Prüfung ab Film 1 und Staffel 1/Episode 1
            print(f"\n[FULL-CHECK] Prüfe '{series_title}' komplett von Anfang an…")
            download_films(series_title, base_url, anime_id, start_film=1)
            download_seasons(series_title, base_url, anime_id, start_season=1, start_episode=1)
            check_deutsch_komplett(anime_id)

    else:
        print("\n=== Modus: Standard  ===")
        for anime in anime_list:
            if anime["complete"]:
                print(f"[SKIP] '{anime['title']}' bereits komplett.")
                check_deutsch_komplett(anime["id"])
                continue
            series_title = anime["title"] or get_series_title(anime["url"])
            anime_id = anime["id"]
            base_url = anime["url"]
            start_film = anime["last_film"] + 1
            start_season = anime["last_season"]
            start_episode = anime["last_episode"] + 1 if start_season > 0 else 1
            print(f"\n[START] Starte Download für: '{series_title}' ab Film {start_film} / Staffel {start_season}, Episode {start_episode}")
            download_films(series_title, base_url, anime_id, start_film=start_film)
            download_seasons(series_title, base_url, anime_id, start_season=max(1, start_season), start_episode=start_episode)
            check_deutsch_komplett(anime_id)
            update_anime(anime_id, complete=True)
            print(f"[COMPLETE] Download abgeschlossen für: '{series_title}'")
    input("\n[FERTIG] Alle Aufgaben abgeschlossen, drücke eine beliebige Taste zum Beenden.")

if __name__ == "__main__":
    main()
