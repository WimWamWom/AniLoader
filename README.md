<p align="center">
  <img src="web/static/AniLoader.png" alt="AniLoader Logo" width="200">
</p>

<h1 align="center">AniLoader</h1>

<p align="center">
  <strong>Anime &amp; Serien Download-Manager mit Web-Interface</strong><br>
  Automatisches Herunterladen von Anime und Serien von aniworld.to und s.to<br>
  mit Jellyfin-kompatibler Ordnerstruktur.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/Unraid-compatible-F15A2C?logo=unraid&logoColor=white" alt="Unraid">
</p>

---

## Inhaltsverzeichnis

- [Features](#features)
- [Screenshots](#screenshots)
- [Voraussetzungen](#voraussetzungen)
- [Installation](#installation)
  - [Lokal (Windows / Linux)](#lokal-windows--linux)
  - [Docker / Docker Compose](#docker--docker-compose)
  - [Unraid](#unraid)
- [Konfiguration](#konfiguration)
  - [config.yaml](#configyaml)
  - [Speicher-Modi](#speicher-modi)
  - [Sprachpriorität](#sprachpriorität)
- [Benutzung](#benutzung)
  - [Web-Interface](#web-interface)
  - [Download-Modi](#download-modi)
  - [Serien hinzufügen](#serien-hinzufügen)
  - [Tampermonkey Browser-Skript](#tampermonkey-browser-skript)
- [API-Referenz](#api-referenz)
- [Projektstruktur](#projektstruktur)
- [Technische Details](#technische-details)
- [FAQ / Fehlerbehebung](#faq--fehlerbehebung)

---

## Features

| Feature | Beschreibung |
|---|---|
| 🌐 **Web-Interface** | Dark-Theme Web-UI mit 4 Tabs – Download, Hinzufügen, Datenbank, Einstellungen |
| 📥 **4 Download-Modi** | Standard, German, Neue Episoden, Integritäts-Check |
| 🔍 **Integrierte Suche** | Durchsuche aniworld.to und s.to direkt aus dem Interface |
| 🇩🇪 **Sprachpriorität** | Konfigurierbare Sprachreihenfolge mit automatischem Fallback |
| 📁 **Jellyfin-kompatibel** | Automatische Ordnerstruktur `Title (Year) [imdbid-xxx]/Season ss/` |
| 💾 **SQLite Datenbank** | Verwaltet alle Serien mit Status, Fortschritt und fehlenden Episoden |
| 🔒 **DNS-over-HTTPS** | Umgeht ISP-DNS-Sperren automatisch über Google DoH |
| 🐋 **Docker & Unraid** | Fertige Docker-Images mit Health-Check und Volume-Mounts |
| 🧩 **Tampermonkey-Skript** | Ein-Klick-Download direkt von der aniworld.to / s.to Seite |
| 📊 **Live-Status** | Echtzeit-Fortschritt mit Auto-Polling im Browser |
| 📤 **Bulk-Import** | TXT-Datei hochladen oder Drag & Drop für viele URLs auf einmal |
| ⚙️ **YAML Konfiguration** | Alle Einstellungen über Web-UI oder `config.yaml` änderbar |

---

## Screenshots

> Das Web-Interface ist unter `http://<ip>:5050` erreichbar und bietet 4 Tabs:

### Download-Tab
- **Steuerung**: 4 Download-Modi starten / stoppen
- **Live-Status**: Aktuelle Serie, Staffel, Episode, Modus
- **Fortschritt**: Heruntergeladen / Übersprungen / Fehlgeschlagen
- **Log-Ausgabe**: Echtzeit-Log des aktuellen Laufs

### Hinzufügen-Tab
- **Link einfügen**: Einzelne URL hinzufügen
- **TXT-Upload**: Datei mit URLs hochladen (Drag & Drop)
- **Suche**: Direkt nach Animes/Serien suchen (Plattform wählbar)

### Datenbank-Tab
- **Übersichtstabelle**: Alle Serien mit Status, Typ, DE-Verfügbarkeit, Fortschritt
- **Sortierung**: Klick auf Spaltenköpfe zum Sortieren
- **Filter**: Suchfeld + „Gelöschte anzeigen" Toggle
- **Aktionen**: Löschen / Wiederherstellen pro Eintrag

### Einstellungen-Tab
- **Server-Port**: Anpassbar
- **Sprachpriorität**: Drag & Drop Reihenfolge
- **Speicher-Modus**: Standard oder separate Pfade
- **Download-Einstellungen**: Min. freier Speicher, Timeout, Autostart

---

## Voraussetzungen

### Lokal
- **Python 3.11+**
- **ffmpeg** (wird von `aniworld` CLI benötigt)
- **aniworld** (wird automatisch über `requirements.txt` installiert)

### Docker
- **Docker** und **Docker Compose**
- Sonst nichts – alles ist im Image enthalten

---

## Installation

### Lokal (Windows / Linux)

```bash
# 1. Repository klonen
git clone https://github.com/WimWamWom/AniLoader.git
cd AniLoader/claude-code

# 2. Virtuelle Umgebung erstellen (empfohlen)
python -m venv venv

# Windows:
venv\Scripts\activate

# Linux/Mac:
source venv/bin/activate

# 3. Abhängigkeiten installieren
pip install -r requirements.txt

# 4. ffmpeg installieren (falls noch nicht vorhanden)
# Windows: https://www.gyan.dev/ffmpeg/builds/ → PATH hinzufügen
# Linux:   sudo apt install ffmpeg
# Mac:     brew install ffmpeg

# 5. Starten
python main.py
```

Der Server startet auf `http://localhost:5050`.

### Docker / Docker Compose

```bash
# 1. Repository klonen
git clone https://github.com/WimWamWom/AniLoader.git
cd AniLoader/claude-code

# 2. Bauen und starten
docker compose up -d

# Logs anzeigen
docker compose logs -f
```

**docker-compose.yml** anpassen:
```yaml
services:
  aniloader:
    build: .
    container_name: aniloader
    ports:
      - "5050:5050"          # Port nach Bedarf ändern
    volumes:
      - ./data:/app/data      # DB, Config, Logs
      - ./Downloads:/app/Downloads  # Standard-Download-Ordner
      # Separate Pfade (optional):
      # - /mnt/media/anime:/animes
      # - /mnt/media/serien:/serien
    environment:
      - PYTHONUNBUFFERED=1
    restart: unless-stopped
```

### Unraid

1. **Docker Template** über Community Applications oder manuell erstellen
2. **Repository**: `https://github.com/WimWamWom/AniLoader`
3. **Ports**: Container-Port `5050` → Host-Port `5050`
4. **Pfade**:

| Container-Pfad | Host-Pfad | Beschreibung |
|---|---|---|
| `/app/data` | `/mnt/user/appdata/aniloader` | Datenbank, Config, Logs |
| `/app/Downloads` | `/mnt/user/data/media/anime` | Download-Verzeichnis |

5. **Icon URL**: `https://raw.githubusercontent.com/WimWamWom/AniLoader/main/static/AniLoader.png`

---

## Konfiguration

AniLoader erstellt beim ersten Start automatisch eine `config.yaml` im `data/` Ordner. Alle Einstellungen können über das Web-Interface (Tab „Einstellungen") oder direkt in der Datei geändert werden.

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
  min_free_gb: 2.0                  # Mindest-Speicherplatz (GB)
  autostart_mode: null              # null | default | german | new | check
  timeout_seconds: 900              # Timeout pro Episode (Sekunden)

data:
  folder: /app/data                 # Pfad für DB, Logs, Config
```

### Speicher-Modi

#### Standard-Modus (`storage.mode: standard`)
Alle Downloads landen in **einem Ordner** (`storage.download_path`):
```
Downloads/
├── Naruto (2002) [imdbid-tt0409591]/
│   ├── Season 01/
│   │   ├── Naruto S01E001.mkv
│   │   └── ...
│   └── Season 02/
└── Breaking Bad (2008) [imdbid-tt0903747]/
    ├── Season 01/
    └── ...
```

#### Separate-Modus (`storage.mode: separate`)
Anime und Serien werden in **verschiedene Ordner** sortiert. Optional können Filme nochmal separat gespeichert werden:
```
Anime/
├── Naruto (2002) [imdbid-tt0409591]/
│   ├── Season 00/   ← Filme
│   ├── Season 01/
│   └── ...

Serien/
├── Breaking Bad (2008) [imdbid-tt0903747]/
│   └── ...

Anime-Filme/      ← Optional (anime_separate_movies: true)
├── Naruto (2002) [imdbid-tt0409591]/
│   └── Season 00/
```

### Sprachpriorität

Die Sprachen in der Liste werden **von oben nach unten** durchprobiert. Wenn die erste Sprache für eine Episode nicht verfügbar ist, wird die nächste versucht.

| Sprache | Beschreibung |
|---|---|
| `German Dub` | Deutsche Synchronfassung |
| `German Sub` | Japanisch/Englisch mit deutschen Untertiteln |
| `English Sub` | Japanisch mit englischen Untertiteln |
| `English Dub` | Englische Synchronfassung |

Die Reihenfolge kann im Web-Interface per **Drag & Drop** geändert werden.

---

## Benutzung

### Web-Interface

Nach dem Start ist das Interface unter `http://localhost:5050` (oder konfiguriertem Port) erreichbar.

<p align="center">
  <img src="web/static/AniLoader.png" alt="AniLoader" width="80">
</p>

### Download-Modi

AniLoader bietet 4 Download-Modi, die jeweils einen unterschiedlichen Zweck erfüllen:

#### ▶ Standard (`default`)
- Lädt **alle nicht-vollständigen** Serien aus der Datenbank herunter
- Nutzt die konfigurierte Sprachpriorität mit automatischem Fallback
- Markiert Serien nach Abschluss als „komplett"
- Speichert den Fortschritt (letzte Staffel/Episode) in der DB
- Trackt fehlende deutsche Episoden für den German-Modus

#### 🇩🇪 German (`german`)
- Prüft alle Serien auf **fehlende deutsche Episoden**
- Versucht, fehlende Videos in „German Dub" erneut herunterzuladen
- Nützlich, wenn deutsche Synchros nachträglich erscheinen
- Markiert `deutsch_komplett` in der DB wenn alles da ist

#### 🆕 Neue Episoden (`new`)
- Prüft **alle Serien** (auch vollständige) auf neue Episoden
- Vergleicht mit dem zuletzt gespeicherten Stand (Staffel/Episode)
- Ideal als regelmäßiger Cronjob / Autostart

#### 🔍 Check (`check`)
- **Integritätsprüfung** aller Downloads
- Prüft: Datei existiert? Größe > 1 MB? Keine .part/.temp-Dateien?
- Defekte oder fehlende Dateien werden automatisch erneut heruntergeladen

### Serien hinzufügen

Es gibt **4 Wege**, Serien zur Datenbank hinzuzufügen:

1. **Web-UI → Link einfügen**: URL direkt eingeben
2. **Web-UI → TXT-Upload**: Textdatei mit einer URL pro Zeile hochladen (Drag & Drop)
3. **Web-UI → Suche**: Nach Titel suchen und per Klick hinzufügen
4. **Tampermonkey-Skript**: Button direkt auf aniworld.to / s.to

**Unterstützte URL-Formate:**
```
https://aniworld.to/anime/stream/naruto
https://aniworld.to/anime/stream/naruto/staffel-1
https://s.to/serie/stream/breaking-bad
https://s.to/serie/stream/breaking-bad/staffel-2
```

### Tampermonkey Browser-Skript

Das Tampermonkey-Skript fügt auf jeder Serien-Seite von aniworld.to und s.to einen **Download-Button** ein.

#### Installation

1. **Tampermonkey** Browser-Extension installieren:
   - [Chrome](https://chrome.google.com/webstore/detail/tampermonkey/dhdgffkkebhmkfjojejmpbldmpobfkfo)
   - [Firefox](https://addons.mozilla.org/de/firefox/addon/tampermonkey/)
   - [Edge](https://microsoftedge.microsoft.com/addons/detail/tampermonkey/iikmkjmpaadaobahmlepeloendndfphd)

2. **Skript installieren**: `Tampermonkey.user.js` öffnen → „Install"

3. **Server-Adresse konfigurieren** – im Skript die Verbindungsdaten anpassen:

```javascript
// Option A: Domain (z.B. hinter Reverse Proxy)
const USE_DOMAIN    = true;
const SERVER_DOMAIN = "aniloader.example.com";
const USE_HTTPS     = true;

// Option B: Direkte IP (z.B. im lokalen Netzwerk)
const USE_DOMAIN    = false;
const SERVER_IP     = "192.168.1.100";
const SERVER_PORT   = 5050;

// Basic-Auth (optional, falls hinter nginx mit Passwortschutz)
const USE_AUTH  = false;
const AUTH_USER = "";
const AUTH_PASS = "";
```

#### Button-Zustände

| Button | Bedeutung |
|---|---|
| 📤 **Downloaden** | Serie noch nicht in der DB – Klick fügt hinzu & startet Download |
| 📄 **In der Liste** | Serie ist in der DB, wartet auf Download |
| ⬇️ **Wird geladen…** | Wird gerade heruntergeladen |
| ✅ **Gedownloaded** | Alle Episoden komplett |
| ⛔ **Server offline** | AniLoader-Server nicht erreichbar |

---

## API-Referenz

AniLoader stellt eine REST-API bereit, die auch vom Web-Interface und dem Tampermonkey-Skript genutzt wird. Swagger-Docs sind verfügbar unter `http://localhost:5050/docs`.

### Endpunkte

| Methode | Pfad | Beschreibung |
|---|---|---|
| `GET` | `/` | Web-Interface (HTML) |
| `GET` | `/health` | Health-Check (`{"status": "ok"}`) |
| `GET` | `/status` | Aktueller Download-Status |
| `POST` | `/start_download` | Download starten (`{"mode": "default"}`) |
| `GET` | `/start_download?mode=default` | Download starten (GET-Variante) |
| `POST` | `/stop_download` | Download stoppen |
| `GET` | `/database` | Alle Einträge (`?q=`, `?sort=`, `?dir=`, `?include_deleted=`) |
| `GET` | `/database/stats` | DB-Statistiken |
| `POST` | `/export` | URL hinzufügen (`{"url": "..."}`) – Tampermonkey-kompatibel |
| `POST` | `/add_link` | URL hinzufügen (Web-UI) |
| `DELETE` | `/anime/{id}` | Eintrag löschen (`?hard=true` für permanentes Löschen) |
| `POST` | `/anime/{id}/restore` | Gelöschten Eintrag wiederherstellen |
| `PUT` | `/anime/{id}` | Eintrag aktualisieren |
| `POST` | `/upload_txt` | TXT-Datei mit URLs importieren (multipart/form-data) |
| `POST` | `/search` | Suche (`{"query": "...", "platform": "both"}`) |
| `GET` | `/config` | Aktuelle Konfiguration |
| `POST` | `/config` | Konfiguration aktualisieren |
| `GET` | `/disk` | Freier Speicherplatz |
| `GET` | `/logs` | Alle Logs |
| `GET` | `/last_run` | Log des letzten/aktuellen Laufs |
| `GET` | `/counts/{id}` | Episoden-Zählung auf der Festplatte |

### Beispiele

```bash
# Status abfragen
curl http://localhost:5050/status

# Download starten
curl -X POST http://localhost:5050/start_download \
  -H "Content-Type: application/json" \
  -d '{"mode": "default"}'

# URL hinzufügen
curl -X POST http://localhost:5050/export \
  -H "Content-Type: application/json" \
  -d '{"url": "https://aniworld.to/anime/stream/naruto"}'

# Suchen
curl -X POST http://localhost:5050/search \
  -H "Content-Type: application/json" \
  -d '{"query": "naruto", "platform": "aniworld"}'
```

---

## Projektstruktur

```
claude-code/
├── main.py                      # Einstiegspunkt – startet Uvicorn
├── requirements.txt             # Python-Abhängigkeiten
├── Dockerfile                   # Multi-stage Docker Build
├── docker-compose.yml           # Docker Compose Konfiguration
├── Tampermonkey.user.js         # Browser-Erweiterung v2.0
├── README.md                    # Diese Datei
│
├── app/                         # Python-Backend
│   ├── __init__.py
│   ├── __main__.py              # python -m app
│   ├── config.py                # YAML-Konfigurationsmanagement
│   ├── logger.py                # Thread-safe Logging-System
│   ├── database.py              # SQLite CRUD-Operationen
│   ├── scraper.py               # HTML-Scraper (aniworld.to + s.to)
│   ├── file_manager.py          # Dateipfade & Integritätsprüfung
│   ├── downloader.py            # Download-Orchestrierung (4 Modi)
│   └── api/
│       ├── __init__.py
│       ├── server.py            # FastAPI App Factory & Lifespan
│       └── routes.py            # Alle REST-API Endpunkte
│
├── web/                         # Frontend
│   ├── static/
│   │   ├── AniLoader.png        # Logo / Icon
│   │   ├── style.css            # Dark-Theme Styles
│   │   └── app.js               # Vanilla JS Client-Logik
│   └── templates/
│       └── index.html           # Single-Page Web-Interface
│
└── data/                        # (wird zur Laufzeit erstellt)
    ├── config.yaml              # Konfiguration
    ├── AniLoader.db             # SQLite Datenbank
    ├── last_run.txt             # Log des aktuellen Laufs
    └── all_logs.txt             # Gesamte Log-History
```

---

## Technische Details

### Architektur

| Komponente | Technologie | Zweck |
|---|---|---|
| Web-Framework | **FastAPI** + Uvicorn | Async HTTP-Server mit Auto-Docs |
| Downloads | **aniworld CLI** (Subprocess) | Bleibt automatisch aktuell via pip |
| HTTP-Client | **niquests** mit DoH | DNS-over-HTTPS umgeht ISP-Sperren |
| HTML-Parsing | **BeautifulSoup** + lxml | Scraping der Serien-Seiten |
| Datenbank | **SQLite** (WAL-Modus) | Thread-safe, kein externer Server nötig |
| Konfiguration | **YAML** (PyYAML) | Menschenlesbar, atomares Speichern |
| Frontend | **Vanilla JS** + CSS | Kein Framework, kein Build-Step |

### Datenbank-Schema

Eine einzige Tabelle `anime`:

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | INTEGER PK | Auto-Increment ID |
| `title` | TEXT | Serien-Titel |
| `url` | TEXT UNIQUE | Serien-URL |
| `complete` | INTEGER | 0/1 – Alle Episoden heruntergeladen? |
| `deutsch_komplett` | INTEGER | 0/1 – Alle deutschen Episoden vorhanden? |
| `deleted` | INTEGER | 0/1 – Soft-Delete |
| `fehlende_deutsch_folgen` | TEXT (JSON) | Liste fehlender deutscher Episode-URLs |
| `last_film` | INTEGER | Letzte heruntergeladene Film-Nummer |
| `last_episode` | INTEGER | Letzte heruntergeladene Episode-Nummer |
| `last_season` | INTEGER | Letzte heruntergeladene Staffel-Nummer |
| `folder_name` | TEXT | Jellyfin-Ordnername (z.B. `Title (2020) [imdbid-xxx]`) |

### Sprach-Erkennung

AniLoader erkennt Sprachen über die **Flag-Images** auf den Serien-Seiten:

| Flag-Datei | Sprache |
|---|---|
| `german.svg` | German Dub |
| `japanese-german.svg` | German Sub |
| `japanese-english.svg` | English Sub |
| `english.svg` | English Dub |

Wenn Sprachinformationen auf der Staffelseite nicht verfügbar sind (häufig bei s.to), wird die **Episoden-Seite** einzeln abgefragt. Falls auch dort keine Info vorhanden ist, werden alle konfigurierten Sprachen der Reihe nach durchprobiert (Kaskade).

### DNS-over-HTTPS

AniLoader nutzt **niquests** mit Google DNS-over-HTTPS (`doh+google://`) als Resolver. Das umgeht DNS-Sperren von Internet-Providern, die aniworld.to und s.to blockieren, ohne dass ein VPN nötig ist.

---

## FAQ / Fehlerbehebung

### Der Server startet, aber ich sehe im Browser nichts
- Prüfe ob Port 5050 bereits belegt ist: `netstat -an | findstr 5050` (Windows) bzw. `ss -tlnp | grep 5050` (Linux)
- Ändere den Port in der `config.yaml` oder im Einstellungen-Tab

### Downloads funktionieren nicht
- Prüfe ob `aniworld` installiert ist: `aniworld --help`
- Prüfe ob `ffmpeg` im PATH ist: `ffmpeg -version`
- Schau in die Logs (Download-Tab oder `data/last_run.txt`)

### „DNS-Fehler" oder Seite nicht erreichbar
- AniLoader nutzt DNS-over-HTTPS (Google) automatisch
- Falls das nicht funktioniert, prüfe die Firewall-Einstellungen für ausgehende HTTPS-Verbindungen

### Tampermonkey-Skript zeigt „Server offline"
- Stelle sicher, dass der AniLoader-Server läuft
- Prüfe die `SERVER_IP` und `SERVER_PORT` im Skript
- Bei Reverse-Proxy: `USE_DOMAIN = true` und korrekte Domain eintragen
- Browser-Konsole prüfen (F12) für detaillierte Fehlermeldungen

### Docker: „Permission denied" für Download-Ordner
```bash
# Host-Ordner mit korrekten Rechten erstellen
mkdir -p data Downloads
chmod 777 Downloads
```

### Wie kann ich den Autostart aktivieren?
In der `config.yaml` oder im Einstellungen-Tab:
```yaml
download:
  autostart_mode: default   # oder: german, new, check
```
Beim nächsten Server-Start wird der gewählte Modus automatisch gestartet.

### Wie funktioniert der Check-Modus?
Check prüft **alle** existierenden Downloads:
1. Für jede Serie werden alle bekannten Staffeln/Episoden abgefragt
2. Für jede Episode wird geprüft: Datei vorhanden? > 1 MB? Keine .part-Datei?
3. Fehlende oder defekte Dateien werden erneut heruntergeladen

---

<p align="center">
  <img src="web/static/AniLoader.png" alt="AniLoader" width="60"><br>
  <sub>Made with ❤️ for Anime & Serien</sub>
</p>
