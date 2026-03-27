#!/bin/bash
# check-new.sh - Prüft auf neue Episoden
# Führt den AniLoader im "new" Modus aus und sendet Discord-Benachrichtigung

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
DISCORD_WEBHOOK_URLS=(
    "https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN"
    # "https://discord.com/api/webhooks/ZWEITE_WEBHOOK_URL"
)

# ============================================
# DISCORD WEBHOOK FUNKTIONEN
# ============================================

json_escape() {
    local string="$1"
    string="${string//\\/\\\\}"
    string="${string//\"/\\\"}"
    string="${string//$'\n'/\\n}"
    string="${string//$'\r'/\\r}"
    string="${string//$'\t'/\\t}"
    echo "$string"
}

send_discord_message() {
    local message="$1"
    local color="$2"
    
    if [ ${#DISCORD_WEBHOOK_URLS[@]} -eq 0 ]; then
        return 0
    fi
    
    local message_escaped=$(json_escape "$message")
    
    local json_payload=$(cat <<EOF
{
  "embeds": [{
    "title": "📺 AniLoader - Neue Episoden Check",
    "description": "$message_escaped",
    "color": ${color},
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%S.000Z)",
    "footer": { "text": "Unraid AniLoader" }
  }]
}
EOF
)
    
    for webhook_url in "${DISCORD_WEBHOOK_URLS[@]}"; do
        [ -z "$webhook_url" ] && continue
        local response=$(curl -s -w "\n%{http_code}" -H "Content-Type: application/json" -d "${json_payload}" "${webhook_url}")
        local http_code=$(echo "$response" | tail -n1)
        if [ "$http_code" != "204" ] && [ "$http_code" != "200" ]; then
            echo "[FEHLER] Discord Webhook fehlgeschlagen (HTTP $http_code)"
        fi
    done
}

send_discord_grouped_embed() {
    local title="$1"
    local summary="$2"
    local color="$3"
    local error_info="$4"
    shift 4
    
    if [ ${#DISCORD_WEBHOOK_URLS[@]} -eq 0 ]; then
        return 0
    fi
    
    local fields="["
    local field_count=0
    declare -A series_episodes
    
    while [ $# -gt 0 ]; do
        local episode="$1"
        shift
        if [[ "$episode" =~ ^(.+)[[:space:]]+(S[0-9]{2}E[0-9]{2}|Film[[:space:]][0-9]+)$ ]]; then
            local series_name="${BASH_REMATCH[1]}"
            local episode_info="${BASH_REMATCH[2]}"
            if [ -z "${series_episodes[$series_name]}" ]; then
                series_episodes["$series_name"]="$episode_info"
            else
                series_episodes["$series_name"]+="|$episode_info"
            fi
        fi
    done
    
    for series in "${!series_episodes[@]}"; do
        local episodes="${series_episodes[$series]}"
        IFS='|' read -ra ep_array <<< "$episodes"
        local ep_count=${#ep_array[@]}
        
        [ $field_count -gt 0 ] && fields+=","
        local series_escaped=$(json_escape "$series")
        
        if [ $ep_count -eq 1 ]; then
            local ep_escaped=$(json_escape "${ep_array[0]}")
            fields+="{\"name\":\"$series_escaped\",\"value\":\"- $ep_escaped\",\"inline\":false}"
        else
            local value=""
            for ep in "${ep_array[@]}"; do
                local ep_escaped=$(json_escape "$ep")
                [ -z "$value" ] && value="- $ep_escaped" || value+="\\n- $ep_escaped"
            done
            fields+="{\"name\":\"$series_escaped ($ep_count x)\",\"value\":\"$value\",\"inline\":false}"
        fi
        field_count=$((field_count + 1))
        [ $field_count -ge 25 ] && break
    done
    fields+="]"
    
    local description=$(json_escape "$summary")
    [ ! -z "$error_info" ] && description+="\\n\\n$(json_escape "$error_info")"
    local title_escaped=$(json_escape "$title")
    
    local json_payload=$(cat <<EOF
{
  "embeds": [{
    "title": "$title_escaped",
    "description": "$description",
    "color": ${color},
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%S.000Z)",
    "fields": ${fields},
    "footer": { "text": "Unraid AniLoader" }
  }]
}
EOF
)
    
    for webhook_url in "${DISCORD_WEBHOOK_URLS[@]}"; do
        [ -z "$webhook_url" ] && continue
        local response=$(curl -s -w "\n%{http_code}" -H "Content-Type: application/json" -d "${json_payload}" "${webhook_url}")
        local http_code=$(echo "$response" | tail -n1)
        if [ "$http_code" = "204" ] || [ "$http_code" = "200" ]; then
            return 0
        else
            echo "[FEHLER] Discord Webhook fehlgeschlagen (HTTP $http_code)"
        fi
    done
}

# Multi-Embed Funktion für sehr lange Listen (>25 Serien)
send_discord_multi_embed() {
    local title="$1"
    local summary="$2"
    local color="$3"
    local error_info="$4"
    shift 4
    
    if [ ${#DISCORD_WEBHOOK_URLS[@]} -eq 0 ]; then
        return 0
    fi
    
    # Sammle alle Episoden
    local -a all_episodes=("$@")
    local total_episodes=${#all_episodes[@]}
    
    # Gruppiere nach Serie
    declare -A series_episodes
    for episode in "${all_episodes[@]}"; do
        if [[ "$episode" =~ ^(.+)[[:space:]]+(S[0-9]{2}E[0-9]{2}|Film[[:space:]][0-9]+)$ ]]; then
            local series_name="${BASH_REMATCH[1]}"
            local episode_info="${BASH_REMATCH[2]}"
            if [ -z "${series_episodes[$series_name]}" ]; then
                series_episodes["$series_name"]="$episode_info"
            else
                series_episodes["$series_name"]+="|$episode_info"
            fi
        fi
    done
    
    local total_series=${#series_episodes[@]}
    local MAX_FIELDS=25
    
    # Wenn <= 25 Serien, nutze normale grouped embed
    if [ $total_series -le $MAX_FIELDS ]; then
        send_discord_grouped_embed "$title" "$summary" "$color" "$error_info" "${all_episodes[@]}"
        return $?
    fi
    
    # Teile in mehrere Embeds auf
    local embeds="["
    local current_fields="["
    local field_count=0
    local embed_count=0
    local series_processed=0
    
    for series in "${!series_episodes[@]}"; do
        local episodes="${series_episodes[$series]}"
        IFS='|' read -ra ep_array <<< "$episodes"
        local ep_count=${#ep_array[@]}
        
        [ $field_count -gt 0 ] && current_fields+=","
        local series_escaped=$(json_escape "$series")
        
        if [ $ep_count -eq 1 ]; then
            local ep_escaped=$(json_escape "${ep_array[0]}")
            current_fields+="{\"name\":\"$series_escaped\",\"value\":\"- $ep_escaped\",\"inline\":false}"
        else
            local value=""
            for ep in "${ep_array[@]}"; do
                local ep_escaped=$(json_escape "$ep")
                [ -z "$value" ] && value="- $ep_escaped" || value+="\\n- $ep_escaped"
            done
            current_fields+="{\"name\":\"$series_escaped ($ep_count x)\",\"value\":\"$value\",\"inline\":false}"
        fi
        
        field_count=$((field_count + 1))
        series_processed=$((series_processed + 1))
        
        # Wenn 25 Fields erreicht oder letzte Serie
        if [ $field_count -ge $MAX_FIELDS ] || [ $series_processed -eq $total_series ]; then
            current_fields+="]"
            embed_count=$((embed_count + 1))
            
            [ $embed_count -gt 1 ] && embeds+=","
            
            local embed_title="$title"
            local embed_desc
            
            if [ $embed_count -eq 1 ]; then
                embed_desc=$(json_escape "$summary")
            else
                embed_desc="📺 **Fortsetzung (Teil $embed_count)...**"
            fi
            
            # Fehler-Info nur im letzten Embed
            if [ $series_processed -eq $total_series ] && [ ! -z "$error_info" ]; then
                embed_desc+="\\n\\n$(json_escape "$error_info")"
            fi
            
            embeds+="{\"title\":\"$(json_escape "$embed_title")\",\"description\":\"$embed_desc\",\"color\":$color,\"fields\":$current_fields,\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%S.000Z)\",\"footer\":{\"text\":\"Unraid AniLoader\"}}"
            
            # Reset für nächstes Embed
            current_fields="["
            field_count=0
        fi
    done
    
    embeds+="]"
    
    # Sende an alle Webhooks
    for webhook_url in "${DISCORD_WEBHOOK_URLS[@]}"; do
        [ -z "$webhook_url" ] && continue
        local response=$(curl -s -w "\n%{http_code}" -H "Content-Type: application/json" -d "{\"embeds\":$embeds}" "${webhook_url}")
        local http_code=$(echo "$response" | tail -n1)
        if [ "$http_code" = "204" ] || [ "$http_code" = "200" ]; then
            return 0
        else
            echo "[FEHLER] Discord Multi-Embed fehlgeschlagen (HTTP $http_code)"
        fi
    done
}

# ============================================
# HAUPTPROGRAMM
# ============================================

AUTH_PARAM=""
[ ! -z "$API_AUTH" ] && AUTH_PARAM="-u ${API_AUTH}"

# Warte-Logik
MAX_WAIT_MINUTES=180
waited=0

echo "Prüfe ob System frei ist..."
while true; do
    STATUS=$(curl -s ${AUTH_PARAM} "${API_ENDPOINT}/status" 2>/dev/null | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
    
    if [ "$STATUS" != "running" ]; then
        echo "[OK] System ist frei, starte New-Check..."
        break
    fi
    
    if [ $waited -ge $MAX_WAIT_MINUTES ]; then
        echo "[WARNUNG] Timeout nach ${MAX_WAIT_MINUTES} Minuten"
        exit 1
    fi
    
    echo "[WARTE] System beschäftigt, warte... (${waited}/${MAX_WAIT_MINUTES} Min)"
    sleep 60
    waited=$((waited + 1))
done

# API Aufruf
echo "Starte New-Check via ${API_ENDPOINT}..."
curl -s -X POST ${AUTH_PARAM} "${API_ENDPOINT}/start_download" \
    -H "Content-Type: application/json" \
    -d '{"mode":"new"}'

echo "Warte auf Abschluss..."
sleep 10

while true; do
    STATUS=$(curl -s ${AUTH_PARAM} "${API_ENDPOINT}/status" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
    if [ "$STATUS" != "running" ]; then
        echo "Check abgeschlossen (Status: $STATUS)"
        break
    fi
    echo "Läuft noch..."
    sleep 30
done

# ============================================
# LOGS AUSWERTEN
# ============================================
echo ""
echo "Werte Logs aus..."

RAW_RESPONSE=$(curl -s ${AUTH_PARAM} "${API_ENDPOINT}/last_run" 2>/dev/null || echo "")

if [ -z "$RAW_RESPONSE" ]; then
    echo "Keine Logs verfügbar."
    exit 0
fi

# Konvertiere JSON-Array zu Plaintext
# API gibt ["zeile1","zeile2",...] zurück, möglicherweise mit Zeilenumbrüchen
if [[ "$RAW_RESPONSE" == \[* ]]; then
    # Entferne Zeilenumbrüche, dann parse JSON-Array
    LOG_CONTENT=$(echo "$RAW_RESPONSE" | tr -d '\n\r' | sed 's/^\["//' | sed 's/"\]$//' | sed 's/","$/\n/g' | sed 's/","/\n/g' | sed 's/\\u00e4/ä/g; s/\\u00f6/ö/g; s/\\u00fc/ü/g; s/\\u00df/ß/g; s/\\u00c4/Ä/g; s/\\u00d6/Ö/g; s/\\u00dc/Ü/g')
else
    LOG_CONTENT="$RAW_RESPONSE"
fi

[ -z "$LOG_CONTENT" ] && echo "Keine Logs verfügbar." && exit 0

echo "[DEBUG] Zeilen im Log: $(echo "$LOG_CONTENT" | wc -l)"

# Parsing für NEW Modus
declare -a PARSED_EPISODES
current_url=""

while IFS= read -r line; do
    # [DOWNLOAD] Versuche ... -> URL (mit Timestamp am Anfang)
    if [[ "$line" =~ \[DOWNLOAD\].*Versuche.*-\>[[:space:]]*(https?://[^[:space:]]+) ]]; then
        current_url="${BASH_REMATCH[1]}"
    # [VERIFY] ... wurde erfolgreich erstellt
    elif [[ "$line" =~ \[VERIFY\].*wurde.*erfolgreich.*erstellt ]] && [ ! -z "$current_url" ]; then
        url="$current_url"
        
        if [[ "$url" =~ /anime/stream/([^/]+)/staffel-([0-9]+)/episode-([0-9]+) ]] || [[ "$url" =~ /serie/stream/([^/]+)/staffel-([0-9]+)/episode-([0-9]+) ]]; then
            series_slug="${BASH_REMATCH[1]}"
            season="${BASH_REMATCH[2]}"
            episode="${BASH_REMATCH[3]}"
            
            series_name=$(echo "$series_slug" | sed 's/-/ /g' | awk '{for(i=1;i<=NF;i++) $i=toupper(substr($i,1,1)) tolower(substr($i,2));}1')
            season_padded=$(printf "%02d" $season)
            episode_padded=$(printf "%02d" $episode)
            
            PARSED_EPISODES+=("$series_name S${season_padded}E${episode_padded}")
        elif [[ "$url" =~ /anime/stream/([^/]+)/filme/film-([0-9]+) ]] || [[ "$url" =~ /serie/stream/([^/]+)/filme/film-([0-9]+) ]]; then
            series_slug="${BASH_REMATCH[1]}"
            film_nr="${BASH_REMATCH[2]}"
            
            series_name=$(echo "$series_slug" | sed 's/-/ /g' | awk '{for(i=1;i<=NF;i++) $i=toupper(substr($i,1,1)) tolower(substr($i,2));}1')
            PARSED_EPISODES+=("$series_name Film $film_nr")
        fi
        current_url=""
    fi
done <<< "$LOG_CONTENT"

# Zähle
SKIPPED_COUNT=$(echo "$LOG_CONTENT" | grep -c "\[SKIP\]" || echo "0")
ERROR_COUNT=$(echo "$LOG_CONTENT" | grep -c "\[ERROR\]" || echo "0")
NEW_EPISODES_COUNT=${#PARSED_EPISODES[@]}

declare -A unique_series
for ep in "${PARSED_EPISODES[@]}"; do
    if [[ "$ep" =~ ^(.+)[[:space:]]+(S[0-9]{2}E[0-9]{2}|Film[[:space:]][0-9]+)$ ]]; then
        unique_series["${BASH_REMATCH[1]}"]=1
    fi
done
SERIES_COUNT=${#unique_series[@]}

echo ""
echo "=== ZUSAMMENFASSUNG ==="
echo "Neue Episoden gefunden: $NEW_EPISODES_COUNT"
echo "Betroffene Serien: $SERIES_COUNT"
echo "Übersprungen: $SKIPPED_COUNT"
echo "Fehler: $ERROR_COUNT"

# ============================================
# DISCORD BENACHRICHTIGUNG
# ============================================

if [ "$NEW_EPISODES_COUNT" -gt 0 ]; then
    summary="✅ **${NEW_EPISODES_COUNT} neue Episode(n) heruntergeladen!**
📊 **${SERIES_COUNT} Serie(n) aktualisiert**"
    
    error_info=""
    [ "$ERROR_COUNT" -gt 0 ] && error_info="⚠️ ${ERROR_COUNT} Fehler aufgetreten"
    
    # Nutze Multi-Embed für automatische Aufteilung bei >25 Serien
    if send_discord_multi_embed "📺 AniLoader - Neue Episoden Check" "$summary" "3066993" "$error_info" "${PARSED_EPISODES[@]}"; then
        echo "[OK] Discord Benachrichtigung gesendet!"
    fi
else
    echo "[INFO] Keine neuen Episoden - keine Discord-Benachrichtigung."
fi

echo ""
echo "Script abgeschlossen: $(date)"
