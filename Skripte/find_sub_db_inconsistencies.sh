#!/usr/bin/env bash
# find_sub_db_inconsistencies.sh
#
# Prüft Inkonsistenzen zwischen Dateisystem und DB:
# Lokal vorhandene [Sub]-Dateien, die in der Datenbank nicht mehr als
# fehlende deutsche Episode (fehlende_deutsch_folgen) geführt werden.
#
# Erwartete DB-Technologie: SQLite (AniLoader.db)
#
# Ausgabe:
# - Konsole (Kurzreport)
# - Textdatei mit Detailreport

set -u
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

CONFIG_PATH="${1:-${ANILOADER_CONFIG:-${PROJECT_DIR}/data/config.yaml}}"
OUTPUT_PATH="${2:-${PROJECT_DIR}/data/sub_db_inconsistencies_$(date +%Y%m%d_%H%M%S).txt}"

TMP_DIR="$(mktemp -d 2>/dev/null || mktemp -d -t aniloader_subcheck)"
trap 'rm -rf "${TMP_DIR}"' EXIT

ROWS_FILE="${TMP_DIR}/rows.tsv"
ISSUES_FILE="${TMP_DIR}/issues.tsv"
CFG_FILE="${TMP_DIR}/cfg.env"
MOUNT_MAP_FILE="${TMP_DIR}/mount_map.tsv"
CONTAINER_NAME="${ANILOADER_CONTAINER:-AniLoader}"

printf "" >"${ISSUES_FILE}"

die() {
    echo "[ERROR] $*" >&2
    exit 1
}

warn() {
    echo "[WARN] $*" >&2
}

info() {
    echo "[INFO] $*"
}

require_cmd() {
    local cmd="$1"
    command -v "${cmd}" >/dev/null 2>&1 || die "Benötigtes Kommando fehlt: ${cmd}"
}

discover_container_mounts() {
    : >"${MOUNT_MAP_FILE}"

    if ! command -v docker >/dev/null 2>&1; then
        warn "docker nicht gefunden – Container-Mount-Mapping wird übersprungen"
        return 0
    fi

    if ! docker inspect "${CONTAINER_NAME}" >/dev/null 2>&1; then
        warn "Container '${CONTAINER_NAME}' nicht gefunden – Container-Mount-Mapping wird übersprungen"
        return 0
    fi

    docker inspect "${CONTAINER_NAME}" --format '{{range .Mounts}}{{println .Destination "|" .Source}}{{end}}' \
        | while IFS='|' read -r dest src; do
            dest="$(echo "${dest}" | sed 's/^ *//; s/ *$//')"
            src="$(echo "${src}" | sed 's/^ *//; s/ *$//')"
            [[ -z "${dest}" || -z "${src}" ]] && continue
            printf "%s\t%s\n" "${dest}" "${src}" >>"${MOUNT_MAP_FILE}"
        done

    if [[ -s "${MOUNT_MAP_FILE}" ]]; then
        info "Docker-Mount-Mapping geladen (Container: ${CONTAINER_NAME})"
    else
        warn "Keine Docker-Mounts aus '${CONTAINER_NAME}' gelesen"
    fi
}

map_container_path_to_host() {
    local p="$1"
    local best_dest=""
    local best_src=""

    if [[ ! -s "${MOUNT_MAP_FILE}" ]]; then
        printf "%s\n" "${p}"
        return 0
    fi

    while IFS=$'\t' read -r dest src; do
        [[ -z "${dest}" || -z "${src}" ]] && continue
        if [[ "${p}" == "${dest}" || "${p}" == "${dest}/"* ]]; then
            if (( ${#dest} > ${#best_dest} )); then
                best_dest="${dest}"
                best_src="${src}"
            fi
        fi
    done <"${MOUNT_MAP_FILE}"

    if [[ -n "${best_dest}" ]]; then
        local suffix
        suffix="${p#${best_dest}}"
        suffix="${suffix#/}"
        if [[ -n "${suffix}" ]]; then
            printf "%s\n" "${best_src%/}/${suffix}"
        else
            printf "%s\n" "${best_src}"
        fi
        return 0
    fi

    printf "%s\n" "${p}"
}

normalize_path() {
    local p="$1"
    if [[ -z "${p}" ]]; then
        return 1
    fi

    # Entfernt optional umgebende Quotes
    p="${p%\"}"
    p="${p#\"}"
    p="${p%\'}"
    p="${p#\'}"

    # Windows-Pfade (C:\foo\bar) in Bash-kompatibles Format umwandeln
    if [[ "${p}" =~ ^([A-Za-z]):\\ ]]; then
        local drive rest
        drive="${BASH_REMATCH[1],,}"
        rest="${p:2}"
        rest="${rest//\\//}"
        p="/${drive}${rest}"
    fi

    # Containerpfade über echte Docker-Mounts auf Hostpfade abbilden
    if [[ "${p}" == /* ]]; then
        p="$(map_container_path_to_host "${p}")"
    fi

    # Unraid-Host: Containerpfade auf Host-Projektpfad abbilden
    # Beispiel: /app/data -> <PROJECT_DIR>/data
    if [[ "${p}" == "/app" ]]; then
        p="${PROJECT_DIR}"
    elif [[ "${p}" == /app/* ]]; then
        p="${PROJECT_DIR}/${p#/app/}"
    fi

    # Relative Pfade auf Projektordner beziehen
    if [[ "${p}" == /* ]]; then
        printf "%s\n" "${p}"
    else
        printf "%s\n" "${PROJECT_DIR}/${p}"
    fi
}

parse_config() {
    local cfg_path="$1"

    [[ -f "${cfg_path}" ]] || die "Config-Datei nicht gefunden: ${cfg_path}"

    if [[ "${cfg_path}" =~ \.(ya?ml)$ ]]; then
        # YAML ohne externe Parser auslesen (2-Level Struktur wie in AniLoader config.yaml)
        # Unterstützt zusätzlich top-level BASE_PATH/MEDIA_PATH als flexible Fallback-Variablen.
        awk '
            function trim(s) {
                gsub(/^\s+|\s+$/, "", s)
                gsub(/^"|"$/, "", s)
                gsub(/^\047|\047$/, "", s)
                return s
            }
            {
                line = $0
                gsub(/\r/, "", line)

                if (match(line, /^storage:[[:space:]]*$/)) { section = "storage"; next }
                if (match(line, /^data:[[:space:]]*$/)) { section = "data"; next }
                if (match(line, /^[A-Za-z0-9_]+:[[:space:]]*$/) && line !~ /^(storage|data):[[:space:]]*$/) {
                    section = ""
                }

                if (section == "storage") {
                    if (match(line, /^[[:space:]]{2}mode:[[:space:]]*/)) {
                        val = line
                        sub(/^[[:space:]]{2}mode:[[:space:]]*/, "", val)
                        print "STORAGE_MODE=" trim(val)
                    }
                    if (match(line, /^[[:space:]]{2}download_path:[[:space:]]*/)) {
                        val = line
                        sub(/^[[:space:]]{2}download_path:[[:space:]]*/, "", val)
                        print "DOWNLOAD_PATH=" trim(val)
                    }
                    if (match(line, /^[[:space:]]{2}anime_path:[[:space:]]*/)) {
                        val = line
                        sub(/^[[:space:]]{2}anime_path:[[:space:]]*/, "", val)
                        print "ANIME_PATH=" trim(val)
                    }
                    if (match(line, /^[[:space:]]{2}series_path:[[:space:]]*/)) {
                        val = line
                        sub(/^[[:space:]]{2}series_path:[[:space:]]*/, "", val)
                        print "SERIES_PATH=" trim(val)
                    }
                    if (match(line, /^[[:space:]]{2}anime_movies_path:[[:space:]]*/)) {
                        val = line
                        sub(/^[[:space:]]{2}anime_movies_path:[[:space:]]*/, "", val)
                        print "ANIME_MOVIES_PATH=" trim(val)
                    }
                    if (match(line, /^[[:space:]]{2}serien_movies_path:[[:space:]]*/)) {
                        val = line
                        sub(/^[[:space:]]{2}serien_movies_path:[[:space:]]*/, "", val)
                        print "SERIEN_MOVIES_PATH=" trim(val)
                    }
                }

                if (section == "data") {
                    if (match(line, /^[[:space:]]{2}folder:[[:space:]]*/)) {
                        val = line
                        sub(/^[[:space:]]{2}folder:[[:space:]]*/, "", val)
                        print "DATA_FOLDER=" trim(val)
                    }
                }

                if (match(line, /^BASE_PATH:[[:space:]]*/)) {
                    val = line
                    sub(/^BASE_PATH:[[:space:]]*/, "", val)
                    print "BASE_PATH=" trim(val)
                }
                if (match(line, /^MEDIA_PATH:[[:space:]]*/)) {
                    val = line
                    sub(/^MEDIA_PATH:[[:space:]]*/, "", val)
                    print "MEDIA_PATH=" trim(val)
                }
            }
        ' "${cfg_path}" >"${CFG_FILE}"
    else
        # Einfache KEY=VALUE Config
        grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "${cfg_path}" >"${CFG_FILE}" || true
    fi

    [[ -s "${CFG_FILE}" ]] || die "Config konnte nicht geparst werden: ${cfg_path}"
}

cfg_get() {
    local key="$1"
    local value
    value="$(grep -E "^${key}=" "${CFG_FILE}" | head -n1 | cut -d'=' -f2-)"
    printf "%s" "${value}"
}

add_root() {
    local p="$1"
    [[ -z "${p}" ]] && return 0

    p="$(normalize_path "${p}")" || return 0
    [[ -z "${p}" ]] && return 0

    # Nur existierende, lesbare Verzeichnisse berücksichtigen
    if [[ -d "${p}" && -r "${p}" ]]; then
        if ! grep -Fxq "${p}" "${TMP_DIR}/roots.txt" 2>/dev/null; then
            echo "${p}" >>"${TMP_DIR}/roots.txt"
        fi
    fi
}

collect_roots() {
    : >"${TMP_DIR}/roots.txt"

    local storage_mode download_path anime_path series_path anime_movies_path serien_movies_path base_path media_path
    storage_mode="$(cfg_get STORAGE_MODE)"
    download_path="$(cfg_get DOWNLOAD_PATH)"
    anime_path="$(cfg_get ANIME_PATH)"
    series_path="$(cfg_get SERIES_PATH)"
    anime_movies_path="$(cfg_get ANIME_MOVIES_PATH)"
    serien_movies_path="$(cfg_get SERIEN_MOVIES_PATH)"
    base_path="$(cfg_get BASE_PATH)"
    media_path="$(cfg_get MEDIA_PATH)"

    # Immer Standardpfade/Fallbacks mitnehmen
    add_root "${download_path}"
    add_root "${anime_path}"
    add_root "${series_path}"
    add_root "${anime_movies_path}"
    add_root "${serien_movies_path}"
    add_root "${base_path}"
    add_root "${media_path}"

    # Harte Fallbacks relativ zum Projekt
    add_root "${PROJECT_DIR}/Downloads"
    add_root "${PROJECT_DIR}/Anime"
    add_root "${PROJECT_DIR}/Serien"
    add_root "${PROJECT_DIR}/Filme"

    if [[ ! -s "${TMP_DIR}/roots.txt" ]]; then
        die "Keine gültigen Medienpfade gefunden (Config prüfen: storage.*, BASE_PATH, MEDIA_PATH)"
    fi

    info "Storage mode: ${storage_mode:-unbekannt}"
    info "Verwendete Medienpfade:"
    sed 's/^/  - /' "${TMP_DIR}/roots.txt"
}

resolve_db_path() {
    local data_folder db_path
    data_folder="$(cfg_get DATA_FOLDER)"

    if [[ -z "${data_folder}" ]]; then
        data_folder="${PROJECT_DIR}/data"
        warn "data.folder fehlt in Config, verwende Fallback: ${data_folder}"
    else
        data_folder="$(normalize_path "${data_folder}")"
    fi

    db_path="${data_folder}/AniLoader.db"
    [[ -f "${db_path}" ]] || die "SQLite DB nicht gefunden: ${db_path}"
    [[ -r "${db_path}" ]] || die "SQLite DB nicht lesbar: ${db_path}"

    printf "%s\n" "${db_path}"
}

detect_sub_files_for_folder() {
    local folder_name="$1"

    : >"${TMP_DIR}/sub_files.txt"

    while IFS= read -r root; do
        # Suche im exakten Serienordner (folder_name aus DB)
        local series_dir="${root}/${folder_name}"
        [[ -d "${series_dir}" ]] || continue

        find "${series_dir}" -type f \( -iname "*.mkv" -o -iname "*.mp4" \) -print0 2>/dev/null \
            | while IFS= read -r -d '' f; do
                local b
                b="$(basename "${f}")"
                if [[ "${b}" =~ \[[Ss][Uu][Bb]\] ]]; then
                    printf "%s\n" "${f}" >>"${TMP_DIR}/sub_files.txt"
                fi
            done
    done <"${TMP_DIR}/roots.txt"

    # Deduplicate
    if [[ -s "${TMP_DIR}/sub_files.txt" ]]; then
        sort -u "${TMP_DIR}/sub_files.txt" -o "${TMP_DIR}/sub_files.txt"
    fi
}

build_missing_key_set() {
    local missing_json="$1"
    local key_file="$2"

    : >"${key_file}"

    # Keys aus URL-Mustern extrahieren (unabhängig von JSON-Parser)
    printf "%s\n" "${missing_json}" \
        | grep -oE '/staffel-[0-9]+/episode-[0-9]+' \
        | sed -E 's#^/staffel-([0-9]+)/episode-([0-9]+)$#\1:\2#' >>"${key_file}" || true

    printf "%s\n" "${missing_json}" \
        | grep -oE '/filme/film-[0-9]+' \
        | sed -E 's#^/filme/film-([0-9]+)$#0:\1#' >>"${key_file}" || true

    if [[ -s "${key_file}" ]]; then
        sort -u "${key_file}" -o "${key_file}"
    fi
}

extract_key_from_filename() {
    local filename="$1"

    if [[ "${filename}" =~ [Ss]([0-9]{2})[Ee]([0-9]{3}) ]]; then
        local s e
        s="${BASH_REMATCH[1]}"
        e="${BASH_REMATCH[2]}"
        # 08er-Interpretation vermeiden
        printf "%d:%d\n" "$((10#${s}))" "$((10#${e}))"
        return 0
    fi

    if [[ "${filename}" =~ [Ff]ilm([0-9]{2}) ]]; then
        local e
        e="${BASH_REMATCH[1]}"
        printf "0:%d\n" "$((10#${e}))"
        return 0
    fi

    return 1
}

write_report_header() {
    local db_path="$1"
    {
        echo "AniLoader Sub-DB Inkonsistenzreport"
        echo "Erstellt: $(date '+%Y-%m-%d %H:%M:%S')"
        echo "Config: ${CONFIG_PATH}"
        echo "DB: ${db_path}"
        echo ""
        echo "Kriterium: Datei ist lokal als [Sub] vorhanden, Episode fehlt aber in fehlende_deutsch_folgen."
        echo ""
    } >"${OUTPUT_PATH}"
}

append_issue() {
    local anime_id="$1"
    local title="$2"
    local url="$3"
    local folder_name="$4"
    local file_path="$5"
    local episode_key="$6"

    printf "%s\t%s\t%s\t%s\t%s\t%s\n" \
        "${anime_id}" "${title}" "${url}" "${folder_name}" "${file_path}" "${episode_key}" >>"${ISSUES_FILE}"
}

render_report() {
    local total_rows total_issues
    total_rows="$(wc -l <"${ROWS_FILE}" | tr -d ' ')"
    total_issues="0"
    [[ -s "${ISSUES_FILE}" ]] && total_issues="$(wc -l <"${ISSUES_FILE}" | tr -d ' ')"

    {
        echo "Analysierte DB-Einträge: ${total_rows}"
        echo "Gefundene Inkonsistenzen: ${total_issues}"
        echo ""
    } >>"${OUTPUT_PATH}"

    if [[ "${total_issues}" -eq 0 ]]; then
        echo "Keine Inkonsistenzen gefunden." >>"${OUTPUT_PATH}"
        info "Keine Inkonsistenzen gefunden."
        info "Report: ${OUTPUT_PATH}"
        return 0
    fi

    {
        echo "Details:"
        echo "--------------------------------------------------------------------------------"
        while IFS=$'\t' read -r anime_id title url folder_name file_path episode_key; do
            echo "ID: ${anime_id}"
            echo "Titel: ${title}"
            echo "Serie-URL: ${url}"
            echo "Ordner: ${folder_name}"
            echo "Datei: ${file_path}"
            echo "Episode-Key: ${episode_key}"
            echo "Status: [Sub] lokal vorhanden, aber nicht in fehlende_deutsch_folgen"
            echo "--------------------------------------------------------------------------------"
        done <"${ISSUES_FILE}"
    } >>"${OUTPUT_PATH}"

    info "Inkonsistenzen gefunden: ${total_issues}"
    info "Report: ${OUTPUT_PATH}"
}

scan_rows() {
    local db_path="$1"

    sqlite3 -separator $'\t' "${db_path}" \
        "SELECT id, title, url, COALESCE(folder_name,''), COALESCE(fehlende_deutsch_folgen,'[]') FROM anime WHERE deleted = 0;" \
        >"${ROWS_FILE}" || die "SQL-Abfrage fehlgeschlagen (DB gesperrt/beschädigt?)"

    while IFS=$'\t' read -r anime_id title url folder_name missing_json; do
        [[ -n "${anime_id}" ]] || continue

        if [[ -z "${folder_name}" ]]; then
            warn "Überspringe ID ${anime_id} (${title}): folder_name fehlt"
            continue
        fi

        detect_sub_files_for_folder "${folder_name}"

        [[ -s "${TMP_DIR}/sub_files.txt" ]] || continue

        local missing_keys_file
        missing_keys_file="${TMP_DIR}/missing_${anime_id}.txt"
        build_missing_key_set "${missing_json}" "${missing_keys_file}"

        while IFS= read -r sub_file; do
            local base key
            base="$(basename "${sub_file}")"

            if ! key="$(extract_key_from_filename "${base}")"; then
                warn "Dateiname ohne erkennbares Episodenmuster: ${sub_file}"
                continue
            fi

            if ! grep -Fxq "${key}" "${missing_keys_file}" 2>/dev/null; then
                append_issue "${anime_id}" "${title}" "${url}" "${folder_name}" "${sub_file}" "${key}"
            fi
        done <"${TMP_DIR}/sub_files.txt"

    done <"${ROWS_FILE}"
}

main() {
    require_cmd sqlite3
    require_cmd find
    require_cmd grep
    require_cmd sort
    require_cmd awk
    require_cmd sed

    discover_container_mounts

    parse_config "${CONFIG_PATH}"
    collect_roots

    local db_path
    db_path="$(resolve_db_path)"

    write_report_header "${db_path}"
    scan_rows "${db_path}"
    render_report
}

main "$@"
