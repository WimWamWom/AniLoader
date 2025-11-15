# AniLoader - Anime Download Manager

![AniLoader Logo](https://raw.githubusercontent.com/WimWamWom/AniLoader/main/static/AniLoader.png)

Automatischer Anime-Download-Manager mit Web-Interface für AniWorld.to

## 🚀 Quick Start

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

## 📦 Volumes

| Container Path | Beschreibung | Erforderlich |
|---------------|--------------|--------------|
| `/app/data` | Datenbank & Konfiguration | ✅ Ja |
| `/app/Downloads` | Standard Download-Verzeichnis | ✅ Ja |
| `/movies` | Filme (nur bei `storage_mode: separate`) | ❌ Optional |
| `/series` | Serien (nur bei `storage_mode: separate`) | ❌ Optional |

## 🔧 Konfiguration

Erstelle eine `config.json` im Data-Volume:

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

### Storage Modes

**Standard Mode:** Alle Downloads in `/app/Downloads`
```json
{
  "storage_mode": "standard"
}
```

**Separate Mode:** Filme und Serien getrennt
```json
{
  "storage_mode": "separate",
  "movies_path": "/movies",
  "series_path": "/series"
}
```

## 🌐 Web-Interface

Nach dem Start erreichbar unter: `http://localhost:5000`

### Features:
- 📥 Anime hinzufügen (URL oder TXT-Upload)
- ⬇️ Automatische Downloads in mehreren Sprachen
- 📊 Echtzeit-Download-Status
- 🔍 Fehlende deutsche Folgen tracken
- 🗂️ Flexible Speicheroptionen

## 🐳 Unraid Installation

1. **Docker Hub Methode:**
   - Community Applications → Search: "AniLoader"
   - Oder manuell: `wimwamwom/aniloader:latest`

2. **Wichtige Pfade:**
   - Config/Data: `/mnt/user/appdata/aniloader/data`
   - Downloads: `/mnt/user/Downloads/AniLoader`
   - Port: `5000` (anpassbar)

## 📝 Environment Variables

| Variable | Beschreibung | Default |
|----------|--------------|---------|
| `PYTHONUNBUFFERED` | Python Output Buffering | `1` |

## 🔍 Health Check

Container verfügt über einen Health Check:
- Interval: 30s
- Timeout: 10s
- Retries: 3

Status prüfen:
```bash
docker inspect --format='{{.State.Health.Status}}' aniloader
```

## 📚 Verwendung

1. **Web-Interface öffnen:** `http://your-server:5000`
2. **Anime hinzufügen:** 
   - URL einfügen (z.B. `https://aniworld.to/anime/stream/demon-slayer`)
   - Oder TXT-Datei mit URLs hochladen
3. **Download starten:**
   - Standard Mode (alle Anime)
   - German Mode (nur deutsche Dubs)
   - New Mode (nur neue Folgen)

## 🛠️ Troubleshooting

**Container startet nicht:**
```bash
docker logs aniloader
```

**Permissions-Probleme:**
```bash
# Volumes mit korrekten Rechten erstellen
chmod -R 755 /path/to/data
chmod -R 755 /path/to/Downloads
```

**Download funktioniert nicht:**
- Prüfe ob `aniworld` CLI installiert ist: `docker exec aniloader aniworld --version`
- Prüfe Logs: `docker logs -f aniloader`

## 🔗 Links

- **GitHub:** https://github.com/WimWamWom/AniLoader
- **Issues:** https://github.com/WimWamWom/AniLoader/issues
- **Docker Hub:** https://hub.docker.com/r/wimwamwom/aniloader

## 📄 Lizenz

Siehe [LICENSE](https://github.com/WimWamWom/AniLoader/blob/main/LICENSE)

## 🤝 Support

Bei Fragen oder Problemen öffne bitte ein Issue auf GitHub.
