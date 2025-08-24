import sqlite3
import json
from pathlib import Path

# Pfad zur Datenbankdatei
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "download.db"


def insert_or_update_anime():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Werte definieren
    title = "Rascal Does Not Dream of Bunny Girl Senpai"
    url = "https://aniworld.to/anime/stream/rascal-does-not-dream-of-bunny-girl-senpai"
    complete = 1
    deutsch_komplett = 0
    fehlende_deutsch_folgen = json.dumps(["https://aniworld.to/anime/stream/rascal-does-not-dream-of-bunny-girl-senpai/staffel-1/episode-13","https://aniworld.to/anime/stream/rascal-does-not-dream-of-bunny-girl-senpai/staffel-2/episode-1", "https://aniworld.to/anime/stream/rascal-does-not-dream-of-bunny-girl-senpai/staffel-2/episode-2", "https://aniworld.to/anime/stream/rascal-does-not-dream-of-bunny-girl-senpai/staffel-2/episode-3", "https://aniworld.to/anime/stream/rascal-does-not-dream-of-bunny-girl-senpai/staffel-2/episode-4", "https://aniworld.to/anime/stream/rascal-does-not-dream-of-bunny-girl-senpai/staffel-2/episode-5", "https://aniworld.to/anime/stream/rascal-does-not-dream-of-bunny-girl-senpai/staffel-2/episode-6", "https://aniworld.to/anime/stream/rascal-does-not-dream-of-bunny-girl-senpai/staffel-2/episode-7", "https://aniworld.to/anime/stream/rascal-does-not-dream-of-bunny-girl-senpai/staffel-2/episode-8"])  # als JSON-String speichern
    last_film = 3
    last_episode = 8
    last_season = 1

    # Insert oder Update bei vorhandenem url (wegen UNIQUE constraint)
    c.execute("""
        INSERT INTO anime (title, url, complete, deutsch_komplett, fehlende_deutsch_folgen, last_film, last_episode, last_season)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(url) DO UPDATE SET
            title=excluded.title,
            complete=excluded.complete,
            deutsch_komplett=excluded.deutsch_komplett,
            fehlende_deutsch_folgen=excluded.fehlende_deutsch_folgen,
            last_film=excluded.last_film,
            last_episode=excluded.last_episode,
            last_season=excluded.last_season
    """, (title, url, complete, deutsch_komplett, fehlende_deutsch_folgen, last_film, last_episode, last_season))

    conn.commit()
    conn.close()
    print("Eintrag wurde erfolgreich hinzugefügt oder aktualisiert.")

if __name__ == "__main__":
    insert_or_update_anime()
