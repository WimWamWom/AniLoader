"""
AniLoader – Download-Orchestrierung.

Verwaltet den Download-Prozess mit 4 Modi:
  - default:  Standardsprache, Fallback auf verfügbare Sprachen
  - german:   Prüft/lädt gezielt deutsche Episoden
  - new:      Prüft alle Serien auf neue Episoden
  - check:    Integritätsprüfung + fehlende Episoden nachladen

Download erfolgt per aniworld CLI (subprocess).
"""

import os
import platform
import re
import shutil
import signal
import subprocess
import threading
import time
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional
import random
from . import database as db
from . import scraper
from .config import (
    get_data_folder,
    get_download_path,
    get_film_naming_mode,
    load_config,
    normalize_language_list,
    sort_languages_by_priority,
)
from .file_manager import (
    check_file_integrity,
    clear_tmp,
    detect_file_language,
    episode_already_downloaded,
    find_downloaded_file,
    find_episode_files,
    get_free_space_gb,
    get_storage_path,
    get_tmp_path,
    move_tmp_to_final,

)
from .logger import log, start_new_run

# ──────────────────────── Status-Tracking ────────────────────────

status: Dict = {
    "status": "idle",  # idle | running | stopping | finished
    "mode": None,
    "current_title": None,
    "current_id": None,
    "current_url": None,
    "current_season": None,
    "current_episode": None,
    "current_is_film": False,
    "total_seasons": 0,
    "total_episodes_in_season": 0,
    "total_episodes_overall": 0,
    "completed_episodes_overall": 0,
    "started_at": None,
    "series_started_at": None,
    "episode_started_at": None,
    "progress": {
        "total_series": 0,
        "completed_series": 0,
        "current_series_index": 0,
        "downloaded_episodes": 0,
        "skipped_episodes": 0,
        "failed_episodes": 0,
    },
}

_download_lock = threading.Lock()
_status_lock = threading.Lock()
_download_thread: Optional[threading.Thread] = None
_last_result_lock = threading.Lock()
_last_run_result: Dict[str, Any] = {
    "mode": None,
    "finished_at": None,
    "result": {"downloaded": [], "failed": []},
}

_CDN_403_MAX_RETRIES = 2   # max. Anzahl Wiederholungen bei 403
_CDN_403_RETRY_DELAY = 15  # Sekunden Pause vor 403-Retry

# Zeit, die der aniworld-Prozessbaum nach SIGTERM zum Aufräumen bekommt,
# bevor SIGKILL folgt.
_KILL_GRACE_SECONDS = 10

# Trennlinie um den Serien-Banner. Feste Breite mit ─ statt einer Reihe von "="
# in Titellänge: so erkennt der Web-Log-View sie als Trennlinie und stylt sie
# dezent, statt 130 Zeichen "=" als normale Logzeile zu rendern.
_LOG_SEPARATOR = "─" * 72

# ANSI-Steuersequenzen (Farben, Cursor-Bewegung) und OSC-Sequenzen der CLI.
# Sie landen sonst wörtlich im Log und im Web-View als "[32m…[0m".
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")

# Fortschrittszeilen von yt-dlp/ffmpeg ("[download]  42.3% of 350.00MiB at 2.50MiB/s").
# aniworld überschreibt sie per \r; text=True übersetzt jedes \r in ein \n, wodurch
# ohne Zusammenfassen jeder Frame eine eigene Logzeile mit Timestamp bekäme.
_PROGRESS_RE = re.compile(
    r"\d+(?:[.,]\d+)?\s?%.*(?:ETA|/s\b|of\s|iB\b)|[━#=]{5,}", re.IGNORECASE
)


def _clean_cli_lines(text: str) -> List[str]:
    """Bereitet aniworld-Ausgabe fürs Log auf.

    Entfernt ANSI-Sequenzen und fasst aufeinanderfolgende Fortschritts-Frames
    zusammen, sodass pro Fortschrittsphase nur der letzte Stand im Log steht.
    """
    lines: List[str] = []

    for raw in (text or "").split("\n"):
        line = _ANSI_RE.sub("", raw).replace("\r", "").strip()
        if not line:
            continue

        if _PROGRESS_RE.search(line) and lines and _PROGRESS_RE.search(lines[-1]):
            lines[-1] = line  # vorherigen Frame ersetzen statt anhängen
            continue

        lines.append(line)

    return lines


def _parse_season_episode_from_url(episode_url: str) -> Optional[tuple[int, int]]:
    """Extrahiert (season, episode) aus einer Episoden-/Film-URL."""
    m = re.search(r"/staffel-(\d+)/episode-(\d+)", episode_url)
    if m:
        return int(m.group(1)), int(m.group(2))

    m = re.search(r"/filme/film-(\d+)", episode_url)
    if m:
        return 0, int(m.group(1))

    return None


def _normalize_aniworld_cli_url(url: str) -> str:
    """Passt URLs an das Format an, das die installierte aniworld-CLI akzeptiert."""
    if scraper.is_sto(url):
        return url.replace("/serie/stream/", "/serie/", 1)
    return url


def _normalize_language_list(languages: List[str]) -> List[str]:
    """Normalisiert Sprachliste und entfernt Duplikate, Reihenfolge bleibt erhalten."""
    return normalize_language_list(languages or [])


def _resolve_target_languages(
    cfg: dict,
    anime: Dict,
    force_languages: Optional[List[str]] = None,
) -> tuple[List[str], bool]:
    """
    Bestimmt die Zielsprachen für einen Eintrag.

    Returns:
        (Sprachliste, multi_mode)

        multi_mode=True  → Der Eintrag hat eine eigene Sprachauswahl in der DB.
                           ALLE dieser Sprachen werden geladen (nacheinander).
        multi_mode=False → Keine eigene Auswahl: globale Prioritäts-Kaskade,
                           die erste erfolgreiche Sprache gewinnt (Alt-Verhalten).
    """
    if force_languages:
        return _normalize_language_list(force_languages), False

    entry_languages = db.parse_languages(anime.get("languages"))
    if entry_languages:
        # Nach globaler Priorität sortieren → German Dub zuerst
        return sort_languages_by_priority(entry_languages, cfg), True

    cascade = cfg.get("languages") or ["German Dub", "German Sub", "English Sub", "English Dub"]
    return _normalize_language_list(cascade), False


def get_status() -> Dict:
    """Gibt den aktuellen Download-Status zurück."""
    with _status_lock:
        return status.copy()


def get_last_run_result() -> Dict[str, Any]:
    """Gibt das strukturierte Ergebnis des zuletzt beendeten Laufs zurück."""
    with _last_result_lock:
        return deepcopy(_last_run_result)


def is_running() -> bool:
    with _status_lock:
        return status["status"] in ("running", "stopping")


def request_stop() -> bool:
    """Fordert einen graceful Stop an (nach aktuellem Episode-Download)."""
    with _status_lock:
        if status["status"] == "running":
            status["status"] = "stopping"
            log("[DOWNLOAD] Stop angefordert – wird nach aktuellem Download gestoppt")
            return True
        return False


def _check_stop() -> bool:
    """Prüft ob ein Stop angefordert wurde."""
    with _status_lock:
        return status["status"] == "stopping"


def _reset_status():
    with _status_lock:
        status["status"] = "idle"
        status["mode"] = None
        status["current_title"] = None
        status["current_id"] = None
        status["current_url"] = None
        status["current_season"] = None
        status["current_episode"] = None
        status["current_is_film"] = False
        status["total_seasons"] = 0
        status["total_episodes_in_season"] = 0
        status["total_episodes_overall"] = 0
        status["completed_episodes_overall"] = 0
        status["started_at"] = None
        status["series_started_at"] = None
        status["episode_started_at"] = None
        status["progress"] = {
            "total_series": 0,
            "completed_series": 0,
            "current_series_index": 0,
            "downloaded_episodes": 0,
            "skipped_episodes": 0,
            "failed_episodes": 0,
        }


# ──────────────────────── Subprocess Download ────────────────────────


class ResourceExhaustedError(RuntimeError):
    """Der Container kann keine neuen Threads/Prozesse mehr starten.

    Wird nach oben durchgereicht, damit der Lauf abbricht statt jede weitere
    Episode fälschlich als 'nicht verfügbar' in die DB zu schreiben.
    """


def _is_resource_exhaustion(stderr_text: str) -> bool:
    """Erkennt, ob aniworld am Prozess-/Thread-Limit des Systems gescheitert ist.

    Bewusst eng gefasst: 'Resource temporarily unavailable' (EAGAIN) tritt auch bei
    normalen Netzwerkfehlern auf und zählt daher nur zusammen mit einem Hinweis auf
    Thread-/Prozesserzeugung.
    """
    if "can't start new thread" in stderr_text:
        return True
    if "Cannot allocate memory" in stderr_text and "fork" in stderr_text:
        return True

    eagain = "Resource temporarily unavailable" in stderr_text or "Errno 11" in stderr_text
    spawn_context = any(
        marker in stderr_text
        for marker in ("threading.py", "_start_new_thread", "fork", "subprocess.py")
    )
    return eagain and spawn_context


def _kill_process_tree(proc: subprocess.Popen, is_windows: bool) -> None:
    """Beendet den kompletten Prozessbaum von proc (aniworld → patchright → Chromium).

    Ohne dies überleben Chromium-Kindprozesse einen Timeout und belegen dauerhaft
    PIDs und Threads, bis der Container keine neuen Threads mehr starten kann.
    """
    if proc.poll() is not None:
        return

    if is_windows:
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
                timeout=30,
            )
        except Exception as e:
            log(f"[WARN] taskkill fehlgeschlagen: {e}")
            proc.kill()
        return

    # POSIX: der Prozess läuft dank start_new_session=True in eigener Prozessgruppe,
    # daher erwischt killpg auch alle Enkel (Chromium & Co.).
    try:
        pgid = os.getpgid(proc.pid)
    except (ProcessLookupError, OSError):
        return

    for sig, label in ((signal.SIGTERM, "SIGTERM"), (signal.SIGKILL, "SIGKILL")):
        try:
            os.killpg(pgid, sig)
        except ProcessLookupError:
            return
        except OSError as e:
            log(f"[WARN] {label} an Prozessgruppe {pgid} fehlgeschlagen: {e}")
            return

        try:
            proc.wait(timeout=_KILL_GRACE_SECONDS)
            # Prozessgruppe kann noch verwaiste Enkel enthalten – SIGKILL folgt trotzdem,
            # falls wir gerade erst SIGTERM geschickt haben.
            if sig == signal.SIGKILL:
                return
        except subprocess.TimeoutExpired:
            log(f"[WARN] Prozessgruppe {pgid} reagiert nicht auf {label} – eskaliere")

    # Finaler Sweep: Enkel, die die Gruppe verlassen haben bzw. SIGTERM überlebt haben.
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, OSError):
        pass


def _run_process_group(
    cmd: Any, timeout: int, env: Dict[str, str], is_windows: bool
) -> tuple:
    """Startet cmd in eigener Prozessgruppe und räumt bei Timeout den ganzen Baum ab.

    Ersetzt subprocess.run(timeout=...), das bei Timeout nur den direkten Kindprozess
    killt und dessen Chromium-Enkel als Waisen zurücklässt.

    Returns:
        (stdout, stderr, returncode)
    """
    popen_kwargs: Dict[str, Any] = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "env": env,
    }

    if is_windows:
        popen_kwargs["shell"] = True
        popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        # Eigene Session/Prozessgruppe, damit killpg den gesamten Baum trifft.
        popen_kwargs["start_new_session"] = True

    proc = subprocess.Popen(cmd, **popen_kwargs)

    try:
        stdout_text, stderr_text = proc.communicate(timeout=timeout)
        return stdout_text, stderr_text, proc.returncode
    except subprocess.TimeoutExpired:
        log("[CLEANUP] Timeout – beende aniworld-Prozessbaum inkl. Chromium …")
        _kill_process_tree(proc, is_windows)
        try:
            proc.communicate(timeout=30)
        except Exception:
            pass
        raise
    except BaseException:
        # Auch bei KeyboardInterrupt/Stop darf kein Chromium zurückbleiben.
        _kill_process_tree(proc, is_windows)
        try:
            proc.communicate(timeout=30)
        except Exception:
            pass
        raise


def _run_aniworld_download(
    episode_url: str, language: str, output_path: str, timeout: int = 900
) -> bool:
    """
    Führt den aniworld CLI Download als subprocess aus.

    Returns:
        True bei Erfolg, False bei Fehler
    """
    is_windows = platform.system() == "Windows"

    # TERM=xterm nötig damit curses/ncurses in aniworld sich initialisieren kann,
    # auch wenn kein echtes Terminal vorhanden ist (z.B. Docker ohne TTY).
    # DISPLAY=:99 explizit setzen als Fallback, falls der Prozess die Variable
    # nicht aus dem entrypoint geerbt hat (z.B. nach Xvfb-Neustart durch Watchdog).
    subprocess_env = os.environ.copy()
    subprocess_env.setdefault("TERM", "xterm")
    if platform.system() != "Windows":
        subprocess_env.setdefault("DISPLAY", ":99")
    cli_url = _normalize_aniworld_cli_url(episode_url)

    if cli_url != episode_url:
        log(f"[CMD] Normalisiere URL für aniworld CLI: {episode_url} -> {cli_url}")

    cmd: Any
    log_cmd = f'aniworld --language "{language}" -a Download -o "{output_path}" {cli_url}'

    if is_windows:
        # chcp 65001 schaltet die Codepage der cmd.exe auf UTF-8, damit Umlaute in
        # Titeln und Pfaden nicht verstümmelt zurückkommen; >nul unterdrückt die
        # Meldung "Aktive Codepage: 65001". Der Prefix bleibt aus dem Log heraus.
        cmd = f"chcp 65001 >nul & {log_cmd}"
    else:
        # Kein shell=True auf POSIX: die Shell wäre ein zusätzlicher Prozess zwischen
        # uns und aniworld und würde das Aufräumen des Prozessbaums erschweren.
        cmd = ["aniworld", "--language", language, "-a", "Download", "-o", output_path, cli_url]

    log(f"[CMD] {log_cmd}")

    for attempt in range(1 + _CDN_403_MAX_RETRIES):
        if attempt > 0:
            log(f"[RETRY] HTTP 403 erkannt – warte {_CDN_403_RETRY_DELAY}s vor Versuch {attempt + 1} …")
            time.sleep(_CDN_403_RETRY_DELAY)

        try:
            stdout_text, stderr_text, returncode = _run_process_group(
                cmd, timeout=timeout, env=subprocess_env, is_windows=is_windows
            )
        except subprocess.TimeoutExpired:
            log(f"[ERROR] Timeout ({timeout}s) für {episode_url}")
            return False
        except Exception as e:
            log(f"[ERROR] Subprocess-Fehler: {e}")
            return False

        # Log Output
        for line in _clean_cli_lines(stdout_text):
            log(f"[ANIWORLD] {line}")

        if returncode == 0:
            # Kurz warten bis Dateisystem aufholt
            time.sleep(3)
            return True

        # Fehlerausgabe prüfen
        stderr_text = stderr_text or ""
        for line in _clean_cli_lines(stderr_text):
            log(f"[ANIWORLD-ERR] {line}")

        if _is_resource_exhaustion(stderr_text):
            log(
                "[FATAL] Container hat keine Threads/PIDs mehr frei – "
                "aniworld konnte nicht einmal starten. Weitere Downloads würden "
                "ebenfalls scheitern und Episoden fälschlich als 'nicht verfügbar' markieren."
            )
            raise ResourceExhaustedError(
                "Prozess-/Thread-Limit des Containers erreicht"
            )

        # Bei HTTP 403 (CDN-Token abgelaufen) → Retry
        if "HTTP error 403" in stderr_text or "403 Forbidden" in stderr_text:
            if attempt < _CDN_403_MAX_RETRIES:
                continue

        return False

    return False


def _select_language(
    available_languages: List[str], preferred_languages: List[str]
) -> Optional[str]:
    """Wählt die beste verfügbare Sprache basierend auf Priorität."""
    for lang in preferred_languages:
        if lang in available_languages:
            return lang
    return None


def _resolve_target_dir(
    cfg: dict,
    data_folder: str,
    anime: Dict,
    found: Path,
    tmp_path: Path,
    season: int,
    is_film: bool,
):
    """
    Bestimmt den finalen Zielordner für eine aus TMP kommende Datei.

    Der Serien-Ordnername wird aus dem TMP-Pfad abgeleitet (zuverlässig, kein
    Raten) und beim ersten Download in der DB gespeichert.
    """
    try:
        rel = found.relative_to(tmp_path)
        parts = rel.parts
        detected_folder = parts[0] if len(parts) >= 2 else None
    except ValueError:
        detected_folder = None

    existing_folder = anime.get("folder_name")

    # DB-Ordnername initial speichern, wenn noch nicht bekannt
    if not existing_folder and detected_folder:
        db.update_anime(data_folder, anime["id"], folder_name=detected_folder)
        anime["folder_name"] = detected_folder
        log(f"[DB] Ordnername gespeichert: {detected_folder}")

    # Finaler Zielordner: DB-Ordnername hat Vorrang vor erkanntem (verhindert Ordner-Drift)
    final_folder = existing_folder or detected_folder
    return get_storage_path(
        cfg,
        anime["url"],
        folder_name=final_folder,
        season=season,
        is_film=is_film,
    )


def _download_episode(
    cfg: dict,
    data_folder: str,
    anime: Dict,
    season: int,
    episode_info: Dict,
    detailed: bool = False,
    ignore_existing: bool = False,
    force_languages: Optional[List[str]] = None,
) -> Any:
    """
    Lädt eine einzelne Episode herunter.

    Bei Einträgen mit eigener Sprachauswahl wird jede Sprache STRIKT
    SEQUENZIELL abgearbeitet:

        TMP leeren → Sprache A laden → Datei sofort ins Zielverzeichnis
        verschieben → TMP leeren → erst danach Sprache B laden → …

    Dadurch liegt zu keinem Zeitpunkt mehr als eine Sprachversion im
    aniworld-Arbeitsordner und aniworld kann die Versionen nicht automatisch
    zusammenführen.

    Returns:
        Standard: "downloaded" | "skipped" | "failed" | "no_german" | "no_language"
        Detailed: {"status": str, "language": Optional[str],
                   "languages": List[str], "missing_languages": List[str]}
    """
    def _result(
        result_status: str,
        language: Optional[str] = None,
        languages: Optional[List[str]] = None,
        missing: Optional[List[str]] = None,
    ) -> Any:
        if detailed:
            return {
                "status": result_status,
                "language": language,
                "languages": languages if languages is not None else ([language] if language else []),
                "missing_languages": missing or [],
            }
        return result_status

    episode_num = episode_info["episode"]
    episode_url = episode_info["url"]
    is_film = season == 0
    ep_label = f"S{season:02d}E{episode_num:03d}"
    target_languages, multi_mode = _resolve_target_languages(cfg, anime, force_languages)
    min_free = cfg.get("download", {}).get("min_free_gb", 2.0)
    timeout = cfg.get("download", {}).get("timeout_seconds", 900)
    output_path = get_download_path(cfg, anime["url"], is_film)

    # Status aktualisieren
    status["current_season"] = season
    status["current_episode"] = episode_num
    status["current_is_film"] = is_film
    status["episode_started_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    # Speicherplatz prüfen
    free_gb = get_free_space_gb(output_path)
    if free_gb < min_free:
        log(f"[WARN] Nur {free_gb:.1f} GB frei (Minimum: {min_free} GB) – überspringe")
        return _result("failed", missing=target_languages)

    # ── Inkrementell: bereits vorhandene (Episode, Sprache)-Kombinationen ermitteln ──
    present_languages: List[str] = []
    pending_languages: List[str] = list(target_languages)

    if not ignore_existing:
        if multi_mode:
            # Pro gewünschter Sprache prüfen – nur fehlende Sprachen werden geladen
            for lang in target_languages:
                if episode_already_downloaded(
                    cfg, anime["url"], anime.get("folder_name"), season, episode_num,
                    title_hint=anime.get("title"), language=lang,
                ):
                    present_languages.append(lang)

            pending_languages = [l for l in target_languages if l not in present_languages]
            if not pending_languages:
                log(f"[SKIP] Bereits vorhanden [{', '.join(target_languages)}]: {ep_label}")
                return _result("skipped", languages=present_languages)
            if present_languages:
                log(f"[LANG] {ep_label} – vorhanden: {present_languages} | fehlt: {pending_languages}")
        else:
            # Kaskaden-Modus: jede vorhandene Sprachversion zählt als erledigt
            existing = episode_already_downloaded(
                cfg, anime["url"], anime.get("folder_name"), season, episode_num,
                title_hint=anime.get("title"),
            )
            if existing:
                log(f"[SKIP] Bereits vorhanden: {ep_label}")
                return _result("skipped")

    # Sprachen der Episode bestimmen.
    #
    # Von der Staffelseite kommen sie NICHT mehr: scraper.get_episodes_for_season
    # enumeriert Episoden bewusst mit genau einem Fetch und laesst "languages" leer,
    # weil die Sprachen pro Episode einen eigenen Fetch kosten. Das Feld bleibt
    # trotzdem erhalten – Aufrufer, die die Sprachen ohnehin schon ermittelt haben
    # (siehe German-Modus), reichen sie hier durch und sparen den zweiten Fetch.
    ep_langs = _normalize_language_list(episode_info.get("languages", []))

    if ep_langs:
        log(f"[LANG] {ep_label} – Sprachen bereits bekannt: {ep_langs}")
    else:
        ep_langs = _normalize_language_list(scraper.get_episode_languages(episode_url))
        log(f"[LANG] {ep_label} – Sprachen von der Episoden-Seite: {ep_langs}")

    # AniWorld: Prüfe ob Episode überhaupt Streams hat (kein Ankündigungs-Placeholder)
    if scraper.is_aniworld(episode_url) and not ep_langs:
        if not scraper.is_episode_available(episode_url):
            log(f"[SKIP] {ep_label} – keine Streams verfügbar (Ankündigung)")
            return _result("no_language", missing=pending_languages)

    # S.to: Keine Sprache gefunden → Episode nicht verfügbar, überspringen
    if scraper.is_sto(episode_url) and not ep_langs:
        log(f"[SKIP] {ep_label} – keine Sprache → nicht verfügbar")
        return _result("no_language", missing=pending_languages)

    # Zielsprachen auf die tatsächlich verfügbaren einschränken
    if ep_langs:
        cascading_languages = [l for l in pending_languages if l in ep_langs]
    else:
        # Sprachen unbekannt → alle offenen Zielsprachen versuchen
        cascading_languages = list(pending_languages)
        log(f"[LANG] Sprachen unbekannt – versuche alle offenen Sprachen: {cascading_languages}")

    # serienstream unterstützt kein English Sub
    if scraper.is_sto(episode_url):
        _sto_supported = {"German Dub", "German Sub", "English Dub"}
        _removed = [l for l in cascading_languages if l not in _sto_supported]
        cascading_languages = [l for l in cascading_languages if l in _sto_supported]
        if _removed:
            log(f"[LANG] serienstream: Nicht unterstützte Sprachen entfernt: {_removed}")

    if not cascading_languages:
        log(f"[SKIP] {ep_label} – keine der gewünschten Sprachen verfügbar "
            f"(gewünscht: {pending_languages} | verfügbar: {ep_langs or 'unbekannt'})")
        return _result("no_language", missing=pending_languages)

    # Download: sequenziell pro Sprache in das TMP-Verzeichnis.
    # TMP immer unter dem konfigurierten download_path (nicht output_path),
    # damit bei separate-Storage kein /app/Serien/tmp entsteht.
    dl_base = cfg.get("storage", {}).get("download_path", output_path)
    tmp_path = get_tmp_path(dl_base)
    film_naming_mode = get_film_naming_mode(cfg)

    downloaded_languages: List[str] = []
    failed_languages: List[str] = []
    ep_title: Optional[str] = None

    for lang in cascading_languages:
        if _check_stop():
            log(f"[STOP] {ep_label} – weitere Sprachen werden nicht mehr geladen")
            break

        log(f"[DL] {ep_label} [{lang}] → TMP: {tmp_path}")
        # TMP vor jedem Versuch leeren: aniworld darf nie zwei Sprachversionen
        # gleichzeitig im selben Ordner sehen, sonst werden sie zusammengeführt.
        clear_tmp(tmp_path)

        if not _run_aniworld_download(episode_url, lang, str(tmp_path), timeout):
            failed_languages.append(lang)
            continue

        found = find_downloaded_file(str(tmp_path), season, episode_num)
        if not found:
            log(f"[WARN] {ep_label} [{lang}] – keine Datei im TMP gefunden")
            failed_languages.append(lang)
            continue

        log(f"[TMP] Gefundene Datei: {found.name}")

        target_dir = _resolve_target_dir(cfg, data_folder, anime, found, tmp_path, season, is_film)
        log(f"[TMP] Zielpfad: {target_dir}")

        if ep_title is None:
            # serienstream liefert Episodentitel nicht auf Staffel-Ebene (das Modul
            # kennt sie nur pro Episoden-Fetch). Deshalb hier – nur beim tatsächlichen
            # Download, wo der Dateiname gebaut wird – gezielt nachladen: 1 Fetch pro
            # Episode statt 1 pro enumerierter Episode oder 1 pro Sprache.
            ep_title = episode_info.get("title_de") or episode_info.get("title_en") or ""
            if not ep_title:
                ep_title = scraper.get_episode_title(episode_url) or ""

        final_path = move_tmp_to_final(
            found, target_dir, season, episode_num, ep_title, lang,
            film_naming_mode=film_naming_mode,
        )

        # TMP sofort nach dem Verschieben leeren – erst danach startet die
        # nächste Sprache (strikt sequenziell, kein paralleler Zugriff).
        clear_tmp(tmp_path)

        if final_path:
            log(f"[OK] {ep_label} [{lang}] → {final_path.name}")
            downloaded_languages.append(lang)
        else:
            log(f"[WARN] {ep_label} [{lang}] – Verschieben aus TMP fehlgeschlagen")
            failed_languages.append(lang)
            continue

        if not multi_mode:
            # Kaskaden-Modus: erste erfolgreiche Sprache gewinnt
            break

    all_present = present_languages + downloaded_languages
    missing_languages = [l for l in target_languages if l not in all_present]

    if not downloaded_languages:
        log(f"[FAIL] {ep_label} – kein Download möglich (versucht: {failed_languages})")
        return _result("failed", missing=missing_languages)

    if multi_mode and missing_languages:
        log(f"[WARN] {ep_label} – nicht geladen: {missing_languages}")

    primary_language = downloaded_languages[0]

    # Fehlende deutsche Episoden tracken – nur wenn German Dub gewünscht ist
    # und weder vorhanden noch geladen wurde.
    if "German Dub" in target_languages and "German Dub" not in all_present:
        return _result("no_german", primary_language, downloaded_languages, missing_languages)

    return _result("downloaded", primary_language, downloaded_languages, missing_languages)


# ──────────────────────── Modi ────────────────────────


def _run_default(cfg: dict, data_folder: str) -> None:
    """
    Default Mode: Alle nicht-vollständigen Serien herunterladen.
    Nutzt konfigurierte Sprachpriorität mit Fallback.
    """
    log("[MODE] Default – Standard-Download")
    anime_list = db.get_incomplete_anime(data_folder)
    status["progress"]["total_series"] = len(anime_list)

    for idx, anime in enumerate(anime_list):
        if _check_stop():
            log("[STOP] Download auf Anfrage gestoppt")
            return

        status["current_title"] = anime["title"]
        status["current_id"] = anime["id"]
        status["current_url"] = anime["url"]
        status["series_started_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        status["episode_started_at"] = None
        status["progress"]["current_series_index"] = idx + 1

        base_url = scraper.get_base_url(anime["url"])
        log(_LOG_SEPARATOR)
        log(f"[SERIE] {anime['title']} – {base_url}")
        log(_LOG_SEPARATOR)

        seasons = scraper.get_season_numbers(anime["url"])
        if not seasons:
            log(f"[WARN] Keine Staffeln gefunden für {anime['title']}")
            continue

        missing_german: List[str] = db.get_missing_german_episodes(data_folder, anime["id"])
        new_missing_german: List[str] = []
        had_failures = False

        # Filme (season=0) als erstes laden
        seasons_ordered = ([0] if 0 in seasons else []) + [s for s in seasons if s != 0]
        status["total_seasons"] = max((s for s in seasons if s != 0), default=0)

        # Pre-fetch aller Episodenlisten für Gesamtfortschritt
        all_eps_by_season: Dict[int, List] = {}
        for _s in seasons_ordered:
            if _s != 0 and _s < anime.get("last_season", 0):
                all_eps_by_season[_s] = []
                continue
            all_eps_by_season[_s] = scraper.get_episodes_for_season(base_url, _s) or []
        status["total_episodes_overall"] = sum(len(v) for v in all_eps_by_season.values())
        status["completed_episodes_overall"] = 0

        for season in seasons_ordered:
            if _check_stop():
                all_missing = missing_german + new_missing_german
                if all_missing:
                    db.set_missing_german_episodes(data_folder, anime["id"], all_missing)
                return

            # Überspringe bereits heruntergeladene Staffeln
            if season != 0 and season < anime.get("last_season", 0):
                continue

            episodes = all_eps_by_season.get(season, [])
            status["total_episodes_in_season"] = len(episodes)
            if not episodes:
                label = "Filme" if season == 0 else f"Staffel {season}"
                log(f"[WARN] Keine Episoden gefunden für {label} – überspringe")
                continue

            for ep in episodes:
                if _check_stop():
                    all_missing = missing_german + new_missing_german
                    if all_missing:
                        db.set_missing_german_episodes(data_folder, anime["id"], all_missing)
                    return

                result = _download_episode(cfg, data_folder, anime, season, ep)
                status["completed_episodes_overall"] += 1

                if result == "downloaded":
                    status["progress"]["downloaded_episodes"] += 1
                elif result == "skipped":
                    status["progress"]["skipped_episodes"] += 1
                elif result == "failed":
                    had_failures = True
                    status["progress"]["failed_episodes"] += 1
                elif result == "no_german":
                    new_missing_german.append(ep["url"])
                    status["progress"]["downloaded_episodes"] += 1
                elif result == "no_language":
                    status["progress"]["skipped_episodes"] += 1

                # Progress in DB speichern (nicht bei nicht verfügbarer Sprache oder Fehler)
                # WICHTIG: Fehlgeschlagene Episoden NICHT als "erledigt" markieren,
                # damit sie beim nächsten Lauf erneut versucht werden.
                if result not in ("no_language", "failed"):
                    if season == 0:
                        db.update_anime(data_folder, anime["id"], last_film=ep["episode"])
                    else:
                        db.update_anime(
                            data_folder, anime["id"],
                            last_season=season, last_episode=ep["episode"],
                        )
                # sec_min = 480
                # sec_max = 600
                # wait_seconds = random.randint(sec_min, sec_max)
                # log(f"[WAIT] Warte {wait_seconds} Sekunden vor nächstem Download...")
                # time.sleep(wait_seconds)

        # Status Updates
        all_missing = missing_german + new_missing_german
        if all_missing:
            db.set_missing_german_episodes(data_folder, anime["id"], all_missing)
            db.update_anime(data_folder, anime["id"], deutsch_komplett=0)
        elif not missing_german:
            db.update_anime(data_folder, anime["id"], deutsch_komplett=1)

        if not had_failures:
            db.update_anime(data_folder, anime["id"], complete=1)
            log(f"[DONE] {anime['title']} als komplett markiert")

        status["progress"]["completed_series"] += 1


def _run_german(cfg: dict, data_folder: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    German Mode: Prüft fehlende deutsche Episoden und lädt diese nach.
    """
    log("[MODE] German – Deutsche Episoden nachladen")
    run_result: Dict[str, List[Dict[str, Any]]] = {"downloaded": [], "failed": []}
    anime_list = db.get_active_anime(data_folder)
    status["progress"]["total_series"] = len(anime_list)

    # German-Mode soll konsistent über die normale Episode-Pipeline laufen,
    # aber ausschließlich German Dub versuchen.
    german_cfg = dict(cfg)
    german_cfg["languages"] = ["German Dub"]

    for idx, anime in enumerate(anime_list):
        if _check_stop():
            return run_result

        missing = db.get_missing_german_episodes(data_folder, anime["id"])
        if not missing:
            status["progress"]["completed_series"] += 1
            continue

        status["current_title"] = anime["title"]
        status["current_id"] = anime["id"]
        status["current_url"] = anime["url"]
        status["series_started_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        status["episode_started_at"] = None
        status["progress"]["current_series_index"] = idx + 1

        log(f"\n[GERMAN] {anime['title']} – {len(missing)} fehlende deutsche Episoden")

        # ── Staffelseiten einmalig scrapen, vollständige Episode-Infos cachen ──
        # Wie in _run_default/_run_new/_run_check: get_episodes_for_season einmal
        # pro Staffel aufrufen → alle Episoden inkl. Titel und Sprachen aus der
        # Staffel-Tabelle (row-genau) im Cache speichern.
        base_url = scraper.get_base_url(anime["url"])
        seasons_needed: set = set()
        for ep_url in missing:
            parsed_pre = _parse_season_episode_from_url(ep_url)
            if parsed_pre:
                seasons_needed.add(parsed_pre[0])

        ep_info_cache: Dict[str, Dict] = {}  # episode_url → vollständiges episode_info-Dict
        for s_num in sorted(seasons_needed):
            log(f"[SCAN] Lade Staffelseite {s_num} …")
            season_eps = scraper.get_episodes_for_season(base_url, s_num) or []
            for ep in season_eps:
                ep_info_cache[ep["url"]] = ep
            log(f"[SCAN] Staffel {s_num}: {len(season_eps)} Episoden gescrapt")
        # ─────────────────────────────────────────────────────────────────────

        still_missing: List[str] = []
        status["total_episodes_overall"] = len(missing)
        status["completed_episodes_overall"] = 0

        for episode_url in missing:
            if _check_stop():
                db.set_missing_german_episodes(data_folder, anime["id"], still_missing)
                return run_result

            log(f"[DL] Versuche German Dub für {episode_url}")
            parsed = _parse_season_episode_from_url(episode_url)
            if not parsed:
                # Fallback: URL-Format unbekannt -> alter Direkt-Download
                output_path = get_download_path(german_cfg, anime["url"])
                timeout = german_cfg.get("download", {}).get("timeout_seconds", 900)
                if _run_aniworld_download(episode_url, "German Dub", output_path, timeout):
                    log(f"[OK] German Dub erfolgreich: {episode_url}")
                    status["progress"]["downloaded_episodes"] += 1
                    run_result["downloaded"].append({
                        "title": anime["title"],
                        "url": episode_url,
                        "season": -1,
                        "episode": -1,
                        "language": "German Dub",
                    })
                else:
                    log(f"[SKIP] German Dub noch nicht verfügbar: {episode_url}")
                    still_missing.append(episode_url)
                    status["progress"]["skipped_episodes"] += 1
                    run_result["failed"].append({
                        "title": anime["title"],
                        "url": episode_url,
                        "season": -1,
                        "episode": -1,
                        "language": "German Dub",
                        "reason": "language_unavailable",
                    })
                status["completed_episodes_overall"] += 1
                continue

            season, episode_num = parsed
            output_path = get_download_path(german_cfg, anime["url"], season == 0)

            # Sprach-Verfügbarkeit gezielt für die laut DB fehlende Sprache (German Dub)
            # ermitteln. Das aniworld-Modul liefert Sprachen nur pro Episode (gebündelt
            # in EINEM Fetch); es wird ausschließlich German Dub geprüft/geladen.
            log(f"[CHECK] Prüfe Sprachverfügbarkeit (German Dub) für {episode_url}")
            cached_ep = ep_info_cache.get(episode_url)
            available_langs = _normalize_language_list((cached_ep or {}).get("languages", []))
            if not available_langs:
                # Sprachen kommen nicht mehr von der Staffelseite → pro Episode holen (1 Fetch).
                available_langs = _normalize_language_list(scraper.get_episode_languages(episode_url))

            if available_langs and "German Dub" not in available_langs:
                log(f"[SKIP] German Dub nicht verfügbar (Staffel-Scan): {episode_url} – verfügbar: {available_langs}")
                still_missing.append(episode_url)
                status["progress"]["skipped_episodes"] += 1
                status["completed_episodes_overall"] += 1
                continue

            if not available_langs and scraper.is_sto(episode_url):
                log(f"[WARN] serienstream-Sprachen konnten nicht sicher erkannt werden – versuche German Dub trotzdem: {episode_url}")

            log(f"[CHECK] German Dub verfügbar – starte Download: {episode_url}")

            # Vorhandene Dateien dieser Episode merken (zum späteren Ersetzen).
            # Nur Dateien entfernen, deren Sprache NICHT gewünscht ist: bei
            # Mehrsprach-Einträgen bleiben z.B. English-Sub-Versionen erhalten,
            # bei Einträgen ohne eigene Auswahl gilt wie bisher "nur German Dub behalten".
            entry_languages = db.parse_languages(anime.get("languages"))
            keep_languages = set(entry_languages) | {"German Dub"} if entry_languages else {"German Dub"}
            replaceable_files = [
                f for f in find_episode_files(
                    german_cfg, anime["url"], anime.get("folder_name"),
                    season, episode_num, title_hint=anime.get("title"),
                )
                if detect_file_language(f) not in keep_languages
            ]

            # Titel aus dem Staffel-Scan uebernehmen und die oben bereits
            # ermittelten Sprachen durchreichen. Ohne das Durchreichen holt
            # _download_episode dieselbe Episodenseite ein zweites Mal, denn der
            # Staffel-Scan laesst "languages" grundsaetzlich leer.
            episode_info = dict(cached_ep) if cached_ep is not None else {
                "episode": episode_num,
                "url": episode_url,
                "title_de": "",
                "title_en": "",
            }
            episode_info["languages"] = available_langs

            # Download in TMP; erst nach Erfolg alte Datei ersetzen.
            detailed_result = _download_episode(
                german_cfg,
                data_folder,
                anime,
                season,
                episode_info,
                detailed=True,
                ignore_existing=True,
                force_languages=["German Dub"],
            )
            result = detailed_result.get("status")
            used_language = detailed_result.get("language") or "German Dub"

            if result == "downloaded":
                # Alte, nicht (mehr) gewünschte Sprachversionen erst jetzt entfernen
                # (der German-Dub-Download war erfolgreich)
                for old_file in replaceable_files:
                    try:
                        old_file.unlink()
                        log(f"[REPLACE] Alte Datei gelöscht: {old_file.name}")
                    except Exception as e:
                        log(f"[WARN] Alte Datei konnte nicht gelöscht werden: {e}")

                log(f"[OK] German Dub erfolgreich: {episode_url}")
                status["progress"]["downloaded_episodes"] += 1
                run_result["downloaded"].append({
                    "title": anime["title"],
                    "url": episode_url,
                    "season": season,
                    "episode": episode_num,
                    "language": used_language,
                })
                if season == 0:
                    db.update_anime(data_folder, anime["id"], last_film=episode_num)
                else:
                    db.update_anime(
                        data_folder,
                        anime["id"],
                        last_season=season,
                        last_episode=episode_num,
                    )
            elif result == "failed":
                log(f"[SKIP] German Dub Download fehlgeschlagen: {episode_url}")
                still_missing.append(episode_url)
                status["progress"]["skipped_episodes"] += 1
                run_result["failed"].append({
                    "title": anime["title"],
                    "url": episode_url,
                    "season": season,
                    "episode": episode_num,
                    "language": "German Dub",
                    "reason": "download_failed",
                })
            elif result == "no_language":
                log(f"[SKIP] German Dub nicht verfügbar (Download-Check): {episode_url}")
                still_missing.append(episode_url)
                status["progress"]["skipped_episodes"] += 1
                run_result["failed"].append({
                    "title": anime["title"],
                    "url": episode_url,
                    "season": season,
                    "episode": episode_num,
                    "language": "German Dub",
                    "reason": "language_unavailable",
                })
            else:
                still_missing.append(episode_url)
                status["progress"]["skipped_episodes"] += 1

            status["completed_episodes_overall"] += 1

        db.set_missing_german_episodes(data_folder, anime["id"], still_missing)
        if not still_missing:
            db.update_anime(data_folder, anime["id"], deutsch_komplett=1)
            log(f"[DONE] {anime['title']} – alle deutschen Episoden komplett")

        status["progress"]["completed_series"] += 1

    return run_result


def _run_new(cfg: dict, data_folder: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    New Mode: Prüft alle Serien auf neue Episoden seit dem letzten Download.
    """
    log("[MODE] New – Neue Episoden prüfen")
    run_result: Dict[str, List[Dict[str, Any]]] = {"downloaded": [], "failed": []}
    anime_list = db.get_active_anime(data_folder)
    status["progress"]["total_series"] = len(anime_list)

    for idx, anime in enumerate(anime_list):
        if _check_stop():
            return run_result

        status["current_title"] = anime["title"]
        status["current_id"] = anime["id"]
        status["current_url"] = anime["url"]
        status["series_started_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        status["episode_started_at"] = None
        status["progress"]["current_series_index"] = idx + 1

        base_url = scraper.get_base_url(anime["url"])
        last_season = anime.get("last_season", 0)
        last_episode = anime.get("last_episode", 0)
        last_film = anime.get("last_film", 0)

        seasons = scraper.get_season_numbers(anime["url"])
        if not seasons:
            continue
        status["total_seasons"] = max((s for s in seasons if s != 0), default=0)

        # Pre-fetch aller Episodenlisten für Gesamtfortschritt
        all_eps_by_season: Dict[int, List] = {}
        for _s in seasons:
            all_eps_by_season[_s] = scraper.get_episodes_for_season(base_url, _s) or []
        status["total_episodes_overall"] = sum(len(v) for v in all_eps_by_season.values())
        status["completed_episodes_overall"] = 0

        has_new = False
        had_failures = False
        had_no_language = False
        missing_german: List[str] = db.get_missing_german_episodes(data_folder, anime["id"])
        new_missing_german: List[str] = []

        for season in seasons:
            if _check_stop():
                all_missing = missing_german + new_missing_german
                if all_missing:
                    db.set_missing_german_episodes(data_folder, anime["id"], all_missing)
                return run_result

            episodes = all_eps_by_season.get(season, [])
            status["total_episodes_in_season"] = len(episodes)
            if not episodes:
                label = "Filme" if season == 0 else f"Staffel {season}"
                log(f"[WARN] Keine Episoden gefunden für {label} – überspringe")
                continue

            for ep in episodes:
                if _check_stop():
                    all_missing = missing_german + new_missing_german
                    if all_missing:
                        db.set_missing_german_episodes(data_folder, anime["id"], all_missing)
                    return run_result

                # Nur neue Episoden (nach dem letzten bekannten Stand)
                if season == 0:
                    if ep["episode"] <= last_film:
                        status["completed_episodes_overall"] += 1
                        continue
                elif season < last_season:
                    status["completed_episodes_overall"] += 1
                    continue
                elif season == last_season and ep["episode"] <= last_episode:
                    status["completed_episodes_overall"] += 1
                    continue

                detailed_result = _download_episode(cfg, data_folder, anime, season, ep, detailed=True)
                result = detailed_result.get("status")
                used_language = detailed_result.get("language") or "Unknown"
                status["completed_episodes_overall"] += 1
                if result in ("downloaded", "no_german"):
                    has_new = True
                    status["progress"]["downloaded_episodes"] += 1
                    run_result["downloaded"].append({
                        "title": anime["title"],
                        "url": ep["url"],
                        "season": season,
                        "episode": ep["episode"],
                        "language": used_language,
                    })
                    if result == "no_german":
                        new_missing_german.append(ep["url"])
                elif result == "skipped":
                    status["progress"]["skipped_episodes"] += 1

                # DB-Position aktualisieren (analog zu Default-Modus):
                # Fehlgeschlagene und sprachlose Episoden NICHT als erledigt markieren.
                if result not in ("no_language", "failed"):
                    if season == 0:
                        db.update_anime(data_folder, anime["id"], last_film=ep["episode"])
                    else:
                        db.update_anime(
                            data_folder, anime["id"],
                            last_season=season, last_episode=ep["episode"],
                        )
                elif result == "failed":
                    had_failures = True
                    status["progress"]["failed_episodes"] += 1
                    run_result["failed"].append({
                        "title": anime["title"],
                        "url": ep["url"],
                        "season": season,
                        "episode": ep["episode"],
                        "language": used_language,
                        "reason": "download_failed",
                    })
                elif result == "no_language":
                    had_no_language = True
                    status["progress"]["skipped_episodes"] += 1

        # Missing-German in DB speichern (analog zu Default-Modus)
        all_missing = missing_german + new_missing_german
        if all_missing:
            db.set_missing_german_episodes(data_folder, anime["id"], all_missing)
            db.update_anime(data_folder, anime["id"], deutsch_komplett=0)
            log(f"[NEW] {len(new_missing_german)} neue fehlende deutsche Episoden für {anime['title']}")
        elif not missing_german:
            db.update_anime(data_folder, anime["id"], deutsch_komplett=1)

        if has_new:
            log(f"[NEW] Neue Episoden heruntergeladen für {anime['title']}")
        else:
            log(f"[NEW] Keine neuen Episoden für {anime['title']}")

        # Komplett markieren wenn alle verfügbaren Episoden geladen sind und
        # die verbleibenden Folgen nur Ankündigungen ohne Streams sind
        if had_no_language and not had_failures:
            db.update_anime(data_folder, anime["id"], complete=1)
            log(f"[DONE] {anime['title']} als komplett markiert (letzte Folgen noch nicht verfügbar)")

        status["progress"]["completed_series"] += 1

    return run_result


def _run_german_new(cfg: dict, data_folder: str) -> Dict[str, Any]:
    """Kombinierter Modus: erst German, dann New im selben Lauf."""
    log("[MODE] German+New – kombinierten Lauf starten")
    german_result = _run_german(cfg, data_folder)

    if _check_stop():
        return {
            "german": german_result,
            "new": {"downloaded": [], "failed": []},
            "downloaded": german_result.get("downloaded", []),
            "failed": german_result.get("failed", []),
        }

    new_result = _run_new(cfg, data_folder)
    return {
        "german": german_result,
        "new": new_result,
        "downloaded": german_result.get("downloaded", []) + new_result.get("downloaded", []),
        "failed": german_result.get("failed", []) + new_result.get("failed", []),
    }


def _run_check(cfg: dict, data_folder: str) -> None:
    """
    Check Mode: Integritätsprüfung aller Downloads.
    Prüft Existenz, Dateigröße und Vollständigkeit.
    Fehlende Dateien werden erneut heruntergeladen.
    """
    log("[MODE] Check – Integritätsprüfung")
    anime_list = db.get_active_anime(data_folder)
    status["progress"]["total_series"] = len(anime_list)

    for idx, anime in enumerate(anime_list):
        if _check_stop():
            return

        status["current_title"] = anime["title"]
        status["current_id"] = anime["id"]
        status["current_url"] = anime["url"]
        status["series_started_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        status["episode_started_at"] = None
        status["progress"]["current_series_index"] = idx + 1

        base_url = scraper.get_base_url(anime["url"])
        log(f"[CHECK] {anime['title']}")

        seasons = scraper.get_season_numbers(anime["url"])
        if not seasons:
            continue
        status["total_seasons"] = max((s for s in seasons if s != 0), default=0)

        # Pre-fetch aller Episodenlisten für Gesamtfortschritt
        all_eps_by_season: Dict[int, List] = {}
        for _s in seasons:
            all_eps_by_season[_s] = scraper.get_episodes_for_season(base_url, _s) or []
        status["total_episodes_overall"] = sum(len(v) for v in all_eps_by_season.values())
        status["completed_episodes_overall"] = 0

        missing_german: List[str] = db.get_missing_german_episodes(data_folder, anime["id"])
        new_missing_german: List[str] = []

        for season in seasons:
            if _check_stop():
                all_missing = missing_german + new_missing_german
                if all_missing:
                    db.set_missing_german_episodes(data_folder, anime["id"], all_missing)
                return

            episodes = all_eps_by_season.get(season, [])
            status["total_episodes_in_season"] = len(episodes)
            if not episodes:
                label = "Filme" if season == 0 else f"Staffel {season}"
                log(f"[WARN] Keine Episoden gefunden für {label} – überspringe")
                continue

            for ep in episodes:
                if _check_stop():
                    all_missing = missing_german + new_missing_german
                    if all_missing:
                        db.set_missing_german_episodes(data_folder, anime["id"], all_missing)
                    return

                target_languages, multi_mode = _resolve_target_languages(cfg, anime)

                if multi_mode:
                    # Pro gewünschter Sprache prüfen: fehlt die Datei oder ist sie defekt?
                    broken: List = []
                    missing_languages: List[str] = []
                    for lang in target_languages:
                        lang_file = episode_already_downloaded(
                            cfg, anime["url"], anime.get("folder_name"),
                            season, ep["episode"],
                            title_hint=anime.get("title"), language=lang,
                        )
                        if lang_file is None:
                            missing_languages.append(lang)
                        elif not check_file_integrity(lang_file):
                            broken.append((lang, lang_file))

                    if not missing_languages and not broken:
                        status["progress"]["skipped_episodes"] += 1
                        status["completed_episodes_overall"] += 1
                        continue

                    # Nur die defekten Dateien der jeweiligen Sprache entfernen
                    unlink_failed = False
                    for lang, lang_file in broken:
                        log(f"[CHECK] Defekte Datei [{lang}]: {lang_file.name} – lade erneut herunter")
                        try:
                            lang_file.unlink()
                        except Exception as e:
                            log(f"[WARN] Defekte Datei konnte nicht gelöscht werden: {e}")
                            unlink_failed = True

                    if unlink_failed:
                        status["progress"]["failed_episodes"] += 1
                        status["completed_episodes_overall"] += 1
                        continue
                else:
                    existing = episode_already_downloaded(
                        cfg, anime["url"], anime.get("folder_name"),
                        season, ep["episode"],
                        title_hint=anime.get("title"),
                    )

                    if existing and check_file_integrity(existing):
                        status["progress"]["skipped_episodes"] += 1
                        status["completed_episodes_overall"] += 1
                        continue

                    if existing:
                        log(f"[CHECK] Defekte Datei: {existing.name} – lade erneut herunter")
                        try:
                            existing.unlink()
                        except Exception as e:
                            log(f"[WARN] Defekte Datei konnte nicht gelöscht werden: {e}")
                            status["progress"]["failed_episodes"] += 1
                            status["completed_episodes_overall"] += 1
                            continue

                result = _download_episode(cfg, data_folder, anime, season, ep)
                status["completed_episodes_overall"] += 1
                if result in ("downloaded", "no_german"):
                    status["progress"]["downloaded_episodes"] += 1
                    if result == "no_german":
                        new_missing_german.append(ep["url"])
                elif result == "failed":
                    status["progress"]["failed_episodes"] += 1

        # Missing-German in DB speichern (analog zu Default-Modus)
        all_missing = missing_german + new_missing_german
        if all_missing:
            db.set_missing_german_episodes(data_folder, anime["id"], all_missing)
            db.update_anime(data_folder, anime["id"], deutsch_komplett=0)
        elif not missing_german:
            db.update_anime(data_folder, anime["id"], deutsch_komplett=1)

        status["progress"]["completed_series"] += 1


# ──────────────────────── Start/Control ────────────────────────

MODE_RUNNERS = {
    "default": _run_default,
    "german": _run_german,
    "new": _run_new,
    "german_new": _run_german_new,
    "check": _run_check,
}


def _download_worker(mode: str) -> None:
    """Haupt-Worker-Thread für Downloads."""
    try:
        cfg = load_config()
        data_folder = get_data_folder(cfg)

        start_new_run()
        log(f"[START] Download-Modus: {mode}")

        with _status_lock:
            status["status"] = "running"
            status["mode"] = mode
            status["started_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

        runner = MODE_RUNNERS.get(mode)
        run_result: Dict[str, Any] = {"downloaded": [], "failed": []}
        if runner:
            runner_result = runner(cfg, data_folder)
            if isinstance(runner_result, dict):
                run_result = runner_result
        else:
            log(f"[ERROR] Unbekannter Modus: {mode}")

        with _status_lock:
            stopping = status["status"] == "stopping"
        if stopping:
            log("[STOP] Download gestoppt")
        else:
            log("[DONE] Download abgeschlossen")

        with _status_lock:
            status["status"] = "finished"

        with _last_result_lock:
            _last_run_result["mode"] = mode
            _last_run_result["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            _last_run_result["result"] = deepcopy(run_result)

    except ResourceExhaustedError as e:
        log(f"[ABORT] Lauf abgebrochen: {e}")
        log(
            "[ABORT] Bitte den Container neu starten. Verwaiste Chromium-Prozesse "
            "eines früheren Timeouts belegen vermutlich alle PIDs."
        )
        with _status_lock:
            status["status"] = "finished"

    except Exception as e:
        log(f"[FATAL] Download-Thread-Fehler: {e}")
        import traceback
        log(traceback.format_exc())
        with _status_lock:
            status["status"] = "finished"


def start_download(mode: str = "default") -> bool:
    """
    Startet den Download in einem Hintergrund-Thread.

    Args:
        mode: "default" | "german" | "new" | "check"

    Returns:
        True wenn gestartet, False wenn bereits läuft
    """
    global _download_thread

    if is_running():
        log("[WARN] Download läuft bereits")
        return False

    if mode not in MODE_RUNNERS:
        log(f"[ERROR] Ungültiger Modus: {mode}")
        return False

    _reset_status()
    _download_thread = threading.Thread(target=_download_worker, args=(mode,), daemon=True)
    _download_thread.start()
    return True
