# Unraid Skripte – Automatischer Scan mit Discord-Benachrichtigung

Diese Skripte sind **optional** und für Unraid-Nutzer gedacht, die automatische Downloads per Cronjob auslösen und sich per Discord über neue Episoden benachrichtigen lassen möchten.

## Skripte

| Skript | Beschreibung | Empfohlener Cron |
|--------|--------------|------------------|
| `check-new.sh` | Prüft alle Serien auf **neue Episoden** (Modus `new`) | `0 */6 * * *` (alle 6h) |
| `check-german.sh` | Prüft auf **fehlende deutsche Episoden** (Modus `german`) | `0 3 * * 0` (So 3 Uhr) |
| `last_run_summary.sh` | Wertet den **letzten Lauf** aus und sendet Discord-Nachricht | Manuell / nach Bedarf |

## Funktionsweise

### check-new.sh / check-german.sh
1. Prüft ob AniLoader gerade beschäftigt ist (wartet bis zu 3 Stunden)
2. Startet den Download im jeweiligen Modus über die API
3. Wartet auf Abschluss
4. Wertet die Logs aus und zählt heruntergeladene Episoden
5. Sendet bei neuen Episoden eine **Discord-Nachricht** mit gruppierten Details

### last_run_summary.sh
1. Holt die Logs des letzten Laufs (API oder lokale Datei)
2. Erkennt automatisch den Modus (german / new / default / check)
3. Zählt heruntergeladene Episoden
4. Sendet bei Ergebnissen eine Discord-Benachrichtigung

## Installation (Unraid User Scripts)

1. **User Scripts Plugin** installieren (falls noch nicht vorhanden):
   - Unraid → Apps → „User Scripts" suchen → installieren

2. **Skript hinzufügen**:
   - Settings → User Scripts → „Add New Script"
   - Inhalt des gewünschten `.sh`-Skripts einfügen

3. **Konfiguration anpassen** (oben im Skript):
   ```bash
   # AniLoader API Adresse
   API_ENDPOINT="https://your-domain.example.com"
   # oder lokal: API_ENDPOINT="http://192.168.1.100:5050"
   
   # Basic Auth (falls hinter Reverse Proxy mit Auth)
   API_AUTH="username:password"
   # Ohne Auth: API_AUTH=""
   
   # Discord Webhook URLs
   DISCORD_WEBHOOK_URLS=(
       "https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN"
   )
   
   # Maximale Wartezeit in Minuten (0 = unbegrenzt)
   MAX_WAIT_MINUTES=180
   ```

4. **Schedule setzen**:
   - `check-new.sh`: Custom Cron → `0 */6 * * *` (alle 6 Stunden)
   - `check-german.sh`: Custom Cron → `0 3 * * 0` (Sonntags um 3 Uhr)
   - `last_run_summary.sh`: „Run Manually" oder als Ergänzung

## Discord Webhook einrichten

1. Discord → Server Settings → Integrations → Webhooks
2. „New Webhook" → Name & Channel wählen → „Copy Webhook URL"
3. URL in das Skript eintragen (mehrere Webhooks möglich)

### Discord Embed Beispiel

Die Benachrichtigungen werden als gruppierte Embeds gesendet:

```
📺 AniLoader - Neue Episoden Check
────────────────────────────────────
✅ 5 neue Episode(n) heruntergeladen!
📊 3 Serie(n) aktualisiert

Naruto (2 x)
  - S01E045
  - S01E046

One Piece
  - S02E100

Breaking Bad (2 x)
  - S03E001
  - S03E002
```

Bei mehr als 25 Serien werden automatisch mehrere Embeds erstellt.

## Hinweise

- Die Skripte kommunizieren über die **REST-API** mit AniLoader – der Container muss laufen
- Discord-Benachrichtigungen werden **nur gesendet**, wenn tatsächlich neue Episoden heruntergeladen wurden
- Alle Skripte warten automatisch, falls gerade ein Download läuft (max. 3 Stunden)
- Umlaute (ä, ö, ü, ß) in Serien-Namen werden korrekt dargestellt
