#!/bin/bash
# last_run_summary.sh - Liest last_run Logs und sendet Discord-Benachrichtigung
# Analysiert die Log-Datei und erkennt automatisch den Modus (german/new)
#
# Für Unraid User Scripts Plugin:
#   Kann manuell ausgeführt werden, um den letzten Lauf auszuwerten
#   Oder nach check-new.sh / check-german.sh als separater Schritt

echo "========================================="
echo "AniLoader - LastRun Auswertung"
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

# Alternativ: Lokale Datei (wird nur verwendet wenn API_ENDPOINT leer ist)
LASTRUN_FILE="/mnt/user/Docker/AniLoader/data/last_run.txt"

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
    "title": "📊 AniLoader - LastRun Auswertung",
    "description": "$message_escaped",
    "color": ${color},
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%S.000Z)",
    "footer": { "text": "Unraid AniLoader" }
  }]
}
EOF
)
    
    local success=0
    local failed=0
    for webhook_url in "${DISCORD_WEBHOOK_URLS[@]}"; do
        [ -z "$webhook_url" ] && continue
        local response=$(curl -s -w "\n%{http_code}" -H "Content-Type: application/json" -d "${json_payload}" "${webhook_url}")
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
    local total_chars=0
    local MAX_FIELDS=25
    local MAX_CHARS=5800
    local MAX_FIELD_VALUE=1024
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
    
    # Basiszeichenlänge: Titel + Beschreibung + Footer
    total_chars=$(( ${#title} + ${#summary} + ${#error_info} + 50 ))
    
    for series in "${!series_episodes[@]}"; do
        local episodes="${series_episodes[$series]}"
        IFS='|' read -ra ep_array <<< "$episodes"
        local ep_count=${#ep_array[@]}
        
        local series_escaped=$(json_escape "$series")
        local field_name="$series_escaped"
        [ $ep_count -gt 1 ] && field_name="$series_escaped ($ep_count x)"
        
        local value=""
        for ep in "${ep_array[@]}"; do
            local ep_escaped=$(json_escape "$ep")
            [ -z "$value" ] && value="- $ep_escaped" || value+="\\n- $ep_escaped"
        done
        
        # Field Value auf 1024 Zeichen begrenzen
        if [ ${#value} -gt $MAX_FIELD_VALUE ]; then
            value="${value:0:$((MAX_FIELD_VALUE - 20))}\\n... (gekürzt)"
        fi
        
        # Prüfe ob Embed-Limit überschritten würde
        local field_chars=$(( ${#field_name} + ${#value} + 30 ))
        if [ $field_count -gt 0 ] && ([ $((total_chars + field_chars)) -gt $MAX_CHARS ] || [ $field_count -ge $MAX_FIELDS ]); then
            break
        fi
        
        [ $field_count -gt 0 ] && fields+=","
        fields+="{\"name\":\"$field_name\",\"value\":\"$value\",\"inline\":false}"
        field_count=$((field_count + 1))
        total_chars=$((total_chars + field_chars))
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
    
    local success=0
    local failed=0
    for webhook_url in "${DISCORD_WEBHOOK_URLS[@]}"; do
        [ -z "$webhook_url" ] && continue
        local response=$(curl -s -w "\n%{http_code}" -H "Content-Type: application/json" -d "${json_payload}" "${webhook_url}")
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

send_discord_multi_embed() {
    local title="$1"
    local summary="$2"
    local color="$3"
    local error_info="$4"
    shift 4
    
    if [ ${#DISCORD_WEBHOOK_URLS[@]} -eq 0 ]; then
        return 0
    fi
    
    local -a all_episodes=("$@")
    local total_episodes=${#all_episodes[@]}
    local MAX_FIELDS=25
    local MAX_CHARS=5800
    local MAX_FIELD_VALUE=1024
    
    # Gruppiere Episoden nach Serie
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
    
    local embeds="["
    local current_fields="["
    local field_count=0
    local current_chars=0
    local embed_count=0
    local series_processed=0
    
    for series in "${!series_episodes[@]}"; do
        local episodes="${series_episodes[$series]}"
        IFS='|' read -ra ep_array <<< "$episodes"
        local ep_count=${#ep_array[@]}
        
        local series_escaped=$(json_escape "$series")
        local field_name="$series_escaped"
        [ $ep_count -gt 1 ] && field_name="$series_escaped ($ep_count x)"
        
        local value=""
        for ep in "${ep_array[@]}"; do
            local ep_escaped=$(json_escape "$ep")
            [ -z "$value" ] && value="- $ep_escaped" || value+="\\n- $ep_escaped"
        done
        
        # Field Value auf 1024 Zeichen begrenzen
        if [ ${#value} -gt $MAX_FIELD_VALUE ]; then
            value="${value:0:$((MAX_FIELD_VALUE - 20))}\\n... (gekürzt)"
        fi
        
        local field_chars=$(( ${#field_name} + ${#value} + 30 ))
        
        # Beschreibungs-Länge für erstes vs. folgende Embeds
        if [ $field_count -eq 0 ]; then
            if [ $embed_count -eq 0 ]; then
                current_chars=$(( ${#title} + ${#summary} + ${#error_info} + 80 ))
            else
                current_chars=$(( ${#title} + 50 + 80 ))
            fi
        fi
        
        # Prüfe ob neues Embed nötig (Zeichen ODER Feld-Limit)
        if [ $field_count -gt 0 ] && ([ $((current_chars + field_chars)) -gt $MAX_CHARS ] || [ $field_count -ge $MAX_FIELDS ]); then
            # Aktuelles Embed abschließen
            current_fields+="]"
            embed_count=$((embed_count + 1))
            [ $embed_count -gt 1 ] && embeds+=","
            
            local embed_desc
            if [ $embed_count -eq 1 ]; then
                embed_desc=$(json_escape "$summary")
            else
                embed_desc="📊 **Fortsetzung (Teil $embed_count)...**"
            fi
            
            embeds+="{\"title\":\"$(json_escape "$title")\",\"description\":\"$embed_desc\",\"color\":$color,\"fields\":$current_fields,\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%S.000Z)\",\"footer\":{\"text\":\"Unraid AniLoader\"}}"
            
            # Reset für nächstes Embed
            current_fields="["
            field_count=0
            current_chars=$(( ${#title} + 50 + 80 ))
        fi
        
        [ $field_count -gt 0 ] && current_fields+=","
        current_fields+="{\"name\":\"$field_name\",\"value\":\"$value\",\"inline\":false}"
        field_count=$((field_count + 1))
        current_chars=$((current_chars + field_chars))
        series_processed=$((series_processed + 1))
    done
    
    # Letztes Embed abschließen (falls noch Fields vorhanden)
    if [ $field_count -gt 0 ]; then
        current_fields+="]"
        embed_count=$((embed_count + 1))
        [ $embed_count -gt 1 ] && embeds+=","
        
        local embed_desc
        if [ $embed_count -eq 1 ]; then
            embed_desc=$(json_escape "$summary")
        else
            embed_desc="📊 **Fortsetzung (Teil $embed_count)...**"
        fi
        
        # Fehler-Info im letzten Embed
        if [ ! -z "$error_info" ]; then
            embed_desc+="\\n\\n$(json_escape "$error_info")"
        fi
        
        embeds+="{\"title\":\"$(json_escape "$title")\",\"description\":\"$embed_desc\",\"color\":$color,\"fields\":$current_fields,\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%S.000Z)\",\"footer\":{\"text\":\"Unraid AniLoader\"}}"
    fi
    
    embeds+="]"
    
    local success=0
    local failed=0
    for webhook_url in "${DISCORD_WEBHOOK_URLS[@]}"; do
        [ -z "$webhook_url" ] && continue
        local response=$(curl -s -w "\n%{http_code}" -H "Content-Type: application/json" -d "{\"embeds\":$embeds}" "${webhook_url}")
        local http_code=$(echo "$response" | tail -n1)
        if [ "$http_code" = "204" ] || [ "$http_code" = "200" ]; then
            ((success++))
        else
            ((failed++))
            echo "[FEHLER] Discord Multi-Embed fehlgeschlagen (HTTP $http_code)"
        fi
    done
    
    [ $failed -gt 0 ] && return 1
    return 0
}

# ============================================
# HAUPTPROGRAMM
# ============================================

# Lade Logs entweder von API oder aus lokaler Datei
if [ ! -z "$API_ENDPOINT" ]; then
    echo "Lade Logs von API: $API_ENDPOINT/last_run"
    
    AUTH_PARAM=""
    [ ! -z "$API_AUTH" ] && AUTH_PARAM="-u ${API_AUTH}"
    
    RAW_RESPONSE=$(curl -s ${AUTH_PARAM} "${API_ENDPOINT}/last_run" 2>/dev/null || echo "")
    
    if [ -z "$RAW_RESPONSE" ]; then
        echo "[FEHLER] Keine Logs von API verfügbar."
        exit 1
    fi
    
    # Konvertiere JSON-Array zu Plaintext
    if [[ "$RAW_RESPONSE" == \[* ]]; then
        LOG_CONTENT=$(echo "$RAW_RESPONSE" | tr -d '\n\r' | sed 's/^\["//' | sed 's/"\]$//' | sed 's/","$/\n/g' | sed 's/","/\n/g' | sed 's/\\u00e4/ä/g; s/\\u00f6/ö/g; s/\\u00fc/ü/g; s/\\u00df/ß/g; s/\\u00c4/Ä/g; s/\\u00d6/Ö/g; s/\\u00dc/Ü/g')
    else
        LOG_CONTENT="$RAW_RESPONSE"
    fi
else
    if [ ! -f "$LASTRUN_FILE" ]; then
        echo "[FEHLER] Datei nicht gefunden: $LASTRUN_FILE"
        exit 1
    fi
    
    echo "Lese Datei: $LASTRUN_FILE"
    LOG_CONTENT=$(cat "$LASTRUN_FILE")
fi

if [ -z "$LOG_CONTENT" ]; then
    echo "[WARNUNG] Keine Logs verfügbar."
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
elif grep -q "Modus: default" <<< "$LOG_CONTENT"; then
    MODE="default"
elif grep -q "Modus: check" <<< "$LOG_CONTENT"; then
    MODE="check"
fi

echo "Erkannter Modus: $MODE"

# Suche nach heruntergeladenen Episoden je nach Modus
declare -a PARSED_EPISODES

if [ "$MODE" = "german" ]; then
    # German Mode: Nur German Dub Downloads zählen
    current_url=""
    current_is_german=false
    
    while IFS= read -r line; do
        if [[ "$line" =~ \[DOWNLOAD\].*Versuche.*German.*Dub.*-\>[[:space:]]*(https?://[^[:space:]]+) ]]; then
            current_url="${BASH_REMATCH[1]}"
            current_is_german=true
        elif [[ "$line" =~ \[VERIFY\].*wurde.*erfolgreich.*erstellt ]] && [ ! -z "$current_url" ] && [ "$current_is_german" = true ]; then
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
            current_is_german=false
        fi
    done <<< "$LOG_CONTENT"
else
    # Alle anderen Modi: Alle Downloads zählen
    current_url=""
    
    while IFS= read -r line; do
        if [[ "$line" =~ \[DOWNLOAD\].*Versuche.*-\>[[:space:]]*(https?://[^[:space:]]+) ]]; then
            current_url="${BASH_REMATCH[1]}"
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
fi

# Zähle Fehler und übersprungene
ERROR_COUNT=$(echo "$LOG_CONTENT" | grep -c "\[ERROR\]" || echo "0")
SKIPPED_COUNT=$(echo "$LOG_CONTENT" | grep -c "\[SKIP\]" || echo "0")

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
else
    echo "Episoden heruntergeladen: $EPISODES_COUNT"
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
    if [ "$MODE" = "german" ]; then
        TITLE="🇩🇪 AniLoader - Deutsche Episoden Check"
        summary="✅ **${EPISODES_COUNT} neue deutsche Episode(n) gefunden!**"
    elif [ "$MODE" = "new" ]; then
        TITLE="📺 AniLoader - Neue Episoden Check"
        summary="✅ **${EPISODES_COUNT} neue Episode(n) heruntergeladen!**
📊 **${SERIES_COUNT} Serie(n) aktualisiert**"
    elif [ "$MODE" = "default" ]; then
        TITLE="📥 AniLoader - Standard Download"
        summary="✅ **${EPISODES_COUNT} Episode(n) heruntergeladen!**
📊 **${SERIES_COUNT} Serie(n) aktualisiert**"
    elif [ "$MODE" = "check" ]; then
        TITLE="🔍 AniLoader - Integritäts-Check"
        summary="✅ **${EPISODES_COUNT} Episode(n) repariert/nachgeladen!**
📊 **${SERIES_COUNT} Serie(n) betroffen**"
    else
        TITLE="📊 AniLoader - LastRun Auswertung"
        summary="✅ **${EPISODES_COUNT} neue Episode(n) gefunden!**"
    fi
    
    error_info=""
    [ "$ERROR_COUNT" -gt 0 ] && error_info="⚠️ ${ERROR_COUNT} Fehler aufgetreten"
    
    if [ ${#PARSED_EPISODES[@]} -gt 0 ]; then
        if send_discord_multi_embed \
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
        msg="$summary"
        [ ! -z "$error_info" ] && msg+="

${error_info}"
        if send_discord_message "$msg" "3066993"; then
            echo "[OK] Discord Benachrichtigung gesendet!"
        else
            echo "[FEHLER] Discord Benachrichtigung konnte nicht gesendet werden!"
        fi
    fi
else
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
