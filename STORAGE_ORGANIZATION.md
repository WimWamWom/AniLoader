# Erweiterte Speicherorganisation

AniLoader unterstützt jetzt eine flexible Speicherorganisation basierend auf Content-Type (Anime vs. Serie) und Film/Staffel-Trennung.

## Features

### 1. **Content-Type-Erkennung**
- **Animes:** URLs von `aniworld.to` werden automatisch als Animes erkannt
- **Serien:** URLs von `s.to` werden automatisch als Serien erkannt

### 2. **Separate Pfade**
Du kannst separate Speicherorte für Animes und Serien definieren:

**Config-Optionen:**
```json
{
  "storage_mode": "separate",
  "anime_path": "/pfad/zu/animes",
  "serien_path": "/pfad/zu/serien"
}
```

### 3. **Film/Staffel-Organisation**
Pro Content-Type kannst du wählen, ob Filme und Staffeln zusammen oder getrennt gespeichert werden:

**Zusammen (Standard):**
```
Animes/
  └── Demon Slayer/
      ├── Filme/
      │   └── Film01 - Mugen Train.mp4
      └── Staffel 1/
          └── S01E01 - Episode.mp4
```

**Getrennt (mit `anime_separate_movies: true`):**
```
Animes/
  ├── Filme/
  │   └── Demon Slayer/
  │       └── Film01 - Mugen Train.mp4
  └── Demon Slayer/
      └── Staffel 1/
          └── S01E01 - Episode.mp4
```

## Konfiguration

### Config.json Beispiele

#### Standard Mode (alles in Downloads)
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
  ├── Attack on Titan/
  └── ...
```

#### Separate Mode: Animes vs Serien
```json
{
  "storage_mode": "separate",
  "anime_path": "/animes",
  "serien_path": "/serien",
  "anime_separate_movies": false,
  "serien_separate_movies": false
}
```
**Struktur:**
```
/animes/
  ├── Demon Slayer/
  │   ├── Filme/
  │   └── Staffel 1/
  └── Attack on Titan/
/serien/
  └── Breaking Bad/
      └── Staffel 1/
```

#### Separate Mode: Mit Film-Trennung
```json
{
  "storage_mode": "separate",
  "anime_path": "/animes",
  "serien_path": "/serien",
  "anime_separate_movies": true,
  "serien_separate_movies": true
}
```
**Struktur:**
```
/animes/
  ├── Filme/
  │   ├── Demon Slayer/
  │   │   └── Film01 - Mugen Train.mp4
  │   └── One Piece/
  │       └── Film01 - Strong World.mp4
  └── Demon Slayer/
      └── Staffel 1/
/serien/
  ├── Filme/
  │   └── Breaking Bad/
  │       └── Film01 - El Camino.mp4
  └── Breaking Bad/
      └── Staffel 1/
```

## Docker Configuration

### docker-compose.yml

```yaml
version: '3.8'

services:
  aniloader:
    image: wimwamwom/aniloader:latest
    container_name: aniloader
    ports:
      - "5000:5000"
    volumes:
      # Persistente Daten
      - ./data:/app/data
      
      # Standard Mode
      - ./Downloads:/app/Downloads
      
      # Oder: Separate Mode
      - /mnt/media/Animes:/animes
      - /mnt/media/Serien:/serien
    restart: unless-stopped
```

### Unraid Template

**Standard Mode:**
- Container Path: `/app/Downloads`
- Host Path: `/mnt/user/Downloads/AniLoader`

**Separate Mode:**
- Container Path: `/animes`
- Host Path: `/mnt/user/Anime`
- Container Path: `/serien`
- Host Path: `/mnt/user/Serien`

## Config-Optionen Referenz

| Option | Typ | Default | Beschreibung |
|--------|-----|---------|--------------|
| `storage_mode` | string | `"standard"` | `"standard"` oder `"separate"` |
| `download_path` | string | `""` | Basis-Download-Pfad (bei standard mode) |
| `anime_path` | string | `"/app/Downloads/Animes"` | Pfad für Animes (bei separate mode) |
| `serien_path` | string | `"/app/Downloads/Serien"` | Pfad für Serien (bei separate mode) |
| `anime_separate_movies` | boolean | `false` | Filme getrennt von Staffeln bei Animes |
| `serien_separate_movies` | boolean | `false` | Filme getrennt von Staffeln bei Serien |
| `movies_path` | string | `""` | (Deprecated) Alter Film-Pfad |
| `series_path` | string | `""` | (Deprecated) Alter Serien-Pfad |

## Migration von alter zu neuer Config

### Alt (deprecated):
```json
{
  "storage_mode": "separate",
  "movies_path": "/filme",
  "series_path": "/serien"
}
```

### Neu (empfohlen):
```json
{
  "storage_mode": "separate",
  "anime_path": "/animes",
  "serien_path": "/serien",
  "anime_separate_movies": false,
  "serien_separate_movies": false
}
```

**Hinweis:** Die alten `movies_path` und `series_path` werden noch als Fallback unterstützt, aber die neuen Optionen haben Vorrang.

## Beispiel-Workflows

### Workflow 1: Plex/Jellyfin Integration
```json
{
  "storage_mode": "separate",
  "anime_path": "/media/Anime",
  "serien_path": "/media/TV Shows",
  "anime_separate_movies": false,
  "serien_separate_movies": false
}
```

### Workflow 2: Kodi/Emby mit Film-Bibliotheken
```json
{
  "storage_mode": "separate",
  "anime_path": "/media/Anime",
  "serien_path": "/media/Series",
  "anime_separate_movies": true,
  "serien_separate_movies": true
}
```

Dann in Kodi/Emby:
- Anime Serie Bibliothek: `/media/Anime/*` (ohne Filme-Ordner)
- Anime Film Bibliothek: `/media/Anime/Filme/`
- Serien Bibliothek: `/media/Series/*` (ohne Filme-Ordner)
- Film Bibliothek: `/media/Series/Filme/`

## Troubleshooting

### Downloads landen im falschen Ordner
- Prüfe die URL: `aniworld.to` → Animes, `s.to` → Serien
- Prüfe `storage_mode` in config.json
- Prüfe ob Pfade korrekt gesetzt sind

### Filme und Staffeln sind gemischt
- Setze `anime_separate_movies: true` oder `serien_separate_movies: true`
- Bereits heruntergeladene Dateien müssen manuell verschoben werden

### Permissions-Probleme
```bash
# Docker Volumes mit korrekten Rechten
chmod -R 755 /pfad/zu/animes
chmod -R 755 /pfad/zu/serien
```
