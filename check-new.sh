#!/bin/bash
# check-new.sh - Prüft auf neue Episoden
# Führt den AniLoader im "new" Modus aus

echo "========================================="
echo "AniLoader - Check New Episodes"
echo "Gestartet am: $(date)"
echo "========================================="

# ============================================
# KONFIGURATION
# ============================================
API_ENDPOINT="https://your-domain.example.com"

# Basic Auth (falls Domain AUTH-geschützt ist)
# Format: "username:password" oder leer lassen
API_AUTH="username:password"

# Discord Webhook URLs (als Array - leer lassen um Discord zu deaktivieren)
# Mehrere URLs einfach untereinander eintragen:
DISCORD_WEBHOOK_URLS=(
    "https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN"
    # "https://discord.com/api/webhooks/ZWEITE_WEBHOOK_URL"
    # "https://discord.com/api/webhooks/DRITTE_WEBHOOK_URL"
)

# ============================================
# DISCORD WEBHOOK FUNKTION
# ============================================
send_discord_message() {
    local message="$1"
    local color="$2"  # Dezimal: 3066993 (grün), 15158332 (rot), 3447003 (blau)
    
    if [ ${#DISCORD_WEBHOOK_URLS[@]} -eq 0 ]; then
        return 0
    fi
    
    local json_payload=$(cat <<EOF
{
  "embeds": [{
    "title": "📺 AniLoader - Neue Episoden Check",
    "description": "${message}",
    "color": ${color},
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%S.000Z)",
    "footer": {
      "text": "Unraid AniLoader"
    }
  }]
}
EOF
)
    
    # Sende an alle konfigurierten Webhooks
    for webhook_url in "${DISCORD_WEBHOOK_URLS[@]}"; do
        [ -z "$webhook_url" ] && continue
        curl -s -H "Content-Type: application/json" \
             -d "${json_payload}" \
             "${webhook_url}" > /dev/null &
    done
    wait  # Warte auf alle parallelen Requests
}

# Multi-Embed Funktion für lange Listen
send_discord_multi_embed() {
    local title="$1"
    local summary="$2"
    local episodes="$3"
    local color="$4"
    local error_info="$5"
    
    if [ ${#DISCORD_WEBHOOK_URLS[@]} -eq 0 ]; then
        return 0
    fi
    
    # Maximale Zeichen pro Embed (2048 - Reserve für Header/Footer)
    local MAX_DESC_LENGTH=1800
    
    # Erstelle Array aus Episoden
    mapfile -t EPISODE_ARRAY < <(echo "$episodes")
    
    # Berechne Header-Länge
    local header="$summary\n\n📺 **Neue Episoden:**\n"
    local header_length=${#header}
    
    # Teile Episoden in Chunks auf
    declare -a chunks
    local current_chunk=""
    local current_length=$header_length
    local chunk_index=0
    
    for episode in "${EPISODE_ARRAY[@]}"; do
        local line="• $episode\n"
        local line_length=${#line}
        
        if [ $((current_length + line_length)) -gt $MAX_DESC_LENGTH ] && [ ! -z "$current_chunk" ]; then
            chunks[$chunk_index]="$current_chunk"
            chunk_index=$((chunk_index + 1))
            current_chunk="$line"
            current_length=$line_length
        else
            current_chunk+="$line"
            current_length=$((current_length + line_length))
        fi
    done
    
    # Letzten Chunk speichern
    if [ ! -z "$current_chunk" ]; then
        chunks[$chunk_index]="$current_chunk"
    fi
    
    local total_chunks=$((chunk_index + 1))
    
    # Erstelle Embeds JSON
    local embeds="["
    
    for i in "${!chunks[@]}"; do
        local part_num=$((i + 1))
        local desc=""
        local embed_title="$title"
        
        if [ $i -eq 0 ]; then
            # Erstes Embed mit Header
            desc="$summary\n\n📺 **Neue Episoden:**\n${chunks[$i]}"
            if [ $total_chunks -gt 1 ]; then
                embed_title="$title (Teil 1/$total_chunks)"
            fi
        else
            # Folge-Embeds
            desc="📺 **Fortsetzung (Teil $part_num/$total_chunks):**\n${chunks[$i]}"
            embed_title="$title (Teil $part_num/$total_chunks)"
        fi
        
        # Fehler im letzten Embed
        if [ $i -eq $chunk_index ] && [ ! -z "$error_info" ]; then
            desc="$desc\n\n$error_info"
        fi
        
        # Escape für JSON
        desc=$(echo -e "$desc" | sed 's/\\/\\\\/g' | sed 's/"/\\"/g' | sed ':a;N;$!ba;s/\n/\\n/g')
        
        if [ $i -gt 0 ]; then
            embeds+=","
        fi
        
        embeds+="{\"title\":\"$embed_title\",\"description\":\"$desc\",\"color\":$color,\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%S.000Z)\""
        
        if [ $i -eq 0 ]; then
            embeds+=",\"footer\":{\"text\":\"Unraid AniLoader\"}"
        fi
        
        embeds+="}"
    done
    
    embeds+="]"
    
    # Sende an alle konfigurierten Webhooks
    for webhook_url in "${DISCORD_WEBHOOK_URLS[@]}"; do
        [ -z "$webhook_url" ] && continue
        curl -s -H "Content-Type: application/json" \
             -d "{\"embeds\":$embeds}" \
             "${webhook_url}" > /dev/null &
    done
    wait  # Warte auf alle parallelen Requests
}

# ============================================
# HAUPTPROGRAMM
# ============================================

# Curl Auth Parameter vorbereiten
AUTH_PARAM=""
if [ ! -z "$API_AUTH" ]; then
    AUTH_PARAM="-u ${API_AUTH}"
fi

# ============================================
# WARTE-LOGIK: Prüfe ob System bereits beschäftigt
# ============================================
MAX_WAIT_MINUTES=120  # Maximal 2 Stunden warten
waited=0

echo "Prüfe ob System frei ist..."
while true; do
    STATUS=$(curl -s ${AUTH_PARAM} "${API_ENDPOINT}/status" 2>/dev/null | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
    
    if [ "$STATUS" != "running" ]; then
        echo "[OK] System ist frei, starte New-Check..."
        break
    fi
    
    if [ $waited -ge $MAX_WAIT_MINUTES ]; then
        echo "[WARNUNG] Timeout: System nach ${MAX_WAIT_MINUTES} Minuten noch beschäftigt"
        echo "New-Check wird abgebrochen."
        exit 1
    fi
    
    echo "[WARTE] System beschäftigt (Status: $STATUS), warte... (${waited}/${MAX_WAIT_MINUTES} Minuten)"
    sleep 60
    waited=$((waited + 1))
done

# API Aufruf zum Starten des new Modus
echo "Starte New-Check via ${API_ENDPOINT}..."
curl -s -X POST ${AUTH_PARAM} "${API_ENDPOINT}/start_download" \
    -H "Content-Type: application/json" \
    -d '{"mode":"new"}'

echo "Warte auf Abschluss des Downloads..."
sleep 10

# Warte bis der Download abgeschlossen ist
while true; do
    STATUS=$(curl -s ${AUTH_PARAM} "${API_ENDPOINT}/status" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
    if [ "$STATUS" != "running" ]; then
        echo "Check abgeschlossen (Status: $STATUS)"
        break
    fi
    echo "Läuft noch... (Status: $STATUS)"
    sleep 30
done

# ============================================
# LOGS AUSWERTEN
# ============================================
echo ""
echo "Werte Logs aus..."

# Hole die Logs vom aktuellen Run über /last_run API
# (nicht /logs, da das ALLE Logs seit Server-Start enthält)
LOG_CONTENT=$(curl -s ${AUTH_PARAM} "${API_ENDPOINT}/last_run" 2>/dev/null || echo "")

if [ -z "$LOG_CONTENT" ]; then
    echo "Keine Logs verfügbar."
    exit 0
fi

# Extrahiere Informationen aus den Logs
NEW_EPISODES_COUNT=$(echo "$LOG_CONTENT" | grep -c "\[SUCCESS\].*heruntergeladen")
SKIPPED_COUNT=$(echo "$LOG_CONTENT" | grep -c "\[SKIP\]")
ERROR_COUNT=$(echo "$LOG_CONTENT" | grep -c "\[ERROR\]")

# Erstelle Liste ALLER neuen Episoden (kein Limit)
NEW_EPISODES=$(echo "$LOG_CONTENT" | grep "\[SUCCESS\].*heruntergeladen" | sed 's/.*\[SUCCESS\] //')

# Zähle betroffene Serien
if [ ! -z "$NEW_EPISODES" ]; then
    SERIES_COUNT=$(echo "$NEW_EPISODES" | cut -d':' -f1 | sort -u | wc -l)
else
    SERIES_COUNT=0
fi

echo ""
echo "=== ZUSAMMENFASSUNG ==="
echo "Neue Episoden gefunden: $NEW_EPISODES_COUNT"
echo "Betroffene Serien: $SERIES_COUNT"
echo "Übersprungen: $SKIPPED_COUNT"
echo "Fehler: $ERROR_COUNT"

# ============================================
# DISCORD BENACHRICHTIGUNG (NUR BEI NEUEN EPISODEN)
# ============================================

if [ "$NEW_EPISODES_COUNT" -gt 0 ]; then
    # NUR wenn neue Episoden heruntergeladen wurden
    summary="✅ **${NEW_EPISODES_COUNT} neue Episode(n) heruntergeladen!**
📊 **${SERIES_COUNT} Serie(n) aktualisiert**"
    
    error_info=""
    if [ "$ERROR_COUNT" -gt 0 ]; then
        error_info="⚠️ ${ERROR_COUNT} Fehler aufgetreten"
    fi
    
    if [ ! -z "$NEW_EPISODES" ]; then
        # Nutze Multi-Embed Funktion für automatische Aufteilung
        send_discord_multi_embed \
            "📺 AniLoader - Neue Episoden Check" \
            "$summary" \
            "$NEW_EPISODES" \
            "3066993" \
            "$error_info"
        echo "[OK] Discord Benachrichtigung gesendet mit ${NEW_EPISODES_COUNT} Episoden!"
    else
        # Keine Episoden-Details, nur Summary
        msg="$summary"
        if [ ! -z "$error_info" ]; then
            msg+="

${error_info}"
        fi
        send_discord_message "$msg" "3066993"
        echo "[OK] Discord Benachrichtigung gesendet!"
    fi
else
    # Keine Discord-Nachricht bei 0 neuen Episoden
    echo "[INFO] Keine neuen Episoden - keine Discord-Benachrichtigung."
fi

echo ""
echo "Script abgeschlossen: $(date)"
