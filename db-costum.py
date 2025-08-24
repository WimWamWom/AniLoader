import sqlite3
import json

# Pfad zur Datenbankdatei
DB_PATH = r"C:\Users\Wim\Desktop\AniLoader\anime.db"

def insert_or_update_anime():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Werte definieren
    title = "SOKO Wismar"
    url = "https://s.to/serie/stream/soko-wismar"
    complete = 0
    deutsch_komplett = 0
    fehlende_deutsch_folgen = json.dumps([])  # als JSON-String speichern
    last_film = 0
    last_episode = 26
    last_season = 16

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
