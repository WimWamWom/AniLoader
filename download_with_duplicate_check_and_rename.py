import os
import subprocess
import time
import requests
from bs4 import BeautifulSoup
from pathlib import Path
import re

# ------------------ Konfiguration ------------------

BASE_DIR = Path(__file__).resolve().parent
ANIME_TXT = BASE_DIR / "Download.txt"
DOWNLOAD_DIR = BASE_DIR / "Downloads"
LANGUAGES = ["German Dub", "German Sub", "English Dub", "English Sub"]

# ------------------ Hilfsfunktionen ------------------

def get_episode_title(url):
    """Holt den deutschen oder englischen Episodentitel."""
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


def get_series_title(base_url):
    """Holt den Serientitel von der Hauptseite."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(base_url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        title_tag = soup.find("div", class_="series-title").find("span")
        if title_tag and title_tag.text.strip():
            return sanitize_filename(title_tag.text.strip())
    except Exception as e:
        print(f"[FEHLER] Konnte Serien-Titel nicht abrufen ({base_url}): {e}")
    return None


def sanitize_filename(name):
    """Entfernt ungültige Zeichen für Dateinamen."""
    return re.sub(r'[<>:"/\\|?*]', ' ', name)


def episode_already_downloaded(series_folder, season, episode):
    """Prüft, ob Episode schon existiert."""
    if not os.path.exists(series_folder):
        return False

    pattern = f"S{season:02d}E{episode:03d}" if season > 0 else f"Film{episode:02d}"

    for file in Path(series_folder).rglob("*.mp4"):
        if pattern.lower() in file.name.lower():
            return True
    return False


def rename_downloaded_episode(series_folder, season, episode, title, language):
    """
    Benennt die heruntergeladene Episode oder den Film passend um.
    Aniworld speichert standardmäßig in:
    Episoden: Series - S01E001 - (German Dub)
    Filme: Series - Movie 001 - (German Dub)
    """
    try:
        # Sprache abkürzen
        lang_suffix = {
            "German Dub": "Dub",
            "German Sub": "Sub",
            "English Dub": "English Dub",
            "English Sub": "English Sub"
        }.get(language, "")

        # Originaldateiname suchen
        if season == 0:
            # Filme → Originaldateiname: "Series - Movie 001 - (German Dub).mp4"
            search_pattern = f"Movie {episode:03d}"
            new_filename = f"Film{episode:02d}"
        else:
            # Episoden → Originaldateiname: "Series - S01E001 - (German Dub).mp4"
            search_pattern = f"S{season:02d}E{episode:03d}"
            new_filename = f"S{season:02d}E{episode:03d}"

        # Neue Dateinamenstruktur
        safe_title = sanitize_filename(title) if title else ""
        if safe_title:
            new_filename += f" - {safe_title}"
        if lang_suffix:
            new_filename += f" [{lang_suffix}]"
        new_filename += ".mp4"

        # Suche die Originaldatei im Serienordner
        for file in Path(series_folder).glob("*.mp4"):
            if search_pattern in file.name:
                new_path = Path(series_folder) / new_filename
                os.rename(file, new_path)
                print(f"[OK] Umbenannt: {file.name} → {new_filename}")
                return True

        print(f"[WARN] Keine passende Datei gefunden für {search_pattern} in {series_folder}")
        return False

    except Exception as e:
        print(f"[FEHLER] Umbenennen fehlgeschlagen: {e}")
        return False


def run_download(cmd):
    """Startet den Download und prüft auf Fehler."""
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


def download_episode(series_title, episode_url, season, episode):
    """Lädt eine Episode herunter, wenn sie noch nicht existiert."""
    series_folder = os.path.join(DOWNLOAD_DIR, series_title)

    # Prüfen, ob schon vorhanden
    if episode_already_downloaded(series_folder, season, episode):
        if season == 0:
            print(f"[SKIP] Film {episode:02d} bereits vorhanden.")
        else:
            print(f"[SKIP] Episode S{season:02d}E{episode:03d} bereits vorhanden.")
        return True

    # Versuch in allen Sprachen
    for lang in LANGUAGES:
        cmd = ["aniworld", "--language", lang, "-o", DOWNLOAD_DIR, "--episode", episode_url]
        result = run_download(cmd)

        if result == "OK":
            title = get_episode_title(episode_url)
            if season == 0:
                print(f"[OK] {episode_url} ({lang}) → Film {episode:02d}")
            else:
                print(f"[OK] {episode_url} ({lang})")
            rename_downloaded_episode(series_folder, season, episode, title, lang)
            return True
        elif result == "LANGUAGE_ERROR":
            print(f"[WARN] {lang} nicht verfügbar → nächster Versuch...")
            continue
        elif result == "NO_STREAMS":
            return False
        else:
            print(f"[FEHLER] Konnte {episode_url} ({lang}) nicht laden.")
            return False

    return False


def download_films(series_title, base_url):
    film_num = 1
    while True:
        film_url = f"{base_url}/filme/film-{film_num}"
        success = download_episode(series_title, film_url, 0, film_num)
        if not success:
            print(f"[INFO] Keine weiteren Filme gefunden bei Film {film_num}.")
            break
        film_num += 1
        time.sleep(1)


def download_seasons(series_title, base_url):
    season = 1
    while True:
        episode = 1
        found_episode = False
        while True:
            episode_url = f"{base_url}/staffel-{season}/episode-{episode}"
            success = download_episode(series_title, episode_url, season, episode)
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


# ------------------ Hauptprogramm ------------------

def main():
    if not os.path.exists(ANIME_TXT):
        print(f"[FEHLER] Anime-Datei nicht gefunden: {ANIME_TXT}")
        return

    with open(ANIME_TXT, "r", encoding="utf-8") as file:
        anime_links = [line.strip() for line in file if line.strip()]

    for base_url in anime_links:
        series_title = get_series_title(base_url)
        if not series_title:
            print(f"[FEHLER] Serientitel konnte nicht ermittelt werden für: {base_url}")
            continue

        print(f"\n========== Starte Download für: {series_title} ==========")
        download_films(series_title, base_url)
        download_seasons(series_title, base_url)

    input("\n[INFO] Alle Downloads abgeschlossen!")


if __name__ == "__main__":
    main()
