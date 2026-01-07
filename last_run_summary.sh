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

# JSON-Escape Funktion
json_escape() {
    local string="$1"
    # Escape backslash, double quotes, newlines, tabs, carriage returns
    string="${string//\\/\\\\}"  # \ -> \\
    string="${string//\"/\\\"}"  # " -> \"
    string="${string//$'\n'/\\n}"  # newline -> \n
    string="${string//$'\r'/\\r}"  # carriage return -> \r
    string="${string//$'\t'/\\t}"  # tab -> \t
    echo "$string"
}

send_discord_message() {
    local message="$1"
    local color="$2"  # Dezimal: 3066993 (grün), 15158332 (rot), 3447003 (blau)
    
    if [ ${#DISCORD_WEBHOOK_URLS[@]} -eq 0 ]; then
        return 0
    fi
    
    # JSON-Escape für die Message
    local message_escaped=$(json_escape "$message")
    
    local json_payload=$(cat <<EOF
{
  "embeds": [{
    "title": "🇩🇪 AniLoader - LastRun Auswertung",
    "description": "$message_escaped",
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
    local success=0
    local failed=0
    for webhook_url in "${DISCORD_WEBHOOK_URLS[@]}"; do
        [ -z "$webhook_url" ] && continue
        
        # Sende Request und zeige Response
        local response=$(curl -s -w "\n%{http_code}" -H "Content-Type: application/json" \
             -d "${json_payload}" \
             "${webhook_url}")
        
        local http_code=$(echo "$response" | tail -n1)
        local body=$(echo "$response" | sed '$d')
        
        if [ "$http_code" = "204" ] || [ "$http_code" = "200" ]; then
            ((success++))
        else
            ((failed++))
            echo "[FEHLER] Discord Webhook fehlgeschlagen (HTTP $http_code)"
            [ ! -z "$body" ] && echo "Response: $body"
        fi
    done
    
    [ $failed -gt 0 ] && return 1
    return 0
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
        
        # JSON-Escape für Serie-Namen
        local series_escaped=$(json_escape "$series")
        
        if [ $ep_count -eq 1 ]; then
            local ep_escaped=$(json_escape "${ep_array[0]}")
            fields+="{\"name\":\"$series_escaped\",\"value\":\"- $ep_escaped\",\"inline\":false}"
        else
            local value=""
            for ep in "${ep_array[@]}"; do
                local ep_escaped=$(json_escape "$ep")
                if [ -z "$value" ]; then
                    value="- $ep_escaped"
                else
                    value+="\\n- $ep_escaped"
                fi
            done
            fields+="{\"name\":\"$series_escaped ($ep_count x)\",\"value\":\"$value\",\"inline\":false}"
        fi
        
        field_count=$((field_count + 1))
        
        if [ $field_count -ge $MAX_FIELDS ]; then
            break
        fi
    done
    
    fields+="]"
    
    # Baue description mit error_info (mit JSON-Escape)
    local description=$(json_escape "$summary")
    if [ ! -z "$error_info" ]; then
        local error_escaped=$(json_escape "$error_info")
        description+="\\n\\n$error_escaped"
    fi
    
    # JSON-Escape für Title
    local title_escaped=$(json_escape "$title")
    
    # Erstelle Embed
    local json_payload=$(cat <<EOF
{
  "embeds": [{
    "title": "$title_escaped",
    "description": "$description",
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
    local success=0
    local failed=0
    for webhook_url in "${DISCORD_WEBHOOK_URLS[@]}"; do
        [ -z "$webhook_url" ] && continue
        
        # Sende Request und zeige Response
        local response=$(curl -s -w "\n%{http_code}" -H "Content-Type: application/json" \
             -d "${json_payload}" \
             "${webhook_url}")
        
        local http_code=$(echo "$response" | tail -n1)
        local body=$(echo "$response" | sed '$d')
        
        if [ "$http_code" = "204" ] || [ "$http_code" = "200" ]; then
            ((success++))
        else
            ((failed++))
            echo "[FEHLER] Discord Webhook fehlgeschlagen (HTTP $http_code)"
            [ ! -z "$body" ] && echo "Response: $body"
        fi
    done
    
    [ $failed -gt 0 ] && return 1
    return 0
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

# Erkenne Modus aus den Logs
MODE="unknown"
if grep -q "Modus: german" <<< "$LOG_CONTENT"; then
    MODE="german"
elif grep -q "Modus: new" <<< "$LOG_CONTENT"; then
    MODE="new"
fi

echo "Erkannter Modus: $MODE"

# Suche nach Episoden je nach Modus
declare -a PARSED_EPISODES

if [ "$MODE" = "german" ]; then
    # German Mode: [DOWNLOAD] Versuche German Dub -> URL followed by [VERIFY]
    current_url=""
    current_is_german=false
    
    while IFS= read -r line; do
        # [DOWNLOAD] Versuche German Dub -> URL
        if [[ "$line" =~ \[DOWNLOAD\][[:space:]]Versuche[[:space:]]German[[:space:]]Dub[[:space:]]-\>[[:space:]](https?://[^[:space:]]+) ]]; then
            current_url="${BASH_REMATCH[1]}"
            current_is_german=true
        # [VERIFY] (only if German Dub)
        elif [[ "$line" =~ \[VERIFY\].*wurde[[:space:]]+erfolgreich[[:space:]]+erstellt ]] && [ ! -z "$current_url" ] && [ "$current_is_german" = true ]; then
            url="$current_url"
            
            # Parse URL to readable format (aniworld or s.to)
            if [[ "$url" =~ /anime/stream/([^/]+)/staffel-([0-9]+)/episode-([0-9]+) ]] || [[ "$url" =~ /serie/stream/([^/]+)/staffel-([0-9]+)/episode-([0-9]+) ]]; then
                series_slug="${BASH_REMATCH[1]}"
                season="${BASH_REMATCH[2]}"
                episode="${BASH_REMATCH[3]}"
                
                # Convert slug to Title Case
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
            current_url=""
            current_is_german=false
        fi
    done <<< "$LOG_CONTENT"
elif [ "$MODE" = "new" ]; then
    # New Mode: [DOWNLOAD] ... -> URL followed by [VERIFY]
    current_url=""
    
    while IFS= read -r line; do
        # [DOWNLOAD] ... -> URL
        if [[ "$line" =~ \[DOWNLOAD\][[:space:]]Versuche[[:space:]].*[[:space:]]-\>[[:space:]](https?://[^[:space:]]+) ]]; then
            current_url="${BASH_REMATCH[1]}"
        # [VERIFY] ... wurde erfolgreich erstellt
        elif [[ "$line" =~ \[VERIFY\].*wurde[[:space:]]+erfolgreich[[:space:]]+erstellt ]] && [ ! -z "$current_url" ]; then
            url="$current_url"
            
            # Parse URL to readable format (aniworld or s.to)
            if [[ "$url" =~ /anime/stream/([^/]+)/staffel-([0-9]+)/episode-([0-9]+) ]] || [[ "$url" =~ /serie/stream/([^/]+)/staffel-([0-9]+)/episode-([0-9]+) ]]; then
                series_slug="${BASH_REMATCH[1]}"
                season="${BASH_REMATCH[2]}"
                episode="${BASH_REMATCH[3]}"
                
                # Convert slug to Title Case
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
            current_url=""
        fi
    done <<< "$LOG_CONTENT"
fi

# Zähle Fehler und übersprungene
ERROR_COUNT=$(echo "$LOG_CONTENT" | grep -c "\[ERROR\]")
SKIPPED_COUNT=$(echo "$LOG_CONTENT" | grep -c "\[SKIP\]")

# Zähle betroffene Serien
declare -A unique_series
for ep in "${PARSED_EPISODES[@]}"; do
    if [[ "$ep" =~ ^(.+)[[:space:]]+(S[0-9]{2}E[0-9]{2}|Film[[:space:]][0-9]+)$ ]]; then
        unique_series["${BASH_REMATCH[1]}"]=1
    fi
done
SERIES_COUNT=${#unique_series[@]}

# ============================================
# ZUSAMMENFASSUNG
# ============================================

EPISODES_COUNT=${#PARSED_EPISODES[@]}

echo "=== ZUSAMMENFASSUNG ==="
if [ "$MODE" = "german" ]; then
    echo "Neue deutsche Episoden gefunden: $EPISODES_COUNT"
elif [ "$MODE" = "new" ]; then
    echo "Neue Episoden gefunden: $EPISODES_COUNT"
    echo "Betroffene Serien: $SERIES_COUNT"
    echo "Übersprungen: $SKIPPED_COUNT"
fi
echo "Fehler: $ERROR_COUNT"
echo ""

if [ $EPISODES_COUNT -gt 0 ]; then
    echo "Gefundene Episoden (gruppiert):"
    for episode in "${PARSED_EPISODES[@]}"; do
        echo "  - $episode"
    done
    echo ""
fi

# ============================================
# DISCORD BENACHRICHTIGUNG (NUR BEI NEUEN EPISODEN)
# ============================================

if [ "$EPISODES_COUNT" -gt 0 ]; then
    # NUR wenn neue Episoden gefunden wurden
    if [ "$MODE" = "german" ]; then
        TITLE="🇩🇪 AniLoader - Deutsche Episoden Check"
        summary="✅ **${EPISODES_COUNT} neue deutsche Episode(n) gefunden!**"
    elif [ "$MODE" = "new" ]; then
        TITLE="📺 AniLoader - Neue Episoden Check"
        summary="✅ **${EPISODES_COUNT} neue Episode(n) heruntergeladen!**
📊 **${SERIES_COUNT} Serie(n) aktualisiert**"
    else
        TITLE="📺 AniLoader - LastRun Auswertung"
        summary="✅ **${EPISODES_COUNT} neue Episode(n) gefunden!**"
    fi
    
    error_info=""
    if [ "$ERROR_COUNT" -gt 0 ]; then
        error_info="⚠️ ${ERROR_COUNT} Fehler aufgetreten"
    fi
    
    if [ ${#PARSED_EPISODES[@]} -gt 0 ]; then
        # Nutze gruppierte Embed Funktion
        if send_discord_grouped_embed \
            "$TITLE" \
            "$summary" \
            "3066993" \
            "$error_info" \
            "${PARSED_EPISODES[@]}"; then
            echo "[OK] Discord Benachrichtigung gesendet mit ${EPISODES_COUNT} Episoden!"
        else
            echo "[FEHLER] Discord Benachrichtigung konnte nicht gesendet werden!"
        fi
    else
        # Keine Episoden-Details, nur Summary
        msg="$summary"
        if [ ! -z "$error_info" ]; then
            msg+="

${error_info}"
        fi
        if send_discord_message "$msg" "3066993"; then
            echo "[OK] Discord Benachrichtigung gesendet!"
        else
            echo "[FEHLER] Discord Benachrichtigung konnte nicht gesendet werden!"
        fi
    fi
else
    # Keine Discord-Nachricht bei 0 neuen Episoden
    if [ "$MODE" = "german" ]; then
        echo "[INFO] Keine neuen deutschen Episoden - keine Discord-Benachrichtigung."
    elif [ "$MODE" = "new" ]; then
        echo "[INFO] Keine neuen Episoden - keine Discord-Benachrichtigung."
    else
        echo "[INFO] Keine Episoden gefunden - keine Discord-Benachrichtigung."
    fi
fi

echo ""
echo "Script abgeschlossen: $(date)"
