"""
AniLoader – Dateiverwaltung.

Verwaltet Dateipfade, prüft ob Episoden bereits heruntergeladen sind,
und findet heruntergeladene Dateien nach dem Download.
"""

import os
import re
import shutil
from pathlib import Path
from typing import Optional

from .config import get_download_path
from .logger import log


# ──────────────────────── Pfad-Hilfsfunktionen ────────────────────────


def get_storage_path(
    cfg: dict,
    url: str,
    folder_name: Optional[str] = None,
    season: int = 1,
    is_film: bool = False,
) -> Path:
    """
    Bestimmt den vollständigen Speicherpfad für eine Episode.

    Jellyfin-Struktur:
        {base_path}/{folder_name}/Season {ss}/
        Filme: {base_path}/{folder_name}/Season 00/

    Args:
        cfg: Geladene Konfiguration
        url: Serien-URL (bestimmt anime vs serie)
        folder_name: z.B. "Title (2020) [imdbid-tt1234567]"
        season: Staffelnummer (0 für Filme)
        is_film: Ob es ein Film ist
    """
    base_path = get_download_path(cfg, url, is_film)

    if folder_name:
        series_dir = Path(base_path) / folder_name
    else:
        series_dir = Path(base_path)

    if is_film or season == 0:
        return series_dir / "Season 00"
    else:
        return series_dir / f"Season {season:02d}"


def episode_already_downloaded(
    cfg: dict,
    url: str,
    folder_name: Optional[str],
    season: int,
    episode: int,
) -> Optional[Path]:
    """
    Prüft ob eine Episode bereits heruntergeladen wurde.

    Sucht nach Dateien mit dem Muster S{ss}E{eee} im erwarteten Verzeichnis.
    Gibt den Dateipfad zurück, falls gefunden, sonst None.
    """
    is_film = season == 0
    storage_dir = get_storage_path(cfg, url, folder_name, season, is_film)

    if not storage_dir.exists():
        return None

    # Suchmuster: *S01E001* oder für Filme im Season 00 Ordner
    if is_film:
        pattern = f"*S00E{episode:03d}*"
    else:
        pattern = f"*S{season:02d}E{episode:03d}*"

    for ext in (".mkv", ".mp4"):
        for f in storage_dir.glob(pattern + ext):
            if f.is_file() and f.stat().st_size > 1_000_000:  # > 1MB
                return f

    return None


def find_downloaded_file(
    download_path: str,
    season: int,
    episode: int,
    timeout_seconds: int = 30,
) -> Optional[Path]:
    """
    Sucht die heruntergeladene Datei nach einem aniworld CLI Download.

    Die aniworld CLI erstellt:
        {download_path}/{Title} ({Year}) [imdbid-{id}]/Season {ss}/{Title} S{ss}E{eee}.mkv

    Sucht rekursiv nach dem Dateinamen-Pattern.
    """
    base = Path(download_path)
    if not base.exists():
        return None

    if season == 0:
        pattern = f"*S00E{episode:03d}*"
    else:
        pattern = f"*S{season:02d}E{episode:03d}*"

    for ext in (".mkv", ".mp4"):
        for f in base.rglob(pattern + ext):
            if f.is_file() and not f.name.endswith(".part"):
                # Prüfe Dateigröße (mind. 1MB)
                if f.stat().st_size > 1_000_000:
                    return f

    return None


def detect_folder_name(download_path: str, season: int, episode: int) -> Optional[str]:
    """
    Erkennt den von aniworld CLI erstellten Ordnernamen.

    Sucht nach der heruntergeladenen Datei und extrahiert den
    ersten Ordner relativ zum Download-Pfad.

    Returns:
        z.B. "Title (2020) [imdbid-tt1234567]" oder None
    """
    found = find_downloaded_file(download_path, season, episode)
    if found:
        try:
            rel = found.relative_to(download_path)
            parts = rel.parts
            if len(parts) >= 2:
                return parts[0]  # Erster Ordner = Serien-Ordner
        except ValueError:
            pass
    return None


def check_file_integrity(filepath: Path, min_size_mb: float = 1.0) -> bool:
    """
    Prüft die Integrität einer heruntergeladenen Datei.

    Checks:
        - Datei existiert
        - Dateigröße > min_size_mb
        - Keine .part/.temp Endung
    """
    if not filepath.exists():
        return False
    if filepath.suffix in (".part", ".temp", ".tmp"):
        return False
    if filepath.stat().st_size < min_size_mb * 1_000_000:
        return False
    return True


def get_free_space_gb(path: str) -> float:
    """Gibt den freien Speicherplatz in GB zurück."""
    try:
        usage = shutil.disk_usage(path)
        return usage.free / (1024 ** 3)
    except Exception:
        return 0.0


def count_episodes_on_disk(
    cfg: dict,
    url: str,
    folder_name: Optional[str],
) -> dict:
    """
    Zählt die heruntergeladenen Episoden/Staffeln/Filme auf der Festplatte.

    Returns:
        {"seasons": 2, "episodes": 24, "films": 1, "total_size_mb": 1234.5}
    """
    base_path = get_download_path(cfg, url)

    if not folder_name:
        return {"seasons": 0, "episodes": 0, "films": 0, "total_size_mb": 0}

    series_dir = Path(base_path) / folder_name
    if not series_dir.exists():
        return {"seasons": 0, "episodes": 0, "films": 0, "total_size_mb": 0}

    seasons = set()
    episodes = 0
    films = 0
    total_size = 0

    for f in series_dir.rglob("*"):
        if not f.is_file():
            continue
        if f.suffix not in (".mkv", ".mp4"):
            continue
        if f.stat().st_size < 1_000_000:
            continue

        total_size += f.stat().st_size

        # Staffel/Episode aus Dateinamen extrahieren
        m = re.search(r"S(\d{2})E(\d{3})", f.name)
        if m:
            s_num = int(m.group(1))
            if s_num == 0:
                films += 1
            else:
                seasons.add(s_num)
                episodes += 1

    return {
        "seasons": len(seasons),
        "episodes": episodes,
        "films": films,
        "total_size_mb": round(total_size / (1024 ** 2), 1),
    }
