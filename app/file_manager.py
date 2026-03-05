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

BASE_DIR = Path(__file__).resolve().parent.parent


# ──────────────────────── Initialisierungsfunktionen ────────────────────────


def ensure_aniloader_txt(data_folder: str) -> None:
    """
    Erstellt AniLoader.txt im data/ Ordner, falls sie nicht existiert.
    
    Diese Datei wird vom Tampermonkey-Script verwendet, um Links hinzuzufügen,
    die dann beim Start der Anwendung importiert werden.
    """
    aniloader_txt = Path(data_folder) / "AniLoader.txt"
    
    if not aniloader_txt.exists():
        try:
            aniloader_txt.touch()
            log("[INIT] AniLoader.txt erstellt")
        except Exception as e:
            log(f"[INIT-ERROR] Konnte AniLoader.txt nicht erstellen: {e}")


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
        Filme: {base_path}/{folder_name}/Filme/

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
        return series_dir / "Filme"
    else:
        return series_dir / f"Season {season:02d}"


def episode_already_downloaded(
    cfg: dict,
    url: str,
    folder_name: Optional[str],
    season: int,
    episode: int,
    title_hint: Optional[str] = None,
) -> Optional[Path]:
    """
    Prüft ob eine Episode bereits heruntergeladen wurde.

    Suchstrategie:
        1. folder_name aus DB bekannt → suche in exaktem Unterordner
        2. folder_name unbekannt, title_hint vorhanden → suche in Unterordnern
           die den Serientitel enthalten (z.B. "The Rookie (2018)...")
        3. Fallback → suche direkt im Basis-Pfad

    Muster: S01E001 / Film01 / S00E001 (CLI-Original)
    Gibt den Dateipfad zurück falls gefunden, sonst None.
    """
    is_film = season == 0
    base_path = Path(get_download_path(cfg, url, is_film))

    if is_film:
        patterns = [f"*Film{episode:02d}*", f"*S00E{episode:03d}*"]
        subdir = "Filme"
    else:
        patterns = [f"*S{season:02d}E{episode:03d}*"]
        subdir = f"Season {season:02d}"

    # Mögliche Suchpfade bestimmen
    if folder_name:
        search_dirs = [base_path / folder_name / subdir]
    elif title_hint:
        title_lower = title_hint.lower()[:15]
        search_dirs = [
            d / subdir
            for d in base_path.iterdir()
            if d.is_dir() and title_lower in d.name.lower()
        ]
        if not search_dirs:
            search_dirs = [base_path / subdir]
    else:
        search_dirs = [base_path / subdir]

    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for pattern in patterns:
            for ext in (".mkv", ".mp4"):
                for f in search_dir.glob(pattern + ext):
                    if f.is_file() and f.stat().st_size > 1_000_000:
                        return f

    return None


def find_downloaded_file(
    download_path: str,
    season: int,
    episode: int,
    folder_name: Optional[str] = None,
    title_hint: Optional[str] = None,
) -> Optional[Path]:
    """
    Sucht die heruntergeladene Datei nach einem aniworld CLI Download.

    Die aniworld CLI erstellt:
        {download_path}/{Title} ({Year}) [imdbid-{id}]/Season {ss}/{Title} S{ss}E{eee}.mkv
        Für Filme: {Title} S00E{eee}.mkv (wird später zu Film{ff} umbenannt)

    Suchstrategie:
        1. folder_name bekannt → suche nur in diesem Unterordner
        2. title_hint bekannt  → suche in Unterordnern die den Titel enthalten
        3. Fallback            → rglob über alle Unterordner (unsicher bei mehreren Serien)
    """
    base = Path(download_path)
    if not base.exists():
        return None

    if season == 0:
        pattern = f"*S00E{episode:03d}*"  # CLI erstellt S00E001 für Filme
    else:
        pattern = f"*S{season:02d}E{episode:03d}*"

    # Suchbereich einschränken
    if folder_name:
        # Exakter Ordner bekannt (aus DB) → nur dort suchen
        search_roots = [base / folder_name]
    elif title_hint:
        # Titel bekannt → Unterordner filtern die den Titel-Anfang enthalten
        title_lower = title_hint.lower()[:15]
        search_roots = [
            d for d in base.iterdir()
            if d.is_dir() and title_lower in d.name.lower()
        ]
        if not search_roots:
            search_roots = [base]  # Fallback
    else:
        search_roots = [base]

    for search_root in search_roots:
        for ext in (".mkv", ".mp4"):
            for f in search_root.rglob(pattern + ext):
                if f.is_file() and not f.name.endswith(".part"):
                    if f.stat().st_size > 1_000_000:
                        return f

    return None


def detect_folder_name(
    download_path: str,
    season: int,
    episode: int,
    title_hint: Optional[str] = None,
) -> Optional[str]:
    """
    Erkennt den von aniworld CLI erstellten Ordnernamen.

    Sucht nach der heruntergeladenen Datei und extrahiert den
    ersten Ordner relativ zum Download-Pfad.

    Returns:
        z.B. "Title (2020) [imdbid-tt1234567]" oder None
    """
    found = find_downloaded_file(download_path, season, episode, title_hint=title_hint)
    if found:
        try:
            rel = found.relative_to(download_path)
            parts = rel.parts
            if len(parts) >= 2:
                return parts[0]  # Erster Ordner = Serien-Ordner
        except ValueError:
            pass
    return None


def sanitize_filename(name: str) -> str:
    """Entfernt für Dateinamen ungültige Zeichen."""
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name[:100]


def rename_episode_file(
    found_path: Path,
    season: int,
    episode: int,
    title: str,
    language: str,
) -> Optional[Path]:
    """
    Benennt eine heruntergeladene Episode in das Zielformat um.

    Zielformat: S{ss}E{eee} - {episode_title} {lang_suffix}{ext}
    Filme:      Film{ff} - {film_title} {lang_suffix}{ext}
    Beispiel:   S01E001 - Pilotfolge [Sub].mkv
    Film:       Film01 - Your Name [Sub].mkv

    Returns:
        Neuen Dateipfad bei Erfolg, None bei Fehler
    """
    lang_suffix = {
        "German Dub": "",
        "German Sub": "[Sub]",
        "English Dub": "[English Dub]",
        "English Sub": "[English Sub]",
    }.get(language, "")

    if season == 0:
        ep_code = f"Film{episode:02d}"
    else:
        ep_code = f"S{season:02d}E{episode:03d}"

    ext = found_path.suffix   # z.B. ".mkv"
    parent = found_path.parent
    stem = found_path.stem

    safe_title = sanitize_filename(title) if title else ""

    # Für Filme: Prüfen ob wir im falschen Ordner sind (Season 00 statt Filme)
    if season == 0 and parent.name == "Season 00":
        # Wechsel zum Filme-Ordner
        series_dir = parent.parent
        target_parent = series_dir / "Filme"
        target_parent.mkdir(exist_ok=True)
        log(f"[MOVE] Verschiebe Film von Season 00 → Filme Ordner")
    else:
        target_parent = parent

    # Ziel-Dateiname aufbauen
    new_name = ep_code
    if safe_title:
        new_name += f" - {safe_title}"
    if lang_suffix:
        new_name += f" {lang_suffix}"
    new_name += ext

    new_path = target_parent / new_name

    # Bereits im Zielformat und richtigen Ordner?
    if found_path == new_path:
        return found_path

    try:
        shutil.move(str(found_path), str(new_path))
        log(f"[RENAME] {found_path.name} → {new_name}")
        
        # Bei Filmen: Leeren Season 00 Ordner entfernen
        if season == 0 and parent.name == "Season 00":
            try:
                if parent.exists() and not any(parent.iterdir()):  # Ordner leer?
                    parent.rmdir()
                    log(f"[CLEANUP] Leerer Season 00 Ordner entfernt")
            except Exception as e:
                log(f"[WARN] Season 00 Ordner konnte nicht entfernt werden: {e}")
        
        return new_path
    except Exception as e:
        log(f"[WARN] Umbenennen fehlgeschlagen: {e}")
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
        else:
            # Filme im neuen Format: Film01, Film02, etc.
            m = re.search(r"Film(\d{2})", f.name)
            if m:
                films += 1

    return {
        "seasons": len(seasons),
        "episodes": episodes,
        "films": films,
        "total_size_mb": round(total_size / (1024 ** 2), 1),
    }
