#!/usr/bin/env python3
"""
fix_sub_db_inconsistencies.py

Liest den Report von find_sub_db_inconsistencies.sh und trägt die betroffenen
Episoden-URLs in fehlende_deutsch_folgen der Datenbank ein.
Setzt außerdem deutsch_komplett = 0 für alle betroffenen Einträge.

Verwendung:
    python fix_sub_db_inconsistencies.py <report_datei> [--db <pfad>] [--dry-run]

Optionen:
    report_datei    Pfad zur Ausgabedatei von find_sub_db_inconsistencies.sh
    --db            Pfad zur AniLoader.db (überschreibt den Pfad aus dem Report-Header)
    --dry-run       Zeigt nur an, was geändert würde, ohne die DB zu schreiben
"""

import argparse
import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path


# ──────────────────────── URL-Logik (analog zu app/scraper.py) ────────────────────────

def is_sto(url: str) -> bool:
    return "s.to" in url


def build_episode_url(series_url: str, season: int, episode: int) -> str:
    """Baut die Episoden-URL analog zu scraper.build_episode_url."""
    if season == 0:
        if is_sto(series_url):
            return f"{series_url}/staffel-0/episode-{episode}"
        else:
            return f"{series_url}/filme/film-{episode}"
    return f"{series_url}/staffel-{season}/episode-{episode}"


def get_base_url(url: str) -> str:
    """Gibt die Serien-Basis-URL ohne Staffel/Episode zurück."""
    url = url.strip().rstrip("/")
    if "aniworld.to" in url:
        m = re.match(r"(https://aniworld\.to/anime/stream/[^/]+)", url, re.IGNORECASE)
        return m.group(1) if m else url
    if "s.to" in url:
        m = re.match(r"(https://s\.to/serie/[^/]+)", url, re.IGNORECASE)
        return m.group(1) if m else url
    return url


# ──────────────────────── Report-Parser ────────────────────────

def parse_report(report_path: Path):
    """
    Parst die Report-Datei von find_sub_db_inconsistencies.sh.

    Gibt zurück:
        db_path_from_header (str | None)
        issues: list of {anime_id, title, series_url, folder_name, file_path, episode_key}
    """
    if not report_path.exists():
        print(f"[ERROR] Report-Datei nicht gefunden: {report_path}", file=sys.stderr)
        sys.exit(1)

    text = report_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    db_path_from_header = None
    for line in lines[:15]:
        m = re.match(r"^DB:\s*(.+)", line.strip())
        if m:
            db_path_from_header = m.group(1).strip()
            break

    issues = []
    current: dict = {}
    for line in lines:
        line = line.strip()

        m = re.match(r"^ID:\s*(\d+)$", line)
        if m:
            current = {"anime_id": int(m.group(1))}
            continue

        m = re.match(r"^Titel:\s*(.+)$", line)
        if m and "anime_id" in current:
            current["title"] = m.group(1)
            continue

        m = re.match(r"^Serie-URL:\s*(.+)$", line)
        if m and "anime_id" in current:
            current["series_url"] = m.group(1).strip()
            continue

        m = re.match(r"^Ordner:\s*(.+)$", line)
        if m and "anime_id" in current:
            current["folder_name"] = m.group(1)
            continue

        m = re.match(r"^Datei:\s*(.+)$", line)
        if m and "anime_id" in current:
            current["file_path"] = m.group(1)
            continue

        m = re.match(r"^Episode-Key:\s*(\d+):(\d+)$", line)
        if m and "anime_id" in current:
            current["season"] = int(m.group(1))
            current["episode"] = int(m.group(2))
            current["episode_key"] = f"{m.group(1)}:{m.group(2)}"
            continue

        if line.startswith("---") and "anime_id" in current:
            if "season" in current and "series_url" in current:
                issues.append(dict(current))
            current = {}

    return db_path_from_header, issues


# ──────────────────────── DB-Operationen ────────────────────────

def load_current_missing(conn: sqlite3.Connection, anime_id: int) -> list:
    """Lädt die aktuelle fehlende_deutsch_folgen-Liste eines Eintrags."""
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT fehlende_deutsch_folgen FROM anime WHERE id = ?", (anime_id,)
    ).fetchone()
    if not row:
        return []
    raw = row["fehlende_deutsch_folgen"] or "[]"
    try:
        result = json.loads(raw)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def apply_fixes(db_path: Path, issues: list, dry_run: bool) -> None:
    """
    Verarbeitet alle gefundenen Inkonsistenzen und schreibt sie in die DB.

    Für jeden betroffenen DB-Eintrag:
    - Fehlende Episoden-URLs werden in fehlende_deutsch_folgen ergänzt
    - deutsch_komplett wird auf 0 gesetzt
    """
    # Gruppieren nach anime_id
    by_id: dict[int, dict] = {}
    for issue in issues:
        aid = issue["anime_id"]
        if aid not in by_id:
            by_id[aid] = {
                "title": issue.get("title", ""),
                "series_url": issue["series_url"],
                "new_episodes": [],
            }
        base = get_base_url(issue["series_url"])
        ep_url = build_episode_url(base, issue["season"], issue["episode"])
        by_id[aid]["new_episodes"].append((issue["season"], issue["episode"], ep_url))

    if not by_id:
        print("[INFO] Keine Einträge zu verarbeiten.")
        return

    print(f"\n{'DRY-RUN – keine Änderungen werden gespeichert' if dry_run else 'DB-Update'}")
    print("=" * 60)

    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")

    total_added = 0
    total_series = 0

    try:
        for anime_id, data in sorted(by_id.items()):
            current_missing = load_current_missing(conn, anime_id)
            current_set = set(current_missing)

            to_add = []
            for season, episode, ep_url in sorted(data["new_episodes"]):
                if ep_url not in current_set:
                    to_add.append(ep_url)
                    current_set.add(ep_url)

            if not to_add:
                print(f"\n[SKIP] ID {anime_id} – {data['title']}: alle URLs bereits vorhanden")
                continue

            updated_missing = current_missing + to_add

            print(f"\n[UPDATE] ID {anime_id} – {data['title']}")
            for url in to_add:
                print(f"  + {url}")

            if not dry_run:
                conn.execute(
                    "UPDATE anime SET fehlende_deutsch_folgen = ?, deutsch_komplett = 0 WHERE id = ?",
                    (json.dumps(updated_missing, ensure_ascii=False), anime_id),
                )

            total_added += len(to_add)
            total_series += 1

        if not dry_run:
            conn.commit()
            print(f"\n[OK] {total_added} Episode(n) in {total_series} Serie(n) eingetragen.")
        else:
            print(f"\n[DRY-RUN] Würde {total_added} Episode(n) in {total_series} Serie(n) eintragen.")

    finally:
        conn.close()


# ──────────────────────── Main ────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Trägt [Sub]-Inkonsistenzen aus dem Report in die AniLoader-DB ein.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  python fix_sub_db_inconsistencies.py data/sub_db_inconsistencies_20260429_095126.txt
  python fix_sub_db_inconsistencies.py report.txt --db data/AniLoader.db
  python fix_sub_db_inconsistencies.py report.txt --dry-run
        """,
    )
    parser.add_argument("report", help="Pfad zur Report-Datei von find_sub_db_inconsistencies.sh")
    parser.add_argument("--db", help="Pfad zur AniLoader.db (überschreibt DB-Pfad aus Report)", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Keine Änderungen schreiben, nur anzeigen")
    args = parser.parse_args()

    report_path = Path(args.report)
    print(f"[INFO] Lese Report: {report_path}")

    db_path_from_header, issues = parse_report(report_path)

    if not issues:
        print("[INFO] Report enthält keine Inkonsistenzen – nichts zu tun.")
        sys.exit(0)

    print(f"[INFO] {len(issues)} Inkonsistenz(en) gefunden.")

    # DB-Pfad bestimmen
    if args.db:
        db_path = Path(args.db)
    elif db_path_from_header:
        db_path = Path(db_path_from_header)
    else:
        # Fallback: data/AniLoader.db relativ zum Script-Verzeichnis
        db_path = Path(__file__).resolve().parent.parent / "data" / "AniLoader.db"
        print(f"[WARN] Kein DB-Pfad im Report gefunden, verwende Fallback: {db_path}")

    if not db_path.exists():
        print(f"[ERROR] DB nicht gefunden: {db_path}", file=sys.stderr)
        print("        Verwende --db <pfad> um den Pfad manuell anzugeben.", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] DB: {db_path}")

    if args.dry_run:
        print("[INFO] Dry-run Modus – keine Änderungen werden geschrieben")

    apply_fixes(db_path, issues, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
