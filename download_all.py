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

# -------------------- Konfiguration --------------------
BASE_DIR = Path(__file__).resolve().parent
ANIME_TXT = BASE_DIR / "Anime.txt"
DOWNLOAD_DIR = BASE_DIR / "Anime"
DB_PATH = BASE_DIR / "anime.db"
LANGUAGES = ["German Dub", "German Sub", "English Dub", "English Sub"]

# -------------------- Datenbankfunktionen --------------------
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
            c.execute("INSERT OR IGNORE INTO anime (url) VALUES (?)", (url,))
        except Exception as e:
            print(f"[FEHLER] DB Insert: {e}")
    conn.commit()
    conn.close()

def load_anime():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, title, url, complete, deutsch_komplett, fehlende_deutsch_folgen, last_film, last_episode, last_season FROM anime")
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
        anime_list.append(entry)
    return anime_list

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

# -------------------- Hilfsfunktionen --------------------
def sanitize_filename(name):
    return re.sub(r'[<>:"/\\|?*]', ' ', name)

def get_episode_title(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
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

def get_series_title(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        title = soup.select_one("div.series-title h1 span")
        if title and title.text.strip():
            return sanitize_filename(title.text.strip())
    except Exception as e:
        print(f"[FEHLER] Konnte Serien-Titel nicht abrufen ({url}): {e}")
    return None

def episode_already_downloaded(series_folder, season, episode):
    if not os.path.exists(series_folder):
        return False
    pattern = f"S{season:02d}E{episode:03d}"
    for root, dirs, files in os.walk(series_folder):
        for file in files:
            if file.lower().endswith(".mp4") and pattern.lower() in file.lower():
                return True
    return False

def rename_latest_episode(latest_folder, season, episode, title, language):
    mp4_files = list(Path(latest_folder).glob("*.mp4"))
    if not mp4_files: return False
    latest_mp4 = str(max(mp4_files, key=os.path.getmtime))
    safe_title = sanitize_filename(title) if title else ""
    lang_suffix = language.split()[-1]  # Dub/Sub/English
    new_name = f"S{season:02d}E{episode:03d}"
    if safe_title: new_name += f" - {safe_title}"
    if lang_suffix: new_name += f" [{lang_suffix}]"
    new_name += ".mp4"
    new_path = os.path.join(latest_folder, new_name)
    try:
        os.rename(latest_mp4, new_path)
        return True
    except Exception as e:
        print(f"[FEHLER] Umbenennen: {e}")
        return False

def run_download(cmd):
    try:
        process = subprocess.run(cmd, capture_output=True, text=True)
        out = process.stdout + process.stderr
        if "No streams available for episode" in out: return "NO_STREAMS"
        if "No provider found for language" in out: return "LANGUAGE_ERROR"
        if process.returncode == 0: return "OK"
        return "FAILED"
    except Exception as e:
        print(f"[FEHLER] {e}")
        return "FAILED"

# -------------------- Downloadfunktionen --------------------
def download_episode(episode_url, season, episode, anime_id, german_only=False):
    series_title = get_series_title(episode_url)
    if not series_title: return False
    series_folder = os.path.join(DOWNLOAD_DIR, series_title)
    if episode_already_downloaded(series_folder, season, episode):
        return True

    langs_to_try = ["German Dub"] if german_only else LANGUAGES
    for lang in langs_to_try:
        cmd = ["aniworld", "--language", lang, "-o", DOWNLOAD_DIR, "--episode", episode_url]
        result = run_download(cmd)
        if result == "OK":
            title = get_episode_title(episode_url)
            rename_latest_episode(series_folder, season, episode, title, lang)
            return True
    return False

def download_films(base_url, anime_id, german_only=False):
    film_num = 1
    while True:
        url = f"{base_url}/filme/film-{film_num}"
        success = download_episode(url, 0, film_num, anime_id, german_only)
        if not success: break
        update_anime(anime_id, last_film=film_num)
        film_num += 1
        time.sleep(1)

def download_seasons(base_url, anime_id, german_only=False, start_season=1, start_episode=1):
    season = start_season
    while True:
        episode = start_episode
        found_episode = False
        while True:
            url = f"{base_url}/staffel-{season}/episode-{episode}"
            success = download_episode(url, season, episode, anime_id, german_only)
            if not success:
                if episode == start_episode: return
                break
            found_episode = True
            update_anime(anime_id, last_episode=episode, last_season=season)
            episode += 1
            time.sleep(1)
        if not found_episode: return
        season += 1

# -------------------- Hauptprogramm --------------------
def main():
    init_db()
    import_anime_txt()
    anime_list = load_anime()

    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "all"

    for anime in anime_list:
        anime_id = anime["id"]
        base_url = anime["url"]
        series_title = get_series_title(base_url)
        print(f"\n========== Starte Download für: {series_title} ==========")

        if mode == "german":
            fehlende = anime["fehlende_deutsch_folgen"]
            for url in fehlende.copy():
                download_episode(url, 0, 0, anime_id, german_only=True)
        elif mode == "new-episodes":
            download_films(base_url, anime_id)
            download_seasons(base_url, anime_id, start_season=anime["last_season"], start_episode=anime["last_episode"] + 1)
        else:  # all
            download_films(base_url, anime_id)
            download_seasons(base_url, anime_id)
            update_anime(anime_id, deutsch_komplett=True, complete=True)

if __name__ == "__main__":
    main()
