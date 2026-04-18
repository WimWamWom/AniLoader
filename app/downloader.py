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
import subprocess
import threading
import time
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional
import random
from . import database as db
from . import scraper
from .config import get_data_folder, get_download_path, load_config
from .file_manager import (
    check_file_integrity,
    detect_folder_name,
    episode_already_downloaded,
    find_downloaded_file,
    get_free_space_gb,
    rename_episode_file,
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
    # auch wenn kein echtes Terminal vorhanden ist (z.B. Docker ohne TTY)
    subprocess_env = os.environ.copy()
    subprocess_env.setdefault("TERM", "xterm")
    cli_url = _normalize_aniworld_cli_url(episode_url)

    if cli_url != episode_url:
        log(f"[CMD] Normalisiere URL für aniworld CLI: {episode_url} -> {cli_url}")

    if is_windows:
        cmd = f'chcp 65001 >nul & aniworld --language "{language}" -a Download -o "{output_path}" {cli_url}'
    else:
        cmd = f"aniworld --language '{language}' -a Download -o '{output_path}' {cli_url}"
    log(f"[CMD] {cmd}")

    for attempt in range(1 + _CDN_403_MAX_RETRIES):
        if attempt > 0:
            log(f"[RETRY] HTTP 403 erkannt – warte {_CDN_403_RETRY_DELAY}s vor Versuch {attempt + 1} …")
            time.sleep(_CDN_403_RETRY_DELAY)

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
                env=subprocess_env,
            )
        except subprocess.TimeoutExpired:
            log(f"[ERROR] Timeout ({timeout}s) für {episode_url}")
            return False
        except Exception as e:
            log(f"[ERROR] Subprocess-Fehler: {e}")
            return False

        # Log Output
        if result.stdout:
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    log(f"[ANIWORLD] {line.strip()}")

        if result.returncode == 0:
            # Kurz warten bis Dateisystem aufholt
            time.sleep(3)
            return True

        # Fehlerausgabe prüfen
        stderr_text = result.stderr or ""
        if result.stderr:
            for line in stderr_text.strip().split("\n"):
                if line.strip():
                    log(f"[ANIWORLD-ERR] {line.strip()}")

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


def _download_episode(
    cfg: dict,
    data_folder: str,
    anime: Dict,
    season: int,
    episode_info: Dict,
    detailed: bool = False,
) -> Any:
    """
    Lädt eine einzelne Episode herunter.

    Returns:
        Standard: "downloaded" | "skipped" | "failed" | "no_german" | "no_language"
        Detailed: {"status": str, "language": Optional[str]}
    """
    def _result(result_status: str, language: Optional[str] = None) -> Any:
        if detailed:
            return {"status": result_status, "language": language}
        return result_status

    episode_num = episode_info["episode"]
    episode_url = episode_info["url"]
    is_film = season == 0
    languages_config = cfg.get("languages", ["German Dub", "German Sub", "English Sub", "English Dub"])
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
        return _result("failed")

    # Bereits heruntergeladen?
    existing = episode_already_downloaded(
        cfg, anime["url"], anime.get("folder_name"), season, episode_num,
        title_hint=anime.get("title"),
    )
    if existing:
        log(f"[SKIP] Bereits vorhanden: S{season:02d}E{episode_num:03d}")
        return _result("skipped")

    # Sprachen IMMER von der Episoden-Seite holen (vor dem Download)
    ep_langs = episode_info.get("languages", [])
    log(f"[LANG] S{season:02d}E{episode_num:03d} – Sprachen aus Staffel-Seite: {ep_langs}")
    
    if not ep_langs:
        # Von Staffelseite nicht vorhanden → von Episoden-Seite scrapen
        log(f"[LANG] Scrape Sprachen von Episode-Seite …")
        ep_langs = scraper.get_episode_languages(episode_url)
        log(f"[LANG] Von Episode-Seite gescraped: {ep_langs}")

    # AniWorld: Prüfe ob Episode überhaupt Streams hat (kein Ankündigungs-Placeholder)
    if scraper.is_aniworld(episode_url) and not ep_langs:
        if not scraper.is_episode_available(episode_url):
            log(f"[SKIP] S{season:02d}E{episode_num:03d} – keine Streams verfügbar (Ankündigung)")
            return _result("no_language")

    # S.to: Keine Sprache gefunden → Episode nicht verfügbar, überspringen
    if scraper.is_sto(episode_url) and not ep_langs:
        log(f"[SKIP] S{season:02d}E{episode_num:03d} – keine Sprache → nicht verfügbar")
        return _result("no_language")

    # Sprachen zur Kaskade vorbereiten
    cascading_languages = []
    if ep_langs:
        # Nur verfügbare Sprachen verwenden
        for lang in languages_config:
            if lang in ep_langs:
                cascading_languages.append(lang)
    else:
        # Sprachen unbekannt → komplette Kaskade
        cascading_languages = languages_config[:]
        log(f"[LANG] Sprachen unbekannt – verwende komplette Kaskade: {cascading_languages}")

    # s.to unterstützt nur German Dub und English Dub
    if scraper.is_sto(episode_url):
        _sto_supported = {"German Dub", "English Dub"}
        _removed = [l for l in cascading_languages if l not in _sto_supported]
        cascading_languages = [l for l in cascading_languages if l in _sto_supported]
        if _removed:
            log(f"[LANG] s.to: Nicht unterstützte Sprachen aus Kaskade entfernt: {_removed}")

    # Download: Sprachen-Kaskade (nur mit verfügbaren Sprachen)
    downloaded = False
    used_language = None
    found = None

    for lang in cascading_languages:
        log(f"[DL] S{season:02d}E{episode_num:03d} [{lang}]")
        if _run_aniworld_download(episode_url, lang, output_path, timeout):
            found = find_downloaded_file(
                output_path, season, episode_num,
                folder_name=anime.get("folder_name"),
                title_hint=anime.get("title"),
            )
            if found:
                downloaded = True
                used_language = lang
                break

    if not downloaded:
        log(f"[FAIL] S{season:02d}E{episode_num:03d} – kein Download möglich")
        return _result("failed")

    # Folder-Name erkennen und speichern
    if not anime.get("folder_name"):
        folder = detect_folder_name(output_path, season, episode_num, title_hint=anime.get("title"))
        if folder:
            db.update_anime(data_folder, anime["id"], folder_name=folder)
            anime["folder_name"] = folder
            log(f"[DB] Ordnername gespeichert: {folder}")

    # Episode umbenennen (Titel + Sprach-Suffix einbauen)
    if found:
        ep_title = episode_info.get("title_de") or episode_info.get("title_en") or ""
        rename_episode_file(found, season, episode_num, ep_title, used_language or "")

    log(f"[OK] S{season:02d}E{episode_num:03d} [{used_language}]")

    # Fehlende deutsche Episoden tracken
    if used_language and used_language != "German Dub":
        return _result("no_german", used_language)

    return _result("downloaded", used_language)


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
        start_msg = f"[SERIE] {anime['title']} – {base_url}"
        log(f"{'='*len(start_msg)}")
        log(start_msg)
        log(f"{'='*len(start_msg)}")

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
            return

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

        still_missing: List[str] = []
        status["total_episodes_overall"] = len(missing)
        status["completed_episodes_overall"] = 0

        for episode_url in missing:
            if _check_stop():
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
                    })
                status["completed_episodes_overall"] += 1
                continue

            season, episode_num = parsed
            output_path = get_download_path(german_cfg, anime["url"], season == 0)

            # Altlasten-Reparatur: rohe SxxExxx/S00Exxx-Datei aus früheren Läufen
            # ohne erneuten Download in das Zielformat überführen.
            found_existing = find_downloaded_file(
                output_path,
                season,
                episode_num,
                folder_name=anime.get("folder_name"),
                title_hint=anime.get("title"),
            )
            if found_existing:
                repaired = rename_episode_file(found_existing, season, episode_num, "", "German Dub")
                if repaired:
                    log(f"[OK] Bestehende Datei repariert: {episode_url}")
                    status["progress"]["downloaded_episodes"] += 1
                    run_result["downloaded"].append({
                        "title": anime["title"],
                        "url": episode_url,
                        "season": season,
                        "episode": episode_num,
                        "language": "German Dub",
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
                    status["completed_episodes_overall"] += 1
                    continue

            episode_info = {
                "episode": episode_num,
                "url": episode_url,
                # Titel optional aus Seite holen; Pipeline nutzt fallbacks falls leer.
                "title_de": "",
                "title_en": "",
                "languages": ["German Dub"],
            }

            # Für robustes Renaming/Moving den Standardpfad nutzen.
            detailed_result = _download_episode(german_cfg, data_folder, anime, season, episode_info, detailed=True)
            result = detailed_result.get("status")
            used_language = detailed_result.get("language") or "German Dub"

            if result == "downloaded":
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
            elif result == "failed" or result == "no_language":
                log(f"[SKIP] German Dub noch nicht verfügbar: {episode_url}")
                still_missing.append(episode_url)
                status["progress"]["skipped_episodes"] += 1
                run_result["failed"].append({
                    "title": anime["title"],
                    "url": episode_url,
                    "season": season,
                    "episode": episode_num,
                    "language": "German Dub",
                })
            else:
                # skipped/no_german: nicht als erfolgreich aus missing entfernen,
                # damit potentielle Altlasten erneut geprüft werden können.
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
            return

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

        for season in seasons:
            if _check_stop():
                return run_result

            episodes = all_eps_by_season.get(season, [])
            status["total_episodes_in_season"] = len(episodes)
            if not episodes:
                label = "Filme" if season == 0 else f"Staffel {season}"
                log(f"[WARN] Keine Episoden gefunden für {label} – überspringe")
                continue

            for ep in episodes:
                if _check_stop():
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

                    if season == 0:
                        db.update_anime(data_folder, anime["id"], last_film=ep["episode"])
                    else:
                        db.update_anime(
                            data_folder, anime["id"],
                            last_season=season, last_episode=ep["episode"],
                        )
                elif result == "skipped":
                    status["progress"]["skipped_episodes"] += 1
                elif result == "failed":
                    had_failures = True
                    status["progress"]["failed_episodes"] += 1
                    run_result["failed"].append({
                        "title": anime["title"],
                        "url": ep["url"],
                        "season": season,
                        "episode": ep["episode"],
                        "language": used_language,
                    })
                elif result == "no_language":
                    had_no_language = True
                    status["progress"]["skipped_episodes"] += 1

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
        log(f"\n[CHECK] {anime['title']}")

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

        for season in seasons:
            if _check_stop():
                return

            episodes = all_eps_by_season.get(season, [])
            status["total_episodes_in_season"] = len(episodes)
            if not episodes:
                label = "Filme" if season == 0 else f"Staffel {season}"
                log(f"[WARN] Keine Episoden gefunden für {label} – überspringe")
                continue

            for ep in episodes:
                if _check_stop():
                    return

                existing = episode_already_downloaded(
                    cfg, anime["url"], anime.get("folder_name"),
                    season, ep["episode"],
                )

                if existing and check_file_integrity(existing):
                    status["progress"]["skipped_episodes"] += 1
                    status["completed_episodes_overall"] += 1
                    continue

                if existing:
                    log(f"[CHECK] Defekte Datei: {existing.name} – lade erneut herunter")

                result = _download_episode(cfg, data_folder, anime, season, ep)
                status["completed_episodes_overall"] += 1
                if result in ("downloaded", "no_german"):
                    status["progress"]["downloaded_episodes"] += 1
                elif result == "failed":
                    status["progress"]["failed_episodes"] += 1

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
