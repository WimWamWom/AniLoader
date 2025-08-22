import os
import subprocess
import time
import requests
from bs4 import BeautifulSoup
from pathlib import Path
import re
import json
import sys

# Konfiguration
BASE_DIR = Path(__file__).resolve().parent
ANIME_TXT = BASE_DIR / "Anime.txt"
DOWNLOAD_DIR = BASE_DIR / "Anime"
DB_PATH = BASE_DIR / "anime.json"
LANGUAGES = ["German Dub", "German Sub", "English Dub", "English Sub"]

# ---------- JSON-Datenbankfunktionen ----------

def init_db():
    if not DB_PATH.exists():
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump([], f, indent=4, ensure_ascii=False)

def load_db():
    with open(DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_db(data):
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def import_anime_txt():
    if not os.path.exists(ANIME_TXT):
        print(f"[FEHLER] Anime-Datei nicht gefunden: {ANIME_TXT}")
        return
    with open(ANIME_TXT, "r", encoding="utf-8") as file:
        anime_links = [line.strip() for line in file if line.strip()]

    db = load_db()
    existing_urls = {entry["url"] for entry in db}

    for url in anime_links:
        title = get_episode_title(url)
        if url not in existing_urls:
            db.append({
                "title": title,
                "url": url,
                "complete": False,
                "deutsch_komplett": False,
                "fehlende_deutsch_folgen": []
            })
    save_db(db)

def get_pending_anime():
    db = load_db()
    return [(idx, entry["url"]) for idx, entry in enumerate(db) if not entry.get("complete", False)]

def update_anime(anime_id, fehlende=None):
    db = load_db()
    if 0 <= anime_id < len(db):
        if fehlende is not None:
            db[anime_id]["fehlende_deutsch_folgen"] = fehlende
            db[anime_id]["deutsch_komplett"] = len(fehlende) == 0
    save_db(db)

def mark_anime_complete(anime_id):
    db = load_db()
    if 0 <= anime_id < len(db):
        db[anime_id]["complete"] = True
    save_db(db)

# ---------- Hilfsfunktionen ----------

def get_episode_title(url):
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
    if not os.path.exists(series_folder):
        return False
    pattern = f"S{season:02d}E{episode:03d}"
    for root, dirs, files in os.walk(series_folder):
        for file in files:
            if file.lower().endswith(".mp4") and pattern.lower() in file.lower():
                return True
    return False

def delete_old_subtitle_versions(series_folder, season, episode):
    """Löscht alle Untertitelversionen außer German Dub"""
    if not os.path.exists(series_folder):
        return
    pattern = f"S{season:02d}E{episode:03d}"
    for root, dirs, files in os.walk(series_folder):
        for file in files:
            if file.lower().endswith(".mp4") and pattern.lower() in file.lower():
                if "dub" not in file.lower():  # alles außer German Dub löschen
                    try:
                        os.remove(os.path.join(root, file))
                        print(f"[INFO] Alte Untertitel-Version gelöscht: {file}")
                    except:
                        pass

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
    lang_suffix = ""
    if language == "German Dub": lang_suffix = "Dub"
    elif language == "German Sub": lang_suffix = "Sub"
    elif language == "English Sub": lang_suffix = "English Sub"

    new_name = f"S{season:02d}E{episode:03d}"
    if safe_title: new_name += f" - {safe_title}"
    if lang_suffix: new_name += f" [{lang_suffix}]"
    new_name += ".mp4"

    new_path = os.path.join(latest_folder, new_name)

    try:
        os.rename(latest_mp4, new_path)
        print(f"[OK] Umbenannt in: {new_name}")
        if language == "German Dub":
            series_folder = os.path.join(DOWNLOAD_DIR, get_series_title(latest_mp4))
            delete_old_subtitle_versions(latest_folder, season, episode)
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

def download_episode(episode_url, season, episode, anime_id, german_only=False):
    series_title = get_series_title(episode_url)
    if not series_title:
        print(f"[FEHLER] Serienordner konnte nicht ermittelt werden.")
        return False
    series_folder = os.path.join(DOWNLOAD_DIR, series_title)
    if episode_already_downloaded(series_folder, season, episode):
        print(f"[SKIP] Episode S{season:02d}E{episode:03d} bereits vorhanden.")
        return True

    langs_to_try = ["German Dub"] if german_only else LANGUAGES
    for lang in langs_to_try:
        cmd = ["aniworld", "--language", lang, "-o", DOWNLOAD_DIR, "--episode", episode_url]
        result = run_download(cmd)
        db = load_db()
        fehlende = db[anime_id]["fehlende_deutsch_folgen"]

        if result == "OK":
            print(f"[OK] {episode_url} ({lang})")
            title = get_episode_title(episode_url)
            if title:
                rename_latest_episode(season, episode, title, lang)
            if episode_url in fehlende:
                fehlende.remove(episode_url)
                update_anime(anime_id, fehlende)
            return True

        elif result == "LANGUAGE_ERROR" and not german_only:
            print(f"[WARN] {lang} nicht verfügbar → nächster Sprachversuch…")
            continue

        elif result == "NO_STREAMS":
            if lang.startswith("German") and not german_only:
                if episode_url not in fehlende:
                    fehlende.append(episode_url)
                    update_anime(anime_id, fehlende)
            return False

        else:
            print(f"[FEHLER] Konnte {episode_url} ({lang}) nicht laden.")
            return False
    return False

def download_films(base_url, anime_id, german_only=False):
    film_num = 1
    while True:
        film_url = f"{base_url}/filme/film-{film_num}"
        success = download_episode(film_url, 0, film_num, anime_id, german_only)
        if not success:
            print(f"[INFO] Keine weiteren Filme gefunden bei Film {film_num}.")
            break
        film_num += 1
        time.sleep(1)

def download_seasons(base_url, anime_id, german_only=False):
    season = 1
    while True:
        episode = 1
        found_episode = False
        while True:
            episode_url = f"{base_url}/staffel-{season}/episode-{episode}"
            success = download_episode(episode_url, season, episode, anime_id, german_only)
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
    db = load_db()

    german_mode = len(sys.argv) > 1 and sys.argv[1].lower() == "german"

    if german_mode:
        # Nur Anime mit fehlenden deutschen Folgen prüfen
        pending = [(idx, entry["url"]) for idx, entry in enumerate(db) if entry["fehlende_deutsch_folgen"]]
    else:
        # Alle Anime normal durchlaufen
        pending = [(idx, entry["url"]) for idx, entry in enumerate(db)]

    for anime_id, base_url in pending:
        series_title = get_series_title(base_url)
        print(f"\n========== Starte Download für: {series_title} ==========")

        if german_mode:
            fehlende = db[anime_id]["fehlende_deutsch_folgen"]
            if not fehlende:
                print(f"[INFO] Keine fehlenden deutschen Folgen für {series_title}.")
                continue
            for url in fehlende.copy():
                print(f"[CHECK] Prüfe deutsche Verfügbarkeit: {url}")
                download_episode(url, 0, 0, anime_id, german_only=True)
        else:
            download_films(base_url, anime_id)
            download_seasons(base_url, anime_id)
            mark_anime_complete(anime_id)

    print("\n[INFO] Alle Downloads abgeschlossen!")

if __name__ == "__main__":
    main()
