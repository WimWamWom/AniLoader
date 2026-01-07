#!/bin/bash
# check-german.sh - Prüft auf neue deutsche Episoden
# Führt den AniLoader im "german" Modus aus

echo "========================================="
echo "AniLoader - Check German Episodes"
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
    "title": "🇩🇪 AniLoader - Deutsche Episoden Check",
    "description": "$message_escaped",
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
                series_episodes["$series_name"]+="|$episode_info"
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
      "text": "Unraid AniLoader"
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
        echo "[OK] System ist frei, starte German-Check..."
        break
    fi
    
    if [ $waited -ge $MAX_WAIT_MINUTES ]; then
        echo "[WARNUNG] Timeout: System nach ${MAX_WAIT_MINUTES} Minuten noch beschäftigt"
        echo "German-Check wird abgebrochen."
        exit 1
    fi
    
    echo "[WARTE] System beschäftigt (Status: $STATUS), warte... (${waited}/${MAX_WAIT_MINUTES} Minuten)"
    sleep 60
    waited=$((waited + 1))
done

# API Aufruf zum Starten des german Modus
echo "Starte German-Check via ${API_ENDPOINT}..."
curl -s -X POST ${AUTH_PARAM} "${API_ENDPOINT}/start_download" \
    -H "Content-Type: application/json" \
    -d '{"mode":"german"}'

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
ERROR_COUNT=$(echo "$LOG_CONTENT" | grep -c "\[ERROR\]")

# Extrahiere URLs und konvertiere zu lesbaren Episode-Namen
declare -a PARSED_EPISODES
declare -A download_urls
current_url=""
current_is_german=false

while IFS= read -r line; do
    # [DOWNLOAD] Versuche German Dub -> URL (Captures German Dub download)
    if [[ "$line" =~ \[DOWNLOAD\][[:space:]]Versuche[[:space:]]German[[:space:]]Dub[[:space:]]-\>[[:space:]](https?://[^[:space:]]+) ]]; then
        current_url="${BASH_REMATCH[1]}"
        current_is_german=true
    # [VERIFY] Datei ... wurde erfolgreich erstellt (Only count if German Dub)
    elif [[ "$line" =~ \[VERIFY\].*wurde[[:space:]]+erfolgreich[[:space:]]+erstellt ]] && [ ! -z "$current_url" ] && [ "$current_is_german" = true ]; then
        url="$current_url"
        
        # Parse URL zu lesbarem Format (aniworld oder s.to)
        if [[ "$url" =~ /anime/stream/([^/]+)/staffel-([0-9]+)/episode-([0-9]+) ]] || [[ "$url" =~ /serie/stream/([^/]+)/staffel-([0-9]+)/episode-([0-9]+) ]]; then
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
        current_url=""
        current_is_german=false
    elif [[ "$line" =~ \[DOWNLOAD\] ]]; then
        # Reset wenn es ein anderer Download ist
        current_is_german=false
    fi
done <<< "$LOG_CONTENT"

# Zähle neue deutsche Episoden
NEW_GERMAN_COUNT=${#PARSED_EPISODES[@]}

echo ""
echo "=== ZUSAMMENFASSUNG ==="
echo "Neue deutsche Episoden gefunden: $NEW_GERMAN_COUNT"
echo "Fehler: $ERROR_COUNT"

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
        if send_discord_grouped_embed \
            "🇩🇪 AniLoader - Deutsche Episoden Check" \
            "$summary" \
            "3066993" \
            "$error_info" \
            "${PARSED_EPISODES[@]}"; then
            echo "[OK] Discord Benachrichtigung gesendet mit ${NEW_GERMAN_COUNT} Episoden!"
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
    echo "[INFO] Keine neuen deutschen Episoden - keine Discord-Benachrichtigung."
fi

echo ""
echo "Script abgeschlossen: $(date)"
