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

# Ensure project root is importable (contains app/ package)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from app.config import VALID_LANGUAGES, get_data_folder, load_config
from app import database as db
from app import file_manager as fm

BEHALTEN = object()  # Sentinel – diesen Wert bitte nicht ändern
DELETE   = object()  # Sentinel – Feld auf Default-Wert zurücksetzen

# ══════════════════════════════════════════════════════
#  KONFIGURATION – hier anpassen
# ══════════════════════════════════════════════════════

# ID des Eintrags der bearbeitet werden soll
ANIME_ID = 1

# Felder setzen – nicht gewünschte Felder auf BEHALTEN lassen
# Zum expliziten Löschen/Zurücksetzen: DELETE

title               = BEHALTEN      # z.B. "My Hero Academia"
url                 = BEHALTEN      # z.B. "https://aniworld.to/anime/stream/..."
complete            = BEHALTEN      # 0 oder 1
deutsch_komplett    = BEHALTEN      # 0 oder 1
deleted             = BEHALTEN      # 0 oder 1
last_season         = BEHALTEN      # z.B. 3
last_episode        = BEHALTEN      # z.B. 12
last_film           = BEHALTEN      # z.B. 0
folder_name         = BEHALTEN      # z.B. "My.Hero.Academia"  |  None = leeren
fehlende_deutsch_folgen = BEHALTEN  # z.B. "[]"

# Gewünschte Sprachen dieses Eintrags (Mehrsprach-Download).
#   BEHALTEN            = nicht ändern
#   []                  = keine eigene Auswahl → globale Kaskade aus config.yaml
#                         (löscht KEINE Dateien)
#   ["German Dub", ...] = genau diese Sprachen werden geladen
# Erlaubt: "German Dub", "German Sub", "English Dub", "English Sub"
# ⚠ Wird eine Sprache aus einer bestehenden Auswahl entfernt, werden die
#   Episodendateien GENAU DIESER Sprache gelöscht (mit Vorschau + Rückfrage).
languages           = BEHALTEN      # z.B. ["German Dub", "English Sub"]

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
    entry_languages = db.parse_languages(row.get("languages"))
    lines.append(
        f"  Sprachen        : {', '.join(entry_languages) if entry_languages else '– (globale Kaskade)'}"
    )
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

    # Sprachen laufen über einen eigenen Pfad, weil beim Entfernen einer Sprache
    # deren Episodendateien gelöscht werden.
    new_languages = None
    removed_languages = []
    if languages is not BEHALTEN:
        raw = [] if languages is DELETE else (languages or [])
        invalid = [l for l in raw if l not in VALID_LANGUAGES]
        if invalid:
            print(f"\n✗ Ungültige Sprachen: {invalid}\n  Erlaubt: {VALID_LANGUAGES}")
            sys.exit(1)
        new_languages = list(raw)
        current = db.parse_languages(row.get("languages"))
        removed_languages = [l for l in current if l not in new_languages]

    if not updates and new_languages is None:
        print("\nKeine Änderungen definiert (alle Felder auf BEHALTEN).")
        return

    print("\n── Geplante Änderungen ──────────────────────────────────")
    for k, v in updates.items():
        alt = row.get(k)
        display_v = f"<DEFAULT: {repr(v)}>" if local_vars[k] is DELETE else repr(v)
        print(f"  {k:28} {repr(alt):30} → {display_v}")

    if new_languages is not None:
        alt_langs = db.parse_languages(row.get("languages"))
        print(f"  {'languages':28} {repr(alt_langs):30} → {repr(new_languages)}")

    # Vorschau der Löschungen (Dry-Run, es wird noch nichts angefasst)
    to_delete = []
    if removed_languages and new_languages:
        cfg = load_config()
        for language in removed_languages:
            preview = fm.delete_language_files(
                cfg, row["url"], row.get("folder_name"), language, dry_run=True
            )
            to_delete.extend(preview["deleted"])
            for err in preview["errors"]:
                print(f"  ⚠ {err}")

        print(f"\n── Zu löschende Dateien ({', '.join(removed_languages)}) ──")
        if to_delete:
            for path in to_delete:
                print(f"  ✗ {path}")
            print(f"\n  {len(to_delete)} Datei(en) werden GELÖSCHT.")
        else:
            print("  (keine passenden Dateien gefunden)")
    elif removed_languages:
        print("\n  Hinweis: Auswahl wird geleert (globale Kaskade) – es werden KEINE Dateien gelöscht.")

    confirm = input("\nÜbernehmen? [j/N] ").strip().lower()
    if confirm != "j":
        print("Abgebrochen.")
        return

    ok = True
    if updates:
        ok = db.update_anime(data_folder, ANIME_ID, **updates)

    if new_languages is not None:
        result = db.apply_language_selection(
            data_folder, ANIME_ID, new_languages, delete_files=True
        )
        if result is None:
            ok = False
        else:
            if result["deleted_files"]:
                print(f"\n✓ {len(result['deleted_files'])} Datei(en) gelöscht.")
            for err in result["errors"]:
                print(f"  ⚠ {err}")
            if result["added"]:
                print(f"✓ Neue Sprachen {result['added']} – Fortschritt zurückgesetzt, "
                      f"fehlende Episoden werden beim nächsten Lauf nachgeladen.")

    if ok:
        print("\n✓ Gespeichert.\n")
        updated = db.get_anime_by_id(data_folder, ANIME_ID)
        if updated:
            print(fmt_row(updated))
    else:
        print("✗ Fehler beim Speichern.")


if __name__ == "__main__":
    main()
