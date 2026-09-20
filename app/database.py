"""
AniLoader – SQLite-Datenbankschicht.

Flat-Schema mit einer `anime`-Tabelle für Serien und Animes.
Thread-safe über separate Connections pro Aufruf.
AniLoader.txt Import- und Backup-Funktionalität.
"""

import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import DEFAULT_CONFIG, normalize_language_list, sort_languages_by_priority
from .logger import log

# Verzögerter Import um zirkuläre Abhängigkeiten zu vermeiden
def _get_scraper():
    from . import scraper
    return scraper


def _get_file_manager():
    from . import file_manager
    return file_manager


def _get_domains():
    from . import domains
    return domains


# Base directory für AniLoader.txt Dateien
BASE_DIR = Path(__file__).resolve().parent.parent


def _get_db_path(data_folder: str) -> str:
    return os.path.join(data_folder, "AniLoader.db")


def _connect(data_folder: str) -> sqlite3.Connection:
    db_path = _get_db_path(data_folder)
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(data_folder: str) -> None:
    """Erstellt die Tabelle und führt Migrationen durch."""
    os.makedirs(data_folder, exist_ok=True)
    conn = _connect(data_folder)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS anime (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            url TEXT UNIQUE,
            series_key TEXT,
            complete INTEGER DEFAULT 0,
            deutsch_komplett INTEGER DEFAULT 0,
            deleted INTEGER DEFAULT 0,
            fehlende_deutsch_folgen TEXT DEFAULT '[]',
            last_film INTEGER DEFAULT 0,
            last_episode INTEGER DEFAULT 0,
            last_season INTEGER DEFAULT 0,
            folder_name TEXT DEFAULT NULL,
            languages TEXT DEFAULT NULL
        )
    """)

    # Migrationen
    try:
        c.execute("PRAGMA table_info(anime)")
        cols = [r["name"] for r in c.fetchall()]

        if "languages" not in cols:
            # NULL = keine eigene Auswahl → globale Sprach-Kaskade aus config.yaml
            c.execute("ALTER TABLE anime ADD COLUMN languages TEXT DEFAULT NULL")
            log("[DB] languages Spalte hinzugefügt")

        if "folder_name" not in cols:
            c.execute("ALTER TABLE anime ADD COLUMN folder_name TEXT DEFAULT NULL")
            log("[DB] folder_name Spalte hinzugefügt")

        if "series_key" not in cols:
            c.execute("ALTER TABLE anime ADD COLUMN series_key TEXT DEFAULT NULL")
            log("[DB] series_key Spalte hinzugefügt")
            # Bestehende Zeilen befüllen
            sc = _get_scraper()
            c.execute("SELECT id, url FROM anime")
            rows = c.fetchall()
            updated = 0
            for row in rows:
                key = sc.get_series_key(row["url"])
                if key:
                    c.execute("UPDATE anime SET series_key = ? WHERE id = ?", (key, row["id"]))
                    updated += 1
            log(f"[DB] series_key für {updated} bestehende Einträge befüllt")
    except Exception as e:
        log(f"[DB-ERROR] Migration: {e}")

    # Alt-Domains (s.to, Mirrors) auf die kanonische Domain umschreiben
    try:
        _migrate_domains(c)
    except Exception as e:
        log(f"[DB-ERROR] Domain-Migration: {e}")

    # Index nach Migrationen setzen (Spalte ist jetzt garantiert vorhanden)
    c.execute("CREATE INDEX IF NOT EXISTS idx_anime_series_key ON anime(series_key)")

    conn.commit()
    conn.close()
    log("[DB] Datenbank initialisiert")


def _migrate_domains(c: sqlite3.Cursor) -> None:
    """
    Schreibt Alt-Domains auf die kanonische Domain um – URL und series_key.

    Läuft bei jedem Start, ist idempotent und fasst nur Zeilen an, bei denen sich
    tatsächlich etwas ändert. Nötig, weil ein Domain-Wechsel sonst die
    Duplikaterkennung bricht: der alte Key (`s.to:slug`) passt nicht mehr zum
    neu berechneten (`serienstream:slug`).
    """
    dom = _get_domains()

    c.execute("SELECT id, url, series_key FROM anime")
    rows = c.fetchall()

    updated = 0
    conflicts: List[str] = []

    for row in rows:
        old_url = row["url"] or ""
        new_url = dom.normalize_series_url(old_url)
        new_key = dom.get_series_key(new_url)

        url_changed = new_url != old_url
        key_changed = new_key is not None and new_key != (row["series_key"] or "")
        if not url_changed and not key_changed:
            continue

        try:
            c.execute(
                "UPDATE anime SET url = ?, series_key = ? WHERE id = ?",
                (new_url, new_key, row["id"]),
            )
            updated += 1
        except sqlite3.IntegrityError:
            # url ist UNIQUE – es gibt bereits einen Eintrag mit der kanonischen URL
            conflicts.append(f"ID {row['id']}: '{old_url}' → '{new_url}' existiert bereits")

    if updated:
        log(f"[DB] Domain-Migration: {updated} Eintrag/Einträge auf kanonische Domains umgeschrieben")
    for conflict in conflicts:
        log(f"[DB-WARN] Domain-Migration übersprungen – {conflict} (Duplikat manuell prüfen)")


# ────────────────────────── CRUD ──────────────────────────


def _find_existing_id_by_series_key(cursor: sqlite3.Cursor, url: str) -> Optional[int]:
    """Findet einen bestehenden Eintrag über den indizierten series_key."""
    sc = _get_scraper()
    series_key = sc.get_series_key(url)
    if not series_key:
        return None

    cursor.execute("SELECT id FROM anime WHERE series_key = ?", (series_key,))
    row = cursor.fetchone()
    return int(row["id"]) if row else None


def add_anime(data_folder: str, url: str, title: Optional[str] = None) -> Optional[int]:
    """Fügt eine Serie/Anime hinzu. Gibt die ID zurück oder None bei Duplikat."""
    sc = _get_scraper()
    normalized_url = sc.normalize_series_url(url)

    conn = _connect(data_folder)
    try:
        c = conn.cursor()

        existing_id = _find_existing_id_by_series_key(c, normalized_url)
        if existing_id is not None:
            return existing_id

        series_key = sc.get_series_key(normalized_url)
        c.execute(
            "INSERT OR IGNORE INTO anime (url, title, series_key) VALUES (?, ?, ?)",
            (normalized_url, title or normalized_url, series_key),
        )
        conn.commit()
        if c.rowcount > 0:
            log(f"[DB] Hinzugefügt: {title or normalized_url}")
            # Backup-Datei aktualisieren
            _update_aniloader_backup(data_folder, normalized_url)
            return c.lastrowid
        else:
            # Already exists – return existing ID
            c.execute("SELECT id FROM anime WHERE url = ?", (normalized_url,))
            row = c.fetchone()
            return row["id"] if row else None
    finally:
        conn.close()


def get_anime_by_url(data_folder: str, url: str) -> Optional[Dict[str, Any]]:
    """Sucht einen Eintrag anhand der URL."""
    conn = _connect(data_folder)
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM anime WHERE url = ?", (url,))
        row = c.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_anime_by_id(data_folder: str, anime_id: int) -> Optional[Dict[str, Any]]:
    conn = _connect(data_folder)
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM anime WHERE id = ?", (anime_id,))
        row = c.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# Stufen der Trefferqualitaet fuer die Suche – kleiner ist besser.
_RANK_EXACT, _RANK_PREFIX, _RANK_WORD, _RANK_INFIX, _RANK_URL_ONLY = 0, 1, 2, 3, 4


def _search_rank(title: Any, needle: str) -> int:
    """Bewertet, wie gut ``title`` zum Suchbegriff passt (0 = beste Übereinstimmung).

    ``LIKE '%x%'`` findet jeden Teilstring – auch mitten im Wort ("Ted" steckt
    in "Wanted", "Limited", "United"). Ohne Bewertung entscheidet allein die
    Spaltensortierung, und ein kurzer, exakt passender Titel verschwindet
    zwischen den Zufallstreffern. Bei langen Suchbegriffen fällt das nicht auf,
    weil es dort kaum Teilwort-Treffer gibt.

    Stufen:
      0  exakter Titel          "Ted"
      1  beginnt mit dem Begriff "Ted Lasso", "Ted 2"
      2  Begriff als ganzes Wort "Der Fall Ted Bundy"
      3  nur Wortbestandteil     "Wanted", "Limited"
      4  Titel passt gar nicht – der Treffer kam über die URL
    """
    text = str(title or "").casefold().strip()
    if not text or not needle:
        return _RANK_URL_ONLY
    if text == needle:
        return _RANK_EXACT

    escaped = re.escape(needle)
    # Wortgrenzen nur dort setzen, wo der Begriff selbst mit einem Wortzeichen
    # anfaengt/endet – sonst greift \b bei Eingaben wie "re:" oder "(2020)" nie.
    left = r"\b" if needle[:1].isalnum() else ""
    right = r"\b" if needle[-1:].isalnum() else ""

    if re.match(escaped + right, text):
        return _RANK_PREFIX
    if re.search(left + escaped + right, text):
        return _RANK_WORD
    if needle in text:
        return _RANK_INFIX
    return _RANK_URL_ONLY


def get_all_anime(
    data_folder: str,
    include_deleted: bool = False,
    search: Optional[str] = None,
    sort_by: str = "id",
    sort_dir: str = "ASC",
    complete: Optional[str] = None,  # "1" | "0" | "deleted" | None
    deutsch: Optional[str] = None,   # "1" | "0" | None
) -> List[Dict[str, Any]]:
    """Gibt alle Anime/Serien zurück, optional gefiltert und sortiert."""
    conn = _connect(data_folder)
    try:
        # Whitelist für sort columns
        allowed_sort = {"id", "title", "url", "complete", "deleted", "last_season", "last_episode", "last_film"}
        if sort_by not in allowed_sort:
            sort_by = "id"
        if sort_dir.upper() not in ("ASC", "DESC"):
            sort_dir = "ASC"

        query = "SELECT * FROM anime"
        params: list = []
        conditions = []

        # Komplett/Gelöscht-Filter
        if complete == "deleted":
            conditions.append("deleted = 1")
        elif complete == "1":
            conditions.append("deleted = 0 AND complete = 1")
        elif complete == "0":
            conditions.append("deleted = 0 AND complete = 0")
        elif not include_deleted:
            conditions.append("deleted = 0")

        if deutsch == "1":
            conditions.append("deutsch_komplett = 1")
        elif deutsch == "0":
            conditions.append("deutsch_komplett = 0")

        if search:
            conditions.append("(title LIKE ? OR url LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += f" ORDER BY {sort_by} {sort_dir}"

        c = conn.cursor()
        c.execute(query, params)
        rows = [dict(row) for row in c.fetchall()]

        if search:
            # Nach Trefferqualitaet vorsortieren. Pythons sort ist stabil, die
            # oben per ORDER BY gewaehlte Spaltensortierung bleibt innerhalb
            # einer Stufe also vollstaendig erhalten.
            needle = search.casefold().strip()
            rows.sort(key=lambda row: _search_rank(row.get("title"), needle))

        return rows
    finally:
        conn.close()


def update_anime(data_folder: str, anime_id: int, **kwargs) -> bool:
    """Update beliebige Felder eines Eintrags."""
    if not kwargs:
        return False

    # Whitelist der erlaubten Felder
    allowed = {
        "title", "complete", "deutsch_komplett", "deleted",
        "fehlende_deutsch_folgen", "last_film", "last_episode",
        "last_season", "folder_name",
    }
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return False

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [anime_id]

    conn = _connect(data_folder)
    try:
        conn.execute(f"UPDATE anime SET {set_clause} WHERE id = ?", values)
        conn.commit()
        return True
    finally:
        conn.close()


def delete_anime(data_folder: str, anime_id: int, hard: bool = False) -> bool:
    """Soft-Delete (deleted=1) oder Hard-Delete."""
    conn = _connect(data_folder)
    try:
        if hard:
            conn.execute("DELETE FROM anime WHERE id = ?", (anime_id,))
        else:
            conn.execute("UPDATE anime SET deleted = 1 WHERE id = ?", (anime_id,))
        conn.commit()
        return True
    finally:
        conn.close()


def restore_anime(data_folder: str, anime_id: int) -> bool:
    """Stellt einen gelöschten Eintrag wieder her und setzt alle Werte auf Standardwerte zurück."""
    conn = _connect(data_folder)
    try:
        conn.execute(
            """UPDATE anime SET
                deleted = 0,
                complete = 0,
                deutsch_komplett = 0,
                fehlende_deutsch_folgen = '[]',
                last_film = 0,
                last_episode = 0,
                last_season = 0
               WHERE id = ?""",
            (anime_id,),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def get_active_anime(data_folder: str) -> List[Dict[str, Any]]:
    """Gibt alle nicht-gelöschten Einträge zurück."""
    return get_all_anime(data_folder, include_deleted=False)


def get_incomplete_anime(data_folder: str) -> List[Dict[str, Any]]:
    """Gibt alle nicht-gelöschten, nicht-vollständigen Einträge zurück."""
    conn = _connect(data_folder)
    try:
        c = conn.cursor()
        c.execute(
            "SELECT * FROM anime WHERE deleted = 0 AND complete = 0 ORDER BY id ASC"
        )
        return [dict(row) for row in c.fetchall()]
    finally:
        conn.close()


def get_completed_anime(data_folder: str) -> List[Dict[str, Any]]:
    """Gibt alle vollständigen Einträge zurück."""
    conn = _connect(data_folder)
    try:
        c = conn.cursor()
        c.execute(
            "SELECT * FROM anime WHERE deleted = 0 AND complete = 1 ORDER BY id ASC"
        )
        return [dict(row) for row in c.fetchall()]
    finally:
        conn.close()


def get_missing_german_episodes(data_folder: str, anime_id: int) -> List[str]:
    """Gibt die Liste der fehlenden deutschen Episoden-URLs zurück."""
    conn = _connect(data_folder)
    try:
        c = conn.cursor()
        c.execute("SELECT fehlende_deutsch_folgen FROM anime WHERE id = ?", (anime_id,))
        row = c.fetchone()
        if row and row["fehlende_deutsch_folgen"]:
            try:
                return json.loads(row["fehlende_deutsch_folgen"])
            except (json.JSONDecodeError, TypeError):
                return []
        return []
    finally:
        conn.close()


def set_missing_german_episodes(data_folder: str, anime_id: int, episodes: List[str]) -> bool:
    """Setzt die Liste der fehlenden deutschen Episoden-URLs."""
    return update_anime(
        data_folder, anime_id,
        fehlende_deutsch_folgen=json.dumps(episodes, ensure_ascii=False),
    )


# ────────────────────────── Gewünschte Sprachen pro Eintrag ──────────────────────────


def parse_languages(raw: Any) -> List[str]:
    """
    Liest den Inhalt der `languages`-Spalte als Liste.

    Leer/NULL/ungültig → leere Liste (= keine eigene Auswahl, es gilt die
    globale Sprach-Kaskade aus der config.yaml).
    """
    if not raw:
        return []
    if isinstance(raw, (list, tuple)):
        return normalize_language_list(list(raw), strict=True)
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(parsed, list):
        return []
    return normalize_language_list(parsed, strict=True)


def get_anime_languages(data_folder: str, anime_id: int) -> List[str]:
    """Gibt die gewünschten Sprachen eines Eintrags zurück (leer = globale Kaskade)."""
    conn = _connect(data_folder)
    try:
        c = conn.cursor()
        c.execute("SELECT languages FROM anime WHERE id = ?", (anime_id,))
        row = c.fetchone()
        return parse_languages(row["languages"]) if row else []
    finally:
        conn.close()


def set_anime_languages(
    data_folder: str,
    anime_id: int,
    languages: List[str],
    cfg: Optional[dict] = None,
) -> Optional[Dict[str, Any]]:
    """
    Setzt die gewünschten Sprachen eines Eintrags (reine DB-Operation).

    Neu hinzugekommene Sprachen setzen den Fortschritt zurück (complete,
    last_season/last_episode/last_film), damit der nächste Lauf die fehlende
    Sprache auch für bereits vorhandene Episoden nachlädt. Bereits vorhandene
    (Episode, Sprache)-Kombinationen werden dabei übersprungen – es wird also
    nichts doppelt geladen.

    Returns:
        {"languages": [...], "previous": [...], "added": [...], "removed": [...]}
        oder None wenn der Eintrag nicht existiert.
    """
    row = get_anime_by_id(data_folder, anime_id)
    if not row:
        return None

    previous = parse_languages(row.get("languages"))
    new_languages = sort_languages_by_priority(
        normalize_language_list(languages, strict=True), cfg
    )

    added = [lang for lang in new_languages if lang not in previous]
    removed = [lang for lang in previous if lang not in new_languages]

    updates: Dict[str, Any] = {
        "languages": json.dumps(new_languages, ensure_ascii=False) if new_languages else None,
    }

    if added:
        # Fortschritts-Zeiger zurücksetzen, damit alte Episoden erneut geprüft
        # werden (heruntergeladen wird nur, was für die Sprache noch fehlt).
        updates.update({"complete": 0, "last_season": 0, "last_episode": 0, "last_film": 0})
        if "German Dub" in added:
            updates["deutsch_komplett"] = 0

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [anime_id]

    conn = _connect(data_folder)
    try:
        conn.execute(f"UPDATE anime SET {set_clause} WHERE id = ?", values)
        conn.commit()
    finally:
        conn.close()

    log(
        f"[DB] Sprachen für ID {anime_id} gesetzt: {new_languages or '(globale Kaskade)'}"
        + (f" | neu: {added}" if added else "")
        + (f" | entfernt: {removed}" if removed else "")
    )
    if added:
        log(f"[DB] Fortschritt für ID {anime_id} zurückgesetzt – fehlende Sprachen werden nachgeladen")

    return {
        "languages": new_languages,
        "previous": previous,
        "added": added,
        "removed": removed,
    }


def apply_language_selection(
    data_folder: str,
    anime_id: int,
    languages: List[str],
    cfg: Optional[dict] = None,
    delete_files: bool = True,
    dry_run: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Setzt die gewünschten Sprachen und räumt entfernte Sprachen auf der Platte auf.

    Für jede entfernte Sprache werden ausschließlich die Episodendateien dieser
    Sprache gelöscht (siehe file_manager.delete_language_files) – alle anderen
    Sprachversionen, Episoden und Serien bleiben unangetastet.

    Args:
        delete_files: False → nur die DB wird geändert, Dateien bleiben liegen
        dry_run:      True  → reine Vorschau: WEDER die DB noch Dateien werden
                              angefasst, es wird nur ermittelt was passieren würde

    Returns:
        Ergebnis von set_anime_languages, ergänzt um "deleted_files" und "errors".
    """
    anime = get_anime_by_id(data_folder, anime_id)
    if not anime:
        return None

    if dry_run:
        # Vorschau ohne jede Änderung – die UI kann das Ergebnis anzeigen und
        # der Nutzer danach immer noch abbrechen.
        previous = parse_languages(anime.get("languages"))
        new_languages = sort_languages_by_priority(
            normalize_language_list(languages, strict=True), cfg
        )
        result = {
            "languages": new_languages,
            "previous": previous,
            "added": [l for l in new_languages if l not in previous],
            "removed": [l for l in previous if l not in new_languages],
        }
    else:
        result = set_anime_languages(data_folder, anime_id, languages, cfg=cfg)
        if result is None:
            return None

    deleted_files: List[str] = []
    errors: List[str] = []

    if delete_files and result["removed"] and not result["languages"]:
        # Leere Auswahl bedeutet "zurück zur globalen Kaskade", NICHT "alles weg".
        # Statt gar nichts zu tun, werden die vorhandenen Dateien auf die Kaskade
        # reduziert: pro Episode bleibt die höchstpriorisierte vorhandene Sprache,
        # die übrigen Sprachversionen werden entfernt. Eine Episode, von der keine
        # Kaskaden-Sprache vorliegt, bleibt vollständig erhalten.
        if cfg is None:
            from .config import load_config
            cfg = load_config()

        cascade = sort_languages_by_priority(
            normalize_language_list(
                cfg.get("languages") or DEFAULT_CONFIG["languages"], strict=True
            ),
            cfg,
        )
        log(
            f"[DB] ID {anime_id}: Sprachauswahl geleert – reduziere vorhandene "
            f"Dateien auf die globale Kaskade {cascade}"
        )

        fm = _get_file_manager()
        cleanup = fm.reduce_to_cascade(
            cfg,
            anime["url"],
            anime.get("folder_name"),
            cascade,
            dry_run=dry_run,
        )
        deleted_files.extend(cleanup["deleted"])
        errors.extend(cleanup["errors"])
    elif delete_files and result["removed"]:
        if cfg is None:
            from .config import load_config
            cfg = load_config()

        fm = _get_file_manager()
        for language in result["removed"]:
            cleanup = fm.delete_language_files(
                cfg,
                anime["url"],
                anime.get("folder_name"),
                language,
                dry_run=dry_run,
            )
            deleted_files.extend(cleanup["deleted"])
            errors.extend(cleanup["errors"])

    result["deleted_files"] = deleted_files
    result["errors"] = errors
    return result


def get_db_stats(data_folder: str) -> Dict[str, int]:
    """Gibt Statistiken über die Datenbank zurück."""
    conn = _connect(data_folder)
    try:
        c = conn.cursor()
        stats = {}
        c.execute("SELECT COUNT(*) as cnt FROM anime WHERE deleted = 0")
        stats["total"] = c.fetchone()["cnt"]
        c.execute("SELECT COUNT(*) as cnt FROM anime WHERE deleted = 0 AND complete = 1")
        stats["complete"] = c.fetchone()["cnt"]
        c.execute("SELECT COUNT(*) as cnt FROM anime WHERE deleted = 0 AND complete = 0")
        stats["incomplete"] = c.fetchone()["cnt"]
        c.execute("SELECT COUNT(*) as cnt FROM anime WHERE deleted = 1")
        stats["deleted"] = c.fetchone()["cnt"]
        c.execute("SELECT COUNT(*) as cnt FROM anime WHERE deleted = 0 AND deutsch_komplett = 1")
        stats["german_complete"] = c.fetchone()["cnt"]
        return stats
    finally:
        conn.close()


def import_txt(data_folder: str, content: str) -> int:
    """
    Importiert URLs aus Textinhalt (eine URL pro Zeile).
    Gibt die Anzahl neu hinzugefügter Einträge zurück.
    """
    sc = _get_scraper()
    added = 0
    for line in content.strip().splitlines():
        url = line.strip()
        if not url or url.startswith("#"):
            continue
        if _get_domains().is_known(url):
            # Echten Titel von der Webseite abrufen
            try:
                title = sc.get_series_title(url)
                if not title:
                    title = url
            except Exception as e:
                log(f"[IMPORT-WARN] Titel konnte nicht abgerufen werden ({e}) – nutze URL als Titel")
                title = url
            try:
                result = add_anime(data_folder, url, title=title)
                if result:
                    added += 1
            except Exception as e:
                log(f"[IMPORT-WARN] Eintrag konnte nicht gespeichert werden ({e}) – übersprungen: {url}")
    return added


def refresh_titles(data_folder: str) -> Dict[str, Any]:
    """
    Aktualisiert alle Titel in der Datenbank anhand der Webseiten.
    Gibt Statistik zurück: {updated: int, failed: int, unchanged: int, details: list}.
    """
    from .scraper import get_series_title

    all_entries = get_all_anime(data_folder, include_deleted=False)
    updated = 0
    failed = 0
    unchanged = 0
    details: List[str] = []

    for entry in all_entries:
        aid = entry["id"]
        url = entry.get("url", "")
        old_title = entry.get("title", "")

        try:
            new_title = get_series_title(url)
            if not new_title:
                failed += 1
                details.append(f"ID {aid}: Kein Titel gefunden für {url}")
                continue

            if new_title != old_title:
                update_anime(data_folder, aid, title=new_title)
                log(f"[DB] Titel aktualisiert (ID {aid}): '{old_title}' -> '{new_title}'")
                details.append(f"ID {aid}: '{old_title}' -> '{new_title}'")
                updated += 1
            else:
                unchanged += 1
        except Exception as e:
            failed += 1
            log(f"[DB-ERROR] Titel-Refresh ID {aid}: {e}")
            details.append(f"ID {aid}: Fehler – {e}")

    total = updated + failed + unchanged
    log(f"[DB] Titel-Refresh abgeschlossen: {updated} aktualisiert, {unchanged} unverändert, {failed} fehlgeschlagen (von {total})")
    return {"updated": updated, "failed": failed, "unchanged": unchanged, "details": details}


# ────────────────────────── AniLoader.txt Import & Backup ──────────────────────────


def import_aniloader_txt(data_folder: str) -> Dict[str, int]:
    """
    Liest alle Links aus AniLoader.txt, fügt sie in die DB ein und leert die Datei.
    Gibt Statistiken über den Import zurück.
    """
    aniloader_txt = Path(data_folder) / "AniLoader.txt"
    
    if not aniloader_txt.exists():
        log("[IMPORT] AniLoader.txt nicht gefunden - überspringe Import")
        return {"imported": 0, "duplicates": 0, "errors": 0, "total_lines": 0}
    
    # Datei auslesen
    try:
        with open(aniloader_txt, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
    except Exception as e:
        log(f"[IMPORT-ERROR] Konnte AniLoader.txt nicht lesen: {e}")
        return {"imported": 0, "duplicates": 0, "errors": 1, "total_lines": 0}
    
    if not lines:
        log("[IMPORT] AniLoader.txt ist leer")
        return {"imported": 0, "duplicates": 0, "errors": 0, "total_lines": 0}
    
    log(f"[IMPORT] Starte Import von {len(lines)} Links aus AniLoader.txt")
    
    imported = 0
    duplicates = 0
    errors = 0
    
    for line_num, url in enumerate(lines, 1):
        try:
            # Prüfe ob gültige URL (einfache Validierung)
            if not (url.startswith('http://') or url.startswith('https://')):
                log(f"[IMPORT-WARN] Zeile {line_num}: Ungültige URL - {url}")
                errors += 1
                continue
            
            # Prüfe ob bereits vorhanden
            existing = get_anime_by_url(data_folder, url)
            if existing:
                log(f"[IMPORT-SKIP] Zeile {line_num}: URL bereits vorhanden - {url}")
                duplicates += 1
                continue
            
            # Füge zur Datenbank hinzu (mit echtem Titel von der Webseite)
            # Versuche echten Titel von der Webseite zu bekommen
            scraper = _get_scraper()
            try:
                title = scraper.get_series_title(url)
                if not title:
                    title = url  # Fallback zur URL wenn kein Titel gefunden
            except Exception as title_error:
                log(f"[IMPORT-WARN] Zeile {line_num}: Titel konnte nicht abgerufen werden ({title_error}) - nutze URL als Titel")
                title = url
            
            # In Datenbank einfügen
            conn = _connect(data_folder)
            try:
                c = conn.cursor()
                c.execute("INSERT INTO anime (url, title) VALUES (?, ?)", (url, title))
                conn.commit()
                if c.rowcount > 0:
                    log(f"[IMPORT] Zeile {line_num}: Importiert - {title} ({url})")
                    imported += 1
                else:
                    log(f"[IMPORT-ERROR] Zeile {line_num}: Unbekannter Fehler bei - {url}")
                    errors += 1
            finally:
                conn.close()
                
        except Exception as e:
            log(f"[IMPORT-ERROR] Zeile {line_num}: {e} - {url}")
            errors += 1
    
    # AniLoader.txt leeren
    try:
        with open(aniloader_txt, "w", encoding="utf-8") as f:
            f.truncate(0)
        log(f"[IMPORT] AniLoader.txt geleert nach erfolgreichem Import")
    except Exception as e:
        log(f"[IMPORT-ERROR] Konnte AniLoader.txt nicht leeren: {e}")
        errors += 1
    
    # Komplettes Backup regenerieren
    regenerate_aniloader_backup(data_folder)
    
    log(f"[IMPORT] Import abgeschlossen: {imported} importiert, {duplicates} Duplikate, {errors} Fehler (von {len(lines)} Zeilen)")
    
    return {
        "imported": imported,
        "duplicates": duplicates,
        "errors": errors,
        "total_lines": len(lines)
    }


def _update_aniloader_backup(data_folder: str, url: str) -> None:
    """Fügt eine einzelne URL zur AniLoader.txt.bak hinzu."""
    backup_file = Path(data_folder) / "AniLoader.txt.bak"
    
    try:
        # Prüfe ob URL bereits in Backup vorhanden
        if backup_file.exists():
            with open(backup_file, "r", encoding="utf-8") as f:
                existing_urls = {line.strip() for line in f if line.strip()}
            if url in existing_urls:
                return  # URL bereits im Backup
        
        # URL zur Backup-Datei hinzufügen
        with open(backup_file, "a", encoding="utf-8") as f:
            f.write(f"{url}\n")
            
    except Exception as e:
        log(f"[BACKUP-ERROR] Konnte AniLoader.txt.bak nicht aktualisieren: {e}")


def regenerate_aniloader_backup(data_folder: str) -> None:
    """Regeneriert die komplette AniLoader.txt.bak aus der Datenbank."""
    backup_file = Path(data_folder) / "AniLoader.txt.bak"
    
    try:
        # Alle URLs aus der Datenbank abrufen
        conn = _connect(data_folder)
        try:
            c = conn.cursor()
            c.execute("SELECT url FROM anime WHERE deleted = 0 ORDER BY id")
            urls = [row["url"] for row in c.fetchall()]
        finally:
            conn.close()
        
        # Backup-Datei komplett überschreiben
        with open(backup_file, "w", encoding="utf-8") as f:
            for url in urls:
                f.write(f"{url}\n")
        
        log(f"[BACKUP] AniLoader.txt.bak regeneriert mit {len(urls)} URLs")
        
    except Exception as e:
        log(f"[BACKUP-ERROR] Konnte AniLoader.txt.bak nicht regenerieren: {e}")
