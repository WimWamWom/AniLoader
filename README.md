<a id="readme-top"></a>

[English README](README_en.md) — English translation of this README

# AniLoader

<ins><strong>In Arbeit, aber bereits funktionsfähig</strong></ins><br/>
Dieser Downloader basiert auf dem Projekt <a href="https://github.com/phoenixthrush/AniWorld-Downloader" target="_blank" rel="noreferrer">AniWorld-Downloader</a> von <a href="https://github.com/phoenixthrush" target="_blank" rel="noreferrer">phoenixthrush</a> und nutzt dessen CLI <code>aniworld</code> für die eigentlichen Downloads.

AniLoader ist ein Python-Tool mit optionalem Webinterface, das Animes von <a href="https://aniworld.to/" target="_blank" rel="noreferrer">AniWorld</a> und Serien von <a href="https://s.to/" target="_blank" rel="noreferrer">SerienStream</a> automatisch laden und sauber in Ordnern (Staffeln/Episoden/Filme) ablegen kann. Der Fokus liegt auf deutschen Versionen (German Dub). Eine SQLite-Datenbank hält den Fortschritt fest, erkennt fehlende deutsche Folgen und vermeidet Dubletten.

## Inhalt

- [Funktion](#funktion)
- [Installation](#installation)
  - [1. Voraussetzungen](#1-voraussetzungen)
  - [2. Repository klonen](#2-repository-klonen)
  - [3. Abhängigkeiten installieren](#3-abhängigkeiten-installieren)
  - [4. Download-Liste anlegen](#4-download-liste-anlegen)
- [Nutzung](#nutzung)
  - [CLI (ohne Webinterface)](#cli-ohne-webinterface)
  - [Webinterface (Flask/Waitress)](#webinterface-flaskwaitress)
  - [Dateistruktur](#dateistruktur)
- [Konfiguration](#konfiguration)
- [Web-UI Features](#web-ui-features)
- [API](#api)
  - [Start Download](#start-download)
  - [Status](#status)
  - [Logs](#logs)
  - [Disk](#disk)
  - [Config](#config)
  - [Datenbank](#datenbank)
  - [Counts](#counts)
  - [Export](#export)
  - [Check](#check)
  - [Queue](#queue)
- [Tampermonkey](#tampermonkey)
- [Hinweise](#hinweise)
- [Beispiele](#beispiele)
- [Debugging & Troubleshooting](#debugging--troubleshooting)
- [Lizenz](#lizenz)

## Funktion

### Features
- Import von Serien-Links aus <code>AniLoader.txt</code>
- Fortschrittsverwaltung in SQLite (welche Staffeln/Episoden/Filme sind geladen, fehlende deutsche Folgen, „komplett“ usw.)
- Sprach-Priorität in dieser Reihenfolge (konfigurierbar):
  1. German Dub
  2. German Sub
  3. English Dub
  4. English Sub
- Bereits vorhandene Folgen werden erkannt und übersprungen
- Automatisches Löschen alter Nicht-Dub-Versionen, sobald German Dub vorhanden ist
- Sauberes Umbenennen nach Schema: <code>S01E023 - Episodentitel [English Sub].mp4</code> bzw. <code>Film01 - Titel.mp4</code>
- Ordnerstruktur: <code>Downloads/Serie/Staffel N/*.mp4</code> und <code>Downloads/Serie/Filme/*.mp4</code>
- Modi: kompletter Lauf, nur neue Inhalte, nur deutsche Nachlieferungen, und Prüfung auf fehlende Dateien
- Webinterface: Fortschritt, Logs, Datenbank-Ansicht, Speicheranzeige, Queue („Als nächstes“)

## Installation

### 1. Voraussetzungen
- Empfohlen: Python 3.9 oder neuer (getestet mit 3.13)
- Betriebssystem: Windows, Linux oder macOS (Windows bevorzugt, da Waitress im README gezeigt wird)

### 2. Repository klonen
```bash
git clone https://github.com/WimWamWom/AniLoader
```

### 3. Abhängigkeiten installieren
Installiere alle benötigten Pakete in einem Schritt:
```bash
pip install requests beautifulsoup4 flask flask_cors aniworld waitress
```

Optional (für DNS-Override bei Titelabfragen via 1.1.1.1):
```bash
pip install dnspython
```

Prüfen, ob das Downloader-CLI vorhanden ist:
```bash
aniworld --help
```

### 4. Download-Liste anlegen
Lege im Projektordner eine Datei <code>AniLoader.txt</code> an und trage je Zeile genau einen Serienlink ein (Basis-URL, keine Episoden-URL), z. B.:

```
https://aniworld.to/anime/stream/naruto
https://s.to/serie/stream/the-rookie
```

## Nutzung

### CLI (ohne Webinterface)
Das CLI-Skript ist <code>downloader.py</code>. Start:

```bash
py downloader.py [mode]
```

Modi:
- <code>default</code> (Standard): kompletter Lauf über Filme und Staffeln; lädt Inhalte gemäß Sprach-Priorität; markiert ggf. komplett
- <code>german</code>: versucht ausschließlich Einträge aus „fehlende_deutsch_folgen“ in German Dub nachzuladen
- <code>new</code>: prüft ab den gespeicherten <code>last_*</code>-Werten auf neue Filme/Staffeln/Episoden
- <code>check-missing</code>: versucht fehlende Dateien anhand DB- und Dateisystem-Infos nachzuladen
- <code>full-check</code>: kompletter Check von Anfang an (Filme ab 1, Staffeln ab 1/Episode 1) für alle Serien; vorhandene Dateien werden übersprungen

Beispiele:
```bash
py downloader.py
py downloader.py german
py downloader.py new
py downloader.py check-missing
py downloader.py full-check
```

Hinweise:
- <code>Downloads/</code> wird automatisch erzeugt
- Minimale Restkapazität ist konfigurierbar (Standard 2 GB); unterhalb wird abgebrochen
- <code>aniworld</code> muss im PATH liegen

### Webinterface (Flask/Waitress)

- Entwicklungsstart (lokal):
```bash
py AniLoader.py
```

- Produktion unter Windows (empfohlen):
```bash
python -m waitress --host=0.0.0.0 --port=5050 AniLoader:app
```

Aufruf: http://localhost:5050

### Dateistruktur

```
AniLoader/
├─ AniLoader.py             # Webserver + Logik
├─ downloader.py            # CLI-Variante (ohne Webserver)
├─ AniLoader.txt            # Import-Liste der Serien-URLs
├─ data/
│  ├─ AniLoader.db         # SQLite-Datenbank
│  └─ config.json          # Konfiguration (languages, min_free_gb, download_path, port, autostart_mode)
├─ Downloads/              # Zielordner der Dateien
│  └─ <Serienname>/
│     ├─ Filme/
│     └─ Staffel 1/, Staffel 2/, ...
├─ templates/              # HTML
├─ static/                 # CSS/JS
└─ README.md
```

## Konfiguration

Die Konfigurationsdatei liegt unter <code>data/config.json</code>. Fehlende Einträge werden beim Start automatisch ergänzt und die Datei wird übersichtlich formatiert gespeichert.

Wichtige Schlüssel:
- <code>languages</code>: Reihenfolge der zu prüfenden Sprachen (Standard: German Dub → German Sub → English Dub → English Sub)
- <code>min_free_gb</code>: Mindest-freier Speicher in GB; darunter werden Downloads abgebrochen (Standard: 2.0)
- <code>download_path</code>: Ziel-Stammordner für alle Downloads (Standard: <code>./Downloads</code>); wird automatisch angelegt
- <code>port</code>: Port des Webservers (nur per Datei änderbar; hat keine Wirkung im CLI-Betrieb)
- <code>autostart_mode</code>: Optionaler Autostart-Modus für das Webinterface (<code>default</code>|<code>german</code>|<code>new</code>|<code>check-missing</code>|<code>full-check</code>)
- <code>refresh_titles</code>: Aktualisiert Serien-Titel beim Start (Standard: <code>true</code>). Gilt sowohl für das Webinterface als auch für <code>downloader.py</code>.

Hinweise:
- Für das CLI (<code>downloader.py</code>) wird <code>download_path</code> genutzt; <code>port</code> ist dort ohne Wirkung.
- Bei der ersten Ausführung wird <code>download_path</code> gesetzt, falls noch nicht vorhanden, und der Ordner angelegt.

### DNS für Titelabfragen (optional)
- AniLoader kann die DNS-Auflösung für die reinen Titelabfragen (HTML-Requests in <code>get_series_title</code>/<code>get_episode_title</code>) gezielt über Cloudflare DNS <code>1.1.1.1</code> durchführen.
- Dafür wird optional <code>dnspython</code> genutzt. Ist es installiert, werden die Ziel-Hosts für diese Requests via <code>1.1.1.1</code> aufgelöst. Ist es nicht installiert, verwendet AniLoader einfach dein System-DNS (Fallback, keine Fehler).
- Es werden keine System- oder Router-Einstellungen geändert. Der DNS-Override gilt ausschließlich für die genannten Titelabfragen und lässt TLS/SNI unberührt (es wird weiterhin per Hostname verbunden).

Optional aktivieren:
```bash
pip install dnspython
```
Hinweis: Wenn wirklich „alles“ (inkl. externem <code>aniworld</code>-CLI) über 1.1.1.1 laufen soll, stell das DNS systemweit in Windows/Router um.

## Web-UI Features
- Start-Buttons für die Modi (inkl. „Kompletter Check“); während eines Laufs sind die Buttons deaktiviert
- Status-Anzeige inkl. „kein Speicher“ (Einheit automatisch in TB/GB/MB)
- Live-Logs mit Filter und Kopieren
- Datenbank-Tab: filtern/sortieren, Liste der fehlenden deutschen Folgen, Knopf „Als nächstes“ (Queue)
- Warteschlangen-Tabellen-Ansicht inkl. Leeren/Einträge entfernen
- Einstellungen: Download-Speicherort direkt setzen oder bequem per „Ordner wählen…“ über den Explorer auswählen; Port ist nur in der <code>config.json</code> änderbar
  - Schalter: „Titelaktualisierung beim Start aktivieren“

## API

Alle Endpunkte laufen standardmäßig unter <code>http://localhost:5050</code>.

### Start Download
- URL: <code>/start_download</code>
- Methode: GET oder POST
- Parameter: <code>mode</code> = <code>default</code> | <code>german</code> | <code>new</code> | <code>check-missing</code> | <code>full-check</code>
- Antwort: <code>{"status":"started","mode":"..."}</code> oder <code>409 already_running</code>

Beispiele:
```bash
curl "http://localhost:5050/start_download"
curl "http://localhost:5050/start_download?mode=german"
curl "http://localhost:5050/start_download?mode=new"
curl "http://localhost:5050/start_download?mode=check-missing"
```

### Status
- URL: <code>/status</code>
- Methode: GET
- Liefert u. a.: <code>status</code> (idle|running|finished|kein-speicher), <code>mode</code>, <code>current_index</code>, <code>current_title</code>, <code>started_at</code>, sowie <code>current_season</code>/<code>current_episode</code>/<code>current_is_film</code> während eines Laufs.

Beispiel:
```json
{"status":"running","mode":"new","current_index":1,"current_title":"Naruto","started_at":1725300000.0}
```

### Logs
- URL: <code>/logs</code>
- Methode: GET
- Liefert die letzten Logzeilen als JSON-Array

### Disk
- URL: <code>/disk</code>
- Methode: GET
- Liefert freien Speicher in GB: <code>{"free_gb": 512.3}</code>

### Config
- URL: <code>/config</code>
- Methoden: GET | POST
- GET liefert z. B.:
```json
{"languages":["German Dub","German Sub","English Dub","English Sub"],"min_free_gb":2.0,"download_path":"C:\\Pfad\\zu\\Downloads","port":5050,"autostart_mode":null}
```
- POST Body (Beispiel):
```json
{"download_path":"D:\\Media\\Anime"}
```
Hinweise:
- <code>download_path</code> kann per POST geändert werden. Der Ordner wird bei Bedarf angelegt.
- <code>port</code> ist nur über die Datei <code>data/config.json</code> änderbar und wird beim Serverstart übernommen.

### Datenbank
- URL: <code>/database</code>
- Methode: GET
- Parameter:
  - <code>q</code>: Suchtext für <code>title</code> oder <code>url</code>
  - <code>complete</code>: 0 | 1
  - <code>deleted</code>: 0 | 1
  - <code>deutsch</code>: 0 | 1 (Filter auf <code>deutsch_komplett</code>)
  - <code>sort_by</code>: <code>id</code> | <code>title</code> | <code>last_film</code> | <code>last_episode</code> | <code>last_season</code>
  - <code>order</code>: <code>asc</code> | <code>desc</code>
  - <code>limit</code> / <code>offset</code>

### Counts
- URL: <code>/counts</code>
- Methode: GET
- Parameter: <code>id</code> (DB-ID) oder <code>title</code> (Serienordner unter Downloads)
- Antwort: <code>{ per_season: {"1":12,...}, total_seasons, total_episodes, films, title }</code>

### Export
- URL: <code>/export</code>
- Methode: POST
- Body: <code>{ "url": "https://..." }</code>
- Fügt eine Serien-URL in die DB ein (für Tampermonkey-Button)

### Check
- URL: <code>/check</code>
- Methode: GET
- Parameter: <code>url</code>
- Prüft, ob die URL in der DB existiert (und nicht als deleted markiert ist)

### Queue
- URL: <code>/queue</code>
- Methoden:
  - GET: Liste der Queue-Einträge
  - POST: <code>{"anime_id": 42}</code> → fügt Anime zur Queue hinzu
  - DELETE: ohne Parameter leert die Queue; mit <code>?id=QID</code> oder <code>?anime_id=AID</code> löscht gezielt

## Tampermonkey
Userscript: https://github.com/WimWamWom/AniLoader/raw/refs/heads/main/Tampermonkey.user.js

Konfiguration im Script:
```js
const SERVER_IP = "localhost"; // ggf. IP/Hostname deines AniLoader-Servers
```

Funktionsweise:
- Prüft beim Laden per <code>/database</code>/<code>/status</code>, ob die Serie existiert bzw. gerade geladen wird
- Legt ggf. per <code>POST /export</code> den Eintrag an
- Startet falls nicht laufend <code>/start_download</code> im Standardmodus
- Button deaktiviert sich, wenn bereits vorhanden/aktiver Download

## Hinweise
- Die Pfade der Dateien werden auf Windows-Länge (<code>MAX_PATH</code>) geprüft; sehr lange Titel werden automatisch gekürzt
- Wird eine German-Dub-Version gefunden, löscht AniLoader ältere Sub-/englische Versionen derselben Folge
- Das System markiert „gelöschte“ Serien (falls Ordner entfernt) und setzt DB-Felder zurück; diese Einträge können reaktiviert werden, wenn dieselbe URL erneut exportiert wird
- Autostart-Modus kann über <code>/config</code> gesetzt werden (<code>default</code>|<code>german</code>|<code>new</code>|<code>check-missing</code>)

## Beispiele

Dateinamen nach Download:
```
S01E005 - Der Ninja-Test.mp4
S01E006 - Kampf der Klingen [Sub].mp4
Film01 - Naruto Movie.mp4
```

Beispiel-Einträge in <code>AniLoader.txt</code>:
```
https://aniworld.to/anime/stream/a-certain-magical-index
https://s.to/serie/stream/family-guy
```

## Debugging & Troubleshooting
- „aniworld: command not found“: <code>aniworld</code> ist nicht installiert oder nicht im PATH; siehe Installation Schritt 4
- Keine Logs im UI: <code>/logs</code> im Browser prüfen
- „Kein Speicher“: <code>/disk</code> prüfen und <code>min_free_gb</code> in <code>/config</code> anpassen
- Remote-Zugriff: Bei <code>host=0.0.0.0</code> ist der Server von außen erreichbar; sichere dein Netz/Firewall. Für Produktivbetrieb nutze einen WSGI-Server (Waitress) und setze ggf. Reverse Proxy/Auth davor

## Lizenz

MIT-Lizenz (siehe LICENSE). Urheberrechte der verwendeten Projekte liegen bei den jeweiligen Autoren.

<p align="right">(<a href="#readme-top">Nach oben</a>)</p>
