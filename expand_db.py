import os
import requests
from bs4 import BeautifulSoup
from pathlib import Path
import json
import re

# Konfiguration
BASE_DIR = Path(__file__).resolve().parent
ANIME_TXT = BASE_DIR / "Serien.txt"
DB_PATH = BASE_DIR / "serien.json"

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
        title = get_series_title(url)
        if url not in existing_urls:
            db.append({
                "title": title,                
                "url": url,
                "complete": False
            })

    save_db(db)

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


def main():
    init_db()
    import_anime_txt()

    print("\n[INFO] Alle Einträge der Datenbank hinzugefügt")

if __name__ == "__main__":  
    main()
