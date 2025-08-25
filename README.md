<a id="readme-top"></a>

# AniLoader

<ins>***Momentan noch in Arbeit.***</ins> </br>
***Dieser Downloader basiert auf dem [AniWorld-Downloader](https://github.com/phoenixthrush/AniWorld-Downloader/tree/next) von [phoenixthrush](https://github.com/phoenixthrush).*** </br>
Ein Python-Skript mit optionalem Webinterface zum automatischen Herunterladen von Anime von [AniWorld](https://aniworld.to/) und Serien von [SerienStream](https://s.to/) mit Fokus auf **deutsche Dub- oder Sub-Versionen**.  
Das Skript verwaltet eine **SQLite-Datenbank**, überprüft **fehlende Episoden**, benennt heruntergeladene Dateien automatisch sauber um und sortiert **Filme** und **Staffeln** nach dem Download in Unterordner.

---

## Inhalt
- [Funktion](#funktion)
- [Installation](#installation)
- [Nutzung](#nutzung)
- [Hinweise](#hinweise)
- [Beispiele](#beispiele)
- [Lizenz](#lizenz)

---

## Funktion

### Features
- **Import von Anime/Serien-Links** aus einer Textdatei (`Download.txt`)
- Verwaltung des Download-Status in einer SQLite-Datenbank (`download.db`)
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

---

## Dateistruktur

```
AniLoader/
├─ Download.txt # Liste der Anime-URLs (eine pro Zeile)
├─ download.db # SQLite-Datenbank für Fortschritt und fehlende Folgen
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
├─ downloader.py # Hauptskript
├─ combined_web_downloader.py # Hauptskript mit Webinterface
├─ templates/ # HTML-Templates für Webinterface
├─ static/ # CSS/JS für Webinterface
└─ README.md # README
```


<p align="right">(<a href="#readme-top">back to top</a>)</p>



## Installation

### 1. Repository klonen
```
git clone https://github.com/WimWamWom/AniLoader
```

2. **Python-Abhängigkeiten installieren**

```
pip install requests beautifulsoup4 flask flask_cors aniworld
 ```


### Download-Liste erstellen

Die Datei `Download.txt` enthält die Links zu den Animes / Serien, z. B.:

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
py AniLoader.py
```

- Lädt alle Filme und Staffeln herunter
- Aktualisiert die SQLite-Datenbank und markiert abgeschlossene Anime
- Sortiert die Dateien automatisch in Unterordner

#### Nur fehlende deutsche Folgen herunterladen

```
py AniLoader.py german
```

- Prüft nur Anime mit fehlenden deutschen Folgen (`fehlende_deutsch_folgen`) und lädt diese herunter
- Löscht automatisch folgen welche nun Syncro haben

#### Neue Episoden prüfen und herunterladen

```
py AniLoader.py new
```

- Prüft bei jedem Anime nach neuen Filmen oder Staffeln ab der letzten heruntergeladenen Folge
- Lädt neue Episoden herunter und aktualisiert die Datenbank

### AniLoader mit Webinterface

#### Starten 
Starte das Programm mit 
```
py fullweb.py
```

#### Web-Interface
Öffne im Browser: [http://localhost:5000](http://localhost:5000)

##### Features
- Start/Stop von Downloads
- Überwachung von Logs in Echtzeit
- Datenbankeinträge anzeigen, filtern und sortieren

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
<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Beispiele

### Dateiname nach Download


```
S01E005 - Der Ninja-Test [Dub].mp4
S01E006 - Kampf der Klingen [Sub].mp4
Film01 - Naruto Movie [Dub].mp4
```

### Beispiel für die Eingabe der Link  (`Download.txt`)
```
https://aniworld.to/anime/stream/a-certain-magical-index
https://s.to/serie/stream/family-guy
https://aniworld.to/anime/stream/classroom-of-the-elite
https://aniworld.to/anime/stream/highschool-dxd
https://s.to/serie/stream/die-schluempfe
https://s.to/serie/stream/die-abenteuer-des-jungen-marco-polo
```


### Beispiel SQLite-Datenbank (`download.db`)
- wird automatisch erstellt, enthält pro Anime:
  - title
  - url
  - complete
  - deutsch_komplett
  - fehlende_deutsch_folgen (JSON-Array)
  - last_film (Integer)
  - last_episode (Integer)

### Ausgabe in CMD 
```
========== Starte Download für: Naruto ==========
[SKIP] Episode S01E001 bereits vorhanden.
[OK] https://aniworld.to/serie/naruto/staffel-1/episode-2 (German Dub)
Umbenannt in: S01E002 - Der Ninja-Test [Dub].mp4
[OK] https://aniworld.to/serie/naruto/staffel-1/episode-3 (German Dub)
Umbenannt in: S01E003 - Kampf der Klingen [Dub].mp4
[WARN] German Sub nicht verfügbar → nächster Sprachversuch…
[OK] https://aniworld.to/serie/naruto/staffel-1/episode-4 (English Sub)
Umbenannt in: S01E004 - Freundschaft und Rivalen [Sub].mp4
[NO_STREAMS] Episode S01E05: Kein Stream verfügbar.
[INFO] Staffel 1 beendet nach 4 Episoden.
```
<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Lizenz

Dieses Projekt ist unter der [MIT-Lizenz](https://github.com/WimWamWom/AniLoader/blob/main/LICENSE) lizenziert. </br>
Genauer Informatoinen stehen in der LICENSE-Datei.
<p align="right">(<a href="#readme-top">back to top</a>)</p>
