import os
import subprocess
import time

# Konfiguration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ANIME_TXT = os.path.join(BASE_DIR, "Anime.txt")
DOWNLOAD_DIR = os.path.join(BASE_DIR, "Anime")
LANGUAGES = ["German Dub", "German Sub", "English Dub", "English Sub"]

# ---------- Hilfsfunktionen ----------

def run_download(cmd):
    """Startet den Download und prüft auf Fehler"""
    try:
        process = subprocess.run(cmd, capture_output=True, text=True)
        output = process.stdout + process.stderr

        # Prüfen auf fehlende Streams
        if "No streams available for episode" in output:
            return "NO_STREAMS"

        # Prüfen auf fehlende Sprache → nächster Sprachversuch
        if "No provider found for language" in output:
            return "LANGUAGE_ERROR"

        # Erfolgreich abgeschlossen
        if process.returncode == 0:
            return "OK"

        return "FAILED"

    except Exception as e:
        print(f"[FEHLER] {e}")
        return "FAILED"


def download_episode(episode_url):
    """Versucht eine Episode oder einen Film in allen verfügbaren Sprachen herunterzuladen"""
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
    """Lädt alle Filme eines Animes herunter"""
    film_num = 1
    while True:
        film_url = f"{base_url}/filme/film-{film_num}"
        success = download_episode(film_url)
        if not success:
            print(f"[INFO] Keine weiteren Filme gefunden bei Film {film_num}.")
            break
        film_num += 1
        time.sleep(1)


def download_seasons(base_url):
    """Lädt alle Staffeln und Episoden herunter"""
    season = 1
    while True:
        episode = 1
        found_episode = False

        while True:
            episode_url = f"{base_url}/staffel-{season}/episode-{episode}"
            success = download_episode(episode_url)
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
    if not os.path.exists(ANIME_TXT):
        print(f"[FEHLER] Anime-Datei nicht gefunden: {ANIME_TXT}")
        return

    with open(ANIME_TXT, "r", encoding="utf-8") as file:
        anime_links = [line.strip() for line in file if line.strip()]

    for base_url in anime_links:
        anime_name = base_url.split("/")[-1]
        print(f"\n========== Starte Download für: {anime_name} ==========")

        # 1. Filme laden
        download_films(base_url)

        # 2. Staffeln laden
        download_seasons(base_url)

    print("\n[INFO] Alle Downloads abgeschlossen!")


if __name__ == "__main__":
    main()
