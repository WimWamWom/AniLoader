"""
AniLoader – Dateiverwaltung.

Verwaltet Dateipfade, prüft ob Episoden bereits heruntergeladen sind,
und findet heruntergeladene Dateien nach dem Download.
"""

import html
import os
import re
import shutil
from pathlib import Path
from typing import Optional

from .config import get_download_path
from .logger import log

BASE_DIR = Path(__file__).resolve().parent.parent


# ──────────────────────── Sprach-Kennzeichnung im Dateinamen ────────────────────────

# Einzige Quelle der Wahrheit für die Sprach-Suffixe. Wird verwendet für
#   1. die Benennung beim Verschieben aus TMP,
#   2. die inkrementelle Prüfung "(Episode, Sprache) schon vorhanden?",
#   3. das sprachgenaue Löschen beim Entfernen einer Sprache.
LANGUAGE_FILE_SUFFIX: dict = {
    "German Dub": "",
    "German Sub": "[Sub]",
    "English Dub": "[English Dub]",
    "English Sub": "[English Sub]",
}

# German Dub trägt historisch KEIN Suffix. Eine Episodendatei ohne bekanntes
# Suffix wird daher eindeutig dieser Sprache zugeordnet.
LANGUAGE_WITHOUT_SUFFIX = "German Dub"

# Längste Suffixe zuerst prüfen, damit "[English Sub]" nicht als "[Sub]" gilt.
_SUFFIX_LOOKUP = sorted(
    ((suffix, language) for language, suffix in LANGUAGE_FILE_SUFFIX.items() if suffix),
    key=lambda item: len(item[0]),
    reverse=True,
)

VIDEO_EXTENSIONS = (".mkv", ".mp4")

# Erkennt einen Episoden-/Filmcode irgendwo im Dateinamen: S01E001, S00E01, Film01 …
# Dient als Sicherheitsnetz beim Löschen: Dateien ohne Episodencode werden nie angefasst.
_RE_ANY_EPISODE_CODE = re.compile(r"(?:^|[^A-Za-z0-9])(?:S\d{2,3}E\d{2,3}|Film\d{2,3})(?![0-9])")

# Wie oben, aber mit benannten Gruppen: erlaubt das Zusammenfassen aller
# Sprachversionen DERSELBEN Episode, unabhaengig von Zero-Padding und
# Benennungsmodus (Film01 und S00E01 meinen denselben Film).
_RE_EPISODE_CODE_PARTS = re.compile(
    r"(?:^|[^A-Za-z0-9])(?:S(?P<season>\d{2,3})E(?P<episode>\d{2,3})|Film(?P<film>\d{2,3}))(?![0-9])"
)


def _episode_group_key(stem: str):
    """Normalisierter Schluessel einer Episode, oder None ohne Episodencode."""
    match = _RE_EPISODE_CODE_PARTS.search(str(stem))
    if not match:
        return None
    if match.group("film") is not None:
        return ("film", int(match.group("film")))
    season = int(match.group("season"))
    episode = int(match.group("episode"))
    # Staffel 0 sind Filme – im Jellyfin-Modus heissen sie S00Exx statt Filmxx
    return ("film", episode) if season == 0 else ("episode", season, episode)



def get_language_suffix(language: str) -> str:
    """Gibt das Dateinamen-Suffix einer Sprache zurück ('' für German Dub)."""
    return LANGUAGE_FILE_SUFFIX.get(language, "")


def detect_file_language(filename) -> str:
    """
    Ermittelt die Sprache einer Episodendatei anhand des Suffixes im Dateinamen.

    Ohne bekanntes Suffix gilt LANGUAGE_WITHOUT_SUFFIX (German Dub) – damit
    werden auch die bereits vorhandenen Dateien ohne Marker korrekt zugeordnet.
    """
    stem = Path(str(filename)).stem.strip()
    for suffix, language in _SUFFIX_LOOKUP:
        if stem.endswith(suffix):
            return language
    return LANGUAGE_WITHOUT_SUFFIX


def build_episode_code(season: int, episode: int, film_naming_mode: str = "local") -> str:
    """Baut den Episoden-/Filmcode für den Zieldateinamen."""
    if season == 0:
        if film_naming_mode == "jellyfin":
            return f"S00E{episode:03d}"
        return f"Film{episode:02d}"
    return f"S{season:02d}E{episode:03d}"


def build_episode_filename(
    season: int,
    episode: int,
    title: str,
    language: str,
    ext: str,
    film_naming_mode: str = "local",
) -> str:
    """Baut den finalen Dateinamen: '<Code> - <Titel> <Sprach-Suffix><ext>'."""
    new_name = build_episode_code(season, episode, film_naming_mode)

    safe_title = sanitize_filename(title) if title else ""
    if safe_title:
        new_name += f" - {safe_title}"

    lang_suffix = get_language_suffix(language)
    if lang_suffix:
        new_name += f" {lang_suffix}"

    return new_name + ext


def _episode_code_candidates(season: int, episode: int) -> list[str]:
    """Alle Code-Schreibweisen, unter denen eine Episode auf der Platte liegen kann."""
    if season == 0:
        return [f"Film{episode:02d}", f"S00E{episode:03d}", f"S00E{episode:02d}"]
    return [f"S{season:02d}E{episode:03d}", f"S{season:02d}E{episode:02d}"]


def _episode_subdirs(season: int) -> list[str]:
    """Unterordner, in denen eine Episode/ein Film liegen kann."""
    if season == 0:
        return ["Filme", "Season 00"]
    return [f"Season {season:02d}"]


def _name_matches_episode(name: str, codes: list[str]) -> bool:
    """
    Prüft, ob ein Dateiname zu einer konkreten Episode gehört.

    Der Code darf irgendwo im Namen stehen (die aniworld-CLI stellt den
    Serientitel voran), direkt danach darf aber keine weitere Ziffer folgen –
    sonst würde 'S01E001' fälschlich auch auf 'S01E0011' passen.
    """
    upper = name.upper()
    for code in codes:
        code_upper = code.upper()
        idx = upper.find(code_upper)
        while idx != -1:
            after = upper[idx + len(code_upper): idx + len(code_upper) + 1]
            if not after.isdigit():
                return True
            idx = upper.find(code_upper, idx + 1)
    return False


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


def _normalize_title(text: str) -> str:
    """Normalisiert Titel für Ordnervergleiche (HTML-Entities, Satzzeichen, Groß/Klein)."""
    # Verbotene Zeichen wie die CLI ersatzlos entfernen ("Re:ZERO" → "ReZERO")
    text = re.sub(r'[<>:"/\\|?*]', '', html.unescape(text))
    return re.sub(r"[\W_]+", " ", text).strip().casefold()


def _folder_title_variants(folder: str) -> set[str]:
    """
    Liefert die normalisierten Titel-Varianten eines Serienordners.

    aniworld CLI: "{title} ({year}) [imdbid-{id}]" – Jahr teils als Bereich
    ("(2020-2026)") oder doppelt ("Genial Daneben (2017) (2017)"), Titel teils
    mit HTML-Entities ("Sam &amp; Cat"). Alte AniLoader-Ordner heißen nur "{title}".
    """
    without_id = re.sub(r"\s*\[[^\]]*\]\s*$", "", folder)
    without_year = re.sub(r"\s*\(\d{4}(?:\s*-\s*\d{4})?\)\s*$", "", without_id)
    return {_normalize_title(folder), _normalize_title(without_id), _normalize_title(without_year)}


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

    elif title_hint:
        # Nur ohne bekannten Ordner raten – und nur bei exaktem Titel-Treffer,
        # sonst matcht z.B. "The Daily Life of the Immortal King" auf
        # "The Daily Life of a Middle-Aged Online Shopper in Another World".
        title_norm = _normalize_title(title_hint)
        if title_norm:
            for d in base_path.iterdir():
                if d.is_dir() and title_norm in _folder_title_variants(d.name):
                    _add(d)

    else:
        # Ohne jeden Hinweis (z.B. TMP-Verzeichnis) direkt im Basis-Pfad suchen.
        # Nicht bei unbekanntem Titel: sonst durchsucht rglob die ganze Bibliothek
        # und liefert Episoden fremder Serien.
        _add(base_path)

    return candidates


def _resolve_series_dirs_strict(base_path: Path, folder_name: Optional[str]) -> list[Path]:
    """
    Serien-Ordner für sicherheitskritische Operationen (Löschen).

    Im Gegensatz zu _resolve_series_dirs gibt es hier bewusst KEINEN
    Titel-Fallback und KEINEN Rückfall auf das Basisverzeichnis: ohne exakt
    zuordenbaren Ordner wird eine leere Liste geliefert, damit niemals Dateien
    anderer Serien erfasst werden können.
    """
    if not folder_name or not base_path.is_dir():
        return []

    dirs: list[Path] = []
    exact = base_path / folder_name
    if exact.is_dir():
        dirs.append(exact)

    # Fallback nur bei identischer imdbid (z.B. geändertes Jahr im Ordnernamen)
    imdb_id = _extract_imdb_id(folder_name)
    if imdb_id:
        marker = f"[imdbid-{imdb_id}]"
        try:
            for d in base_path.iterdir():
                if d.is_dir() and marker in d.name.lower() and d not in dirs:
                    dirs.append(d)
        except OSError as e:
            log(f"[WARN] Serienordner konnten nicht gelesen werden ({base_path}): {e}")

    return dirs


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


def find_episode_files(
    cfg: dict,
    url: str,
    folder_name: Optional[str],
    season: int,
    episode: int,
    title_hint: Optional[str] = None,
    language: Optional[str] = None,
    min_size_bytes: int = 1_000_000,
) -> list[Path]:
    """
    Listet alle vorhandenen Dateien einer Episode – optional nur einer Sprache.

    Suchstrategie (wie episode_already_downloaded):
        1. folder_name aus DB bekannt → suche in exaktem Unterordner (+ gleiche imdbid)
        2. folder_name unbekannt, title_hint vorhanden → suche in Unterordnern
           mit exakt diesem Serientitel (z.B. "The Rookie (2018)...")
        3. Weder folder_name noch title_hint → suche direkt im Basis-Pfad

    Muster: S01E001 / Film01 / S00E001 (CLI-Original) / S00E01 (Jellyfin-Final)

    Args:
        language: Wenn gesetzt, werden nur Dateien dieser Sprache zurückgegeben
                  (Zuordnung über das Suffix im Dateinamen).
    """
    base_path = Path(get_download_path(cfg, url, season == 0))
    codes = _episode_code_candidates(season, episode)

    # Mögliche Suchpfade bestimmen (inkl. imdbid-Fallback bei geändertem Jahr im Ordnernamen)
    series_dirs = _resolve_series_dirs(base_path, folder_name=folder_name, title_hint=title_hint)
    search_dirs = [d / sub for d in series_dirs for sub in _episode_subdirs(season)]

    matches: list[Path] = []
    for search_dir in search_dirs:
        if not search_dir.is_dir():
            continue
        try:
            entries = sorted(search_dir.iterdir(), key=lambda p: p.name.lower())
        except OSError as e:
            log(f"[WARN] Ordner konnte nicht gelesen werden ({search_dir}): {e}")
            continue

        for f in entries:
            if not f.is_file() or f.suffix.lower() not in VIDEO_EXTENSIONS:
                continue
            if not _name_matches_episode(f.stem, codes):
                continue
            try:
                if f.stat().st_size < min_size_bytes:
                    continue
            except OSError:
                continue
            if language is not None and detect_file_language(f) != language:
                continue
            if f not in matches:
                matches.append(f)

    return matches


def episode_already_downloaded(
    cfg: dict,
    url: str,
    folder_name: Optional[str],
    season: int,
    episode: int,
    title_hint: Optional[str] = None,
    language: Optional[str] = None,
) -> Optional[Path]:
    """
    Prüft ob eine Episode bereits heruntergeladen wurde.

    Args:
        language: Wenn gesetzt, gilt die Episode nur dann als vorhanden, wenn
                  sie in genau dieser Sprache existiert (inkrementelle Logik
                  für Mehrsprach-Einträge).

    Gibt den Dateipfad zurück falls gefunden, sonst None.
    """
    matches = find_episode_files(
        cfg, url, folder_name, season, episode,
        title_hint=title_hint, language=language,
    )
    return matches[0] if matches else None


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
        2. title_hint bekannt  → suche in Unterordnern mit exakt diesem Titel
        3. Keine Hinweise      → rglob über alle Unterordner (nur für TMP gedacht)
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
    ext = found_path.suffix
    parent = found_path.parent

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

    # Ziel-Dateiname aufbauen (inkl. Sprach-Suffix)
    new_name = build_episode_filename(season, episode, title, language, ext, film_naming_mode)
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
    new_name = build_episode_filename(
        season, episode, title, language, tmp_file.suffix, film_naming_mode
    )

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


# ──────────────────────── Sprachgenaues Löschen ────────────────────────


def delete_language_files(
    cfg: dict,
    url: str,
    folder_name: Optional[str],
    language: str,
    dry_run: bool = False,
) -> dict:
    """
    Löscht ausschließlich die Episodendateien EINER Sprache EINER Serie.

    Sicherheitsregeln (alle müssen erfüllt sein, sonst wird nichts gelöscht):
        1. Die Sprache muss bekannt sein (LANGUAGE_FILE_SUFFIX).
        2. Der Serien-Ordnername muss in der DB stehen. Ohne eindeutigen
           Ordner wird abgebrochen – es wird nie geraten.
        3. Es werden nur Ordner der Serie selbst durchsucht: exakter
           Ordnername oder identische imdbid (kein Titel-Fallback,
           kein Rückfall auf das Download-Basisverzeichnis).
        4. Nur Video-Dateien (.mkv/.mp4) in 'Season xx'-/'Filme'-Ordnern.
        5. Der Dateiname muss einen Episoden-/Filmcode enthalten.
        6. Die aus dem Dateinamen erkannte Sprache muss exakt der zu
           löschenden Sprache entsprechen.

    Args:
        dry_run: True → es wird nur ermittelt, was gelöscht würde.

    Returns:
        {"language": str, "deleted": [str], "kept": int, "errors": [str]}
    """
    result: dict = {"language": language, "deleted": [], "kept": 0, "errors": []}

    if language not in LANGUAGE_FILE_SUFFIX:
        result["errors"].append(f"Unbekannte Sprache: '{language}' – kein Löschvorgang")
        return result

    if not folder_name:
        result["errors"].append(
            "Ordnername der Serie ist nicht bekannt – Dateien können nicht "
            "eindeutig zugeordnet werden, es wird nichts gelöscht"
        )
        return result

    # Serien- und Film-Basispfad können bei separate-Storage unterschiedlich sein
    base_paths: list[Path] = []
    for is_film in (False, True):
        candidate = Path(get_download_path(cfg, url, is_film))
        if candidate not in base_paths:
            base_paths.append(candidate)

    series_dirs: list[Path] = []
    for base in base_paths:
        for d in _resolve_series_dirs_strict(base, folder_name):
            if d not in series_dirs:
                series_dirs.append(d)

    if not series_dirs:
        result["errors"].append(
            f"Kein Serien-Ordner '{folder_name}' gefunden – nichts zu löschen"
        )
        return result

    for series_dir in series_dirs:
        try:
            subdirs = [
                d for d in series_dir.iterdir()
                if d.is_dir() and (d.name.lower().startswith("season ") or d.name.lower() == "filme")
            ]
        except OSError as e:
            result["errors"].append(f"Ordner nicht lesbar ({series_dir}): {e}")
            continue

        for subdir in sorted(subdirs, key=lambda p: p.name.lower()):
            try:
                entries = sorted(subdir.iterdir(), key=lambda p: p.name.lower())
            except OSError as e:
                result["errors"].append(f"Ordner nicht lesbar ({subdir}): {e}")
                continue

            for f in entries:
                if not f.is_file() or f.suffix.lower() not in VIDEO_EXTENSIONS:
                    continue
                # Ohne Episodencode im Namen wird die Datei nie angefasst
                if not _RE_ANY_EPISODE_CODE.search(f.stem):
                    continue
                if detect_file_language(f) != language:
                    result["kept"] += 1
                    continue

                if dry_run:
                    # Vorschau, kein Vorgang – sie laeuft bei jedem Klick in der
                    # Sprachauswahl und hat frueher das Log geflutet.
                    result["deleted"].append(str(f))
                    continue

                try:
                    f.unlink()
                    result["deleted"].append(str(f))
                    log(f"[LANG-DEL] Gelöscht [{language}]: {f}")
                except Exception as e:
                    result["errors"].append(f"{f}: {e}")
                    log(f"[LANG-DEL-ERROR] {f}: {e}")

    if not dry_run:
        log(
            f"[LANG-DEL] {folder_name} – {len(result['deleted'])} Datei(en) [{language}] gelöscht, "
            f"{result['kept']} Datei(en) anderer Sprachen unberührt, {len(result['errors'])} Fehler"
        )
    return result


def reduce_to_cascade(
    cfg: dict,
    url: str,
    folder_name: Optional[str],
    cascade: list[str],
    dry_run: bool = False,
) -> dict:
    """
    Reduziert jede Episode auf die Sprachversion, die der Kaskade entspricht.

    Wird beim Wechsel von einer eigenen Sprachauswahl zurück zur globalen
    Kaskade aufgerufen. Pro Episode wird die ERSTE in der Kaskade vorhandene
    Sprache behalten, alle anderen Sprachversionen derselben Episode werden
    gelöscht. Die Entscheidung fällt einzeln pro Episode: liegt Folge 1 als
    German Dub + English Dub vor, bleibt German Dub; hat Folge 2 nur
    German Sub + English Dub, bleibt German Sub.

    Sicherheitsregeln (alle müssen erfüllt sein, sonst wird nichts gelöscht):
        1. Die Kaskade muss mindestens eine bekannte Sprache enthalten.
        2. Der Serien-Ordnername muss in der DB stehen – es wird nie geraten.
        3. Es werden nur Ordner der Serie selbst durchsucht: exakter
           Ordnername oder identische imdbid.
        4. Nur Video-Dateien in 'Season xx'-/'Filme'-Ordnern.
        5. Der Dateiname muss einen Episoden-/Filmcode enthalten.
        6. Enthält eine Episode KEINE der Kaskaden-Sprachen, bleibt sie
           komplett unangetastet. Die letzte Datei einer Episode wird nie
           gelöscht, nur weil die Kaskade ihre Sprache nicht kennt.

    Args:
        cascade: Sprachen in Prioritätsreihenfolge (erste = höchste Priorität)
        dry_run: True → es wird nur ermittelt, was gelöscht würde.

    Returns:
        {"cascade": [str], "deleted": [str], "kept": int, "errors": [str]}
    """
    known = [lang for lang in cascade if lang in LANGUAGE_FILE_SUFFIX]
    result: dict = {"cascade": known, "deleted": [], "kept": 0, "errors": []}

    if not known:
        result["errors"].append(
            "Kaskade enthält keine bekannte Sprache – es wird nichts gelöscht"
        )
        return result

    if not folder_name:
        result["errors"].append(
            "Ordnername der Serie ist nicht bekannt – Dateien können nicht "
            "eindeutig zugeordnet werden, es wird nichts gelöscht"
        )
        return result

    # Serien- und Film-Basispfad können bei separate-Storage unterschiedlich sein
    base_paths: list[Path] = []
    for is_film in (False, True):
        candidate = Path(get_download_path(cfg, url, is_film))
        if candidate not in base_paths:
            base_paths.append(candidate)

    series_dirs: list[Path] = []
    for base in base_paths:
        for d in _resolve_series_dirs_strict(base, folder_name):
            if d not in series_dirs:
                series_dirs.append(d)

    if not series_dirs:
        result["errors"].append(
            f"Kein Serien-Ordner '{folder_name}' gefunden – nichts zu löschen"
        )
        return result

    # Nur fuer die Zusammenfassung – pro Datei zu loggen flutet das Log, und der
    # Dry-Run laeuft bei jedem Klick in der Sprachauswahl erneut.
    per_language: dict = {}
    untouched = 0

    for series_dir in series_dirs:
        try:
            subdirs = [
                d for d in series_dir.iterdir()
                if d.is_dir() and (d.name.lower().startswith("season ") or d.name.lower() == "filme")
            ]
        except OSError as e:
            result["errors"].append(f"Ordner nicht lesbar ({series_dir}): {e}")
            continue

        for subdir in sorted(subdirs, key=lambda p: p.name.lower()):
            try:
                entries = sorted(subdir.iterdir(), key=lambda p: p.name.lower())
            except OSError as e:
                result["errors"].append(f"Ordner nicht lesbar ({subdir}): {e}")
                continue

            # Alle Sprachversionen einer Episode zusammenfassen
            groups: dict = {}
            for f in entries:
                if not f.is_file() or f.suffix.lower() not in VIDEO_EXTENSIONS:
                    continue
                key = _episode_group_key(f.stem)
                if key is None:
                    continue
                groups.setdefault(key, []).append(f)

            for key in sorted(groups):
                files = groups[key]
                by_language: dict = {}
                for f in files:
                    by_language.setdefault(detect_file_language(f), []).append(f)

                present = [lang for lang in known if lang in by_language]
                if not present:
                    # Regel 6: keine Kaskaden-Sprache vorhanden → nichts anfassen
                    result["kept"] += len(files)
                    untouched += 1
                    continue

                keep = present[0]
                for language, lang_files in by_language.items():
                    for f in lang_files:
                        if language == keep:
                            result["kept"] += 1
                            continue

                        if dry_run:
                            result["deleted"].append(str(f))
                            per_language[language] = per_language.get(language, 0) + 1
                            continue

                        try:
                            f.unlink()
                            result["deleted"].append(str(f))
                            per_language[language] = per_language.get(language, 0) + 1
                        except Exception as e:
                            result["errors"].append(f"{f}: {e}")
                            log(f"[CASCADE-ERROR] {f}: {e}")

    # Der Dry-Run ist reine UI-Vorschau und laeuft bei jedem Klick – er schweigt.
    if not dry_run:
        detail = ", ".join(f"{lang}: {n}" for lang, n in sorted(per_language.items()))
        parts = [f"{len(result['deleted'])} Datei(en) gelöscht" + (f" ({detail})" if detail else "")]
        parts.append(f"{result['kept']} behalten")
        if untouched:
            parts.append(f"{untouched} Folge(n) ohne Kaskaden-Sprache unverändert")
        if result["errors"]:
            parts.append(f"{len(result['errors'])} Fehler")
        log(f"[CASCADE] {folder_name} – auf Kaskade reduziert: " + ", ".join(parts))

    return result


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
    aniworld- und serienstream-URLs, um exakt dieselben Pfade zu bestimmen
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

            # Alle Film-bezogenen Dateien sammeln (Video, Thumbnails, Metadaten, …)
            # Die Regex entscheidet ob eine Datei zum Film-Namensmuster passt.
            film_files = [
                f for f in film_dir.iterdir()
                if f.is_file() and not f.name.endswith(".migrate_tmp")
                and src_re.match(f.name)
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
                    # sollte durch Vorfilterung nicht auftreten
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
