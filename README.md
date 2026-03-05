<p align="center">
  <img src="web/static/AniLoader.png" alt="AniLoader Logo" width="200">
</p>

<h1 align="center">AniLoader</h1>

<p align="center">
  <strong>Anime &amp; Serien Download-Manager mit Web-Interface</strong><br>
  Automatisches Herunterladen von aniworld.to und s.to mit Jellyfin-Struktur
</p>

---

## TooLazyToRead

```bash
# Docker (empfohlen)
docker run -d -p 5050:5050 -v ./data:/app/data -v ./Downloads:/app/Downloads wimwamwom/aniloader:latest

# Web-Interface: http://localhost:5050
# 1. Serie suchen/hinzufügen → 2. Download-Modus starten → 3. Fertig
```

---

## Funktionen

- **🌐 Web-Interface:** Dark-Theme mit Live-Status und Poster-Vorschau
- **📥 4 Download-Modi:** Standard, German, New, Check
- **🔍 Suche:** aniworld.to + s.to mit Poster-Anzeige  
- **🇩🇪 Sprachpriorität:** German Dub → Sub → English (konfigurierbar)
- **📁 Jellyfin-kompatibel:** `Title (Year)/Season 01/` + `Filme/Film01.mkv`
- **💾 SQLite-DB:** Fortschritt, Status, fehlende deutsche Episoden
- **🔒 Anti-Sperre:** DNS-over-HTTPS umgeht ISP-Blocks automatisch

---

## Installation

### Windows
```powershell
git clone https://github.com/WimWamWom/AniLoader.git && cd AniLoader
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt && python main.py
```
Benötigt: **Python 3.11+**, **ffmpeg** im PATH

### Linux  
```bash
git clone https://github.com/WimWamWom/AniLoader.git && cd AniLoader
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt && python main.py
```

### Docker/Unraid
```yaml
services:
  aniloader:
    image: wimwamwom/aniloader:latest
    ports: ["5050:5050"]
    volumes: 
      - ./data:/app/data
      - ./Downloads:/app/Downloads
      - ./Anime:/app/Anime
      - ./Serien:/app/Serien
    environment: [TZ=Europe/Berlin]
    restart: unless-stopped
```

**Unraid:** Template von Community Apps oder Docker Hub `wimwamwom/aniloader:latest`

---

## Verwendung

### Web-Interface (`http://localhost:5050`)
- **📥 Download:** Modi starten/stoppen, Live-Status, Logs
- **📂 Hinzufügen:** URLs, TXT-Upload, Suche mit Poster
- **🗃️ Datenbank:** Alle Serien, Sortierung, Filter, Aktionen
- **⚙️ Einstellungen:** Pfade, Sprachen, Autostart

### API
```bash
# Status
GET /status

# Download starten/stoppen  
POST /start_download {"mode": "default"}
POST /stop_download

# URLs hinzufügen
POST /export {"url": "https://aniworld.to/anime/stream/naruto"}

# Suchen
POST /search {"query": "attack on titan", "platform": "both"}
```

**Swagger:** `http://localhost:5050/docs`

### Tampermonkey
Download `Tampermonkey.user.js` → Installieren → Button auf aniworld.to/s.to Seiten

---

## Config

`data/config.yaml` (automatisch erstellt):

```yaml
storage:
  mode: separate              # separate=Anime/Serien getrennt, standard=alles in Downloads
  download_path: /app/Downloads
  anime_path: /app/Anime      # aniworld.to → hier  
  series_path: /app/Serien    # s.to → hier

languages:                   # Priorität von oben nach unten
  - German Dub
  - German Sub
  - English Sub

download:
  autostart_mode: null       # null, default, german, new, check
  refresh_titles: false      # Titel beim Start updaten
  min_free_gb: 2.0
```

### Modi
- **default:** Alle unvollständigen Serien
- **german:** Fehlende deutsche Episoden  
- **new:** Neue Episoden bei allen Serien
- **check:** Integritätsprüfung + Reparatur

---

## FAQ

**Q: Downloads funktionieren nicht?**  
A: ffmpeg installiert? Python 3.11+? Logs prüfen im Download-Tab

**Q: „DNS-Fehler" / Seite nicht erreichbar?**  
A: DNS-over-HTTPS ist aktiviert, Firewall für HTTPS prüfen

**Q: Filme als „Season 00"?**  
A: Update auf neueste Version → Filme werden als `Filme/Film01.mkv` gespeichert

**Q: Autostart aktivieren?**  
A: `config.yaml` → `autostart_mode: default` oder Web-UI Einstellungen

**Q: Tampermonkey Button zeigt „offline"?**  
A: Server-IP im Skript anpassen, AniLoader muss laufen

---

<p align="center">
  <img src="web/static/AniLoader.png" alt="AniLoader" width="60"><br>
  <sub>Made with ❤️ for Anime & Serien</sub>
</p>

### Docker
- **Docker** und **Docker Compose**
- Sonst nichts – alles ist im Image enthalten

---

## Installation

### Lokal – Windows

```powershell
# 1. Repository klonen
git clone https://github.com/WimWamWom/AniLoader.git
cd AniLoader

# 2. Virtuelle Umgebung erstellen
python -m venv venv
venv\Scripts\activate

# 3. Abhängigkeiten installieren
pip install -r requirements.txt

# 4. ffmpeg installieren
#    → https://www.gyan.dev/ffmpeg/builds/ herunterladen
#    → Entpacken und den bin/ Ordner zum Windows PATH hinzufügen
#    → PowerShell neu starten und testen:
ffmpeg -version

# 5. Starten
python main.py
```

> **Tipp:** Falls `aniworld.to` / `s.to` vom Provider gesperrt ist, nutzt AniLoader automatisch DNS-over-HTTPS (Google). Windows-Firewalls müssen ausgehende HTTPS-Verbindungen erlauben.

### Lokal – Linux

```bash
# 1. Repository klonen
git clone https://github.com/WimWamWom/AniLoader.git
cd AniLoader

# 2. Abhängigkeiten
sudo apt update
sudo apt install python3 python3-venv python3-pip ffmpeg -y

# 3. Virtuelle Umgebung
python3 -m venv venv
source venv/bin/activate

# 4. Python-Pakete
pip install -r requirements.txt

# 5. Starten
python main.py
```

Der Server startet auf `http://localhost:5050`.

### Docker – Windows

Voraussetzung: [Docker Desktop](https://www.docker.com/products/docker-desktop/) installiert und gestartet.

```powershell
# 1. Repository klonen
git clone https://github.com/WimWamWom/AniLoader.git
cd AniLoader

# 2. Ordner erstellen (Docker Desktop braucht diese vorab)
mkdir data, Downloads, Anime, Serien, "Anime-Filme", "Serien-Filme"

# 3. Bauen und starten
docker compose up -d

# Status prüfen
docker compose ps

# Logs anzeigen
docker compose logs -f
```

### Docker – Linux

```bash
# 1. Docker installieren (falls nicht vorhanden)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Neu einloggen, damit die Gruppe wirkt

# 2. Repository klonen
git clone https://github.com/WimWamWom/AniLoader.git
cd AniLoader

# 3. Ordner anlegen + Rechte setzen
mkdir -p data Downloads Anime Serien Anime-Filme Serien-Filme
chmod 777 Downloads Anime Serien Anime-Filme Serien-Filme

# 4. Bauen und starten
docker compose up -d

# Status & Logs
docker compose ps
docker compose logs -f
```

### Unraid

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

#### `docker-compose.yml` Referenz

Die mitgelieferte `docker-compose.yml` enthält alle Volumes bereits fertig konfiguriert:

```yaml
services:
  aniloader:
    build: .
    image: AniLoader
    container_name: aniloader
    hostname: aniloader
    ports:
      - "5050:5050"
    volumes:
      # Persistente Daten (DB, Config, Logs)
      - ./data:/app/data
      # Download-Verzeichnis (storage.mode: standard)
      - ./Downloads:/app/Downloads
      # Separate Pfade (storage.mode: separate)
      - ./Anime:/app/Anime
      - ./Serien:/app/Serien
      - ./Anime-Filme:/app/Anime-Filme
      - ./Serien-Filme:/app/Serien-Filme
    environment:
      - PYTHONUNBUFFERED=1
      - TZ=Europe/Berlin
    dns:
      - 8.8.8.8
      - 1.1.1.1
    restart: unless-stopped
```

> Die Host-Pfade (linke Seite der `:`) können beliebig angepasst werden. Die Container-Pfade (rechte Seite) müssen mit den Pfaden in der `config.yaml` übereinstimmen.

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
  anime_path: /app/Anime            # Anime (separate Modus)
  series_path: /app/Serien           # Serien (separate Modus)
  anime_movies_path: /app/Anime-Filme   # Anime-Filme (optional)
  serien_movies_path: /app/Serien-Filme # Serien-Filme (optional)
  anime_separate_movies: false
  serien_separate_movies: false

download:
  min_free_gb: 2.0                  # Mindest-Speicherplatz (GB)
  autostart_mode: null              # null | default | german | new | check
  timeout_seconds: 900              # Timeout pro Episode (Sekunden)
  refresh_titles: false             # Titel beim Start aktualisieren

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
Anime/                   ← storage.anime_path = /app/Anime
├── Naruto (2002) [imdbid-tt0409591]/
│   ├── Filme/       ← Filme (Film01 - Title.mkv)
│   ├── Season 01/   ← Serien (S01E001 - Title.mkv)
│   └── ...

Serien/                  ← storage.series_path = /app/Serien
├── Breaking Bad (2008) [imdbid-tt0903747]/
│   ├── Filme/       ← Filme falls vorhanden
│   └── Season 01/   ← Serien

Anime-Filme/             ← storage.anime_movies_path = /app/Anime-Filme
├── Your Name (2016) [imdbid-tt5311514]/  (anime_separate_movies: true)
│   └── Filme/
│       └── Film01 - Your Name.mkv

Serien-Filme/            ← storage.serien_movies_path = /app/Serien-Filme
├── Avengers (2019) [...]/ (serien_separate_movies: true)
│   └── Filme/
│       └── Film01 - Avengers Endgame.mkv
```

> **Film-Struktur:** Filme werden in `Filme/` Ordnern mit `Film01`, `Film02` etc. gespeichert. Die verwirrende `Season 00` Struktur wurde durch eindeutige Film-Benennung ersetzt.

> **Docker-Hinweis:** Im Container sind alle Pfade bereits als Volume gemappt. Die `config.yaml`-Pfade (z.B. `/app/Anime`) müssen den Container-Pfaden in `docker-compose.yml` entsprechen.

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
| `GET` | `/poster` | Poster-URL für Serie extrahieren (`?url=`) |
| `GET` | `/proxy_poster` | Poster-Bild mit CORS-Headers laden (`?url=`) |
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
AniLoader/
├── main.py                      # Einstiegspunkt – startet Uvicorn
├── requirements.txt             # Python-Abhängigkeiten
├── Dockerfile                   # Multi-stage Docker Build
├── docker-compose.yml           # Docker Compose Konfiguration
├── Tampermonkey.user.js         # Browser-Erweiterung v2.0
├── README.md                    # Diese Datei
├── README_DOCKER.md             # Docker-spezifische Dokumentation
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

### Wie kann ich den Titel-Refresh aktivieren?
In der `config.yaml` oder im Einstellungen-Tab → Download:
```yaml
download:
  refresh_titles: true
```
Beim nächsten Server-Start werden alle Titel aus der Datenbank von den Original-Webseiten aktualisiert.

### Was zeigt "Fehlende DE" in der Datenbank?
Diese Spalte zeigt an, wie viele deutsche Episoden noch fehlen (z.B. "E001, E002" oder "5 Episoden"). Der German-Modus kann diese gezielt nachladen.

### Filme werden als "Season 00" angezeigt – ist das normal?
**Nein!** In der neuen Version werden Filme in `Filme/` Ordnern mit `Film01` Dateinamen gespeichert. Falls du noch `Season 00` siehst, aktualisiere auf die neueste Version.

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
