"""
AniLoader – SQLite-Datenbankschicht.

Flat-Schema mit einer `anime`-Tabelle für Serien und Animes.
Thread-safe über separate Connections pro Aufruf.
AniLoader.txt Import- und Backup-Funktionalität.
"""

import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from .logger import log

# Verzögerter Import um zirkuläre Abhängigkeiten zu vermeiden
def _get_scraper():
    from . import scraper
    return scraper


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
            complete INTEGER DEFAULT 0,
            deutsch_komplett INTEGER DEFAULT 0,
            deleted INTEGER DEFAULT 0,
            fehlende_deutsch_folgen TEXT DEFAULT '[]',
            last_film INTEGER DEFAULT 0,
            last_episode INTEGER DEFAULT 0,
            last_season INTEGER DEFAULT 0,
            folder_name TEXT DEFAULT NULL
        )
    """)

    # Migration: folder_name Spalte
    try:
        c.execute("PRAGMA table_info(anime)")
        cols = [r["name"] for r in c.fetchall()]
        if "folder_name" not in cols:
            c.execute("ALTER TABLE anime ADD COLUMN folder_name TEXT DEFAULT NULL")
            log("[DB] folder_name Spalte hinzugefügt")
    except Exception as e:
        log(f"[DB-ERROR] Migration folder_name: {e}")

    conn.commit()
    conn.close()
    log("[DB] Datenbank initialisiert")


# ────────────────────────── CRUD ──────────────────────────


def add_anime(data_folder: str, url: str, title: Optional[str] = None) -> Optional[int]:
    """Fügt eine Serie/Anime hinzu. Gibt die ID zurück oder None bei Duplikat."""
    conn = _connect(data_folder)
    try:
        c = conn.cursor()
        c.execute(
            "INSERT OR IGNORE INTO anime (url, title) VALUES (?, ?)",
            (url, title or url),
        )
        conn.commit()
        if c.rowcount > 0:
            log(f"[DB] Hinzugefügt: {title or url}")
            # Backup-Datei aktualisieren
            _update_aniloader_backup(data_folder, url)
            return c.lastrowid
        else:
            # Already exists – return existing ID
            c.execute("SELECT id FROM anime WHERE url = ?", (url,))
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
        return [dict(row) for row in c.fetchall()]
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
    """Stellt einen gelöschten Eintrag wieder her."""
    conn = _connect(data_folder)
    try:
        conn.execute("UPDATE anime SET deleted = 0 WHERE id = ?", (anime_id,))
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
    added = 0
    for line in content.strip().splitlines():
        url = line.strip()
        if not url or url.startswith("#"):
            continue
        if "aniworld.to" in url or "s.to" in url:
            result = add_anime(data_folder, url)
            if result:
                added += 1
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
