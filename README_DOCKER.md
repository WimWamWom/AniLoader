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
  --restart unless-stopped \
  wimwamwom/aniloader:latest
```

Web-Interface: `http://<server-ip>:5050`

---

## Docker Compose

```yaml
version: '3.8'

services:
  aniloader:
    image: wimwamwom/aniloader:latest
    container_name: aniloader
    ports:
      - "5050:5050"
    volumes:
      # Persistente Daten (Datenbank, Config, Logs)
      - ./data:/app/data
      # Download-Verzeichnis (Standard-Modus)
      - ./Downloads:/app/Downloads
      # ── Separate Pfade (optional, bei storage.mode: separate) ──
      # - /pfad/zu/animes:/animes
      # - /pfad/zu/serien:/serien
    environment:
      - PYTHONUNBUFFERED=1
    restart: unless-stopped
```

```bash
docker compose up -d
```

---

## Volumes

| Container-Pfad | Beschreibung | Pflicht |
|---|---|---|
| `/app/data` | SQLite-Datenbank, `config.yaml`, Logs | ✅ Ja |
| `/app/Downloads` | Standard-Download-Verzeichnis | ✅ Ja |
| `/animes` | Anime-Pfad (bei `storage.mode: separate`) | Optional |
| `/serien` | Serien-Pfad (bei `storage.mode: separate`) | Optional |

> **Wichtig:** Ohne gemountete Volumes gehen Datenbank und Downloads bei Container-Neustart verloren!

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
  anime_path: /app/Downloads/Anime
  series_path: /app/Downloads/Serien
  anime_movies_path: /app/Downloads/Anime-Filme
  serien_movies_path: /app/Downloads/Serien-Filme
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

**Separate** (`storage.mode: separate`): Anime und Serien werden in verschiedene Ordner sortiert. Dafür zusätzliche Volumes mounten:

```yaml
volumes:
  - ./data:/app/data
  - /mnt/media/anime:/animes
  - /mnt/media/serien:/serien
```

Und in der Config die Pfade entsprechend setzen:
```yaml
storage:
  mode: separate
  anime_path: /animes
  series_path: /serien
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

1. **Docker Template** über Community Applications oder manuell erstellen
2. **Repository:** `wimwamwom/aniloader:latest`
3. **Icon URL:** `https://raw.githubusercontent.com/WimWamWom/AniLoader/main/web/static/AniLoader.png`
4. **Port:** Container `5050` → Host `5050`
5. **Pfade:**

| Container-Pfad | Host-Pfad | Beschreibung |
|---|---|---|
| `/app/data` | `/mnt/user/appdata/aniloader` | Datenbank, Config, Logs |
| `/app/Downloads` | `/mnt/user/data/media/anime` | Download-Verzeichnis |

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
