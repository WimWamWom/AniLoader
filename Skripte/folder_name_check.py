#!/usr/bin/env python3
"""
Prueft, ob Titel und Ordnername in der AniLoader-Datenbank zusammenpassen.

Ignoriert typische Ordner-Zusaetze wie:
- (1983)
- [imdbid-tt0175863]
"""

from __future__ import annotations

import argparse
import html
import re
import sys
import unicodedata
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app import database as db
from app.config import get_data_folder, load_config


YEAR_SUFFIX_RE = re.compile(r"\s*\((?:19|20)\d{2}(?:\s*-\s*(?:19|20)\d{2})?\)\s*$")
IMDB_SUFFIX_RE = re.compile(r"\s*\[(?:imdb[^\]]*|tt\d+)\]\s*$", re.IGNORECASE)
SEPARATOR_RE = re.compile(r"[._\-]+")
NON_ALNUM_RE = re.compile(r"[^\w\s]")
WHITESPACE_RE = re.compile(r"\s+")


def get_data_folder_path() -> str:
    try:
        cfg = load_config()
        return get_data_folder(cfg)
    except Exception:
        return str(PROJECT_ROOT / "data")


def strip_known_suffixes(folder_name: str) -> str:
    cleaned = folder_name.strip()
    while cleaned:
        updated = YEAR_SUFFIX_RE.sub("", cleaned)
        updated = IMDB_SUFFIX_RE.sub("", updated)
        updated = updated.strip()
        if updated == cleaned:
            break
        cleaned = updated
    return cleaned


def strip_one_known_suffix(folder_name: str) -> str:
    cleaned = folder_name.strip()

    updated = IMDB_SUFFIX_RE.sub("", cleaned).strip()
    if updated != cleaned:
        return updated

    updated = YEAR_SUFFIX_RE.sub("", cleaned).strip()
    if updated != cleaned:
        return updated

    return cleaned


def folder_name_candidates(value: str | None) -> list[str]:
    if not value:
        return [""]

    current = Path(value).name.strip()
    candidates = [current]

    while current:
        updated = strip_one_known_suffix(current)
        if updated == current:
            break
        candidates.append(updated)
        current = updated

    return candidates


def normalize_name(value: str | None, *, is_folder: bool = False) -> str:
    if not value:
        return ""

    text = Path(value).name.strip() if is_folder else value.strip()
    text = html.unescape(text)
    if is_folder:
        text = strip_known_suffixes(text)

    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = SEPARATOR_RE.sub(" ", text)
    text = NON_ALNUM_RE.sub(" ", text)
    text = WHITESPACE_RE.sub(" ", text).strip().casefold()
    return text


def comparable_name(value: str | None, *, is_folder: bool = False) -> str:
    normalized = normalize_name(value, is_folder=is_folder)
    return normalized.replace(" ", "")


def iter_mismatches(data_folder: str, include_deleted: bool) -> list[dict[str, object]]:
    mismatches: list[dict[str, object]] = []
    rows = db.get_all_anime(data_folder, include_deleted=include_deleted)

    for row in rows:
        title = row.get("title")
        folder_name = row.get("folder_name")
        normalized_title = normalize_name(title)
        comparable_title = comparable_name(title)
        folder_candidates = folder_name_candidates(folder_name)
        comparable_candidates = [comparable_name(candidate) for candidate in folder_candidates]
        normalized_candidates = [normalize_name(candidate) for candidate in folder_candidates]

        if comparable_title and comparable_title in comparable_candidates:
            continue

        normalized_folder = normalized_candidates[-1] if normalized_candidates else ""

        mismatches.append(
            {
                "id": row.get("id"),
                "title": title or "",
                "folder_name": folder_name or "",
                "normalized_title": normalized_title,
                "normalized_folder": normalized_folder,
                "deleted": row.get("deleted", 0),
            }
        )

    return mismatches


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Vergleicht Titel und folder_name in der AniLoader-Datenbank.",
    )
    parser.add_argument(
        "--include-deleted",
        action="store_true",
        help="Auch geloeschte Eintraege pruefen.",
    )
    return parser


def format_separator(char: str = "=") -> str:
    return char * 78


def format_entry_header(entry: dict[str, object]) -> str:
    status = " [deleted]" if entry["deleted"] else ""
    return f"ID {entry['id']}{status}"


def print_section(title: str, entries: list[dict[str, object]], *, show_comparison: bool) -> None:
    print(f"\n{title} ({len(entries)})")
    print(format_separator("-"))

    for entry in entries:
        print(format_entry_header(entry))
        print(f"  Titel     : {entry['title'] or '–'}")
        print(f"  Ordner    : {entry['folder_name'] or '–'}")
        if show_comparison:
            print(f"  Normalisiert Titel  : {entry['normalized_title'] or '–'}")
            print(f"  Normalisiert Ordner : {entry['normalized_folder'] or '–'}")
        print()


def main() -> int:
    args = build_parser().parse_args()
    data_folder = get_data_folder_path()
    mismatches = iter_mismatches(data_folder, include_deleted=args.include_deleted)

    if not mismatches:
        print("Alle geprueften Titel passen zu den Ordnernamen.")
        return 0

    missing_folder = [entry for entry in mismatches if not entry["folder_name"]]
    differing_folder = [entry for entry in mismatches if entry["folder_name"]]

    print(format_separator())
    print("Pruefung Titel <-> Ordnername")
    print(format_separator())
    print(f"Gepruefte Abweichungen : {len(mismatches)}")
    print(f"Fehlender Ordnername  : {len(missing_folder)}")
    print(f"Abweichender Ordner   : {len(differing_folder)}")

    if differing_folder:
        print_section("Abweichender Ordnername", differing_folder, show_comparison=True)

    if missing_folder:
        print_section("Fehlender Ordnername", missing_folder, show_comparison=False)

    print(format_separator())
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
