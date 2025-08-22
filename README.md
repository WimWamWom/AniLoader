<a id="readme-top"></a>

# AniLoader

<ins> ***Momentan noch in Arbeit.*** </ins> </br>
***Dieser Downloader basiert auf dem [AniWorld-Downloader](https://github.com/phoenixthrush/AniWorld-Downloader/tree/next) von [phoenixthrush](https://github.com/phoenixthrush).*** </br>
Ein Python-Skript zum automatischen Herunterladen von Anime von [AniWorld](https://aniworld.to/) und Serien von [SerienStream](https://s.to/) mit Fokus auf deutsche Dub- oder Sub-Versionen. Das Skript verwaltet eine SQLite-Datenbank, überprüft fehlende Episoden und benennt heruntergeladene Dateien automatisch sauber um. Außerdem werden Filme und Staffeln nach dem Download automatisch in Unterordner sortiert.

---
## Inhalt
- [Funktion](#Funktion)
- [Installation](#Installation)
- [Nutzung](#Nutzung)
- [Hinweise](#Hinweise)  
- [Beispiele](#Beispiele)

## Funktion
### Features

- Import von Anime-Links aus einer Textdatei (`Anime.txt`)
- Verwaltung des Download-Status in einer SQLite-Datenbank (`anime.db`)
- Priorisierung von Sprachen:
  - German Dub
  -> German Sub
  -> English Dub
  -> English Sub
- Automatische Erkennung bereits heruntergeladener Episoden
- Löschen alter Untertitelversionen außer German Dub
- Sauberes Umbenennen von Episoden nach Staffel, Episode, Titel und Sprache
- Download von Staffeln und Filmen
- Sortierung nach Download: Filme → `Filme`, Staffeln → `Staffel 1`, `Staffel 2` …
- Option, nur fehlende deutsche Folgen zu prüfen (`german`) oder neue Episoden zu prüfen (`new-episodes`)

### Dateistruktur

```
AniLoader/
├─ Anime.txt # Liste der Anime-URLs (eine pro Zeile)
├─ anime.db # SQLite-Datenbank für Fortschritt und fehlende Folgen
├─ Anime/ # Standard-Downloadordner
│ ├─ Titel/ # Unterordner pro Serie
│ │ ├─ Filme/ # Filme
│ │ │ ├─ Film-1.mp4
│ │ │ └─ ...
│ │ ├─ Staffel 1/ # Staffeln
│ │ │ ├─ S01E001 - Titel [Dub].mp4
│ │ │ └─ ...
├─ downloader.py # Hauptskript
└─ README.md # Diese Datei
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Installation

1. **Repository klonen**

- ```https://github.com/WimWamWom/AniLoader```

2. **Python-Abhängigkeiten installieren**

- ```pip install requests beautifulsoup4```

3. **Download-Tool `aniworld` installieren**  

- Stelle sicher, dass das CLI-Tool `pip install aniworld` auf deinem System verfügbar ist.

### Anime-Liste erstellen

Die Datei `Anime.txt` enthält die Links zu den Animes / Serien, z. B.:

```
https://aniworld.to/serie/naruto
https://s.to/serie/stream/the-rookie
```
Jede URL muss in einer neuen Zeile stehen. Es darf dabei nur der Link zu dem Anime/der Serie sein, nicht zu einer spezifischen Folge.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Nutzung

### Alle Anime herunterladen

```py downloader.py```

- Lädt alle Filme und Staffeln herunter
- Aktualisiert die SQLite-Datenbank und markiert abgeschlossene Anime
- Sortiert die Dateien automatisch in Unterordner

### Nur fehlende deutsche Folgen herunterladen

```py downloader.py german```

- Prüft nur Anime mit fehlenden deutschen Folgen (`fehlende_deutsch_folgen`) und lädt diese nach

### Neue Episoden prüfen und herunterladen

```py downloader.py new-episodes```

- Prüft bei jedem Anime nach neuen Filmen oder Staffeln ab der letzten heruntergeladenen Folge
- Lädt neue Episoden herunter und aktualisiert die Datenbank

## Hinweise
### Good to Know
- Die URL-Struktur des Anime muss dem Format von AniWorld oder SerienStream entsprechen
- Alte Untertitelversionen (außer German Dub) werden automatisch gelöscht
- Fehlende Streams oder Sprachprobleme zeigen Warnungen an

### Anpassung

- `DOWNLOAD_DIR`: Ordner für die Downloads
- `ANIME_TXT`: Pfad zur Anime-Textdatei
- `LANGUAGES`: Reihenfolge und Sprachen, die beim Download versucht werden
- `DB_PATH`: Speicherort der SQLite-Datenbank
<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Beispiele

### Dateiname nach Download


```
S01E005 - Der Ninja-Test [Dub].mp4
S01E006 - Kampf der Klingen [Sub].mp4
```

### Beispiel für die Eingabe der Link  (`Anime.txt`)
```
https://aniworld.to/anime/stream/a-certain-magical-index
https://s.to/serie/stream/family-guy
https://aniworld.to/anime/stream/classroom-of-the-elite
https://aniworld.to/anime/stream/highschool-dxd
https://s.to/serie/stream/die-schluempfe
https://s.to/serie/stream/die-abenteuer-des-jungen-marco-polo
```


### Beispiel SQLite-Datenbank (`anime.db`)
- wird automatisch erstellt, enthält pro Anime:
  - `title`
  - `url`
  - `complete`
  - `deutsch_komplett`
  - `fehlende_deutsch_folgen` (JSON-Array)
  - `last_film` (Integer)
  - `last_episode` (Integer)

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
