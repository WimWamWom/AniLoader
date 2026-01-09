
<img src="https://raw.githubusercontent.com/WimWamWom/AniLoader/main/static/AniLoader.png" width="32" align="center"> 
# AniLoader Docker Dokumentation

Diese Anleitung beschreibt die Installation und Konfiguration von AniLoader mit Docker.

## Inhaltsverzeichnis

- [Quick Start](#quick-start)
- [Installation](#installation)
  - [Docker Hub](#docker-hub)
  - [Manueller Build](#manueller-build)
- [Volumes & Pfade](#volumes--pfade)
- [Konfiguration](#konfiguration)
  - [Standard Mode](#standard-mode)
  - [Separate Mode](#separate-mode)
- [Speicherorganisation](#speicherorganisation)
- [Unraid Installation](#unraid-installation)
- [Tampermonkey Browser-Extension](#tampermonkey-browser-extension)
- [Docker Hub Upload](#docker-hub-upload)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

### Docker Run
```bash
docker run -d \
  --name aniloader \
  -p 5000:5000 \
  -v /path/to/data:/app/data \
  -v /path/to/downloads:/app/Downloads \
  --restart unless-stopped \
  wimwamwom/aniloader:latest
```

### Docker Compose
```yaml
version: '3.8'

services:
  aniloader:
    image: wimwamwom/aniloader:latest
    container_name: aniloader
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data
      - ./Downloads:/app/Downloads
    environment:
      - PYTHONUNBUFFERED=1
    restart: unless-stopped
```

---

## Installation

### Docker Hub

Das Image ist auf Docker Hub verfügbar:
```bash
docker pull wimwamwom/aniloader:latest
```

### Manueller Build

```bash
# Repository klonen
git clone https://github.com/WimWamWom/AniLoader
cd AniLoader

# Image bauen
docker build -t aniloader:latest .

# Optional: Lokal testen
docker run -d -p 5000:5000 \
  -v ${PWD}/data:/app/data \
  -v ${PWD}/Downloads:/app/Downloads \
  --name aniloader-test aniloader:latest
```

---

## Volumes & Pfade

| Container Path | Beschreibung | Erforderlich |
|---------------|--------------|--------------|
| `/app/data` | Datenbank & Konfiguration | ✅ Ja |
| `/app/Downloads` | Standard Download-Verzeichnis | ✅ Ja |
| `/movies` | Filme (nur bei `storage_mode: separate`) | ❌ Optional |
| `/series` | Serien (nur bei `storage_mode: separate`) | ❌ Optional |
| `/animes` | Animes (nur bei `storage_mode: separate`) | ❌ Optional |

---

## Konfiguration

Erstelle eine `config.json` im Data-Volume (`/app/data/config.json`):

```json
{
  "languages": ["German Dub", "German Sub", "English Dub", "English Sub"],
  "min_free_gb": 2.0,
  "download_path": "",
  "autostart_mode": null,
  "refresh_titles": true,
  "storage_mode": "standard",
  "movies_path": "",
  "series_path": "",
  "server_port": 5000
}
```

### Standard Mode

Alle Downloads landen in `/app/Downloads`:

```json
{
  "storage_mode": "standard",
  "download_path": "/app/Downloads"
}
```

**Struktur:**
```
Downloads/
  ├── Demon Slayer/
  │   ├── Filme/
  │   └── Staffel 1/
  └── Attack on Titan/
```

### Separate Mode

Filme und Serien/Animes getrennt speichern:

```json
{
  "storage_mode": "separate",
  "anime_path": "/animes",
  "serien_path": "/series",
  "anime_separate_movies": false,
  "serien_separate_movies": false
}
```

**docker-compose.yml für Separate Mode:**
```yaml
version: '3.8'

services:
  aniloader:
    image: wimwamwom/aniloader:latest
    container_name: aniloader
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data
      - /mnt/media/Animes:/animes
      - /mnt/media/Serien:/series
    restart: unless-stopped
```

---

## Speicherorganisation

AniLoader erkennt automatisch den Content-Type:
- **Animes:** URLs von `aniworld.to`
- **Serien:** URLs von `s.to`

### Ordnerstruktur-Optionen

**Standard (Filme im Serienordner):**
```
Animes/
  └── Demon Slayer/
      ├── Filme/
      │   └── Film01 - Mugen Train.mp4
      └── Staffel 1/
          └── S01E01 - Episode.mp4
```

**Mit Film-Trennung (`anime_separate_movies: true`):**
```
Animes/
  ├── Filme/
  │   └── Demon Slayer/
  │       └── Film01 - Mugen Train.mp4
  └── Demon Slayer/
      └── Staffel 1/
          └── S01E01 - Episode.mp4
```

---

## Unraid Installation

### Via Docker Hub

1. Öffne **Unraid WebUI** → **Docker** Tab
2. Klicke **Add Container**
3. Konfiguration:

| Feld | Wert |
|------|------|
| Name | `aniloader` |
| Repository | `wimwamwom/aniloader:latest` |
| Network Type | `bridge` |

**Port Mapping:**
| Container Port | Host Port |
|----------------|-----------|
| `5000` | `5000` |

**Volume Mappings:**

| Container Path | Host Path |
|----------------|-----------|
| `/app/data` | `/mnt/user/appdata/aniloader/data` |
| `/app/Downloads` | `/mnt/user/Downloads/AniLoader` |
| `/animes` (optional) | `/mnt/user/Anime` |
| `/series` (optional) | `/mnt/user/TV Shows` |

4. Klicke **Apply**

### Via docker-compose

1. Installiere **Compose Manager** Plugin via Community Applications
2. Kopiere `docker-compose.yml` nach `/mnt/user/appdata/aniloader/`
3. Passe Pfade an
4. Starte via Compose Manager

---

## Tampermonkey Browser-Extension

Das Tampermonkey-Skript fügt einen "📤 Downloaden"-Button auf AniWorld.to und S.to hinzu.

### Installation

1. Installiere [Tampermonkey](https://www.tampermonkey.net/) für deinen Browser
2. Installiere das Skript: [Tampermonkey.user.js](https://github.com/WimWamWom/AniLoader/raw/refs/heads/main/Tampermonkey.user.js)
3. Passe die Server-Konfiguration an:

```javascript
// Im Skript oben anpassen:
const SERVER_IP = "192.168.1.100";  // Deine Server-IP
const SERVER_PORT = 5000;            // Dein Port
```

### Button-Status

| Button | Bedeutung |
|--------|-----------|
| 📤 Downloaden | Noch nicht in AniLoader |
| 📄 In der Liste | Bereits hinzugefügt |
| ⬇️ Downloaded | Wird gerade geladen |
| ✅ Gedownloaded | Download komplett |
| ⛔ Server offline | Server nicht erreichbar |

### Troubleshooting

**"Server offline" obwohl Server läuft:**
- Prüfe IP und Port im Skript
- Teste manuell: `http://SERVER_IP:PORT/status`

**CORS-Fehler:**
- Seit Version 1.5 behoben
- Docker-Container neu starten: `docker restart aniloader`
- Browser-Cache leeren (Strg+F5)

---

## Docker Hub Upload

### Image zu Docker Hub hochladen

```bash
# 1. Bei Docker Hub anmelden
docker login

# 2. Image taggen
docker tag aniloader:latest deinusername/aniloader:latest

# 3. Image pushen
docker push deinusername/aniloader:latest
```

### Automatische Builds mit GitHub Actions

Das Repository enthält einen GitHub Actions Workflow (`.github/workflows/docker-build.yml`), der bei jedem Push automatisch ein neues Image baut und zu Docker Hub pusht.

**Erforderliche GitHub Secrets:**
- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`

---

## Troubleshooting

### Container startet nicht
```bash
docker logs aniloader
```

### Permission-Probleme
```bash
# Auf Unraid
chown -R nobody:users /mnt/user/appdata/aniloader
chmod -R 755 /mnt/user/appdata/aniloader
chmod -R 755 /mnt/user/Downloads/AniLoader
```

### Download funktioniert nicht
```bash
# Prüfe aniworld CLI
docker exec aniloader aniworld --version

# Live-Logs
docker logs -f aniloader
```

### Webinterface nicht erreichbar
- Prüfe Port-Mapping
- Prüfe Firewall-Einstellungen
- Prüfe ob Port in config.json mit Container-Port übereinstimmt

### Health Check Status
```bash
docker inspect --format='{{.State.Health.Status}}' aniloader
```

---

## Environment Variables

| Variable | Beschreibung | Default |
|----------|--------------|---------|
| `PYTHONUNBUFFERED` | Python Output Buffering | `1` |

---

## Links

- [GitHub Repository](https://github.com/WimWamWom/AniLoader)
- [Docker Hub](https://hub.docker.com/r/wimwamwom/aniloader)
- [Haupt-README](README.md)
