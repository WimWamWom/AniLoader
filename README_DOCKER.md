<p align="center">
  <img src="https://raw.githubusercontent.com/WimWamWom/AniLoader/main/web/static/AniLoader.png" alt="AniLoader Logo" width="150">
</p>

<h1 align="center">AniLoader – Docker</h1>

<p align="center">
  <strong>Anime & Serien Download-Manager mit Web-Interface</strong><br>
  Automatisches Herunterladen von Anime und Serien von aniworld.to und s.to<br>
  mit Jellyfin-kompatibler Ordnerstruktur.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Docker-Hub-2496ED?logo=docker&logoColor=white" alt="Docker Hub">
  <img src="https://img.shields.io/badge/amd64-supported-green" alt="amd64">
  <img src="https://img.shields.io/badge/arm64-supported-green" alt="arm64">
  <img src="https://img.shields.io/badge/Unraid-compatible-F15A2C?logo=unraid&logoColor=white" alt="Unraid">
</p>

---

## Quickstart

```bash
docker run -d \
  --name aniloader \
  -p 5050:5050 \
  -v /pfad/zu/data:/app/data \
  -v /pfad/zu/downloads:/app/Downloads \
  -v /pfad/zu/anime:/app/Anime \
  -v /pfad/zu/serien:/app/Serien \
  -v /pfad/zu/anime-filme:/app/Anime-Filme \
  -v /pfad/zu/serien-filme:/app/Serien-Filme \
  -e PYTHONUNBUFFERED=1 \
  -e TZ=Europe/Berlin \
  --dns 8.8.8.8 --dns 1.1.1.1 \
  --restart unless-stopped \
  wimwamwom/aniloader:latest
```

Web-Interface: `http://<server-ip>:5050`

---

## Docker Compose

```yaml
services:
  aniloader:
    image: wimwamwom/aniloader:latest
    container_name: aniloader
    hostname: aniloader
    ports:
      - "5050:5050"
    volumes:
      # Persistente Daten (DB, Config, Logs)
      # config.yaml: data.folder = /app/data
      - ./data:/app/data
      # Download-Verzeichnis (storage.mode: standard)
      # config.yaml: storage.download_path = /app/Downloads
      - ./Downloads:/app/Downloads
      # Separate Pfade (storage.mode: separate)
      # config.yaml: storage.anime_path = /app/Anime
      - ./Anime:/app/Anime
      # config.yaml: storage.series_path = /app/Serien
      - ./Serien:/app/Serien
      # config.yaml: storage.anime_movies_path = /app/Anime-Filme
      - ./Anime-Filme:/app/Anime-Filme
      # config.yaml: storage.serien_movies_path = /app/Serien-Filme
      - ./Serien-Filme:/app/Serien-Filme
    environment:
      - PYTHONUNBUFFERED=1
      - TZ=Europe/Berlin
    dns:
      - 8.8.8.8
      - 1.1.1.1
    restart: unless-stopped
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5050/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
```

```bash
docker compose up -d
```

> **Selbst bauen:** Statt `image:` kann `build: .` verwendet werden, um aus dem Repository-Quellcode zu bauen.

---

## Volumes

| Container-Pfad | config.yaml-Key | Beschreibung | Pflicht |
|---|---|---|---|
| `/app/data` | `data.folder` | SQLite-Datenbank, `config.yaml`, Logs | ✅ Ja |
| `/app/Downloads` | `storage.download_path` | Standard-Download-Verzeichnis | ✅ Ja |
| `/app/Anime` | `storage.anime_path` | Anime (bei `storage.mode: separate`) | ✅ Ja |
| `/app/Serien` | `storage.series_path` | Serien (bei `storage.mode: separate`) | ✅ Ja |
| `/app/Anime-Filme` | `storage.anime_movies_path` | Anime-Filme (bei `anime_separate_movies: true`) | ✅ Ja |
| `/app/Serien-Filme` | `storage.serien_movies_path` | Serien-Filme (bei `serien_separate_movies: true`) | ✅ Ja |

> **Wichtig:** Ohne gemountete Volumes gehen Datenbank und Downloads bei Container-Neustart verloren!
>
> Die Pfade in der `config.yaml` müssen den **Container-Pfaden** (rechte Seite der `:`) entsprechen.

---

## Ports

| Container-Port | Beschreibung |
|---|---|
| `5050` | Web-Interface & REST-API |

Der Port kann im Host frei gemappt werden (z.B. `-p 8080:5050`).

---

## Konfiguration

Beim ersten Start wird automatisch eine `config.yaml` im `/app/data`-Verzeichnis erstellt. Alle Einstellungen können über das **Web-Interface** (Tab „Einstellungen") oder direkt in der Datei geändert werden.

### config.yaml

```yaml
server:
  port: 5050

languages:
  - German Dub
  - German Sub
  - English Sub
  - English Dub

storage:
  mode: standard                    # standard | separate
  download_path: /app/Downloads     # Haupt-Download-Pfad
  anime_path: /app/Anime            # Anime (separate Modus)
  series_path: /app/Serien           # Serien (separate Modus)
  anime_movies_path: /app/Anime-Filme   # Anime-Filme (optional)
  serien_movies_path: /app/Serien-Filme # Serien-Filme (optional)
  anime_separate_movies: false
  serien_separate_movies: false

download:
  min_free_gb: 2.0                  # Mindest freier Speicherplatz (GB)
  autostart_mode: null              # null | default | german | new | check
  timeout_seconds: 900              # Timeout pro Episode (Sekunden)

data:
  folder: /app/data                 # Pfad für DB, Logs, Config
```

### Speicher-Modi

**Standard** (`storage.mode: standard`): Alle Downloads landen in einem Ordner.

**Separate** (`storage.mode: separate`): Anime und Serien werden in verschiedene Ordner sortiert. Alle Pfade sind bereits als Volumes gemappt:

```yaml
storage:
  mode: separate
  anime_path: /app/Anime              # → Volume ./Anime:/app/Anime
  series_path: /app/Serien             # → Volume ./Serien:/app/Serien
  anime_movies_path: /app/Anime-Filme  # → Volume ./Anime-Filme:/app/Anime-Filme
  serien_movies_path: /app/Serien-Filme # → Volume ./Serien-Filme:/app/Serien-Filme
  anime_separate_movies: true
  serien_separate_movies: true
```

### Autostart

AniLoader kann beim Container-Start automatisch einen Download-Modus starten:

```yaml
download:
  autostart_mode: default   # Optionen: default, german, new, check
```

| Modus | Beschreibung |
|---|---|
| `default` | Alle nicht-vollständigen Serien herunterladen |
| `german` | Fehlende deutsche Episoden nachprüfen |
| `new` | Alle Serien auf neue Episoden prüfen |
| `check` | Integritätsprüfung aller Downloads |

---

## Features

| Feature | Beschreibung |
|---|---|
| 🌐 **Web-Interface** | Dark-Theme UI mit 4 Tabs – Download, Hinzufügen, Datenbank, Einstellungen |
| 📥 **4 Download-Modi** | Standard, German, Neue Episoden, Integritäts-Check |
| 🔍 **Integrierte Suche** | Durchsuche aniworld.to und s.to direkt aus dem Interface |
| 🇩🇪 **Sprachpriorität** | Konfigurierbare Reihenfolge mit automatischem Fallback |
| 📁 **Jellyfin-kompatibel** | Ordnerstruktur `Title (Year) [imdbid-xxx]/Season ss/` |
| 💾 **SQLite Datenbank** | Serien-Verwaltung mit Status, Fortschritt und fehlenden Episoden |
| 🔒 **DNS-over-HTTPS** | Umgeht ISP-DNS-Sperren automatisch |
| 🧩 **Tampermonkey-Skript** | Ein-Klick-Download direkt von aniworld.to / s.to |
| 📊 **Live-Status** | Echtzeit-Fortschritt mit Auto-Polling im Browser |
| 📤 **Bulk-Import** | TXT-Datei oder Drag & Drop für viele URLs |

---

## Unterstützte Architekturen

| Architektur | Tag |
|---|---|
| `linux/amd64` | `latest` |
| `linux/arm64` | `latest` |

Das Multi-Arch-Image wird automatisch über GitHub Actions gebaut und gepusht.

---

## Health Check

Der Container enthält einen eingebauten Health Check:

```
GET http://localhost:5050/health → {"status": "ok"}
```

- **Interval:** 30s
- **Timeout:** 10s
- **Retries:** 3
- **Start Period:** 5s

---

## Unraid

**Docker Hub:** `wimwamwom/aniloader:latest`

**Port:**

| Container-Port | Host-Port |
|---|---|
| `5050` | `5050` |

**Volumes:**

| Container-Pfad | Host-Pfad | Beschreibung |
|---|---|---|
| `/app/data` | `/mnt/user/appdata/aniloader` | Datenbank, Config, Logs |
| `/app/Downloads` | `/mnt/user/data/media/Downloads` | Standard-Download-Ordner |
| `/app/Anime` | `/mnt/user/data/media/Anime` | Anime (separate Modus) |
| `/app/Serien` | `/mnt/user/data/media/Serien` | Serien (separate Modus) |
| `/app/Anime-Filme` | `/mnt/user/data/media/Anime-Filme` | Anime-Filme (optional) |
| `/app/Serien-Filme` | `/mnt/user/data/media/Serien-Filme` | Serien-Filme (optional) |

**Environment-Variablen:**

| Variable | Wert |
|---|---|
| `PYTHONUNBUFFERED` | `1` |
| `TZ` | `Europe/Berlin` |

**Icon URL:** `https://raw.githubusercontent.com/WimWamWom/AniLoader/main/web/static/AniLoader.png`

**WebUI:** `http://[IP]:[PORT:5050]`

---

## API

Swagger-Dokumentation verfügbar unter `http://<server-ip>:5050/docs`.

Wichtige Endpunkte:

| Methode | Pfad | Beschreibung |
|---|---|---|
| `GET` | `/health` | Health Check |
| `GET` | `/status` | Download-Status |
| `POST` | `/start_download` | Download starten (`{"mode": "default"}`) |
| `POST` | `/stop_download` | Download stoppen |
| `POST` | `/export` | URL hinzufügen (`{"url": "..."}`) |
| `GET` | `/database` | Alle DB-Einträge |
| `POST` | `/search` | Suche (`{"query": "...", "platform": "both"}`) |
| `GET` | `/config` | Konfiguration abrufen |
| `POST` | `/config` | Konfiguration ändern |

---

## Fehlerbehebung

### „Permission denied" für Download-Ordner
```bash
mkdir -p data Downloads
chmod 777 Downloads
```

### Container startet, aber Web-Interface nicht erreichbar
- Port-Mapping prüfen: `docker port aniloader`
- Logs prüfen: `docker logs aniloader`
- Health Check: `docker inspect --format='{{.State.Health.Status}}' aniloader`

### Downloads funktionieren nicht
- Logs prüfen: `docker logs -f aniloader`
- `ffmpeg` und `aniworld` sind im Image enthalten – kein manuelles Installieren nötig

### Container neu bauen (aus Source)
```bash
git clone https://github.com/WimWamWom/AniLoader.git
cd AniLoader

# Ordner anlegen + Rechte setzen
mkdir -p data Downloads Anime Serien Anime-Filme Serien-Filme
chmod 777 Downloads Anime Serien Anime-Filme Serien-Filme

docker compose up -d --build
```

---

## Links

- **GitHub:** [https://github.com/WimWamWom/AniLoader](https://github.com/WimWamWom/AniLoader)
- **Docker Hub:** [https://hub.docker.com/r/wimwamwom/aniloader](https://hub.docker.com/r/wimwamwom/aniloader)

---

<p align="center">
  <img src="https://raw.githubusercontent.com/WimWamWom/AniLoader/main/web/static/AniLoader.png" alt="AniLoader" width="50"><br>
  <sub>Made with ❤️ for Anime & Serien</sub>
</p>
