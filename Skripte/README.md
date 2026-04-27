# AniLoader Hilfsskripte

Dieses Verzeichnis enthält Automations- und Wartungsskripte für AniLoader.
Funktionsgleiche Varianten sind jeweils als `.sh` und `.ps1` vorhanden.

## Quick Start

- Neue Folgen prüfen: `check-new.sh` oder `check-new.ps1`
- Fehlende deutsche Folgen prüfen: `check-german.sh` oder `check-german.ps1`
- Letzten Lauf auswerten: `last_run_summary.sh` oder `last_run_summary.ps1`
- Einzelnen DB-Eintrag ändern: `db_edit.py`
- Titel/Ordnernamen prüfen: `folder_name_check.py`

## Übersicht nach Aufgabe

| Aufgabe | Dateien | Zweck |
|--------|---------|-------|
| Neue Episoden prüfen und benachrichtigen | `check-new.sh` + `check-new.ps1` | Startet Modus `new`, wertet den Lauf aus, sendet Discord bei Treffern |
| Fehlende deutsche Episoden prüfen und benachrichtigen | `check-german.sh` + `check-german.ps1` | Startet Modus `german`, wertet nur German-Dub-Downloads aus |
| Letzten Lauf zusammenfassen | `last_run_summary.sh` + `last_run_summary.ps1` | Liest `last_run`, erkennt Modus automatisch und sendet optional Discord |
| Datenbankeintrag gezielt bearbeiten | `db_edit.py` | Ändert einzelne Felder eines DB-Eintrags per ID mit Bestätigung |
| Titel gegen Ordnername prüfen | `folder_name_check.py` | Findet DB-Einträge, bei denen `title` und `folder_name` nicht zusammenpassen |

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
```

## Hinweise

- Für die API-basierten Skripte muss AniLoader laufen und erreichbar sein.
- Discord-Benachrichtigungen werden nur gesendet, wenn Episoden gefunden wurden.
- `.sh` und `.ps1` eines Paares sind funktional gleich gedacht; nutze die passende Variante für deine Umgebung.
