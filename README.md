<h1 align="center"><sub><img src="web/static/AniLoader.png" width="35"></sub>AniLoader </h1>


  
  Anime & Serien Download-Manager mit Web-Interface
  Automatisches Herunterladen von aniworld.to und s.to mit Jellyfin-Struktur


  ---

  ## TL;DR 

  ```bash
  # Docker starten (empfohlen)
  docker run -d -p 5050:5050 -v ./data:/app/data -v ./Downloads:/app/Downloads wimwamwom/aniloader:latest

  # Web-Interface öffnen: http://localhost:5050
  # Serie hinzufügen → Download-Modus wählen → Fertig!
  ```

  **Das wars! AniLoader lädt Anime/Serien automatisch herunter, benennt sie für Jellyfin um und verwaltet alles über eine Web-Oberfläche.**

  ---

  ## Inhaltsübersicht

  - [Funktionen](#funktionen)
  - [Installation](#installation)
    - [Windows](#windows)
    - [Linux](#linux) 
    - [Docker](#docker)
    - [Unraid](#unraid)
  - [Verwendung](#verwendung)
    - [Web-Interface](#web-interface)
    - [API](#api)
    - [Tampermonkey](#tampermonkey)
  - [Konfiguration](#konfiguration)
  - [Datei-Struktur](#datei-struktur)
    - [Standard-Modus](#standard-modus)
    - [Separate-Modus](#separate-modus)
  - [FAQ](#faq)

  ---

  ## Funktionen

  - **🌐 Web-Interface:** Moderne Dark-Theme Oberfläche mit Live-Status  
  - **📥 4 Download-Modi:** Standard, German, New Episode Check, Integrity Check
  - **🔍 Suche + Poster:** Durchsuche Aniworld und SerieStream
  - **🇩🇪 Sprach-Priorität:** German Dub → Sub → English (automatischer Fallback)
  - **📁 Jellyfin-Ready:** `Title (Year) [IMDB]/Season/Episode.mkv`
  - **💾 Persistent:** SQLite-DB und Config überleben Container-Neustarts
  - **📄 AniLoader.txt Import:** Automatischer Import beim Container-Start
  - **💾 Export-Funktionen:** Datenbank + Links als Download exportieren
  - **🔓 Anti-Sperre:** DNS-over-HTTPS umgeht Provider-Blocks
  - **⚡ Autostart:** Optional bei Container-Start Download-Modus starten
  - **🐋 Docker-Ready:** Multi-Arch Images (amd64/arm64) mit Health-Checks

  ---

  ## Installation

  ### Windows
  ```powershell
  # Repository klonen
  git clone https://github.com/WimWamWom/AniLoader.git
  cd AniLoader

  # Virtual Environment
  python -m venv venv
  venv\Scripts\activate
  pip install -r requirements.txt

  # Starten
  python main.py
  ```
  **Voraussetzungen:** Python 3.11+, ffmpeg im PATH

  ### Linux
  ```bash
  # Repository klonen  
  git clone https://github.com/WimWamWom/AniLoader.git
  cd AniLoader

  # Dependencies + Virtual Environment
  sudo apt install python3 python3-venv ffmpeg -y
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt

  # Starten
  python main.py
  ```

  ### Docker
  ```yaml
  # docker-compose.yml
  services:
    aniloader:
      image: wimwamwom/aniloader:latest
      container_name: aniloader
      ports:
        - "5050:5050"
      volumes:
        - ./data:/app/data              # Config + DB
        - ./Downloads:/app/Downloads    # Standard-Modus  
        - ./Anime:/app/Anime           # Separate: aniworld.to
        - ./Serien:/app/Serien         # Separate: s.to
      environment:
        - TZ=Europe/Berlin
      restart: unless-stopped
  ```

  ```bash
  docker compose up -d
  ```

  ### Unraid
  **Template:** Community Apps → AniLoader  
  **Docker Hub:** `wimwamwom/aniloader:latest`

  **Port:** `5050:5050`  
  **Volumes:**
  - `/mnt/user/appdata/aniloader` → `/app/data`
  - `/mnt/user/data/media/Downloads` → `/app/Downloads`
  - `/mnt/user/data/media/Anime` → `/app/Anime`
  - `/mnt/user/data/media/Serien` → `/app/Serien`

  **WebUI:** `http://[IP]:5050`

  ---

  ## Verwendung

  ### Web-Interface
  **URL:** `http://localhost:5050`

  **📥 Download-Tab**
  - Download-Modi starten/stoppen
  - Live-Status: Aktuelle Serie, Episode, Fortschritt
  - Echtzeit-Logs des laufenden Downloads

  **📂 Hinzufügen-Tab**  
  - URLs einzeln eingeben
  - TXT-Datei hochladen (Drag & Drop)
  - Suche mit Poster-Vorschau

  **🗃️ Datenbank-Tab**
  - Alle Serien mit Status, Fortschritt, fehlendem DE-Content
  - Sortierung, Filter, Löschen/Wiederherstellen
  - **💾 Export DB:** Komplette SQLite-Datenbank herunterladen
  - **📄 Export Links:** Alle URLs als AniLoader.txt herunterladen

  **📜 Logs-Tab**
  - Echtzeit-Logs mit Filter-Funktionen 
  - Archivierte Logs nach Datum durchsuchen
  - Automatische Bereinigung nach konfigurierbaren Tagen

  **⚙️ Einstellungen-Tab**
  - Speicherpfade (Standard/Separate Mode)
  - Sprachpriorität per Drag & Drop  
  - Autostart, Titel-Refresh, System-Einstellungen

  ### API
  **Base URL:** `http://localhost:5050`  
  **Swagger Docs:** `/docs`

  ```bash
  # Status abrufen
  GET /status

  # Download starten
  POST /start_download
  {"mode": "default"}  # default, german, new, check

  # URL hinzufügen  
  POST /export
  {"url": "https://aniworld.to/anime/stream/naruto"}

  # Suchen
  POST /search  
  {"query": "attack on titan", "platform": "both"}  # aniworld, sto, both

  # Alle Serien
  GET /database?q=naruto&sort=title&dir=asc

  # Export-Funktionen
  GET /export/database     # SQLite-DB Download
  GET /export/links        # AniLoader.txt Download

  # Konfiguration
  GET /config
  POST /config
  ```

  ### Tampermonkey
  1. **Tampermonkey Extension** installieren
  2. **`Tampermonkey.user.js`** öffnen → Install
  3. **Server-Adresse anpassen** im Skript:
  ```javascript
  const SERVER_IP = "192.168.1.100";    // Deine AniLoader-IP
  const SERVER_PORT = 5050;
  ```
  4. **Fertig!** Button erscheint auf aniworld.to/s.to Seiten

  **Button-Status:**
  - 📤 Downloaden → Serie hinzufügen
  - 📄 In Liste → Wartet auf Download  
  - ⬇️ Lädt... → Download aktiv
  - ✅ Komplett → Alle Episoden da

  ---

  ## Konfiguration

  **Datei:** `data/config.yaml` (wird automatisch erstellt)

  ```yaml
  server:
    port: 5050

  languages:                    # Priorität: Erste verfügbare wird verwendet
    - German Dub               # 1. Priorität
    - German Sub               # 2. Priorität  
    - English Sub              # 3. Priorität
    - English Dub              # 4. Priorität

  storage:
    mode: standard             # standard | separate
    download_path: /app/Downloads
    anime_path: /app/Anime     # Nur bei separate mode
    series_path: /app/Serien   # Nur bei separate mode

  download:
    autostart_mode: null       # null, default, german, new, check
    refresh_titles: false      # Titel beim Start von Webseiten aktualisieren
    min_free_gb: 2.0          # Mindest freier Speicher
    timeout_seconds: 900       # Timeout pro Episode
  ```

  **Download-Modi:**
  - **default:** Lädt alle unvollständigen Serien
  - **german:** Sucht fehlende deutsche Episoden  
  - **new:** Prüft alle Serien auf neue Episoden
  - **check:** Integritätsprüfung + defekte Downloads reparieren

  ---

  ## Datei-Struktur

  ### Standard-Modus
  **Ein Ordner für alles** (`storage.mode: standard`)

  ```
  Downloads/
  ├── Naruto (2002) [imdbid-tt0409591]/
  │   ├── Season 01/
  │   │   ├── S01E001 - Erste Episode.mkv
  │   │   ├── S01E002 - Zweite Episode [Sub].mkv    # German Sub
  │   │   └── S01E003 - Episode 3 [English].mkv    # English Dub
  │   ├── Season 02/
  │   └── Filme/
  │       └── Film01 - Naruto Movie.mkv
  ├── Breaking Bad (2008) [imdbid-tt0903747]/  
  │   ├── Season 01/
  │   └── Season 02/
  └── Avatar (2009) [imdbid-tt0499549]/
      └── Filme/
          └── Film01 - Avatar.mkv
  ```

  ### Separate-Modus  
  **Getrennte Ordner** (`storage.mode: separate`)

  ```
  Anime/                        # aniworld.to Content
  ├── Naruto (2002)/
  │   ├── Season 01/
  │   ├── Season 02/ 
  │   └── Filme/
  └── Attack on Titan (2013)/
      ├── Season 01/
      └── Season 02/

  Serien/                       # s.to Content  
  ├── Breaking Bad (2008)/
  │   ├── Season 01/
  │   └── Season 02/
  └── Game of Thrones (2011)/
      ├── Season 01/
      └── Season 08/
  ```

  **Datei-Benennung:**
  - **Serien:** `S01E001 - Titel.mkv`, `S01E002 - Titel [Sub].mkv`
  - **Filme:** `Film01 - Titel.mkv`, `Film02 - Titel [Sub].mkv`  
  - **Suffixe:** `""` (German Dub), `[Sub]` (German Sub), `[English Dub]`, `[English Sub]`

  ---

  ## FAQ

  **Q: Downloads funktionieren nicht / Timeouts**  
  A: ffmpeg installiert? Python 3.11+? Genug Speicherplatz? Logs im Download-Tab prüfen

  **Q: "DNS-Fehler" oder Seiten nicht erreichbar**  
  A: AniLoader nutzt DNS-over-HTTPS automatisch. Firewall für ausgehende HTTPS-Verbindungen prüfen

  **Q: Tampermonkey zeigt "Server offline"**  
  A: Server-IP im Skript korrekt? AniLoader läuft? Browser-Konsole (F12) für Details prüfen

  **Q: Autostart beim Docker-Start aktivieren**  
  A: `config.yaml` → `autostart_mode: default` oder in Web-UI Einstellungen ändern

  **Q: AniLoader.txt Import wie im alten AniLoader?**  
  A: Links in `AniLoader.txt` (Hauptordner) → beim Start automatisch importiert + Datei geleert

  **Q: Datenbank/Links exportieren?**  
  A: Datenbank-Tab → "💾 Export DB" (SQLite-Datei) oder "📄 Export Links" (AniLoader.txt)

  **Q: Separate vs Standard Mode?**  
  A: **Standard** = Alles in Downloads. **Separate** = Anime/Serien getrennt für bessere Jellyfin-Organisation

  **Q: Welche Sprache wird heruntergeladen?**  
  A: Erste verfügbare aus der `languages`-Liste. Kaskade: German Dub → German Sub → English Sub → English Dub

  ---

  <p align="center">
    <img src="web/static/AniLoader.png" alt="AniLoader" width="60"><br>
    <sub>Made with ❤️ for Anime & Serien</sub>
  </p>
