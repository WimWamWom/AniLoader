#!/bin/bash
# last_run_summary.sh - Liest last_run.txt und sendet Discord-Benachrichtigung
# Analysiert die Log-Datei nach deutschen Episoden

echo "========================================="
echo "AniLoader - LastRun Auswertung"
echo "Gestartet am: $(date)"
echo "========================================="

# ============================================
# KONFIGURATION
# ============================================
LASTRUN_FILE="/mnt/user/Docker/AniLoader/data/last_run.txt"  # ANPASSEN!

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
    "title": "🇩🇪 AniLoader - LastRun Auswertung",
    "description": "${message}",
    "color": ${color},
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%S.000Z)",
    "footer": {
      "text": "AniLoader"
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

# Gruppierte Discord Embed Funktion mit Fields
send_discord_grouped_embed() {
    local title="$1"
    local summary="$2"
    local color="$3"
    local error_info="$4"
    shift 4
    # Rest sind Serie:Episode Paare
    
    if [ ${#DISCORD_WEBHOOK_URLS[@]} -eq 0 ]; then
        return 0
    fi
    
    # Baue Fields Array
    local fields="["
    local field_count=0
    local MAX_FIELDS=25
    
    # Temporäre Arrays für Gruppierung
    declare -A series_episodes
    
    # Gruppiere Episoden nach Serie
    while [ $# -gt 0 ]; do
        local episode="$1"
        shift
        
        # Extrahiere Serie und Episode-Info
        if [[ "$episode" =~ ^(.+)[[:space:]]+(S[0-9]{2}E[0-9]{2}|Film[[:space:]][0-9]+)$ ]]; then
            local series_name="${BASH_REMATCH[1]}"
            local episode_info="${BASH_REMATCH[2]}"
            
            if [ -z "${series_episodes[$series_name]}" ]; then
                series_episodes["$series_name"]="$episode_info"
            else
                series_episodes["$series_name"]+=" |$episode_info"
            fi
        fi
    done
    
    # Erstelle Fields
    for series in "${!series_episodes[@]}"; do
        local episodes="${series_episodes[$series]}"
        IFS='|' read -ra ep_array <<< "$episodes"
        local ep_count=${#ep_array[@]}
        
        if [ $field_count -gt 0 ]; then
            fields+=","
        fi
        
        if [ $ep_count -eq 1 ]; then
            fields+="{\"name\":\"$series\",\"value\":\"- ${ep_array[0]}\",\"inline\":false}"
        else
            local value=""
            for ep in "${ep_array[@]}"; do
                if [ -z "$value" ]; then
                    value="- $ep"
                else
                    value+="\\n- $ep"
                fi
            done
            fields+="{\"name\":\"$series ($ep_count x)\",\"value\":\"$value\",\"inline\":false}"
        fi
        
        field_count=$((field_count + 1))
        
        if [ $field_count -ge $MAX_FIELDS ]; then
            break
        fi
    done
    
    fields+="]"
    
    # Baue description mit error_info
    local description="$summary"
    if [ ! -z "$error_info" ]; then
        description+="\\n\\n$error_info"
    fi
    
    # Erstelle Embed
    local json_payload=$(cat <<EOF
{
  "embeds": [{
    "title": "${title}",
    "description": "${description}",
    "color": ${color},
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%S.000Z)",
    "fields": ${fields},
    "footer": {
      "text": "AniLoader"
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
    wait
}

# ============================================
# HAUPTPROGRAMM
# ============================================

# Prüfe ob Datei existiert
if [ ! -f "$LASTRUN_FILE" ]; then
    echo "[FEHLER] Datei nicht gefunden: $LASTRUN_FILE"
    exit 1
fi

echo "Lese Datei: $LASTRUN_FILE"
LOG_CONTENT=$(cat "$LASTRUN_FILE")

if [ -z "$LOG_CONTENT" ]; then
    echo "[WARNUNG] Datei ist leer."
    exit 0
fi

echo "Werte Logs aus..."
echo ""

# ============================================
# LOGS PARSEN
# ============================================

# Suche nach deutschen Episoden: [GERMAN].*erfolgreich auf deutsch
declare -a PARSED_EPISODES

while IFS= read -r line; do
    if [[ "$line" =~ \[GERMAN\][[:space:]]+\'(https://aniworld\.to/anime/stream/[^\']+)\'[[:space:]]+erfolgreich[[:space:]]+auf[[:space:]]+deutsch ]]; then
        url="${BASH_REMATCH[1]}"
        
        # Parse URL zu lesbarem Format
        if [[ "$url" =~ /anime/stream/([^/]+)/staffel-([0-9]+)/episode-([0-9]+) ]]; then
            series_slug="${BASH_REMATCH[1]}"
            season="${BASH_REMATCH[2]}"
            episode="${BASH_REMATCH[3]}"
            
            # Konvertiere slug zu Title Case
            series_name=$(echo "$series_slug" | sed 's/-/ /g' | awk '{for(i=1;i<=NF;i++) $i=toupper(substr($i,1,1)) tolower(substr($i,2));}1')
            season_padded=$(printf "%02d" $season)
            episode_padded=$(printf "%02d" $episode)
            
            PARSED_EPISODES+=("$series_name S${season_padded}E${episode_padded}")
        elif [[ "$url" =~ /anime/stream/([^/]+)/filme/film-([0-9]+) ]]; then
            series_slug="${BASH_REMATCH[1]}"
            film_nr="${BASH_REMATCH[2]}"
            
            series_name=$(echo "$series_slug" | sed 's/-/ /g' | awk '{for(i=1;i<=NF;i++) $i=toupper(substr($i,1,1)) tolower(substr($i,2));}1')
            PARSED_EPISODES+=("$series_name Film $film_nr")
        fi
    fi
done <<< "$LOG_CONTENT"

# Zähle Fehler
ERROR_COUNT=$(echo "$LOG_CONTENT" | grep -c "\[ERROR\]")

# ============================================
# ZUSAMMENFASSUNG
# ============================================

NEW_GERMAN_COUNT=${#PARSED_EPISODES[@]}

echo "=== ZUSAMMENFASSUNG ==="
echo "Neue deutsche Episoden gefunden: $NEW_GERMAN_COUNT"
echo "Fehler: $ERROR_COUNT"
echo ""

if [ $NEW_GERMAN_COUNT -gt 0 ]; then
    echo "Gefundene Episoden (gruppiert):"
    for episode in "${PARSED_EPISODES[@]}"; do
        echo "  - $episode"
    done
    echo ""
fi

# ============================================
# DISCORD BENACHRICHTIGUNG (NUR BEI NEUEN EPISODEN)
# ============================================

if [ "$NEW_GERMAN_COUNT" -gt 0 ]; then
    # NUR wenn neue Episoden gefunden wurden
    summary="✅ **${NEW_GERMAN_COUNT} neue deutsche Episode(n) gefunden!**"
    
    error_info=""
    if [ "$ERROR_COUNT" -gt 0 ]; then
        error_info="⚠️ ${ERROR_COUNT} Fehler aufgetreten"
    fi
    
    if [ ${#PARSED_EPISODES[@]} -gt 0 ]; then
        # Nutze gruppierte Embed Funktion
        send_discord_grouped_embed \
            "🇩🇪 AniLoader - LastRun Auswertung" \
            "$summary" \
            "3066993" \
            "$error_info" \
            "${PARSED_EPISODES[@]}"
        echo "[OK] Discord Benachrichtigung gesendet mit ${NEW_GERMAN_COUNT} Episoden!"
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
    echo "[INFO] Keine neuen deutschen Episoden - keine Discord-Benachrichtigung."
fi

echo ""
echo "Script abgeschlossen: $(date)"
