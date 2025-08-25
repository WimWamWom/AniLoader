import sqlite3
import json
from pathlib import Path

# Pfad zur Datenbankdatei
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "download.db"

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
    
def insert_or_update_anime():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Werte definieren
    title = "Nicht nachmachen!"
    url = "https://s.to/serie/stream/nicht-nachmachen"
    complete = 0
    deutsch_komplett = 0
    fehlende_deutsch_folgen = json.dumps([])  # als JSON-String speichern
    last_film = 0
    last_episode = 0
    last_season = 0

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
    init_db()  # Tabelle erstellen, falls sie nicht existiert


