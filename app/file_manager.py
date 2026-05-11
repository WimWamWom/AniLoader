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


def _set_hidden_on_windows(path: Path) -> None:
    """Markiert Verzeichnisse unter Windows als versteckt (Best-Effort)."""
    if os.name != "nt":
        return

    try:
        import ctypes

        attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
        if attrs == -1:
            return

        hidden_flag = 0x02
        if attrs & hidden_flag:
            return

        ctypes.windll.kernel32.SetFileAttributesW(str(path), attrs | hidden_flag)
    except Exception as e:
        log(f"[WARN] Konnte Windows-Hidden-Attribut nicht setzen: {e}")


def _extract_imdb_id(folder_name: Optional[str]) -> Optional[str]:
    """Extrahiert tt1234567 aus einem Ordnernamen wie [...][imdbid-tt1234567]."""
    text = str(folder_name or "")
    m = re.search(r"\[imdbid-(tt\d+)\]", text, re.IGNORECASE)
    return m.group(1).lower() if m else None


def _resolve_series_dirs(
    base_path: Path,
    folder_name: Optional[str] = None,
    title_hint: Optional[str] = None,
) -> list[Path]:
    """Bestimmt sinnvolle Serien-Ordnerkandidaten (exakt, imdbid, Titel-Fallback)."""
    if not base_path.exists():
        return []

    candidates: list[Path] = []
    seen: set[str] = set()

    def _add(path: Path) -> None:
        key = str(path).lower()
        if key in seen:
            return
        seen.add(key)
        candidates.append(path)

    if folder_name:
        _add(base_path / folder_name)

        # Fallback bei geänderter Jahresangabe im Namen:
        # Suche alle Ordner mit gleicher imdbid.
        imdb_id = _extract_imdb_id(folder_name)
        if imdb_id:
            marker = f"[imdbid-{imdb_id}]"
            for d in base_path.iterdir():
                if d.is_dir() and marker in d.name.lower():
                    _add(d)

    if title_hint:
        title_sanitized = re.sub(r'[<>:"/\\|?*]', '', title_hint)
        title_lower = title_sanitized.lower()[:15]
        for d in base_path.iterdir():
            if d.is_dir() and title_lower in d.name.lower():
                _add(d)

    if not candidates:
        _add(base_path)

    return candidates


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

    Lokal-Modus (film_naming_mode='local'):
        {base_path}/{folder_name}/Filme/
    Jellyfin-Modus (film_naming_mode='jellyfin'):
        {base_path}/{folder_name}/Season 00/
    Staffeln:
        {base_path}/{folder_name}/Season {ss}/
    """
    from .config import get_film_naming_mode
    base_path = get_download_path(cfg, url, is_film)

    if folder_name:
        series_dir = Path(base_path) / folder_name
    else:
        series_dir = Path(base_path)

    if is_film or season == 0:
        film_naming_mode = get_film_naming_mode(cfg)
        if film_naming_mode == "jellyfin":
            return series_dir / "Season 00"
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

    Muster: S01E001 / Film01 / S00E001 (CLI-Original) / S00E01 (Jellyfin-Final)
    Gibt den Dateipfad zurück falls gefunden, sonst None.
    """
    is_film = season == 0
    base_path = Path(get_download_path(cfg, url, is_film))

    if is_film:
        # Alle möglichen Film-Namensmuster (Lokal + Jellyfin + CLI-Rohformat)
        patterns = [
            f"*Film{episode:02d}*",        # Lokal: Film01
            f"*S00E{episode:03d}*",        # Jellyfin / CLI: S00E001 (3-stellig)
        ]
        subdirs = ["Filme", "Season 00"]
    else:
        patterns = [f"*S{season:02d}E{episode:03d}*"]
        subdirs = [f"Season {season:02d}"]

    # Mögliche Suchpfade bestimmen (inkl. imdbid-Fallback bei geändertem Jahr im Ordnernamen)
    series_dirs = _resolve_series_dirs(base_path, folder_name=folder_name, title_hint=title_hint)
    search_dirs = [d / sub for d in series_dirs for sub in subdirs]

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

    # Suchbereich einschränken (inkl. imdbid-Fallback bei geändertem Jahr im Ordnernamen)
    search_roots = _resolve_series_dirs(base, folder_name=folder_name, title_hint=title_hint)

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
    film_naming_mode: str = "local",
) -> Optional[Path]:
    """
    Benennt eine heruntergeladene Episode in das Zielformat um.

    Lokal-Modus:   Film{ff} - {film_title} {lang_suffix}{ext}  (Ordner: Filme/)
    Jellyfin-Modus: S00E{ff} - {film_title} {lang_suffix}{ext}  (Ordner: Season 00/)
    Staffeln:       S{ss}E{eee} - {episode_title} {lang_suffix}{ext}

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
        if film_naming_mode == "jellyfin":
            ep_code = f"S00E{episode:03d}"
        else:
            ep_code = f"Film{episode:02d}"
    else:
        ep_code = f"S{season:02d}E{episode:03d}"

    ext = found_path.suffix
    parent = found_path.parent

    safe_title = sanitize_filename(title) if title else ""

    # Für Filme: Sicherstellen, dass wir im richtigen Ordner sind
    if season == 0:
        target_folder_name = "Season 00" if film_naming_mode == "jellyfin" else "Filme"
        wrong_folder_names = {"Season 00", "Filme"} - {target_folder_name}
        if parent.name in wrong_folder_names:
            series_dir = parent.parent
            target_parent = series_dir / target_folder_name
            target_parent.mkdir(exist_ok=True)
            log(f"[MOVE] Verschiebe Film von '{parent.name}' → '{target_folder_name}'")
        else:
            target_parent = parent
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

    # Bereits im Zielformat und richtigem Ordner?
    if found_path == new_path:
        return found_path

    try:
        shutil.move(str(found_path), str(new_path))
        log(f"[RENAME] {found_path.name} → {new_name}")

        # Leeren Quell-Film-Ordner entfernen
        if season == 0 and parent != target_parent:
            try:
                if parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()
                    log(f"[CLEANUP] Leerer Ordner '{parent.name}' entfernt")
            except Exception as e:
                log(f"[WARN] Ordner konnte nicht entfernt werden: {e}")

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
        # Matcht: S01E001 (Staffeln, 3-stellig), S00E001 (CLI-Film), S00E01 (Jellyfin-Film, 2-stellig)
        m = re.search(r"S(\d{2})E(\d{2,3})", f.name)
        if m:
            s_num = int(m.group(1))
            if s_num == 0:
                films += 1
            else:
                seasons.add(s_num)
                episodes += 1
        else:
            # Lokal-Format: Film01, Film02 …
            m = re.search(r"Film(\d{2})", f.name)
            if m:
                films += 1

    return {
        "seasons": len(seasons),
        "episodes": episodes,
        "films": films,
        "total_size_mb": round(total_size / (1024 ** 2), 1),
    }


# ──────────────────────── TMP-Download-Hilfsfunktionen ────────────────────────


def get_tmp_path(base_download_path) -> Path:
    """
    Gibt das TMP-Verzeichnis für Staged-Downloads zurück.

    Downloads landen zuerst hier, bevor sie in den finalen Pfad verschoben werden.
    Das verhindert, dass die Dateisuche von dynamischen Serienordnernamen abhängt.

    Returns:
        <base_download_path>/.tmp/
    """
    return Path(base_download_path) / ".tmp"


def clear_tmp(tmp_path: Path) -> None:
    """
    Leert das TMP-Verzeichnis vor einem neuen Download.

    Löscht alle Inhalte (Dateien und Unterordner), erstellt den Ordner neu.
    Fehler werden geloggt aber nicht weitergegeben, damit der Download fortgesetzt
    werden kann.
    """
    if tmp_path.exists():
        for item in tmp_path.iterdir():
            try:
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            except Exception as e:
                log(f"[WARN] TMP-Cleanup fehlgeschlagen für {item.name}: {e}")
    try:
        tmp_path.mkdir(parents=True, exist_ok=True)
        _set_hidden_on_windows(tmp_path)
    except Exception as e:
        log(f"[WARN] TMP-Verzeichnis konnte nicht erstellt werden: {e}")


def move_tmp_to_final(
    tmp_file: Path,
    target_dir: Path,
    season: int,
    episode: int,
    title: str,
    language: str,
    film_naming_mode: str = "local",
) -> Optional[Path]:
    """
    Verschiebt eine Datei aus dem TMP-Verzeichnis in den finalen Zielordner
    und benennt sie dabei in das Zielformat um.

    Lokal-Modus:    Film{ff} - {film_title} {lang_suffix}{ext}
    Jellyfin-Modus: S00E{ff} - {film_title} {lang_suffix}{ext}
    Staffeln:       S{ss}E{eee} - {episode_title} {lang_suffix}{ext}

    Args:
        tmp_file:          Quelldatei im TMP-Verzeichnis
        target_dir:        Finaler Zielordner (wird angelegt falls nicht vorhanden)
        season:            Staffelnummer (0 = Film)
        episode:           Episoden-/Filmnummer
        title:             Episodentitel (kann leer sein)
        language:          Sprache für Suffix-Bestimmung
        film_naming_mode:  'local' oder 'jellyfin'

    Returns:
        Neuer Dateipfad bei Erfolg, None bei Fehler
    """
    lang_suffix = {
        "German Dub": "",
        "German Sub": "[Sub]",
        "English Dub": "[English Dub]",
        "English Sub": "[English Sub]",
    }.get(language, "")

    if season == 0:
        if film_naming_mode == "jellyfin":
            ep_code = f"S00E{episode:03d}"
        else:
            ep_code = f"Film{episode:02d}"
    else:
        ep_code = f"S{season:02d}E{episode:03d}"

    ext = tmp_file.suffix
    safe_title = sanitize_filename(title) if title else ""

    new_name = ep_code
    if safe_title:
        new_name += f" - {safe_title}"
    if lang_suffix:
        new_name += f" {lang_suffix}"
    new_name += ext

    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        log(f"[ERROR] Zielordner konnte nicht erstellt werden ({target_dir}): {e}")
        return None

    target_path = target_dir / new_name

    # Kollision: Datei existiert bereits im Ziel
    if target_path.exists():
        log(f"[WARN] Zieldatei existiert bereits, überspringe Verschieben: {new_name}")
        return target_path

    try:
        shutil.move(str(tmp_file), str(target_path))
        log(f"[MOVE] TMP → Final: {new_name}")
        return target_path
    except Exception as e:
        log(f"[ERROR] Verschieben aus TMP fehlgeschlagen: {e}")
        return None


# ──────────────────────── Film-Benennungsmigration ────────────────────────

# Regex-Muster für Film-Dateinamen beider Modi
# Lokal:    Film01 - Titel.mkv   (2-stellig)
# Jellyfin: S00E01 - Titel.mkv   (2-stellig)
# CLI-Raw:  S00E001 - Titel.mkv  (3-stellig, tritt nur in TMP auf, aber zur Sicherheit abgedeckt)
_RE_FILM_LOCAL = re.compile(r"^Film(\d{2})(\s*-.+)?(\.[^.]+)$", re.IGNORECASE)
_RE_FILM_JELLYFIN = re.compile(r"^S00E(\d{2,3})(\s*-.+)?(\.[^.]+)$", re.IGNORECASE)


def _collect_film_roots(cfg: dict) -> list[Path]:
    """
    Sammelt alle Ordner, in denen Filme liegen können.

    Nutzt get_download_path() mit is_film=True/False für alle registrierten
    aniworld.to- und s.to-artigen URLs, um exakt dieselben Pfade zu bestimmen
    wie der Downloader selbst.  Da URLs nicht bekannt sind, werden die
    konfigurierten Pfade direkt aus dem Storage-Block gelesen — analog zu
    get_download_path, aber ohne URL-Abhängigkeit.

    Gibt deduplizierte, existierende Pfade zurück.
    """
    storage = cfg.get("storage", {})
    paths: list[Path] = []
    seen: set[str] = set()

    def _add(p: str) -> None:
        if not p:
            return
        resolved = str(Path(p).resolve())
        if resolved not in seen:
            seen.add(resolved)
            paths.append(Path(p))

    mode = storage.get("mode", "standard")

    if mode == "standard":
        # Alle Downloads landen in download_path
        _add(storage.get("download_path", ""))
    else:
        # Separate Mode: Filme folgen je nach separate_movies-Flag
        # Anime-Filme
        if storage.get("anime_separate_movies"):
            _add(storage.get("anime_movies_path", ""))
        else:
            # ohne separaten Filme-Pfad landen Anime-Filme in anime_path
            _add(storage.get("anime_path", ""))

        # Serien-Filme
        if storage.get("serien_separate_movies"):
            _add(storage.get("serien_movies_path", ""))
        else:
            # ohne separaten Filme-Pfad landen Serien-Filme in series_path
            _add(storage.get("series_path", ""))

    return [p for p in paths if p.exists()]


def migrate_film_naming(cfg: dict, target_mode: str) -> dict:
    """
    Migriert alle Film-Dateien zwischen Lokal- und Jellyfin-Modus.

    Lokal   → Jellyfin: Film01… → S00E01…, Ordner Filme/ → Season 00/
    Jellyfin → Lokal:   S00E01… → Film01…, Ordner Season 00/ → Filme/

    Sicherheitsmechanismus (Zwei-Phasen-Umbenennung):
        1. Datei → <name>.migrate_tmp  (atomare Phase 1)
        2. <name>.migrate_tmp → <zielname>  (atomare Phase 2)
    Schlägt Phase 2 fehl, bleibt die .migrate_tmp-Datei erhalten und
    wird beim nächsten Lauf erkannt – kein Datenverlust.

    Returns:
        {
          "renamed": int,      # erfolgreich umbenannte Dateien
          "skipped": int,      # bereits im Zielformat
          "errors": list[str], # Fehlermeldungen
        }
    """
    if target_mode not in ("local", "jellyfin"):
        return {"renamed": 0, "skipped": 0, "errors": [f"Ungültiger Modus: {target_mode}"]}

    if target_mode == "jellyfin":
        src_folder = "Filme"
        dst_folder = "Season 00"
        src_re = _RE_FILM_LOCAL
        _make_ep_code = lambda n: f"S00E{n:03d}"
    else:
        src_folder = "Season 00"
        dst_folder = "Filme"
        src_re = _RE_FILM_JELLYFIN
        _make_ep_code = lambda n: f"Film{n:02d}"

    roots = _collect_film_roots(cfg)
    renamed = 0
    skipped = 0
    errors: list[str] = []

    for root in roots:
        # Iteriere alle Serien-Ordner direkt unterhalb des Root
        try:
            series_dirs = [d for d in root.iterdir() if d.is_dir() and not d.name.startswith(".")]
        except PermissionError as exc:
            errors.append(f"Kein Zugriff auf {root}: {exc}")
            continue

        for series_dir in series_dirs:
            film_dir = series_dir / src_folder
            if not film_dir.exists():
                continue

            target_dir = series_dir / dst_folder

            # Alle Film-Dateien im Quell-Ordner sammeln
            film_files = [
                f for f in film_dir.iterdir()
                if f.is_file() and f.suffix.lower() in (".mkv", ".mp4")
                and not f.name.endswith(".migrate_tmp")
            ]

            # Abgebrochene Migrationen bereinigen (.migrate_tmp ohne Zieldatei)
            for leftover in film_dir.glob("*.migrate_tmp"):
                errors.append(f"[MIGRATE-WARN] Unvollständige Migration gefunden: {leftover} – manuell prüfen")

            if not film_files:
                # Leerer Quell-Ordner: nur umbenennen wenn er existiert
                if film_dir.exists() and not any(film_dir.iterdir()):
                    try:
                        film_dir.rmdir()
                    except Exception:
                        pass
                continue

            for f in film_files:
                m = src_re.match(f.name)
                if not m:
                    skipped += 1
                    continue

                ep_num = int(m.group(1))
                rest = m.group(2) or ""     # " - Titel [Sub]" Teil
                ext = m.group(3)            # ".mkv"

                new_stem = _make_ep_code(ep_num) + rest
                new_name = new_stem + ext

                # Zielordner anlegen
                try:
                    target_dir.mkdir(parents=True, exist_ok=True)
                except Exception as exc:
                    errors.append(f"Ordner konnte nicht erstellt werden ({target_dir}): {exc}")
                    continue

                final_path = target_dir / new_name

                # Datei schon vorhanden im Ziel?
                if final_path.exists():
                    log(f"[MIGRATE-SKIP] Zieldatei existiert bereits: {new_name}")
                    skipped += 1
                    continue

                # Phase 1: Quelle → .migrate_tmp
                tmp_path = target_dir / (new_name + ".migrate_tmp")
                try:
                    shutil.move(str(f), str(tmp_path))
                except Exception as exc:
                    errors.append(f"Phase-1-Fehler für {f.name}: {exc}")
                    continue

                # Phase 2: .migrate_tmp → finale Zieldatei
                try:
                    os.replace(str(tmp_path), str(final_path))
                    log(f"[MIGRATE] {f.name} → {dst_folder}/{new_name}")
                    renamed += 1
                except Exception as exc:
                    errors.append(
                        f"Phase-2-Fehler für {tmp_path.name}: {exc} "
                        f"– Datei liegt als .migrate_tmp vor"
                    )

            # Quell-Ordner entfernen wenn er jetzt leer ist
            try:
                if film_dir.exists() and not any(film_dir.iterdir()):
                    film_dir.rmdir()
                    log(f"[MIGRATE-CLEANUP] Leerer Ordner '{src_folder}' entfernt: {series_dir.name}")
            except Exception:
                pass

    log(f"[MIGRATE] Migration abgeschlossen: {renamed} umbenannt, {skipped} übersprungen, {len(errors)} Fehler")
    return {"renamed": renamed, "skipped": skipped, "errors": errors}
