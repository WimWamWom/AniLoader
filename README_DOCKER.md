<h1 align="center"><sub><img src="https://raw.githubusercontent.com/WimWamWom/AniLoader/refs/heads/main/web/static/AniLoader.png" width="35"></sub>AniLoader </h1>


  
  Anime & Serien Download-Manager mit Web-Interface
  Automatisches Herunterladen von aniworld.to und s.to mit Jellyfin-Struktur
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
  - [Docker Run](#docker-run)
  - [Docker Compose](#docker-compose)
  - [Unraid](#unraid)
- [Verwendung](#verwendung)
  - [Web-Interface](#web-interface)
  - [API](#api)
  - [Tampermonkey](#tampermonkey)
- [Konfiguration](#konfiguration)
- [Automation](#automation)
- [Volumes & Pfade](#volumes--pfade)
- [Datei-Struktur](#datei-struktur)
  - [Standard-Modus](#standard-modus)
  - [Separate-Modus](#separate-modus)
- [FAQ](#faq)

---

## Funktionen

- **🐋 Docker-Ready:** Multi-Arch Images (amd64/arm64) mit Health-Checks
- **🌐 Web-Interface:** Moderne Dark-Theme Oberfläche mit Live-Status  
- **📥 5 Download-Modi:** Default, German, New Episode Check, German+New, Integrity Check
- **🤖 Automation:** Geplante Läufe per Cron-Schedule oder Intervall mit Discord-Benachrichtigungen
- **🔍 Suche + Poster:** Durchsuche Aniworld und SerieStream
- **🇩🇪 Sprach-Priorität:** German Dub → Sub → English (automatischer Fallback)
- **📁 Jellyfin-Ready:** `Title (Year) [IMDB]/Season/Episode.mkv`
- **💾 Persistent:** SQLite-DB und Config überleben Container-Neustarts
- **📄 AniLoader.txt Import:** Automatischer Import beim Container-Start
- **💾 Export-Funktionen:** Datenbank + Links als Download exportieren
- **🔓 Anti-Sperre:** DNS-over-HTTPS umgeht Provider-Blocks
- **⚡ Autostart:** Optional bei Container-Start Download-Modus starten
- **📂 Separate Filmpfade:** Anime-Filme und Serien-Filme in eigene Ordner
- **🎬 Film-Benennung:** Umschaltbar zwischen Lokal (`Film01`) und Jellyfin (`S00E001`) – mit automatischer Migration aller vorhandenen Dateien

---

## Installation

> **Image verfügbar auf:** Docker Hub `wimwamwom/aniloader:latest` · GHCR `ghcr.io/wimwamwom/aniloader:latest`

### Docker Run
```bash
# Minimale Konfiguration
docker run -d \
  --name aniloader \
  -p 5050:5050 \
  -v ./data:/app/data \
  -v ./Downloads:/app/Downloads \
  -e TZ=Europe/Berlin \
  --restart unless-stopped \
  wimwamwom/aniloader:latest

# Separate Modus (Anime/Serien getrennt)
docker run -d \
  --name aniloader \
  -p 5050:5050 \
  -v ./data:/app/data \
  -v ./Downloads:/app/Downloads \
  -v ./Anime:/app/Anime \
  -v ./Serien:/app/Serien \
  -v ./Anime-Filme:/app/Anime-Filme \
  -v ./Serien-Filme:/app/Serien-Filme \
  -e TZ=Europe/Berlin \
  --dns 8.8.8.8 \
  --restart unless-stopped \
  wimwamwom/aniloader:latest
```

### Docker Compose
```yaml
# docker-compose.yml
services:
  aniloader:
    image: wimwamwom/aniloader:latest
    container_name: aniloader
    hostname: aniloader
    ports:
      - "5050:5050"
    volumes:
      # Persistente Daten (Config, DB, Logs)
      - ./data:/app/data
      # Downloads (Standard-Modus)
      - ./Downloads:/app/Downloads
      # Separate Pfade (Optional)
      - ./Anime:/app/Anime              # aniworld.to
      - ./Serien:/app/Serien            # s.to
      - ./Anime-Filme:/app/Anime-Filme  # Separate Filme
      - ./Serien-Filme:/app/Serien-Filme
    environment:
      - TZ=Europe/Berlin
      - PYTHONUNBUFFERED=1
    dns:
      - 8.8.8.8
      - 1.1.1.1
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5050/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

```bash
# Ordner erstellen + Rechte
mkdir -p data Downloads Anime Serien Anime-Filme Serien-Filme
chmod 777 Downloads Anime Serien

# Starten
docker compose up -d

# Logs verfolgen
docker compose logs -f
```

### Unraid
**Community Apps:** AniLoader Template  
**Docker Hub:** `wimwamwom/aniloader:latest`

**Port Mapping:**
- Container: `5050` → Host: `5050`

**Volume Mappings:**
| Container-Pfad | Host-Pfad | Beschreibung |
|---|---|---|
| `/app/data` | `/mnt/user/appdata/aniloader` | Config, DB, Logs |
| `/app/Downloads` | `/mnt/user/data/Downloads` | Standard-Downloads |
| `/app/Anime` | `/mnt/user/data/Anime` | Anime (separate mode) |
| `/app/Serien` | `/mnt/user/data/Serien` | Serien (separate mode) |
| `/app/Anime-Filme` | `/mnt/user/data/Anime-Filme` | Anime-Filme (separate mode) |
| `/app/Serien-Filme` | `/mnt/user/data/Serien-Filme` | Serien-Filme (separate mode) |

**Environment Variables:**
- `TZ=Europe/Berlin`
- `PYTHONUNBUFFERED=1`

**WebUI:** `http://[IP]:5050`

---

## Verwendung

### Web-Interface
**URL:** `http://localhost:5050`

**📥 Download-Tab**
- Download-Modi starten/stoppen (default, german, new, german_new, check)
- Live-Status mit aktueller Serie/Episode/Fortschritt  
- Echtzeit-Logs des laufenden Downloads

**📂 Hinzufügen-Tab**
- URLs einzeln eingeben oder per TXT-Upload
- Integrierte Suche mit Poster-Vorschau
- Drag & Drop für Bulk-Import

**🗃️ Datenbank-Tab**
- Alle Serien mit Status, Fortschritt, fehlende DE-Episoden
- Sortierung, Filter, Löschen/Wiederherstellen
- **💾 Export DB:** Komplette SQLite-Datenbank herunterladen
- **📄 Export Links:** Alle URLs als AniLoader.txt herunterladen

**📋 Logs-Tab**
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
- Storage-Mode (Standard vs Separate) mit Ordner-Browser
- Separate Filmpfade für Anime-Filme und Serien-Filme
- **Film-Benennung:** Lokal (`Film01 - Titel.mkv`) oder Jellyfin (`S00E001 - Titel.mkv`) wählbar; bei Modusänderung erscheint ein Button zum automatischen Umbenennen aller vorhandenen Dateien
- Sprachpriorität per Drag & Drop
- Autostart, Titel-Refresh, System-Settings

### API
**Base URL:** `http://localhost:5050`  
**Swagger Docs:** `/docs`

```bash
# Container-Status + AniLoader-Status
docker ps  # Container läuft?
curl http://localhost:5050/health  # {"status": "ok"}
curl http://localhost:5050/status  # Download-Status

# Downloads steuern
curl -X POST http://localhost:5050/start_download \
  -H "Content-Type: application/json" \
  -d '{"mode": "default"}'  # default | german | new | check | german_new

curl -X POST http://localhost:5050/stop_download

# URLs hinzufügen
curl -X POST http://localhost:5050/add_link \
  -H "Content-Type: application/json" \
  -d '{"url": "https://aniworld.to/anime/stream/naruto"}'

# Suchen mit Platform
curl -X POST http://localhost:5050/search \
  -H "Content-Type: application/json" \
  -d '{"query": "demon slayer", "platform": "both"}'

# Datenbank
curl http://localhost:5050/database?q=naruto
curl http://localhost:5050/database/stats

# Export-Funktionen
curl http://localhost:5050/export/database  # SQLite-DB Download
curl http://localhost:5050/export/links     # AniLoader.txt Download

# Automation
curl http://localhost:5050/automation/status
curl -X POST http://localhost:5050/automation/trigger/german
curl -X POST http://localhost:5050/automation/trigger/new
curl -X POST http://localhost:5050/automation/trigger/german_new
curl http://localhost:5050/automation/history

# Speicherplatz
curl http://localhost:5050/disk
```

### Tampermonkey
1. **Tampermonkey Extension** installieren  
2. **`Tampermonkey.user.js`** vom Repository → Install
3. **Docker-IP konfigurieren** im Skript:
```javascript
const USE_DOMAIN = false;
const SERVER_IP = "192.168.1.100";    // Docker-Host-IP
const SERVER_PORT = 5050;
```
4. **Button auf aniworld.to/s.to** nutzen

---

## Konfiguration

**Automatische Erstellung:** `data/config.yaml`  
**Änderung:** Web-Interface → Einstellungen oder Datei editieren

```yaml
server:
  port: 5050

languages:                    # Download-Priorität
  - German Dub               # 1. Erste verfügbare Sprache
  - German Sub               # 2. Fallback  
  - English Sub              # 3. Fallback
  - English Dub              # 4. Letztmöglicher Fallback

storage:
  mode: separate             # standard | separate
  download_path: /app/Downloads        # Standard-Modus
  anime_path: /app/Anime              # aniworld.to → hier
  series_path: /app/Serien            # s.to → hier
  anime_movies_path: /app/Anime-Filme  # Optional: Separate Filme
  serien_movies_path: /app/Serien-Filme
  anime_separate_movies: false
  serien_separate_movies: false
  film_naming_mode: local               # local | jellyfin
  # ⚠ Der finale Ordnername (letztes Pfadsegment) darf nicht mit '.' beginnen.
  #   Erlaubt:  /app/Downloads  oder  /mnt/.cache/Downloads
  #   Verboten: /app/.Downloads

download:
  autostart_mode: null       # null, default, german, new, check, german_new
  refresh_titles: false      # Titel beim Start aktualisieren
  min_free_gb: 2.0           # Mindest-Speicherplatz in GB
  timeout_seconds: 900       # Download-Timeout pro Episode in Sekunden

logging:
  log_retention_days: 7      # Logs nach X Tagen automatisch löschen

data:
  folder: /app/data          # Config, DB, Logs (gemounted!)
```

**Autostart-Modi:**
- **null:** Kein Autostart
- **default:** Alle unvollständigen Serien beim Container-Start  
- **german:** Fehlende deutsche Episoden
- **new:** Neue Episoden-Check
- **german_new:** German + New in einem Lauf
- **check:** Integritätsprüfung

---

## Automation

Geplante Download-Läufe per Cron-Schedule oder Intervall.

```yaml
automation:
  enabled: true

  german:
    enabled: true
    schedule: "0 3 * * 0"    # Cron: jeden Sonntag um 3 Uhr
    interval_minutes: 0       # Alternativ: Intervall in Minuten (0 = cron)
    discord_webhook: ""       # Optional: Discord-Webhook URL
    notify_on_empty: false    # Benachrichtigen wenn keine neuen Episoden
    filter_mode: whitelist    # whitelist | blacklist
    whitelist: []             # Nur diese Serien prüfen (leer = alle)
    blacklist: []             # Diese Serien überspringen

  new:
    enabled: true
    schedule: "0 */6 * * *"   # Alle 6 Stunden
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

---

## Volumes & Pfade

### Pflicht-Volumes
```bash
-v ./data:/app/data                    # Config + SQLite-DB + Logs
-v ./Downloads:/app/Downloads          # Downloads (Standard-Modus)
```

### Optional-Volumes (Separate-Modus)
```bash
-v ./Anime:/app/Anime                  # aniworld.to Content
-v ./Serien:/app/Serien                # s.to Content  
-v ./Anime-Filme:/app/Anime-Filme      # Separate Anime-Filme
-v ./Serien-Filme:/app/Serien-Filme    # Separate Serien-Filme
```

**Wichtig:** Container-Pfade (rechts) müssen mit `config.yaml` übereinstimmen!

### Berechtigungen
```bash
# Linux: Downloads-Ordner beschreibbar machen
chmod 777 Downloads Anime Serien

# Docker-User hat UID 1000 - alternativ:
chown -R 1000:1000 data Downloads Anime Serien
```

---

## Datei-Struktur

### Standard-Modus
**Ein Volume für alles** (`storage.mode: standard`)

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
**Getrennte Volumes** (`storage.mode: separate`)

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

Serien/                       # s.to Serien  
├── Breaking Bad (2008)/
│   └── Season 01/
└── Game of Thrones (2011)/
    └── Season 01/

Serien-Filme/                 # s.to Filme (serien_separate_movies: true)
└── Some Movie (2010)/
    └── Filme/
```

**Datei-Benennung:**
- **Serien:** `S01E001 - Titel.mkv`, `S01E002 - Titel [Sub].mkv`
- **Filme (Lokal):** `Filme/Film01 - Titel.mkv` – Standard, unabhängig von Jellyfin
- **Filme (Jellyfin):** `Season 00/S00E001 - Titel.mkv` – Jellyfin erkennt Season 00 als "Specials"
- **Suffixe:** `""` (German Dub), `[Sub]` (German Sub), `[English Dub]`, `[English Sub]`

> **Film-Benennung wechseln:** Einstellungen → Film-Benennung → Modus wählen → "Dateien jetzt umbenennen & verschieben". Die Migration ist transaktional – bei einem Abbruch können `.migrate_tmp`-Dateien beim nächsten Wechsel aufgeräumt werden. Wechsel in beide Richtungen möglich.

---

## FAQ

**Q: Container startet, aber Web-Interface nicht erreichbar**  
A: `docker ps` → Port-Mapping korrekt? `docker logs aniloader` → Startup-Fehler?

**Q: "Permission denied" für Download-Ordner**  
A: `chmod 777 Downloads Anime Serien` oder `chown -R 1000:1000 Downloads`

**Q: Downloads funktionieren nicht im Container**  
A: ffmpeg und aniworld-CLI sind pre-installiert. `docker logs -f aniloader` für Details

**Q: "DNS-Fehler" oder Seiten nicht erreichbar**  
A: AniLoader nutzt DNS-over-HTTPS automatisch. Firewall für ausgehende HTTPS-Verbindungen prüfen

**Q: Konfiguration geht bei Container-Neustart verloren**  
A: `data/` Volume gemounted? Ohne Volume wird config.yaml nicht gespeichert!

**Q: Autostart aktivieren bei Docker-Start**  
A: `data/config.yaml` → `autostart_mode: default` oder Web-UI → Einstellungen → System

**Q: AniLoader.txt Import im Container?**  
A: `AniLoader.txt` ins Host-Verzeichnis (wird zu Container-Root gemounted) → automatischer Import beim Start

**Q: Export-Funktionen nutzen?**  
A: Web-UI → Datenbank-Tab → "💾 Export DB" oder "📄 Export Links" für Downloads

**Q: Separate vs Standard Mode?**  
A: **Standard** = Alles in Downloads. **Separate** = Anime/Serien getrennt für bessere Jellyfin-Organisation

**Q: Welche Sprache wird heruntergeladen?**  
A: Erste verfügbare aus der `languages`-Liste. Kaskade: German Dub → German Sub → English Sub → English Dub

**Q: Was ist der Unterschied zwischen `german` und `german_new`?**  
A: `german` sucht nur fehlende deutsche Episoden bei bereits vorhandenen Serien. `german_new` prüft zusätzlich auf neue Episoden – beides in einem Lauf.

**Q: Lokal vs. Jellyfin Filmbenennung – was ist der Unterschied?**  
A: **Lokal** speichert Filme als `Filme/Film01 - Titel.mkv` – übersichtlich und unabhängig von Jellyfin. **Jellyfin** speichert als `Season 00/S00E001 - Titel.mkv` – Jellyfin erkennt Season 00 automatisch als Specials-Staffel und zeigt Poster/Metadaten korrekt an. Umschalten jederzeit möglich, alle Dateien werden automatisch umbenannt und verschoben.

**Q: Wie richte ich Automation ein?**  
A: Web-UI → Automation-Tab → gewünschten Modus aktivieren, Cron-Schedule eintragen, optional Discord-Webhook hinzufügen.

**Q: Wie richte ich Discord-Benachrichtigungen ein?**  
A: Im Automation-Tab pro Modus einen Discord-Webhook eintragen. AniLoader sendet eine Zusammenfassung nach jedem automatischen Lauf.

**Q: Separate Filmpfade einrichten?**  
A: Im Separate-Modus: `anime_separate_movies: true` und/oder `serien_separate_movies: true` in `config.yaml` setzen. Die Volumes `./Anime-Filme:/app/Anime-Filme` und `./Serien-Filme:/app/Serien-Filme` einbinden.

**Q: "Permission denied" für Download-Ordner**  
A: `chmod 777 Downloads Anime Serien` oder `chown -R 1000:1000 Downloads`

**Q: Container nutzt zu viel CPU/RAM**  
A: Download-Modi sind CPU-intensiv (Video-Processing). Normal während aktiver Downloads

**Q: Multi-Arch Support (ARM/Intel)**  
A: `wimwamwom/aniloader:latest` unterstützt automatisch amd64 + arm64

**Q: Reverse Proxy (nginx/Traefik)**  
A: Container-Port 5050, externe URL im Tampermonkey-Skript anpassen

---

<p align="center">
  <img src="https://raw.githubusercontent.com/WimWamWom/AniLoader/main/web/static/AniLoader.png" alt="AniLoader" width="60"><br>
  <sub>Made with ❤️ for Anime & Serien</sub>
</p>
