
<img src="https://raw.githubusercontent.com/WimWamWom/AniLoader/main/static/AniLoader.png" width="32" align="center"> 
# AniLoader Docker Documentation

This guide covers installation and configuration of AniLoader with Docker.

## Table of Contents

- [Quick Start](#quick-start)
- [Installation](#installation)
  - [Docker Hub](#docker-hub)
  - [Manual Build](#manual-build)
- [Volumes & Paths](#volumes--paths)
- [Configuration](#configuration)
  - [Standard Mode](#standard-mode)
  - [Separate Mode](#separate-mode)
- [Storage Organization](#storage-organization)
- [Unraid Installation](#unraid-installation)
- [Tampermonkey Browser Extension](#tampermonkey-browser-extension)
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

The image is available on Docker Hub:
```bash
docker pull wimwamwom/aniloader:latest
```

### Manual Build

```bash
# Clone repository
git clone https://github.com/WimWamWom/AniLoader
cd AniLoader

# Build image
docker build -t aniloader:latest .

# Optional: Test locally
docker run -d -p 5000:5000 \
  -v ${PWD}/data:/app/data \
  -v ${PWD}/Downloads:/app/Downloads \
  --name aniloader-test aniloader:latest
```

---

## Volumes & Paths

| Container Path | Description | Required |
|---------------|-------------|----------|
| `/app/data` | Database & configuration | ✅ Yes |
| `/app/Downloads` | Default download directory | ✅ Yes |
| `/movies` | Movies (only with `storage_mode: separate`) | ❌ Optional |
| `/series` | Series (only with `storage_mode: separate`) | ❌ Optional |
| `/animes` | Animes (only with `storage_mode: separate`) | ❌ Optional |

---

## Configuration

Create a `config.json` in the data volume (`/app/data/config.json`):

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

All downloads go to `/app/Downloads`:

```json
{
  "storage_mode": "standard",
  "download_path": "/app/Downloads"
}
```

**Structure:**
```
Downloads/
  ├── Demon Slayer/
  │   ├── Filme/
  │   └── Staffel 1/
  └── Attack on Titan/
```

### Separate Mode

Store movies and series/animes separately:

```json
{
  "storage_mode": "separate",
  "anime_path": "/animes",
  "serien_path": "/series",
  "anime_separate_movies": false,
  "serien_separate_movies": false
}
```

**docker-compose.yml for Separate Mode:**
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
      - /mnt/media/Series:/series
    restart: unless-stopped
```

---

## Storage Organization

AniLoader automatically detects content type:
- **Animes:** URLs from `aniworld.to`
- **Series:** URLs from `s.to`

### Folder Structure Options

**Standard (movies inside series folder):**
```
Animes/
  └── Demon Slayer/
      ├── Filme/
      │   └── Film01 - Mugen Train.mp4
      └── Staffel 1/
          └── S01E01 - Episode.mp4
```

**With movie separation (`anime_separate_movies: true`):**
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

1. Open **Unraid WebUI** → **Docker** Tab
2. Click **Add Container**
3. Configuration:

| Field | Value |
|-------|-------|
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

4. Click **Apply**

### Via docker-compose

1. Install **Compose Manager** Plugin via Community Applications
2. Copy `docker-compose.yml` to `/mnt/user/appdata/aniloader/`
3. Adjust paths
4. Start via Compose Manager

---

## Tampermonkey Browser Extension

The Tampermonkey script adds a "📤 Download" button on AniWorld.to and S.to pages.

### Installation

1. Install [Tampermonkey](https://www.tampermonkey.net/) for your browser
2. Install the script: [Tampermonkey.user.js](https://github.com/WimWamWom/AniLoader/raw/refs/heads/main/Tampermonkey.user.js)
3. Adjust server configuration:

```javascript
// Adjust at the top of the script:
const SERVER_IP = "192.168.1.100";  // Your server IP
const SERVER_PORT = 5000;            // Your port
```

### Button States

| Button | Meaning |
|--------|---------|
| 📤 Downloaden | Not yet in AniLoader |
| 📄 In der Liste | Already added |
| ⬇️ Downloaded | Currently downloading |
| ✅ Gedownloaded | Download complete |
| ⛔ Server offline | Server unreachable |

### Troubleshooting

**"Server offline" even though server is running:**
- Check IP and port in script
- Test manually: `http://SERVER_IP:PORT/status`

**CORS errors:**
- Fixed since version 1.5
- Restart Docker container: `docker restart aniloader`
- Clear browser cache (Ctrl+F5)

---

## Docker Hub Upload

### Upload image to Docker Hub

```bash
# 1. Login to Docker Hub
docker login

# 2. Tag image
docker tag aniloader:latest yourusername/aniloader:latest

# 3. Push image
docker push yourusername/aniloader:latest
```

### Automatic Builds with GitHub Actions

The repository includes a GitHub Actions workflow (`.github/workflows/docker-build.yml`) that automatically builds and pushes a new image on every push.

**Required GitHub Secrets:**
- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`

---

## Troubleshooting

### Container won't start
```bash
docker logs aniloader
```

### Permission issues
```bash
# On Unraid
chown -R nobody:users /mnt/user/appdata/aniloader
chmod -R 755 /mnt/user/appdata/aniloader
chmod -R 755 /mnt/user/Downloads/AniLoader
```

### Downloads not working
```bash
# Check aniworld CLI
docker exec aniloader aniworld --version

# Live logs
docker logs -f aniloader
```

### Web interface not accessible
- Check port mapping
- Check firewall settings
- Verify port in config.json matches container port

### Health Check Status
```bash
docker inspect --format='{{.State.Health.Status}}' aniloader
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PYTHONUNBUFFERED` | Python Output Buffering | `1` |

---

## Links

- [GitHub Repository](https://github.com/WimWamWom/AniLoader)
- [Docker Hub](https://hub.docker.com/r/wimwamwom/aniloader)
- [Main README](README_en.md)
