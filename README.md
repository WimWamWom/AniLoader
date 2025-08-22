# AniWorld Downloader

Ein Python-Skript zum automatischen Herunterladen von Anime von https://aniworld.to/ mit Schwerpunkt auf deutsche Dub- oder Sub-Versionen. Das Skript verwaltet eine JSON-Datenbank, überprüft fehlende Episoden und benennt heruntergeladene Dateien automatisch um.

---

📦 Features

- Import von Anime-Links aus einer Textdatei (Anime.txt)
- Verwaltung des Download-Status in einer JSON-Datenbank (anime.json)
- Unterstützung mehrerer Sprachen: German Dub, German Sub, English Dub, English Sub
- Automatische Erkennung bereits heruntergeladener Episoden
- Löschen alter Untertitelversionen außer German Dub
- Sauberes Umbenennen von Episoden nach Staffel, Episode, Titel und Sprache
- Download von Staffeln und Filmen
- Option, nur fehlende deutsche Folgen zu prüfen und herunterzuladen

---

🗂 Dateistruktur

AniWorld-Downloader/<br/>
├─ Anime.txt<br/>
├─ anime.json<br/>
├─ Anime/<br/>
│  ├─ Serientitel/<br/>
│  │  ├─ S01E001 - Titel [Dub].mp4<br/>
│  │  ├─ S01E002 - Titel [Sub].mp4<br/>
│  │  └─ ...<br/>
├─ downloader.py<br/>
└─ README.md<br/>

---

⚙️ Installation

1. Repository klonen:

git clone https://github.com/dein-nutzername/aniworld-downloader.git
cd aniworld-downloader

2. Python-Abhängigkeiten installieren:

pip install requests beautifulsoup4

3. Download-Tool `aniworld` installieren. Stelle sicher, dass das CLI-Tool auf deinem System verfügbar ist.

---

📄 Anime-Liste erstellen

Die Datei Anime.txt enthält die Links zu den Anime-Serien, z. B.:

https://aniworld.to/serie/naruto
https://aniworld.to/serie/one-piece
https://aniworld.to/serie/attack-on-titan

Jede URL muss in einer neuen Zeile stehen.

---

🚀 Nutzung

### Alle Anime herunterladen

python downloader.py

- Lädt alle Filme und Staffeln herunter.
- Aktualisiert die JSON-Datenbank und markiert abgeschlossene Anime.

### Nur fehlende deutsche Folgen herunterladen

python downloader.py german

- Prüft nur Anime mit fehlenden deutschen Folgen (fehlende_deutsch_folgen) und lädt diese nach.

---

📝 Beispiele

### Beispiel JSON-Datenbank (anime.json)

[
    {
        "title": "Naruto",
        "url": "https://aniworld.to/serie/naruto",
        "complete": false,
        "deutsch_komplett": false,
        "fehlende_deutsch_folgen": [
            "https://aniworld.to/serie/naruto/staffel-1/episode-5"
        ]
    },
    {
        "title": "One Piece",
        "url": "https://aniworld.to/serie/one-piece",
        "complete": true,
        "deutsch_komplett": true,
        "fehlende_deutsch_folgen": []
    }
]

### Dateibenennung nach Download

S01E005 - Der Ninja-Test [Dub].mp4
S01E006 - Kampf der Klingen [Sub].mp4

---

⚠️ Hinweise

- Die URL-Struktur des Anime muss dem Format von AniWorld entsprechen:

https://aniworld.to/serie/<anime-name>/staffel-<n>/episode-<m>
https://aniworld.to/serie/<anime-name>/filme/film-<n>

- Alte Untertitelversionen (außer German Dub) werden automatisch gelöscht.
- Bei fehlenden Streams oder Sprachproblemen zeigt das Skript Warnungen an.

---

🔧 Anpassung

- DOWNLOAD_DIR: Ordner für die Downloads
- ANIME_TXT: Pfad zur Anime-Textdatei
- LANGUAGES: Reihenfolge und Sprachen, die beim Download versucht werden
- DB_PATH: Speicherort der JSON-Datenbank

---

📌 Lizenz

Dieses Projekt ist unter der MIT-Lizenz lizenziert.
