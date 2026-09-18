<h1 align="center"><sub><img src="web/static/AniLoader.png" width="35"></sub>AniLoader v1</h1>


  
  Anime & Serien Download-Manager mit Web-Interface. 
  Automatisches Herunterladen von aniworld.to und serienstream.to mit Jellyfin-Struktur </br>
  Basiert auf dem [AniWorld-Downloader](https://github.com/phoenixthrush/AniWorld-Downloader) Tool von [phoenixthrush](https://github.com/phoenixthrush) 🍻

![Python](https://img.shields.io/badge/python-3.11+-blue?logo=python)
![GitHub Issues or Pull Requests](https://img.shields.io/github/issues/wimwamwom/AniLoader)
![GitHub Issues or Pull Requests](https://img.shields.io/github/issues-pr/wimwamwom/AniLoader)
![Docker Pulls](https://img.shields.io/docker/pulls/wimwamwom/aniloader)
![GitHub License](https://img.shields.io/github/license/wimwamwom/aniloader)
![GitHub Release](https://img.shields.io/github/v/release/wimwamwom/aniloader)
![GitHub Repo stars](https://img.shields.io/github/stars/wimwamwom/aniloader)
![GitHub forks](https://img.shields.io/github/forks/wimwamwom/aniloader)


  ---

  ## TL;DR 

  **1. Docker (empfohlen)**
  ```bash
  docker run -d -p 5050:5050 -v ./data:/app/data -v ./Downloads:/app/Downloads wimwamwom/aniloader:latest
  ```

  **2. Lokal**
  ```bash
  git clone https://github.com/WimWamWom/AniLoader.git
  cd AniLoader
  pip install -r requirements.txt
  python main.py
  ```

  **Web-Interface:** `http://localhost:5050` → Serie hinzufügen → Download starten → Fertig!

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
  - [Domains & Mirrors](#domains--mirrors)
  - [Mehrere Sprachen pro Serie](#mehrere-sprachen-pro-serie)
  - [Automation](#automation)
  - [Datei-Struktur](#datei-struktur)
    - [Standard-Modus](#standard-modus)
    - [Separate-Modus](#separate-modus)
  - [FAQ](#faq)

  ---

  ## Funktionen

  - **🌐 Web-Interface:** Moderne Dark-Theme Oberfläche mit Live-Status  
  - **📥 5 Download-Modi:** Default, German, New Episode Check, German+New, Integrity Check
  - **🤖 Automation:** Geplante Läufe per Cron-Schedule oder Intervall mit Discord-Benachrichtigungen
  - **🔍 Suche + Poster:** Durchsuche Aniworld und SerieStream
  - **🇩🇪 Sprach-Priorität:** German Dub → Sub → English (automatischer Fallback)
  - **🌍 Mehrsprach-Download:** Pro Serie mehrere Sprachen gleichzeitig pflegen (Datenbank-Tab → Spalte *Sprachen*) – jede Sprache landet als eigene Datei, sequenziell geladen (kein Merging durch aniworld)
  - **📁 Jellyfin-Ready:** `Title (Year) [IMDB]/Season/Episode.mkv`
  - **💾 Persistent:** SQLite-DB und Config überleben Container-Neustarts
  - **📄 AniLoader.txt Import:** Automatischer Import beim Container-Start
  - **💾 Export-Funktionen:** Datenbank + Links als Download exportieren
  - **🔓 Anti-Sperre:** DNS-over-HTTPS umgeht Provider-Blocks
  - **⚡ Autostart:** Optional bei Container-Start Download-Modus starten
  - **📂 Separate Filmpfade:** Anime-Filme und Serien-Filme in eigene Ordner (Separate-Modus)
  - **🎬 Film-Benennung:** Umschaltbar zwischen Lokal (`Film01`) und Jellyfin (`S00E001`) – mit automatischer Migration aller vorhandenen Dateien
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

  > **Image verfügbar auf:** Docker Hub `wimwamwom/aniloader:latest` · GHCR `ghcr.io/wimwamwom/aniloader:latest`

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
        - ./Serien:/app/Serien         # Separate: serienstream.to
        - ./Anime-Filme:/app/Anime-Filme   # Separate: Anime-Filme
        - ./Serien-Filme:/app/Serien-Filme # Separate: Serien-Filme
      environment:
        - TZ=Europe/Berlin
      restart: unless-stopped
  ```

  ```bash
  docker compose up -d
  ```

  ### Unraid
  **Docker Hub:** `wimwamwom/aniloader:latest`

  **Port:** `5050:5050`  
  **Volumes:**
  - `/mnt/user/appdata/aniloader` → `/app/data`
  - `/mnt/user/data/media/Downloads` → `/app/Downloads`
  - `/mnt/user/data/media/Anime` → `/app/Anime`
  - `/mnt/user/data/media/Serien` → `/app/Serien`
  - `/mnt/user/data/media/Anime-Filme` → `/app/Anime-Filme`
  - `/mnt/user/data/media/Serien-Filme` → `/app/Serien-Filme`

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

  **🤖 Automation-Tab**
  - Cron-Schedules oder Intervall-basierte Läufe konfigurieren
  - Modi: `german`, `new`, `german_new`
  - Discord-Webhook für Benachrichtigungen pro Modus
  - Whitelist/Blacklist-Filter pro Modus
  - Lauf-Historie einsehen und Läufe manuell triggern

  **⚙️ Einstellungen-Tab**
  - Speicherpfade (Standard/Separate Mode) mit Ordner-Browser
  - Separate Filmpfade für Anime-Filme und Serien-Filme
  - **Film-Benennung:** Lokal (`Film01 - Titel.mkv`) oder Jellyfin (`S00E001 - Titel.mkv`) wählbar; bei Modusänderung erscheint ein Button zum automatischen Umbenennen aller vorhandenen Dateien
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
  {"mode": "default"}  # default, german, new, check, german_new

  # Download stoppen
  POST /stop_download

  # URL hinzufügen  
  POST /add_link
  {"url": "https://aniworld.to/anime/stream/naruto"}

  # Suchen
  POST /search  
  {"query": "attack on titan", "platform": "both"}  # aniworld, sto, both

  # Alle Serien
  GET /database?q=naruto&sort=title&dir=asc

  # Datenbank-Statistiken
  GET /database/stats

  # Serien-Eintrag aktualisieren / löschen / wiederherstellen
  PUT    /anime/{id}
  DELETE /anime/{id}?hard=false
  POST   /anime/{id}/restore

  # TXT-Datei importieren
  POST /upload_txt

  # Export-Funktionen
  GET /export/database     # SQLite-DB Download
  GET /export/links        # AniLoader.txt Download

  # Gewünschte Sprachen eines Eintrags (Mehrsprach-Download)
  GET /anime/{id}/languages
  PUT /anime/{id}/languages
  {"languages": ["German Dub", "English Sub"],
   "delete_files": true,    # optional: Dateien entfernter Sprachen löschen (Standard: true)
   "dry_run": false}        # optional: nur anzeigen, was gelöscht würde

  # Titel aktualisieren (aus Webseiten)
  POST /refresh_titles

  # Konfiguration
  GET  /config
  POST /config

  # Speicherplatz-Info
  GET /disk

  # Ordner-Browser (für Pfad-Auswahl)
  POST /browse
  {"path": "/app"}

  # Film-Benennung migrieren (umbenennen + verschieben aller Film-Dateien)
  POST /migrate_film_naming
  {"target_mode": "jellyfin"}  # jellyfin | local

  # Poster-URL abrufen
  GET /poster?url=https://aniworld.to/anime/stream/naruto

  # Automation
  GET  /automation/status
  POST /automation/trigger/{mode}   # german | new | german_new
  GET  /automation/history
  ```

  ### Tampermonkey
  1. **Tampermonkey Extension** installieren
  2. **`Tampermonkey.user.js`** öffnen → Install
  3. **Server-Adresse anpassen** im Skript:
  ```javascript
  const USE_DOMAIN = false;
  const SERVER_IP = "192.168.1.100";    // Deine AniLoader-IP
  const SERVER_PORT = 5050;
  ```
  4. **Fertig!** Button erscheint auf aniworld.to/serienstream.to Seiten

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

  domains:                      # Domains der Plattformen – siehe "Domains & Mirrors"
    aniworld:
      canonical: aniworld.to
      aliases: []
    serienstream:
      canonical: serienstream.to  # einzige Domain, die gespeichert/ausgegeben wird
      aliases:                    # nur als Eingabe akzeptiert, werden normalisiert
        - serienstream.cx
        - 186.2.175.5
        - s.to

  storage:
    mode: standard             # standard | separate
    download_path: /app/Downloads
    anime_path: /app/Anime               # Nur bei separate mode
    series_path: /app/Serien             # Nur bei separate mode
    anime_movies_path: /app/Anime-Filme  # Nur bei separate mode + anime_separate_movies: true
    serien_movies_path: /app/Serien-Filme # Nur bei separate mode + serien_separate_movies: true
    anime_separate_movies: false          # Anime-Filme in eigenen Ordner
    serien_separate_movies: false         # Serien-Filme in eigenen Ordner
    film_naming_mode: local               # local | jellyfin
    # ⚠ Der finale Ordnername (letztes Pfadsegment) darf nicht mit '.' beginnen.
    #   Erlaubt:  /app/Downloads  oder  /mnt/.cache/Downloads
    #   Verboten: /app/.Downloads

  download:
    autostart_mode: null       # null, default, german, new, check, german_new
    refresh_titles: false      # Titel beim Start von Webseiten aktualisieren
    min_free_gb: 2.0           # Mindest freier Speicher in GB
    timeout_seconds: 900       # Timeout pro Episode in Sekunden

  logging:
    log_retention_days: 7      # Logs nach X Tagen automatisch löschen
  ```

  **Download-Modi:**
  - **default:** Lädt alle unvollständigen Serien
  - **german:** Sucht fehlende deutsche Episoden  
  - **new:** Prüft alle Serien auf neue Episoden
  - **german_new:** Kombiniert german + new in einem Lauf
  - **check:** Integritätsprüfung + defekte Downloads reparieren

  ---

  ## Domains & Mirrors

  aniworld.to und serienstream.to ziehen regelmäßig um. Alle Domains stehen deshalb
  an **einer** Stelle – im Abschnitt `domains:` der `config.yaml`. Ein Umzug ist damit
  eine Konfigurationsänderung, kein Code-Eingriff.

  ```yaml
  domains:
    serienstream:
      canonical: serienstream.to    # wird gespeichert und ausgegeben
      aliases:                      # werden nur erkannt und normalisiert
        - serienstream.cx
        - 186.2.175.5
        - s.to
  ```

  **Regeln:**
  - `canonical` ist die **einzige** Domain, die je in der Datenbank landet oder nach
    außen geht. `s.to` erscheint dadurch nirgends mehr.
  - `aliases` werden ausschließlich als **Eingabe** akzeptiert (alte Lesezeichen,
    Mirrors, IP-Adresse) und sofort auf `canonical` umgeschrieben.
  - Werte sind reine Hosts – ohne `https://` und ohne `/`.

  **Neue Mirror-Domain hinzufügen:**
  1. Domain unter `aliases` eintragen (Einstellungen → oder direkt in `config.yaml`)
  2. Im `Tampermonkey.user.js` dieselbe Domain in `PLATFORMS` **und** als
     `// @match https://<domain>/*` ergänzen
  3. Speichern – AniLoader lädt die Domainliste sofort neu, kein Neustart nötig

  > ⚠️ **Die `aniworld`-Library bringt ihre eigene Domainliste mit**
  > (`aniworld/config.py` → `_STO_HOST`, `aniworld/cf_bypass.py` → `_CF_BYPASS_DOMAINS`).
  > Sie kennt aktuell `serienstream.to`, `serienstream.cx`, `s.to` und `186.2.175.5`,
  > der Cloudflare-Bypass greift aber nur für `serienstream.to` und `s.to`.
  > Eine hier ergänzte, der Library **unbekannte** Domain wird von AniLoader zwar
  > akzeptiert und normalisiert, das eigentliche Laden schlägt aber fehl, bis die
  > Library nachzieht.

  ### Automatische Migration der Datenbank

  Beim Start (`python main.py` bzw. Container-Start) werden vorhandene Einträge
  automatisch auf die kanonische Domain umgeschrieben – URL **und** `series_key`:

  ```
  https://s.to/serie/the-rookie   →  https://serienstream.to/serie/the-rookie
  s.to:the-rookie                 →  serienstream:the-rookie
  ```

  Der `series_key` enthält bewusst **keine Domain mehr**, sondern den Plattformnamen –
  so übersteht die Duplikaterkennung jeden weiteren Domain-Wechsel. Die Migration ist
  idempotent und läuft bei jedem Start; sie ändert nur Zeilen, bei denen sich etwas
  ergibt. Sollte eine kanonische URL bereits belegt sein (echtes Duplikat), wird die
  Zeile übersprungen und im Log als `[DB-WARN]` gemeldet.

  ---

  ## Mehrere Sprachen pro Serie

  Die `languages`-Liste in der `config.yaml` ist eine **Prioritäts-Kaskade**: es wird
  genau *eine* Sprache geladen – die erste verfügbare. Wer eine Serie in **mehreren
  Sprachen parallel** haben möchte (z.B. German Dub *und* English Sub), hinterlegt die
  gewünschten Sprachen direkt am Datenbank-Eintrag.

  **Erlaubte Werte:** `German Dub` · `German Sub` · `English Dub` · `English Sub`
  (identisch mit den Sprachcodes der aniworld-CLI)

  ### Sprachen setzen

  **Im Web-Interface (empfohlen):** Tab **Datenbank** → Spalte **Sprachen** → auf die
  Chips der Zeile klicken. Im Dialog die gewünschten Sprachen anhaken und speichern.

  - Einträge ohne eigene Auswahl zeigen den Chip **`Kaskade`**
  - Wird eine Sprache abgewählt, erscheint direkt im Dialog eine **Vorschau aller
    Dateien, die gelöscht würden** – vor dem Speichern und vor einer zusätzlichen
    Sicherheitsabfrage

  **Per API:**

  ```bash
  # Aktuelle Auswahl abfragen
  curl http://localhost:5050/anime/12/languages

  # German Dub + English Sub für Eintrag 12 gewünscht
  curl -X PUT http://localhost:5050/anime/12/languages \
       -H "Content-Type: application/json" \
       -d '{"languages": ["German Dub", "English Sub"]}'
  ```

  **Per Skript:** In **`Skripte/db_edit.py`** `ANIME_ID` und
  `languages = ["German Dub", "English Sub"]` setzen und ausführen – auch hier gibt es
  vor dem Speichern eine Vorschau aller betroffenen Dateien.

  **Leere Liste = keine eigene Auswahl** → es gilt wieder die globale Kaskade aus der
  `config.yaml` (Standard für alle bestehenden Einträge, es ändert sich also nichts,
  solange nichts gesetzt wird).

  ### Wie der Download abläuft

  aniworld führt mehrere Sprachversionen automatisch zusammen, sobald beide im selben
  Arbeitsordner landen. AniLoader verhindert das durch einen **strikt sequenziellen**
  Ablauf – niemals parallel:

  ```
  TMP leeren → Sprache A laden → Datei sofort ins Zielverzeichnis verschieben
             → TMP leeren → Sprache B laden → Datei verschieben → TMP leeren
  ```

  Dadurch liegt zu keinem Zeitpunkt mehr als eine Sprachversion im aniworld-Ordner.

  ### Inkrementell – nichts wird doppelt geladen

  Bei jedem Lauf wird pro **(Episode, Sprache)** geprüft, ob die Datei bereits existiert
  (Erkennung über das Sprach-Suffix im Dateinamen). Geladen wird nur, was fehlt:

  - neue Episoden in allen gewünschten Sprachen
  - fehlende Sprachen bei bereits vorhandenen Episoden

  Wird eine Sprache **ergänzt**, setzt AniLoader den Fortschritts-Zeiger des Eintrags
  zurück (`complete`, `last_season`, `last_episode`, `last_film`), damit der nächste
  Lauf auch alte Staffeln erneut prüft. Bereits vorhandene Dateien werden dabei
  übersprungen.

  ### Sprache entfernen

  Wird eine Sprache aus der Auswahl entfernt, löscht AniLoader **ausschließlich die
  Episodendateien dieser Sprache**. Alle anderen Sprachversionen, Episoden und Serien
  bleiben unangetastet. Sicherheitsregeln:

  - Ohne bekannten Serien-Ordnernamen (`folder_name`) wird **nichts** gelöscht
  - Nur Ordner der Serie selbst (exakter Name oder identische imdbid) – kein Titel-Raten
  - Nur `.mkv`/`.mp4` mit erkennbarem Episodencode (`S01E001`, `Film01`, …)
  - Die Sprache muss eindeutig aus dem Dateinamen hervorgehen
  - Jede gelöschte Datei wird im Log protokolliert (`[LANG-DEL]`)

  Im Web-Interface passiert das automatisch: sobald eine Sprache abgewählt wird, listet
  der Dialog die betroffenen Dateien auf, bevor irgendetwas gespeichert wird.

  ```bash
  # Vorher anschauen, was gelöscht würde (ändert weder DB noch Dateien)
  curl -X PUT http://localhost:5050/anime/12/languages \
       -H "Content-Type: application/json" \
       -d '{"languages": ["German Dub"], "dry_run": true}'

  # Dateien behalten und nur die DB ändern
  curl -X PUT http://localhost:5050/anime/12/languages \
       -H "Content-Type: application/json" \
       -d '{"languages": ["German Dub"], "delete_files": false}'
  ```

  > **Hinweis:** Das Leeren der kompletten Auswahl (`[]`) löscht **keine** Dateien –
  > es bedeutet „zurück zur globalen Kaskade", nicht „alles entfernen".

  ### 🎬 Jellyfin: Sprachversionen wieder zusammenführen

  Auf der Platte liegt pro Sprache eine eigene Datei, damit aniworld sie sauber getrennt
  hält. Jellyfin zeigt sie dadurch standardmäßig als **mehrere Episoden** an.

  Das Plugin **[jellyfin-plugin-mergeversions](https://github.com/danieladov/jellyfin-plugin-mergeversions)**
  führt sie clientseitig wieder zu **einer Episode mit Versionsauswahl** zusammen – der
  Zuschauer wählt die Sprache dann direkt im Player, die Dateien bleiben unverändert.

  **Installation in Jellyfin:**
  1. Dashboard → *Plugins* → *Repositories* → Repository hinzufügen:
     `https://raw.githubusercontent.com/danieladov/JellyfinPluginManifest/master/manifest.json`
  2. *Katalog* → **Merge Versions** installieren → Jellyfin neu starten
  3. Dashboard → *Geplante Aufgaben* → **Merge All Versions** ausführen
     (oder als wiederkehrende Aufgabe einplanen, damit neue Downloads automatisch
     zusammengeführt werden)

  ---

  ## Automation

  Der Automation-Scheduler startet Download-Läufe automatisch nach einem Zeitplan.  
  Konfiguration über den **Automation-Tab** im Web-Interface oder direkt in `data/config.yaml`.

  ```yaml
  automation:
    enabled: true

    german:
      enabled: true
      schedule: "0 3 * * 0"   # Cron: jeden Sonntag um 3 Uhr
      interval_minutes: 0      # Alternativ: Intervall in Minuten (0 = cron verwenden)
      discord_webhook: ""      # Optional: Discord-Webhook URL
      notify_on_empty: false   # Benachrichtigen wenn keine neuen Episoden
      filter_mode: whitelist   # whitelist | blacklist
      whitelist: []            # Nur diese Serien prüfen (leer = alle)
      blacklist: []            # Diese Serien überspringen

    new:
      enabled: true
      schedule: "0 */6 * * *"  # Alle 6 Stunden
      interval_minutes: 0
      discord_webhook: ""
      notify_on_empty: false
      filter_mode: whitelist
      whitelist: []
      blacklist: []

    german_new:
      enabled: false
      schedule: ""
      interval_minutes: 0
      discord_webhook: ""
      notify_on_empty: false
      filter_mode: whitelist
      whitelist: []
      blacklist: []
  ```

  **Automation API:**
  ```bash
  GET  /automation/status              # Scheduler-Status + nächste Läufe
  POST /automation/trigger/german      # Manuell starten
  POST /automation/trigger/new
  POST /automation/trigger/german_new
  GET  /automation/history             # Lauf-Historie (letzte 20)
  ```

  ---

  ## Datei-Struktur

  ### Standard-Modus
  **Ein Ordner für alles** (`storage.mode: standard`)

  **Lokal-Modus** (`film_naming_mode: local`):
  ```
  Downloads/
  ├── Naruto (2002) [imdbid-tt0409591]/
  │   ├── Season 01/
  │   │   ├── S01E001 - Erste Episode.mkv
  │   │   ├── S01E002 - Zweite Episode [Sub].mkv
  │   │   └── S01E003 - Episode 3 [English].mkv
  │   ├── Season 02/
  │   └── Filme/
  │       └── Film01 - Naruto Movie.mkv
  └── Avatar (2009) [imdbid-tt0499549]/
      └── Filme/
          └── Film01 - Avatar.mkv
  ```

  **Jellyfin-Modus** (`film_naming_mode: jellyfin`):
  ```
  Downloads/
  ├── Naruto (2002) [imdbid-tt0409591]/
  │   ├── Season 00/                          # Jellyfin "Specials"
  │   │   └── S00E001 - Naruto Movie.mkv
  │   ├── Season 01/
  │   │   └── S01E001 - Erste Episode.mkv
  │   └── Season 02/
  └── Avatar (2009) [imdbid-tt0499549]/
      └── Season 00/
          └── S00E001 - Avatar.mkv
  ```

  ### Separate-Modus  
  **Getrennte Ordner** (`storage.mode: separate`)

  ```
  Anime/                        # aniworld.to Serien
  ├── Naruto (2002)/
  │   ├── Season 01/
  │   └── Season 02/ 
  └── Attack on Titan (2013)/
      └── Season 01/

  Anime-Filme/                  # aniworld.to Filme (anime_separate_movies: true)
  └── Naruto Movie (2004)/
      └── Filme/

  Serien/                       # serienstream.to Serien  
  ├── Breaking Bad (2008)/
  │   └── Season 01/
  └── Game of Thrones (2011)/
      └── Season 01/

  Serien-Filme/                 # serienstream.to Filme (serien_separate_movies: true)
  └── Some Movie (2010)/
      └── Filme/
  ```

  **Datei-Benennung:**
  - **Serien:** `S01E001 - Titel.mkv`, `S01E002 - Titel [Sub].mkv`
  - **Filme (Lokal):** `Filme/Film01 - Titel.mkv` – Standard, unabhängig von Jellyfin
  - **Filme (Jellyfin):** `Season 00/S00E001 - Titel.mkv` – Jellyfin erkennt Season 00 als "Specials"
  - **Suffixe:** `""` (German Dub), `[Sub]` (German Sub), `[English Dub]`, `[English Sub]`

  > **Mehrere Sprachen:** Bei Einträgen mit eigener Sprachauswahl liegt pro Sprache eine
  > eigene Datei nebeneinander (`S01E001 - Titel.mkv` + `S01E001 - Titel [English Sub].mkv`).
  > Das Suffix ist gleichzeitig die Sprach-Kennung für inkrementelle Downloads und für das
  > gezielte Löschen. Zum Zusammenführen in Jellyfin siehe
  > [Mehrere Sprachen pro Serie](#mehrere-sprachen-pro-serie).

  > **Film-Benennung wechseln:** Einstellungen → Film-Benennung → Modus wählen → "Dateien jetzt umbenennen & verschieben". Die Migration ist transaktional – bei einem Abbruch können `.migrate_tmp`-Dateien beim nächsten Wechsel aufgeräumt werden. Wechsel in beide Richtungen möglich.

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

  **Q: serienstream.to ist umgezogen – was muss ich tun?**  
  A: Neue Domain in `config.yaml` unter `domains.serienstream.aliases` eintragen (oder als neue `canonical` setzen) und im `Tampermonkey.user.js` unter `PLATFORMS` + `@match` ergänzen. Kein Code-Eingriff. Details: [Domains & Mirrors](#domains--mirrors). Achtung: die `aniworld`-Library muss die Domain ebenfalls kennen, sonst schlägt der Download fehl.

  **Q: Was ist aus `s.to` geworden?**  
  A: `s.to` ist nur noch ein Eingabe-Alias – alte Links funktionieren weiter, werden aber sofort auf `serienstream.to` normalisiert. Gespeichert oder ausgegeben wird `s.to` nirgends mehr. Bestehende Datenbank-Einträge werden beim Start automatisch umgeschrieben.

  **Q: Welche Sprache wird heruntergeladen?**  
  A: Erste verfügbare aus der `languages`-Liste. Kaskade: German Dub → German Sub → English Sub → English Dub

  **Q: Kann ich eine Serie in mehreren Sprachen gleichzeitig laden?**  
  A: Ja – Datenbank-Tab → Spalte **Sprachen** → Zeile anklicken → Sprachen anhaken. Alternativ per `PUT /anime/{id}/languages` oder `Skripte/db_edit.py`. Jede Sprache wird nacheinander geladen und als eigene Datei abgelegt. Details: [Mehrere Sprachen pro Serie](#mehrere-sprachen-pro-serie)

  **Q: Jellyfin zeigt jede Sprachversion als eigene Episode – wie führe ich sie zusammen?**  
  A: Mit dem Plugin [jellyfin-plugin-mergeversions](https://github.com/danieladov/jellyfin-plugin-mergeversions). Es fasst die Dateien clientseitig zu einer Episode mit Versionsauswahl zusammen; die Dateien auf der Platte bleiben getrennt (nötig, damit aniworld sie nicht mergt).

  **Q: Was passiert, wenn ich eine Sprache wieder entferne?**  
  A: Nur die Episodendateien genau dieser Sprache werden gelöscht – erkannt am Suffix im Dateinamen. Andere Sprachen, Episoden und Serien bleiben unberührt. Mit `"dry_run": true` lässt sich vorher anzeigen, was betroffen wäre.

  **Q: Was ist der Unterschied zwischen `german` und `german_new`?**  
  A: `german` sucht nur fehlende deutsche Episoden bei bereits vorhandenen Serien. `german_new` prüft zusätzlich auf neue Episoden – beides in einem Lauf.

  **Q: Lokal vs. Jellyfin Filmbenennung – was ist der Unterschied?**  
  A: **Lokal** speichert Filme als `Filme/Film01 - Titel.mkv` – übersichtlich und unabhängig von Jellyfin. **Jellyfin** speichert als `Season 00/S00E001 - Titel.mkv` – Jellyfin erkennt Season 00 automatisch als Specials-Staffel und zeigt Poster/Metadaten korrekt an. Umschalten jederzeit möglich, alle Dateien werden automatisch umbenannt und verschoben.

  **Q: Wie richte ich Discord-Benachrichtigungen ein?**  
  A: Im Automation-Tab pro Modus einen Discord-Webhook eintragen. AniLoader sendet eine Zusammenfassung nach jedem automatischen Lauf.

  **Q: Separate Filmpfade einrichten?**  
  A: `anime_separate_movies: true` und/oder `serien_separate_movies: true` in `config.yaml` setzen und die entsprechenden Volumes einbinden.

  ## ⚠️ Disclaimer
  I provide this tool for educational and informational purposes only.
  You are solely responsible for how you use it.
  Any actions taken using this tool are entirely your own responsibility.
  I do not condone or support illegal use.
  ---

  <p align="center">
    <img src="web/static/AniLoader.png" alt="AniLoader" width="60"><br>
    <sub>Made with ❤️ for Anime & Serien</sub>
  </p>
