<a id="readme-top"></a>

# AniLoader

<ins>***Momentan noch in Arbeit. Bereits Funktionsfähig***</ins> </br>
***Dieser Downloader basiert auf dem [AniWorld-Downloader](https://github.com/phoenixthrush/AniWorld-Downloader/tree/next) von [phoenixthrush](https://github.com/phoenixthrush).*** </br>
Dieses Projekt ist ein Python-Skript mit optionalem Webinterface, das den automatischen Download von Animes von [AniWorld](https://aniworld.to/) und Serien von [SerienStream](https://s.to/) ermöglicht. Der Schwerpunkt liegt dabei auf deutschen Dub-Versionen. Das Skript verwaltet eine **SQLite-Datenbank**, in der alle heruntergeladenen Inhalte gespeichert und **fehlende duetsche Episoden** automatisch erkannt werden. Heruntergeladene Dateien werden sauber umbenannt und übersichtlich nach **Staffeln, Episoden und Filmen sortiert**. Dadurch entsteht eine klar strukturierte Ordnerhierarchie, in der Serien und Filme leicht auffindbar sind. Zusätzlich bietet das Webinterface eine komfortable Möglichkeit, Downloads zu verwalten und den aktuellen Fortschritt einzusehen.



## Inhalt
- [Funktion](#funktion)
- [Installation](#installation)
  - [1. Repository klonen](#1-repository-klonen)
  - [2. Python-Abhängigkeiten installieren](#2-python-abhängigkeiten-installieren)
  - [3. Download-Liste erstellen](#download-liste-erstellen)
- [Nutzung](#nutzung)
  - [AniLoader als lokales Programm](#aniloader-als-lokales-programm)
    - [Alle Anime herunterladen](#alle-anime-herunterladen)
    - [Nur fehlende deutsche Folgen herunterladen](#nur-fehlende-deutsche-folgen-herunterladen)
    - [Neue Episoden prüfen und herunterladen](#neue-episoden-prüfen-und-herunterladen)
  - [AniLoader mit Webinterface](#aniloader-mit-webinterface)
    - [Starten](#starten)
    - [Web-Interface](#web-interface)
- [API](#api)
  - [Start Download](#start-download)
  - [Status](#status)
  - [Logs](#logs)
  - [Datenbank-Einträge](#datenbank-einträge-suchefiltersort)
- [Tampermonkey](#tampermonkey)
- [Hinweise](#hinweise)
  - [Good to Know](#good-to-know)
  - [Anpassung](#anpassung)
- [Beispiele](#beispiele)
- [Debugging & Troubleshooting](#debugging--troubleshooting-häufige-fehler)
- [Lizenz](#lizenz)



## Funktion

### Features
- **Import von Anime/Serien-Links** aus einer Textdatei (`AniLoader.txt`)
- Verwaltung des Download-Status in einer SQLite-Datenbank (`AniLoader.db`)
- **Priorisierung von Sprachen**:
  1. German Dub
  2. German Sub
  3. English Dub
  4. English Sub
- Automatische Erkennung bereits heruntergeladener Episoden
- **Löschen alter Untertitelversionen** außer German Dub
- Sauberes **Umbenennen** von Episoden nach Staffel, Episode, Titel und Sprache
- **Download von Staffeln und Filmen**
- Automatische Sortierung der Downloads:  
  - Filme → `Filme`
  - Staffeln → `Staffel 1`, `Staffel 2`, …
- Option, nur **fehlende deutsche Folgen** (`german`) oder **neue Episoden** (`new`) zu prüfen
- **Webinterface** zur Kontrolle des Downloads, Überwachung der Logs und Datenbankabfrage



## Dateistruktur

```
AniLoader/
├─ AniLoader.txt # Liste der Anime-URLs (eine pro Zeile)
├─ AniLoader.db # SQLite-Datenbank für Fortschritt und fehlende Folgen
├─ downloader.py # Hauptskript ohne Webinterface
├─ AniLoader.py # Hauptskript mit Webinterface
├─ templates/ # HTML-Templates für Webinterface
├─ static/ # CSS/JS für Webinterface
├─ README.md # README
├─ Downloads/ # Standard-Downloadordner
│ ├─ Naruto/
│ │ ├─ Filme/
│ │ │ ├─ Film01.mp4
│ │ │ └─ ...
│ │ ├─ Staffel 1/
│ │ │ ├─ S01E001 - Titel.mp4
│ │ │ └─ ...
│ │ ├─ Staffel 2/
│ │ │ ├─ S02E001 - Titel [Sub].mp4
│ │ │ └─ ...

```


<p align="right">(<a href="#readme-top">back to top</a>)</p>



## Installation

### 1. Repository klonen
```
git clone https://github.com/WimWamWom/AniLoader
```

### 2. **Python-Abhängigkeiten installieren**

```
pip install requests beautifulsoup4 flask flask_cors aniworld
 ```


### Download-Liste erstellen

Die Datei `AniLoader.txt` enthält die Links zu den Animes / Serien, z. B.:

```
https://aniworld.to/serie/naruto
https://s.to/serie/stream/the-rookie
```
Jede URL muss in einer neuen Zeile stehen. Es darf dabei nur der Link zu dem Anime/der Serie sein, nicht zu einer spezifischen Folge.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Nutzung

### AniLoader als lokales Programm

#### Alle Anime herunterladen

```
py downloader.py
```

- Lädt alle Filme und Staffeln herunter
- Aktualisiert die SQLite-Datenbank und markiert abgeschlossene Anime
- Sortiert die Dateien automatisch in Unterordner

#### Nur fehlende deutsche Folgen herunterladen

```
py downloader.py german
```

- Prüft nur Anime mit fehlenden deutschen Folgen (`fehlende_deutsch_folgen`) und lädt diese herunter
- Löscht automatisch folgen welche nun Syncro haben

#### Neue Episoden prüfen und herunterladen

```
py downloader.py new
```

- Prüft bei jedem Anime nach neuen Filmen oder Staffeln ab der letzten heruntergeladenen Folge
- Lädt neue Episoden herunter und aktualisiert die Datenbank

## AniLoader mit Webinterface


### Starten

### Als Lokaler "Test"-Server
Starte das Programm mit
```
py AniLoader.py
```
**Achtung:**
Der eingebaute Flask-Server ist nur für Entwicklung und Tests gedacht. Er ist nicht für den produktiven Einsatz geeignet, da er keine Sicherheit gegen Angriffe bietet und bei hoher Last instabil werden kann.

### Start mit WSGI-Server (empfohlen)

Für den produktiven Einsatz solltest du einen WSGI-Server wie `waitress` verwenden (empfohlen für Windows):

1. Installiere waitress:
  ```
  pip install waitress
  ```
2. Starte AniLoader mit waitress:
  ```
  python -m waitress --host=0.0.0.0 --port=5050 AniLoader:app
  ```
  (Das `:app` bezieht sich auf das Flask-App-Objekt in AniLoader.py)


## Web-Interface

### Zugang
Das Webinterface ist dann wie unter [http://localhost:5050](http://localhost:5050) erreichbar.

Weitere Hinweise zu Sicherheit und Remote-Zugriff siehe Abschnitt "Debugging & Troubleshooting".

##### Features
- Starten und Verfolgen von Downloads
- Überwachung von Logs in Echtzeit
- Datenbankeinträge anzeigen, filtern und sortieren
- Endpunkt für Tampermonkey skript

<p align="right">(<a href="#readme-top">back to top</a>)</p>


## API 

### Start Download
URL: /start_download </br>
Method: GET oder POST </br>
Query / JSON: mode = default | german | new </br>
Beschreibung: startet den Hintergrund-Runner in einem der Modi. Der Endpoint startet die Hintergrund-Thread-Funktion run_mode(mode). </br>

#### GET, Standardmodus:
```
curl "http://localhost:5050/start_download"
```

#### GET, German-Modus:
```
curl "http://localhost:5050/start_download?mode=german"
```
#### GET, Überprüfe auf neue Episoden:
```
curl "http://localhost:5050/new"
```
Überprüft ob bei abgeschlossenen Animes neue Filme, Staffeln oder Episoden existieren

#### GET, Überprüfe auf fehlende Episoden:
```
curl "http://localhost:5050/check_missing"
```
Überprüft ob bei angefangenen Animes ob der Download alle Folgen geladen hat, oder ob welche nicht heruntergeladen wurden.

### Status

URL: /status </br>
Method: GET </br>
Beschreibung: liefert den aktuellen Status (idle | running | finished), aktueller Modus, Index/Titel der Serie, Startzeit. </br>

#### Aufruf
```
curl http://localhost:5050/status
```

#### Ausgabe
```
{"status":"running","mode":"new","current_index":1,"current_title":"Naruto","started_at":1600000000.0}
```

### Logs

URL: /logs </br>
Method: GET </br>
Beschreibung: liefert die im Speicher gehaltenen Log-Zeilen als JSON-Array (letzte MAX_LOG_LINES). </br>
```
curl http://localhost:5050/logs
```
<p align="right">(<a href="#readme-top">back to top</a>)</p>


### Datenbank-Einträge (Suche/Filter/Sort)
URL: `/database` </br>
Method: GET </br>
Query-Parameter:
- q = Suchbegriff (match auf title oder url)
- complete = 0 oder 1 (Filter)
- sort_by = id | title | last_film | last_episode | last_season
- order = asc | desc
- limit = Zahl
- offset = Zahl

#### Beispiel Aufruf 
```
curl "http://localhost:5050/database?q=naruto&complete=0&sort_by=title&order=asc&limit=50"
```
#### Ausgabe
```
{id,title,url,complete,deutsch_komplett,fehlende,last_film,last_episode,last_season}
```
<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Tampermonkey
[Benutzer-Script](https://github.com/WimWamWom/AniLoader/raw/refs/heads/main/Tampermonkey.user.js) (JavaScript) fügt auf AniWorld / S.to einen Button hinzu. </br>
Ändere im Tampermonkey-Script die Basis-URL für deinen Server (falls nicht `localhost`)</br>
--> Wenn dein Flask auf einem anderen Rechner läuft, setze die SERVER_IP auf dessen `IP-Adresse`(Bsp.: 123.45.67): 
```
const SERVER_IP = "localhost";
oder
const SERVER_IP = "123.45.67";
```
Verhalten:
- Beim Laden prüft das Script /check?url=… → wenn vorhanden, Button ist grün und deaktiviert.
- Klick auf Button sendet POST /export mit JSON {url}.
<p align="right">(<a href="#readme-top">back to top</a>)</p>


## Hinweise
### Good to Know
- Die URL-Struktur des Anime muss dem Format von AniWorld oder SerienStream entsprechen
- Alte Untertitelversionen (außer German Dub) werden automatisch gelöscht
- Fehlende Streams oder Sprachprobleme zeigen Warnungen an

### Anpassung

Die wichtigsten Konfigurationen befinden sich am Anfang von `AniLoader.py`:
- `DOWNLOAD_DIR`: Ordner für die Downloads
- `DOWNLOAD_TXT`: Pfad zur Download-Textdatei
- `LANGUAGES`: Reihenfolge und Sprachen, die beim Download versucht werden
- `DB_PATH`: Speicherort der SQLite-Datenbank
- 
<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Beispiele

### Dateiname nach Download


```
S01E005 - Der Ninja-Test [Dub].mp4
S01E006 - Kampf der Klingen [Sub].mp4
Film01 - Naruto Movie [Dub].mp4
```

### Beispiel für die Eingabe der Link  (`AniLoader.txt`)
```
https://aniworld.to/anime/stream/a-certain-magical-index
https://s.to/serie/stream/family-guy
https://aniworld.to/anime/stream/classroom-of-the-elite
https://aniworld.to/anime/stream/highschool-dxd
https://s.to/serie/stream/die-schluempfe
https://s.to/serie/stream/die-abenteuer-des-jungen-marco-polo
```


### Beispiel SQLite-Datenbank (`AniLoader.db`)
- wird automatisch erstellt, enthält pro Anime:
  - title
  - url
  - complete
  - deutsch_komplett
  - fehlende_deutsch_folgen (JSON-Array)
  - last_film (Integer)
  - last_episode (Integer)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Debugging & Troubleshooting (häufige Fehler)

### Kein Download startet / aniworld: command not found
aniworld nicht installiert oder nicht in PATH. Installiere / passe run_download an.

### AniLoader.txt wird nicht eingelesen
Stelle sicher, dass AniLoader.txt im selben Ordner wie combined_web_downloader.py liegt. Beim Start wird update_db() ausgeführt.

### Keine Logs im UI
/logs liefert die Log-Zeilen als JSON. Prüfe mit curl http://localhost:5050/logs. UI muss diese anzeigen.

### Server wird beim Seiten-Reload neu gestartet
Das Skript läuft als normaler Flask-Prozess. Wenn du im Entwickler-Modus (debug=True) startest, kann der Reloader Threads neu starten. In deinem Code ist debug=False, das ist gut — Threads überleben Seitenreloads nicht automatisch, aber hier ist der Server persistent.

### Datenbank-Inkonsistenzen
SQLite Datei AniLoader.db kannst du mit sqlite3 AniLoader.db öffnen. Backup machen bevor du Änderungen vornimmst.

### Remote Zugriff / Firewall
Standardmäßig host="0.0.0.0" heißt erreichbar von Außen. Setze Firewall/Router-Portforwarding wenn nötig. Achtung: unsicher, wenn öffentlich zugänglich — siehe Sicherheitsabschnitt.


<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Lizenz

Dieses Projekt ist unter der [MIT-Lizenz](https://github.com/WimWamWom/AniLoader/blob/main/LICENSE) lizenziert. </br>
Genauer Informatoinen stehen in der LICENSE-Datei.
<p align="right">(<a href="#readme-top">back to top</a>)</p>
