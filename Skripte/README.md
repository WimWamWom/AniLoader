# AniLoader Hilfsskripte

Dieses Verzeichnis enthält Automations- und Wartungsskripte für AniLoader.
Funktionsgleiche Varianten sind jeweils als `.sh` und `.ps1` vorhanden.

## Quick Start

- Neue Folgen prüfen: `check-new.sh` oder `check-new.ps1`
- Fehlende deutsche Folgen prüfen: `check-german.sh` oder `check-german.ps1`
- Letzten Lauf auswerten: `last_run_summary.sh` oder `last_run_summary.ps1`
- Einzelnen DB-Eintrag ändern: `db_edit.py`
- Titel/Ordnernamen prüfen: `folder_name_check.py`
- [Sub]-Inkonsistenzen zwischen Dateisystem und DB finden: `find_sub_db_inconsistencies.sh`
- [Sub]-Inkonsistenzen in DB eintragen (Fix): `fix_sub_db_inconsistencies.py`

## Übersicht nach Aufgabe

| Aufgabe | Dateien | Zweck |
|--------|---------|-------|
| Neue Episoden prüfen und benachrichtigen | `check-new.sh` + `check-new.ps1` | Startet Modus `new`, wertet den Lauf aus, sendet Discord bei Treffern |
| Fehlende deutsche Episoden prüfen und benachrichtigen | `check-german.sh` + `check-german.ps1` | Startet Modus `german`, wertet nur German-Dub-Downloads aus |
| Letzten Lauf zusammenfassen | `last_run_summary.sh` + `last_run_summary.ps1` | Liest `last_run`, erkennt Modus automatisch und sendet optional Discord |
| Datenbankeintrag gezielt bearbeiten | `db_edit.py` | Ändert einzelne Felder eines DB-Eintrags per ID mit Bestätigung |
| Titel gegen Ordnername prüfen | `folder_name_check.py` | Findet DB-Einträge, bei denen `title` und `folder_name` nicht zusammenpassen |
| [Sub]-Inkonsistenzen analysieren | `find_sub_db_inconsistencies.sh` | Findet lokal vorhandene [Sub]-Dateien, die nicht mehr in `fehlende_deutsch_folgen` stehen |
| [Sub]-Inkonsistenzen in DB eintragen | `fix_sub_db_inconsistencies.py` | Trägt die vom Bash-Skript gefundenen Inkonsistenzen in die DB ein |

## Detailliert pro Skript

### 1) check-new (.sh/.ps1)

**Dateien:** `check-new.sh`, `check-new.ps1`

**Was es macht:**
1. Prüft, ob AniLoader aktuell läuft (`/status`).
2. Wartet bei Bedarf bis `MAX_WAIT_MINUTES`.
3. Startet Download-Modus `new` über `/start_download`.
4. Wartet bis der Lauf fertig ist.
5. Liest `/last_run` aus.
6. Zählt erfolgreich geladene Episoden über Download- und Verify-Logzeilen.
7. Sendet nur dann Discord, wenn neue Episoden gefunden wurden.

**Typischer Einsatz:** zyklisch (z.B. alle 6 Stunden).

---

### 2) check-german (.sh/.ps1)

**Dateien:** `check-german.sh`, `check-german.ps1`

**Was es macht:**
1. Prüft, ob AniLoader frei ist (`/status`) und wartet bei Bedarf.
2. Startet Download-Modus `german` über `/start_download`.
3. Wartet bis der Lauf abgeschlossen ist.
4. Liest `/last_run` aus.
5. Zählt nur Downloads, die als **German Dub** geloggt wurden.
6. Sendet nur dann Discord, wenn neue deutsche Episoden gefunden wurden.

**Typischer Einsatz:** seltener Cron-Job (z.B. 1x pro Woche).

---

### 3) last_run_summary (.sh/.ps1)

**Dateien:** `last_run_summary.sh`, `last_run_summary.ps1`

**Was es macht:**
1. Holt Logs entweder von der API (`/last_run`) oder aus lokaler Datei.
2. Erkennt den Modus automatisch (`german`, `new`, `default`, `check`).
3. Ermittelt gefundene/geladene Episoden aus den Logzeilen.
4. Gibt eine Zusammenfassung im Terminal aus.
5. Sendet Discord nur bei vorhandenen Episoden.

**Typischer Einsatz:** manuell nach einem Lauf oder als Reporting-Schritt.

---

### 4) db_edit.py

**Datei:** `db_edit.py`

**Was es macht:**
1. Lädt einen Datensatz über `ANIME_ID` aus der Datenbank.
2. Zeigt den aktuellen Stand aller editierbaren Felder.
3. Übernimmt nur Felder, die im Konfigurationsblock geändert wurden.
4. Fragt vor dem Speichern explizit nach Bestätigung.
5. Zeigt nach dem Speichern den aktualisierten Datensatz.

**Besonderheit:**
- `BEHALTEN` = Feld nicht ändern.
- `DELETE` = Feld auf den jeweiligen Default zurücksetzen.

**Typischer Einsatz:** Korrekturen einzelner DB-Einträge (Titel, Ordnername, Statusfelder).

---

### 5) folder_name_check.py

**Datei:** `folder_name_check.py`

**Was es macht:**
1. Liest alle AniLoader-Einträge aus der Datenbank.
2. Vergleicht `title` mit `folder_name`.
3. Ignoriert typische Suffixe im Ordnernamen, z.B. Jahr/Zeitraum und IMDb-Block.
4. Normalisiert Sonderzeichen, Trennzeichen und Schreibweisen für robusten Vergleich.
5. Gibt übersichtliche Listen für:
   - fehlende Ordnernamen
   - abweichende Ordnernamen

**Optionen:**
- `--include-deleted`: nimmt gelöschte Einträge in die Prüfung auf.

**Typischer Einsatz:** Qualitätscheck der Datenbank vor/ nach größeren Importen.

---

### 6) find_sub_db_inconsistencies (.sh)

**Datei:** `find_sub_db_inconsistencies.sh`

**Was es macht:**
1. Liest Medienpfade und DB-Pfad aus der `config.yaml`.
2. Mappt Container-Pfade (`/app/...`) automatisch auf Host-Pfade via `docker inspect`.
3. Durchsucht alle Serien-Ordner nach Dateien mit `[Sub]` im Namen.
4. Vergleicht gefundene Episoden mit `fehlende_deutsch_folgen` in der DB.
5. Gibt alle Episoden aus, die lokal als `[Sub]` vorliegen, aber nicht mehr als fehlende deutsche Version in der DB geführt werden.
6. Schreibt einen detaillierten Report als Textdatei.

**Optionen:**
- Argument 1: Pfad zur `config.yaml` (Standard: `data/config.yaml`)
- Argument 2: Pfad zur Report-Ausgabedatei (Standard: `data/sub_db_inconsistencies_<timestamp>.txt`)
- Umgebungsvariable `ANILOADER_CONTAINER`: Name des Docker-Containers (Standard: `AniLoader`)

**Typischer Einsatz:** einmalig oder nach größeren Änderungen am Dateibestand.

**Ausführung:**
```bash
bash find_sub_db_inconsistencies.sh /mnt/user/Docker/AniLoader/data/config.yaml
```

---

### 7) fix_sub_db_inconsistencies (.py)

**Datei:** `fix_sub_db_inconsistencies.py`

**Was es macht:**
1. Liest den Report von `find_sub_db_inconsistencies.sh` ein.
2. Rekonstruiert die fehlenden Episoden-URLs (analog zu `app/scraper.py`).
3. Ergänzt diese URLs in `fehlende_deutsch_folgen` der betroffenen DB-Einträge.
4. Setzt `deutsch_komplett = 0` für alle betroffenen Serien.
5. Gibt eine Übersicht aller Änderungen aus (mit `--dry-run` ohne zu schreiben).

**Optionen:**
- `--db <pfad>`: DB-Pfad manuell angeben (wird sonst aus Report-Header gelesen)
- `--dry-run`: Zeigt nur was geändert würde, ohne die DB zu schreiben

**Typischer Einsatz:** direkt nach `find_sub_db_inconsistencies.sh` ausführen, danach AniLoader im German-Modus starten um die fehlenden Dubs nachzuladen.

**Ausführung:**
```bash
# Erst Dry-run zur Kontrolle
python fix_sub_db_inconsistencies.py data/sub_db_inconsistencies_<timestamp>.txt --dry-run

# Dann schreiben
python fix_sub_db_inconsistencies.py data/sub_db_inconsistencies_<timestamp>.txt --db data/AniLoader.db
```

## Konfiguration der API/Discord-Skripte

In allen drei Automations-Skriptpaaren werden oben dieselben Werte gesetzt:

- `API_ENDPOINT`: AniLoader-URL, z.B. `http://192.168.1.100:5050`
- `API_AUTH`: optional `username:password` für Basic Auth
- `DISCORD_WEBHOOK_URLS`: eine oder mehrere Webhook-URLs
- `MAX_WAIT_MINUTES`: maximale Wartezeit, wenn ein Lauf bereits aktiv ist (`0` = unbegrenzt)

## Ausführung

### Bash (.sh)

```bash
bash ./check-new.sh
bash ./check-german.sh
bash ./last_run_summary.sh
```

### PowerShell (.ps1)

```powershell
powershell -ExecutionPolicy Bypass -File .\check-new.ps1
powershell -ExecutionPolicy Bypass -File .\check-german.ps1
powershell -ExecutionPolicy Bypass -File .\last_run_summary.ps1
```

### Python-Helfer

```bash
python ./db_edit.py
python ./folder_name_check.py
python ./folder_name_check.py --include-deleted
python ./fix_sub_db_inconsistencies.py data/sub_db_inconsistencies_20260429_095126.txt
python ./fix_sub_db_inconsistencies.py data/sub_db_inconsistencies_20260429_095126.txt --dry-run
```

## Hinweise

- Für die API-basierten Skripte muss AniLoader laufen und erreichbar sein.
- Discord-Benachrichtigungen werden nur gesendet, wenn Episoden gefunden wurden.
- `.sh` und `.ps1` eines Paares sind funktional gleich gedacht; nutze die passende Variante für deine Umgebung.
