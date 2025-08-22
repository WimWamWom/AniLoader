import os
import subprocess
import time
import requests
from bs4 import BeautifulSoup
from pathlib import Path
import re
import json

# Konfiguration
BASE_DIR = Path(__file__).resolve().parent
ANIME_TXT = BASE_DIR / "Anime.txt"
DOWNLOAD_DIR = BASE_DIR / "Anime"
DB_PATH = BASE_DIR / "anime.json"
LANGUAGES = ["German Dub", "German Sub", "English Dub", "English Sub"]

# ---------- JSON-Datenbankfunktionen ----------

def init_db():
    """Initialisiert die JSON-Datenbank, falls sie nicht existiert"""
    if not DB_PATH.exists():
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump([], f, indent=4, ensure_ascii=False)

def load_db():
    """Lädt die JSON-Datenbank"""
    with open(DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_db(data):
    """Speichert die JSON-Datenbank"""
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def import_anime_txt():
    """Importiert Anime-Links aus der TXT-Datei in die JSON-Datenbank"""
    if not os.path.exists(ANIME_TXT):
        print(f"[FEHLER] Anime-Datei nicht gefunden: {ANIME_TXT}")
        return

    with open(ANIME_TXT, "r", encoding="utf-8") as file:
        anime_links = [line.strip() for line in file if line.strip()]

    db = load_db()
    existing_urls = {entry["url"] for entry in db}

    for url in anime_links:
        if url not in existing_urls:
            db.append({
                "url": url,
                "title": None,
                "complete": False
            })

    save_db(db)

def get_pending_anime():
    """Gibt alle Anime zurück, die noch nicht abgeschlossen sind"""
    db = load_db()
    return [(idx, entry["url"]) for idx, entry in enumerate(db) if not entry.get("complete", False)]

def mark_anime_complete(anime_id):
    """Setzt das complete-Flag auf True"""
    db = load_db()
    if 0 <= anime_id < len(db):
        db[anime_id]["complete"] = True
    save_db(db)

# ---------- Hilfsfunktionen ----------

def get_episode_title(url):
    """Holt den Episodentitel"""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

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
    """Holt den Serientitel für den Ordnernamen"""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        series_title = soup.select_one("div.series-title h1 span")
        if series_title and series_title.text.strip():
            return sanitize_filename(series_title.text.strip())

    except Exception as e:
        print(f"[FEHLER] Konnte Serien-Titel nicht abrufen ({url}): {e}")
    return None

def sanitize_filename(name):
    """Ersetzt unerlaubte Zeichen im Dateinamen"""
    return re.sub(r'[<>:"/\\|?*]', ' ', name)

def get_latest_subfolder(base_dir):
    subfolders = [f for f in Path(base_dir).iterdir() if f.is_dir()]
    if not subfolders:
        return None
    return str(max(subfolders, key=os.path.getmtime))

def get_latest_mp4(folder):
    mp4_files = list(Path(folder).glob("*.mp4"))
    if not mp4_files:
        return None
    return str(max(mp4_files, key=os.path.getmtime))

def episode_already_downloaded(series_folder, season, episode):
    """Prüft, ob Episode bereits vorhanden ist"""
    if not os.path.exists(series_folder):
        return False
    pattern = f"S{season:02d}E{episode:03d}"
    for root, dirs, files in os.walk(series_folder):
        for file in files:
            if file.lower().endswith(".mp4") and pattern.lower() in file.lower():
                return True
    return False

def rename_latest_episode(season, episode, title, language):
    latest_folder = get_latest_subfolder(DOWNLOAD_DIR)
    if not latest_folder:
        print(f"[FEHLER] Kein Unterordner gefunden.")
        return False

    latest_mp4 = get_latest_mp4(latest_folder)
    if not latest_mp4:
        print(f"[FEHLER] Keine MP4-Datei in {latest_folder} gefunden.")
        return False

    safe_title = sanitize_filename(title) if title else ""

    if language == "German Dub":
        lang_suffix = "Dub"
    elif language == "German Sub":
        lang_suffix = "Sub"
    elif language == "English Sub":
        lang_suffix = "English Sub"
    else:
        lang_suffix = ""

    new_name = f"S{season:02d}E{episode:03d}"
    if safe_title:
        new_name += f" - {safe_title}"
    if lang_suffix:
        new_name += f" [{lang_suffix}]"
    new_name += ".mp4"

    new_path = os.path.join(latest_folder, new_name)

    try:
        os.rename(latest_mp4, new_path)
        print(f"[OK] Umbenannt in: {new_name}")
        return True
    except Exception as e:
        print(f"[FEHLER] Konnte Datei nicht umbenennen: {e}")
        return False

def run_download(cmd):
    try:
        process = subprocess.run(cmd, capture_output=True, text=True)
        output = process.stdout + process.stderr

        if "No streams available for episode" in output:
            return "NO_STREAMS"
        if "No provider found for language" in output:
            return "LANGUAGE_ERROR"
        if process.returncode == 0:
            return "OK"
        return "FAILED"

    except Exception as e:
        print(f"[FEHLER] {e}")
        return "FAILED"

def download_episode(episode_url, season, episode):
    series_title = get_series_title(episode_url)
    if not series_title:
        print(f"[FEHLER] Serienordner konnte nicht ermittelt werden.")
        return False

    series_folder = os.path.join(DOWNLOAD_DIR, series_title)

    if episode_already_downloaded(series_folder, season, episode):
        print(f"[SKIP] Episode S{season:02d}E{episode:03d} bereits vorhanden.")
        return True

    for lang in LANGUAGES:
        cmd = [
            "aniworld",
            "--language", lang,
            "-o", DOWNLOAD_DIR,
            "--episode", episode_url
        ]
        result = run_download(cmd)

        if result == "OK":
            print(f"[OK] {episode_url} ({lang})")
            title = get_episode_title(episode_url)
            if title:
                rename_latest_episode(season, episode, title, lang)
            else:
                print(f"[WARN] Kein Titel gefunden. Umbenennen übersprungen.")
            return True

        elif result == "LANGUAGE_ERROR":
            print(f"[WARN] {lang} nicht verfügbar → nächster Sprachversuch…")
            continue

        elif result == "NO_STREAMS":
            return False

        else:
            print(f"[FEHLER] Konnte {episode_url} ({lang}) nicht laden.")
            return False

    return False

def download_films(base_url):
    film_num = 1
    while True:
        film_url = f"{base_url}/filme/film-{film_num}"
        success = download_episode(film_url, 0, film_num)
        if not success:
            print(f"[INFO] Keine weiteren Filme gefunden bei Film {film_num}.")
            break
        film_num += 1
        time.sleep(1)

def download_seasons(base_url):
    season = 1
    while True:
        episode = 1
        found_episode = False

        while True:
            episode_url = f"{base_url}/staffel-{season}/episode-{episode}"
            success = download_episode(episode_url, season, episode)
            if not success:
                if episode == 1:
                    print(f"[INFO] Staffel {season} existiert nicht. Anime abgeschlossen.")
                    return
                else:
                    print(f"[INFO] Staffel {season} beendet nach {episode-1} Episoden.")
                    break

            found_episode = True
            episode += 1
            time.sleep(1)

        if not found_episode:
            return
        season += 1

# ---------- Hauptprogramm ----------

def main():
    init_db()
    import_anime_txt()
    pending_anime = get_pending_anime()

    for anime_id, base_url in pending_anime:
        anime_name = base_url.split("/")[-1]
        print(f"\n========== Starte Download für: {anime_name} ==========")
        download_films(base_url)
        download_seasons(base_url)
        mark_anime_complete(anime_id)

    print("\n[INFO] Alle Downloads abgeschlossen!")

if __name__ == "__main__":
    main()
