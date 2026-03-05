<p align="center">
  <img src="https://raw.githubusercontent.com/WimWamWom/AniLoader/main/web/static/AniLoader.png" alt="AniLoader Logo" width="200">
</p>

<h1 align="center">AniLoader – Docker</h1>

<p align="center">
  <strong>Anime &amp; Serien Download-Manager mit Web-Interface</strong><br>
  Automatisches Herunterladen von aniworld.to und s.to mit Jellyfin-Struktur
</p>

---

## TL;DR
```bash
# Schnellstart Docker
docker run -d -p 5050:5050 -v ./data:/app/data -v ./Downloads:/app/Downloads wimwamwom/aniloader:latest

# Docker Compose (empfohlen)
curl -o docker-compose.yml https://raw.githubusercontent.com/WimWamWom/AniLoader/main/docker-compose.yml
docker compose up -d
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
- [Volumes & Pfade](#volumes--pfade)
- [Datei-Struktur](#datei-struktur)
  - [Standard-Modus](#standard-modus)
  - [Separate-Modus](#separate-modus)
- [FAQ](#faq)

---

## Funktionen

- **🐋 Docker-Ready:** Multi-Arch Images (amd64/arm64) mit Health-Checks
- **🌐 Web-Interface:** Moderne Dark-Theme Oberfläche mit Live-Status  
- **📥 4 Download-Modi:** Standard, German, New Episode Check, Integrity Check
- **🔍 Suche + Poster:** Durchsuche beide Plattformen mit Poster-Vorschau
- **🇩🇪 Sprach-Kaskade:** German Dub → Sub → English (automatischer Fallback)
- **📁 Jellyfin-Ready:** `Title (Year)/Season 01/S01E001.mkv` + `Filme/Film01.mkv`
- **💾 Persistent:** SQLite-DB und Config überleben Container-Neustarts
- **🔒 Anti-Sperre:** DNS-over-HTTPS umgeht Provider-Blocks
- **⚡ Autostart:** Optional bei Container-Start Download-Modus starten

---

## Installation

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

**Environment Variables:**
- `TZ=Europe/Berlin`
- `PYTHONUNBUFFERED=1`

**WebUI:** `http://[IP]:5050`

---

## Verwendung

### Web-Interface
**URL:** `http://localhost:5050`

**📥 Download-Tab**
- Download-Modi starten/stoppen (default, german, new, check)
- Live-Status mit aktueller Serie/Episode/Fortschritt  
- Echtzeit-Logs des laufenden Downloads

**📂 Hinzufügen-Tab**
- URLs einzeln eingeben oder per TXT-Upload
- Integrierte Suche mit Poster-Vorschau
- Drag & Drop für Bulk-Import

**🗃️ Datenbank-Tab**
- Alle Serien mit Status, Fortschritt, fehlende DE-Episoden
- Sortierung, Filter, Löschen/Wiederherstellen

**⚙️ Einstellungen-Tab**
- Storage-Mode (Standard vs Separate)
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
  -d '{"mode": "default"}'

# URLs hinzufügen
curl -X POST http://localhost:5050/export \
  -H "Content-Type: application/json" \
  -d '{"url": "https://aniworld.to/anime/stream/naruto"}'

# Suchen mit Platform
curl -X POST http://localhost:5050/search \
  -H "Content-Type: application/json" \
  -d '{"query": "demon slayer", "platform": "both"}'
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

download:
  autostart_mode: null       # null, default, german, new, check  
  refresh_titles: false      # Titel beim Start aktualisieren
  min_free_gb: 2.0          # Mindest-Speicherplatz
  timeout_seconds: 900       # Download-Timeout pro Episode

data:
  folder: /app/data          # Config, DB, Logs (gemounted!)
```

**Autostart-Modi:**
- **null:** Kein Autostart
- **default:** Alle unvollständigen Serien beim Container-Start  
- **german:** Fehlende deutsche Episoden
- **new:** Neue Episoden-Check
- **check:** Integritätsprüfung

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

```
Downloads/                              # ./Downloads:/app/Downloads
├── Naruto (2002) [imdbid-tt0409591]/
│   ├── Season 01/
│   │   ├── S01E001 - Uzumaki Naruto.mkv
│   │   ├── S01E002 - My Name is Konohamaru [Sub].mkv
│   │   └── S01E003 - Sasuke and Sakura [English].mkv
│   ├── Season 02/
│   └── Filme/
│       └── Film01 - Naruto Movie.mkv
└── Breaking Bad (2008) [imdbid-tt0903747]/
    ├── Season 01/
    └── Season 05/
```

### Separate-Modus
**Getrennte Volumes** (`storage.mode: separate`)

```
Anime/                                  # ./Anime:/app/Anime (aniworld.to)
├── Naruto (2002)/
│   ├── Season 01/
│   ├── Season 02/
│   └── Filme/
└── Attack on Titan (2013)/
    ├── Season 01/
    └── Season 04/

Serien/                                 # ./Serien:/app/Serien (s.to)
├── Breaking Bad (2008)/
│   ├── Season 01/
│   └── Season 05/
└── The Office (2005)/
    ├── Season 01/
    └── Season 09/

Anime-Filme/                            # ./Anime-Filme:/app/Anime-Filme  
└── Your Name (2016)/                   # anime_separate_movies: true
    └── Filme/
        └── Film01 - Your Name [Sub].mkv
```

**Datei-Benennung:**
- **Serien:** `S01E001 - Titel.mkv`
- **Filme:** `Film01 - Titel.mkv` 
- **Sprach-Suffixe:** `[Sub]`, `[English Dub]`, `[English Sub]`

---

## FAQ

**Q: Container startet, aber Web-Interface nicht erreichbar**  
A: `docker ps` → Port-Mapping korrekt? `docker logs aniloader` → Startup-Fehler?

**Q: "Permission denied" für Download-Ordner**  
A: `chmod 777 Downloads Anime Serien` oder `chown -R 1000:1000 Downloads`

**Q: Downloads funktionieren nicht im Container**  
A: ffmpeg und aniworld-CLI sind pre-installiert. `docker logs -f aniloader` für Details

**Q: Konfiguration geht bei Container-Neustart verloren**  
A: `data/` Volume gemounted? Ohne Volume wird config.yaml nicht gespeichert!

**Q: Autostart aktivieren bei Docker-Start**  
A: `data/config.yaml` → `autostart_mode: default` oder Web-UI → Einstellungen → System

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
