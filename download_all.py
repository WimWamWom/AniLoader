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
ANIME_TXT = BASE_DIR / "Download.txt"
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
                print(f"[FEHLER] Konnte Datei nicht löschen: {file.name} → {e}")

def rename_downloaded_file(series_folder, season, episode, title, language):
    lang_suffix = {"German Dub": "Dub", "German Sub": "Sub", "English Dub": "English Dub", "English Sub": "English Sub"}.get(language, "")
    pattern = f"S{season:02d}E{episode:03d}" if season > 0 else f"Film{episode:02d}"
    matching_files = [f for f in Path(series_folder).rglob("*.mp4") if pattern.lower() in f.name.lower()]
    if not matching_files:
        print(f"[WARN] Keine Datei gefunden für {pattern}")
        return False
    file_to_rename = matching_files[0]
    safe_title = sanitize_filename(title) if title else ""
    new_name = f"{pattern}"
    if safe_title:
        new_name += f" - {safe_title}"
    if lang_suffix:
        new_name += f" [{lang_suffix}]"
    new_name += ".mp4"

    dest_folder = Path(series_folder) / ("Filme" if season == 0 else f"Staffel {season}")
    dest_folder.mkdir(parents=True, exist_ok=True)
    new_path = dest_folder / new_name
    try:
        shutil.move(file_to_rename, new_path)
        print(f"[OK] Umbenannt: {file_to_rename.name} → {new_name}")
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
    series_folder = os.path.join(DOWNLOAD_DIR, series_title)
    if episode_already_downloaded(series_folder, season, episode):
        print(f"[SKIP] Episode bereits vorhanden: {series_title} - " + (f"S{season}E{episode}" if season > 0 else f"Film {episode}"))
        return "SKIPPED"
    langs_to_try = ["German Dub"] if german_only else LANGUAGES
    for lang in langs_to_try:
        print(f"[DOWNLOAD] Versuche {lang} → {episode_url}")
        cmd = ["aniworld", "--language", lang, "-o", DOWNLOAD_DIR, "--episode", episode_url]
        result = run_download(cmd)
        if result == "NO_STREAMS":
            print(f"[INFO] Kein Stream verfügbar: {episode_url} → Abbruch")
            return "NO_STREAMS"  # sofort abbrechen, keine weiteren Sprachen
        elif result == "OK":
            title = get_episode_title(episode_url)
            rename_downloaded_file(series_folder, season, episode, title, lang)
            if lang == "German Dub":
                delete_old_non_german_versions(series_folder, season, episode)
            print(f"[SUCCESS] {lang} erfolgreich geladen: {episode_url}")
            return "OK"
        elif result == "LANGUAGE_ERROR":
            continue
    print(f"[FAILED] Download fehlgeschlagen: {episode_url}")
    return "FAILED"

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
    while True:
        episode = start_episode
        found_episode_in_season = False
        while True:
            episode_url = f"{base_url}/staffel-{season}/episode-{episode}"
            result = download_episode(series_title, episode_url, season, episode, anime_id, german_only)
            if result in ["NO_STREAMS", "FAILED"]:
                if episode == start_episode:
                    print(f"[INFO] Keine Episoden gefunden in Staffel {season}. Anime abgeschlossen.")
                    update_anime(anime_id, complete=True)
                    return
                else:
                    print(f"[INFO] Staffel {season} beendet nach {episode-1} Episoden.")
                    break
            found_episode_in_season = True
            update_anime(anime_id, last_episode=episode, last_season=season)
            episode += 1
            time.sleep(1)
        season += 1
        start_episode = 1

def check_deutsch_komplett(anime):
    series_folder = os.path.join(DOWNLOAD_DIR, anime["title"])
    all_episodes = list(Path(series_folder).rglob("*.mp4"))
    german_missing = any("Dub" not in f.name for f in all_episodes if "Film" not in f.name)
    if not german_missing:
        update_anime(anime["id"], deutsch_komplett=True)
        print(f"[INFO] Serie komplett auf Deutsch: {anime['title']}")

# -------------------- Hauptprogramm --------------------
def main():
    init_db()
    import_anime_txt()
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
                continue
            print(f"[GERMAN] '{series_title}': {len(fehlende)} neue deutsche Folgen gefunden")
            verbleibend = fehlende.copy()
            for url in fehlende:
                match = re.search(r"/staffel-(\d+)/episode-(\d+)", url)
                season = int(match.group(1)) if match else 0
                episode = int(match.group(2)) if match else int(re.search(r"/film-(\d+)", url).group(1))
                result = download_episode(series_title, url, season, episode, anime_id, german_only=True)
                if result == "OK" and url in verbleibend:
                    verbleibend.remove(url)
                    update_anime(anime_id, fehlende_deutsch_folgen=verbleibend)
            if not verbleibend:
                update_anime(anime_id, deutsch_komplett=True)
                print(f"[GERMAN] Serie jetzt komplett auf Deutsch: {series_title}")

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

    else:
        print("\n=== Modus: Standard  ===")
        for anime in anime_list:
            if anime["complete"]:
                print(f"[SKIP] '{anime['title']}' bereits komplett.")
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
            check_deutsch_komplett(anime)
            update_anime(anime_id, complete=True)
            print(f"[COMPLETE] Download abgeschlossen für: '{series_title}'")
    input("\n[FERTIG] Alle Aufgaben abgeschlossen, drücke eine beliebige Taste zum Beenden.")

if __name__ == "__main__":
    main()
