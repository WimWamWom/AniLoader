#!/usr/bin/env python3
"""
AniLoader – Datenbank-Editor

Variablen unten anpassen und Skript ausführen.
Felder die auf BEHALTEN bleiben, werden nicht geändert.
Felder die auf "" oder 0 gesetzt werden, werden explizit geleert.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import get_data_folder, load_config
from app import database as db

# ══════════════════════════════════════════════════════
#  KONFIGURATION – hier anpassen
# ══════════════════════════════════════════════════════

# ID des Eintrags der bearbeitet werden soll
ANIME_ID = 1

# Felder setzen – nicht gewünschte Felder auf BEHALTEN lassen
# Zum expliziten Löschen/Zurücksetzen: None (Text) oder 0 (Zahlen)

BEHALTEN = object()  # Sentinel – diesen Wert bitte nicht ändern
DELETE   = object()  # Sentinel – Feld auf Default-Wert zurücksetzen

# Default-Werte gemäß DB-Schema

title               = BEHALTEN   # z.B. "My Hero Academia"
url                 = BEHALTEN   # z.B. "https://aniworld.to/anime/stream/..."
complete            = BEHALTEN  # 0 oder 1
deutsch_komplett    = BEHALTEN  # 0 oder 1
deleted             = BEHALTEN  # 0 oder 1
last_season         = BEHALTEN   # z.B. 3
last_episode        = BEHALTEN   # z.B. 12
last_film           = BEHALTEN   # z.B. 0
folder_name         = BEHALTEN   # z.B. "My.Hero.Academia"  |  None = leeren
fehlende_deutsch_folgen = BEHALTEN # z.B. "[]"

# ══════════════════════════════════════════════════════
#  AB HIER NICHTS ÄNDERN
# ══════════════════════════════════════════════════════

EDITABLE_FIELDS = [
    "title", "url", "complete", "deutsch_komplett", "deleted",
    "last_season", "last_episode", "last_film",
    "folder_name", "fehlende_deutsch_folgen",
]

INT_FIELDS = {"complete", "deutsch_komplett", "deleted", "last_season", "last_episode", "last_film"}
FIELD_DEFAULTS = {
    "complete":                0,
    "deutsch_komplett":        0,
    "deleted":                 0,
    "last_season":             0,
    "last_episode":            0,
    "last_film":               0,
    "fehlende_deutsch_folgen": "[]",
    "folder_name":             None,
    "title":                   None,
    "url":                     None,
}


def get_data_folder_path() -> str:
    try:
        cfg = load_config()
        return get_data_folder(cfg)
    except Exception:
        return str(Path(__file__).resolve().parent / "data")


def fmt_row(row: dict) -> str:
    lines = [f"  ID              : {row['id']}"]
    lines.append(f"  Titel           : {row.get('title', '–')}")
    lines.append(f"  URL             : {row.get('url', '–')}")
    lines.append(f"  Komplett        : {row.get('complete', 0)}")
    lines.append(f"  DE komplett     : {row.get('deutsch_komplett', 0)}")
    lines.append(f"  Gelöscht        : {row.get('deleted', 0)}")
    lines.append(f"  Letzte Staffel  : {row.get('last_season', 0)}")
    lines.append(f"  Letzte Episode  : {row.get('last_episode', 0)}")
    lines.append(f"  Letzter Film    : {row.get('last_film', 0)}")
    lines.append(f"  Ordnername      : {row.get('folder_name') or '–'}")
    try:
        missing = json.loads(row.get("fehlende_deutsch_folgen") or "[]")
        lines.append(f"  Fehlende DE     : {len(missing)} Einträge")
    except Exception:
        lines.append(f"  Fehlende DE     : {row.get('fehlende_deutsch_folgen', '[]')}")
    return "\n".join(lines)


def main() -> None:
    data_folder = get_data_folder_path()

    row = db.get_anime_by_id(data_folder, ANIME_ID)
    if not row:
        print(f"Kein Eintrag mit ID {ANIME_ID} gefunden.")
        sys.exit(1)

    print(f"\n── Aktueller Stand: Eintrag #{ANIME_ID} ─────────────────────")
    print(fmt_row(row))

    # Variablen aus dem Konfigurations-Block einlesen
    local_vars = {
        "title": title,
        "url": url,
        "complete": complete,
        "deutsch_komplett": deutsch_komplett,
        "deleted": deleted,
        "last_season": last_season,
        "last_episode": last_episode,
        "last_film": last_film,
        "folder_name": folder_name,
        "fehlende_deutsch_folgen": fehlende_deutsch_folgen,
    }

    updates = {
        k: (FIELD_DEFAULTS.get(k) if v is DELETE else v)
        for k, v in local_vars.items()
        if v is not BEHALTEN
    }

    if not updates:
        print("\nKeine Änderungen definiert (alle Felder auf BEHALTEN).")
        return

    print("\n── Geplante Änderungen ──────────────────────────────────")
    for k, v in updates.items():
        alt = row.get(k)
        display_v = f"<DEFAULT: {repr(v)}>" if local_vars[k] is DELETE else repr(v)
        print(f"  {k:28} {repr(alt):30} → {display_v}")

    confirm = input("\nÜbernehmen? [j/N] ").strip().lower()
    if confirm != "j":
        print("Abgebrochen.")
        return

    ok = db.update_anime(data_folder, ANIME_ID, **updates)
    if ok:
        print("\n✓ Gespeichert.\n")
        updated = db.get_anime_by_id(data_folder, ANIME_ID)
        if updated:
            print(fmt_row(updated))
    else:
        print("✗ Fehler beim Speichern.")


if __name__ == "__main__":
    main()
