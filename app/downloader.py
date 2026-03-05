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
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

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
    "started_at": None,
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
_download_thread: Optional[threading.Thread] = None


def get_status() -> Dict:
    """Gibt den aktuellen Download-Status zurück."""
    return status.copy()


def is_running() -> bool:
    return status["status"] in ("running", "stopping")


def request_stop() -> bool:
    """Fordert einen graceful Stop an (nach aktuellem Episode-Download)."""
    if status["status"] == "running":
        status["status"] = "stopping"
        log("[DOWNLOAD] Stop angefordert – wird nach aktuellem Download gestoppt")
        return True
    return False


def _check_stop() -> bool:
    """Prüft ob ein Stop angefordert wurde."""
    return status["status"] == "stopping"


def _reset_status():
    status["status"] = "idle"
    status["mode"] = None
    status["current_title"] = None
    status["current_id"] = None
    status["current_url"] = None
    status["current_season"] = None
    status["current_episode"] = None
    status["current_is_film"] = False
    status["started_at"] = None
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

    if is_windows:
        cmd = f'chcp 65001 >nul & aniworld --language "{language}" -a Download -o "{output_path}" {episode_url}'
        log(f"[CMD] {cmd}")
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.TimeoutExpired:
            log(f"[ERROR] Timeout ({timeout}s) für {episode_url}")
            return False
        except Exception as e:
            log(f"[ERROR] Subprocess-Fehler: {e}")
            return False
    else:
        cmd_list = [
            "aniworld",
            "--language", language,
            "-a", "Download",
            "-o", output_path,
            episode_url,
        ]
        log(f"[CMD] {' '.join(cmd_list)}")
        try:
            result = subprocess.run(
                cmd_list,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
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

    if result.returncode != 0:
        if result.stderr:
            for line in result.stderr.strip().split("\n"):
                if line.strip():
                    log(f"[ANIWORLD-ERR] {line.strip()}")
        return False

    # Kurz warten bis Dateisystem aufholt
    time.sleep(3)
    return True


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
) -> str:
    """
    Lädt eine einzelne Episode herunter.

    Returns:
        "downloaded" | "skipped" | "failed" | "no_german"
    """
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

    # Speicherplatz prüfen
    free_gb = get_free_space_gb(output_path)
    if free_gb < min_free:
        log(f"[WARN] Nur {free_gb:.1f} GB frei (Minimum: {min_free} GB) – überspringe")
        return "failed"

    # Bereits heruntergeladen?
    existing = episode_already_downloaded(
        cfg, anime["url"], anime.get("folder_name"), season, episode_num
    )
    if existing:
        log(f"[SKIP] Bereits vorhanden: S{season:02d}E{episode_num:03d}")
        return "skipped"

    # Sprachen IMMER von der Episoden-Seite holen (vor dem Download)
    ep_langs = episode_info.get("languages", [])
    log(f"[LANG] S{season:02d}E{episode_num:03d} – Sprachen aus Staffel-Seite: {ep_langs}")
    
    if not ep_langs:
        # Von Staffelseite nicht vorhanden → von Episoden-Seite scrapen
        log(f"[LANG] Scrape Sprachen von Episode-Seite …")
        ep_langs = scraper.get_episode_languages(episode_url)
        log(f"[LANG] Von Episode-Seite gescraped: {ep_langs}")

    # Sprachen zur Kaskade vorbereiten
    cascading_languages = []
    if ep_langs:
        # Nur verfügbare Sprachen verwenden
        for lang in languages_config:
            if lang in ep_langs:
                cascading_languages.append(lang)
        log(f"[LANG] Finale Kaskade: {cascading_languages}")
    else:
        # Sprachen unbekannt → komplette Kaskade
        cascading_languages = languages_config[:]
        log(f"[LANG] Sprachen unbekannt – verwende komplette Kaskade: {cascading_languages}")

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
        return "failed"

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
        return "no_german"

    return "downloaded"


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
        status["progress"]["current_series_index"] = idx + 1

        base_url = scraper.get_base_url(anime["url"])
        log(f"\n{'='*60}")
        log(f"[SERIE] {anime['title']} ({base_url})")
        log(f"{'='*60}")

        seasons = scraper.get_season_numbers(anime["url"])
        if not seasons:
            log(f"[WARN] Keine Staffeln gefunden für {anime['title']}")
            continue

        missing_german: List[str] = db.get_missing_german_episodes(data_folder, anime["id"])
        new_missing_german: List[str] = []
        any_downloaded = False

        for season in seasons:
            if _check_stop():
                return

            # Überspringe bereits heruntergeladene Staffeln
            if season != 0 and season < anime.get("last_season", 0):
                continue

            episodes = scraper.get_episodes_for_season(base_url, season)
            if not episodes:
                continue

            for ep in episodes:
                if _check_stop():
                    return

                # Überspringe bereits heruntergeladene Episoden
                if season != 0:
                    if season == anime.get("last_season", 0) and ep["episode"] <= anime.get("last_episode", 0):
                        continue
                elif ep["episode"] <= anime.get("last_film", 0):
                    continue

                result = _download_episode(cfg, data_folder, anime, season, ep)

                if result == "downloaded":
                    any_downloaded = True
                    status["progress"]["downloaded_episodes"] += 1
                elif result == "skipped":
                    status["progress"]["skipped_episodes"] += 1
                elif result == "failed":
                    status["progress"]["failed_episodes"] += 1
                elif result == "no_german":
                    any_downloaded = True
                    new_missing_german.append(ep["url"])
                    status["progress"]["downloaded_episodes"] += 1

                # Progress in DB speichern
                if season == 0:
                    db.update_anime(data_folder, anime["id"], last_film=ep["episode"])
                else:
                    db.update_anime(
                        data_folder, anime["id"],
                        last_season=season, last_episode=ep["episode"],
                    )

        # Status Updates
        all_missing = missing_german + new_missing_german
        if all_missing:
            db.set_missing_german_episodes(data_folder, anime["id"], all_missing)
            db.update_anime(data_folder, anime["id"], deutsch_komplett=0)
        elif not missing_german:
            db.update_anime(data_folder, anime["id"], deutsch_komplett=1)

        if any_downloaded:
            db.update_anime(data_folder, anime["id"], complete=1)
            log(f"[DONE] {anime['title']} als komplett markiert")

        status["progress"]["completed_series"] += 1


def _run_german(cfg: dict, data_folder: str) -> None:
    """
    German Mode: Prüft fehlende deutsche Episoden und lädt diese nach.
    """
    log("[MODE] German – Deutsche Episoden nachladen")
    anime_list = db.get_active_anime(data_folder)
    status["progress"]["total_series"] = len(anime_list)

    languages_config = cfg.get("languages", [])

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
        status["progress"]["current_series_index"] = idx + 1

        log(f"\n[GERMAN] {anime['title']} – {len(missing)} fehlende deutsche Episoden")

        still_missing: List[str] = []
        output_path = get_download_path(cfg, anime["url"])
        timeout = cfg.get("download", {}).get("timeout_seconds", 900)

        for episode_url in missing:
            if _check_stop():
                return

            log(f"[DL] Versuche German Dub für {episode_url}")
            if _run_aniworld_download(episode_url, "German Dub", output_path, timeout):
                log(f"[OK] German Dub erfolgreich: {episode_url}")
                status["progress"]["downloaded_episodes"] += 1
            else:
                log(f"[SKIP] German Dub noch nicht verfügbar: {episode_url}")
                still_missing.append(episode_url)
                status["progress"]["skipped_episodes"] += 1

        db.set_missing_german_episodes(data_folder, anime["id"], still_missing)
        if not still_missing:
            db.update_anime(data_folder, anime["id"], deutsch_komplett=1)
            log(f"[DONE] {anime['title']} – alle deutschen Episoden komplett")

        status["progress"]["completed_series"] += 1


def _run_new(cfg: dict, data_folder: str) -> None:
    """
    New Mode: Prüft alle Serien auf neue Episoden seit dem letzten Download.
    """
    log("[MODE] New – Neue Episoden prüfen")
    anime_list = db.get_active_anime(data_folder)
    status["progress"]["total_series"] = len(anime_list)

    for idx, anime in enumerate(anime_list):
        if _check_stop():
            return

        status["current_title"] = anime["title"]
        status["current_id"] = anime["id"]
        status["current_url"] = anime["url"]
        status["progress"]["current_series_index"] = idx + 1

        base_url = scraper.get_base_url(anime["url"])
        last_season = anime.get("last_season", 0)
        last_episode = anime.get("last_episode", 0)
        last_film = anime.get("last_film", 0)

        seasons = scraper.get_season_numbers(anime["url"])
        if not seasons:
            continue

        has_new = False

        for season in seasons:
            if _check_stop():
                return

            episodes = scraper.get_episodes_for_season(base_url, season)
            if not episodes:
                continue

            for ep in episodes:
                if _check_stop():
                    return

                # Nur neue Episoden (nach dem letzten bekannten Stand)
                if season == 0:
                    if ep["episode"] <= last_film:
                        continue
                elif season < last_season:
                    continue
                elif season == last_season and ep["episode"] <= last_episode:
                    continue

                result = _download_episode(cfg, data_folder, anime, season, ep)
                if result in ("downloaded", "no_german"):
                    has_new = True
                    status["progress"]["downloaded_episodes"] += 1

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
                    status["progress"]["failed_episodes"] += 1

        if has_new:
            log(f"[NEW] Neue Episoden heruntergeladen für {anime['title']}")
        else:
            log(f"[NEW] Keine neuen Episoden für {anime['title']}")

        status["progress"]["completed_series"] += 1


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
        status["progress"]["current_series_index"] = idx + 1

        base_url = scraper.get_base_url(anime["url"])
        log(f"\n[CHECK] {anime['title']}")

        seasons = scraper.get_season_numbers(anime["url"])
        if not seasons:
            continue

        for season in seasons:
            if _check_stop():
                return

            episodes = scraper.get_episodes_for_season(base_url, season)
            if not episodes:
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
                    continue

                if existing:
                    log(f"[CHECK] Defekte Datei: {existing.name} – lade erneut herunter")

                result = _download_episode(cfg, data_folder, anime, season, ep)
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
    "check": _run_check,
}


def _download_worker(mode: str) -> None:
    """Haupt-Worker-Thread für Downloads."""
    try:
        cfg = load_config()
        data_folder = get_data_folder(cfg)

        start_new_run()
        log(f"[START] Download-Modus: {mode}")

        status["status"] = "running"
        status["mode"] = mode
        status["started_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

        runner = MODE_RUNNERS.get(mode)
        if runner:
            runner(cfg, data_folder)
        else:
            log(f"[ERROR] Unbekannter Modus: {mode}")

        if status["status"] == "stopping":
            log("[STOP] Download gestoppt")
        else:
            log("[DONE] Download abgeschlossen")

        status["status"] = "finished"

    except Exception as e:
        log(f"[FATAL] Download-Thread-Fehler: {e}")
        import traceback
        log(traceback.format_exc())
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
