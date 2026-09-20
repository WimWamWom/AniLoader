"""
AniLoader – YAML-Konfigurationsmanagement.

Lädt, validiert und speichert die config.yaml.
Erstellt bei Bedarf eine Standardkonfiguration.
"""

import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .domains import DEFAULT_DOMAINS

try:
    from croniter import croniter
except Exception:  # pragma: no cover - fallback if optional dependency is missing
    croniter = None

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = BASE_DIR / "data"
DEFAULT_DOWNLOAD_DIR = BASE_DIR / "Downloads"

DEFAULT_CONFIG: Dict[str, Any] = {
    "server": {
        "port": 5050,
    },
    "languages": [
        "German Dub",
        "German Sub",
        "English Sub",
        "English Dub",
    ],
    # Domains der unterstützten Plattformen. `canonical` wird gespeichert und
    # ausgegeben, `aliases` nur als Eingabe akzeptiert und normalisiert.
    # Neue Mirror-Domain? Einfach unter aliases ergänzen. Details: app/domains.py
    "domains": {
        platform: {"canonical": entry["canonical"], "aliases": list(entry["aliases"])}
        for platform, entry in DEFAULT_DOMAINS.items()
    },
    "storage": {
        "mode": "standard",  # standard | separate
        "download_path": str(DEFAULT_DOWNLOAD_DIR),
        "anime_path": str(BASE_DIR / "Anime"),
        "series_path": str(BASE_DIR / "Serien"),
        "anime_movies_path": str(BASE_DIR / "Anime-Filme"),
        "serien_movies_path": str(BASE_DIR / "Serien-Filme"),
        "anime_separate_movies": False,
        "serien_separate_movies": False,
        "film_naming_mode": "local",  # local | jellyfin
    },
    "download": {
        "min_free_gb": 2.0,
        "autostart_mode": None,  # null | default | german | new | check | german_new
        "timeout_seconds": 900,
        "refresh_titles": False,
    },
    "automation": {
        "enabled": False,
        "german": {
            "enabled": False,
            "schedule": "0 3 * * 0",
            "interval_minutes": 0,
            "discord_webhook": "",
            "notify_on_empty": False,
            "hide_failed_checks": False,
            "filter_mode": "whitelist",
            "whitelist": [],
            "blacklist": [],
        },
        "new": {
            "enabled": False,
            "schedule": "0 */6 * * *",
            "interval_minutes": 0,
            "discord_webhook": "",
            "notify_on_empty": False,
            "hide_failed_checks": False,
            "filter_mode": "whitelist",
            "whitelist": [],
            "blacklist": [],
        },
        "german_new": {
            "enabled": False,
            "schedule": "",
            "interval_minutes": 0,
            "discord_webhook": "",
            "notify_on_empty": False,
            "hide_failed_checks": False,
            "filter_mode": "whitelist",
            "whitelist": [],
            "blacklist": [],
        },
    },
    "data": {
        "folder": str(DEFAULT_DATA_DIR),
    },
    "logging": {
        "log_retention_days": 7,
        # debug | info | warn – steuert, was ueberhaupt geschrieben wird.
        # Details siehe app/logger.py.
        "level": "info",
    },
}

VALID_LANGUAGES = ["German Dub", "German Sub", "English Dub", "English Sub"]
VALID_LOG_LEVELS = ["debug", "info", "warn"]
VALID_MODES = [None, "default", "german", "new", "check", "german_new"]
VALID_STORAGE_MODES = ["standard", "separate"]
VALID_FILM_NAMING_MODES = ["local", "jellyfin"]
AUTOMATION_MODES = ["german", "new", "german_new"]


# ──────────────────────── Sprach-Normalisierung ────────────────────────
# Zentral hier, damit Downloader (gescrapte Labels) und Datenbank
# (gewünschte Sprachen pro Eintrag) dieselben Namen verwenden.

_LANGUAGE_ALIASES = {
    "german dub": "German Dub",
    "german": "German Dub",
    "deutsch": "German Dub",
    "de": "German Dub",
    "german sub": "German Sub",
    "deutsch sub": "German Sub",
    "deutsch untertitel": "German Sub",
    "english dub": "English Dub",
    "english": "English Dub",
    "en": "English Dub",
    "english sub": "English Sub",
    "englisch sub": "English Sub",
    "englische untertitel": "English Sub",
}


def normalize_language_label(label: Any) -> str:
    """
    Normalisiert ein Sprach-Label auf einen internen Namen.

    Unbekannte Labels werden unverändert (nur getrimmt) zurückgegeben, damit
    gescrapte Sprachen von der Webseite nicht verloren gehen.
    """
    text = str(label or "").strip()
    return _LANGUAGE_ALIASES.get(text.lower(), text)


def normalize_language_list(languages: Any, strict: bool = False) -> List[str]:
    """
    Normalisiert eine Sprachliste, entfernt Duplikate, behält die Reihenfolge.

    Args:
        languages: Liste beliebiger Sprach-Labels
        strict:    True → nur Sprachen aus VALID_LANGUAGES behalten
                   (für die gewünschten Sprachen eines DB-Eintrags)
    """
    if not isinstance(languages, (list, tuple, set)):
        return []

    normalized: List[str] = []
    seen: set = set()
    for lang in languages:
        norm = normalize_language_label(lang)
        if not norm or norm in seen:
            continue
        if strict and norm not in VALID_LANGUAGES:
            continue
        seen.add(norm)
        normalized.append(norm)
    return normalized


def sort_languages_by_priority(languages: List[str], cfg: Optional[dict] = None) -> List[str]:
    """
    Sortiert Sprachen nach der global konfigurierten Prioritäts-Kaskade.

    Dadurch wird bei Mehrsprach-Einträgen immer zuerst die höchstpriorisierte
    Sprache (i.d.R. German Dub) geladen. Unbekannte Sprachen landen am Ende.
    """
    priority = (cfg or {}).get("languages") or DEFAULT_CONFIG["languages"]
    order = {lang: idx for idx, lang in enumerate(priority)}
    return sorted(languages, key=lambda lang: (order.get(lang, len(order)), lang))


def _is_valid_webhook_url(url: str) -> bool:
    if not url:
        return True
    if not isinstance(url, str):
        return False
    return url.startswith("https://") or url.startswith("http://")


def _validate_string_list(values: Any) -> bool:
    return isinstance(values, list) and all(isinstance(v, str) for v in values)


def _is_bare_host(value: Any) -> bool:
    """Prüft, ob ein Wert ein reiner Host ist ('serienstream.to', '186.2.175.5')."""
    text = str(value or "").strip()
    if not text:
        return False
    return "://" not in text and "/" not in text and " " not in text


def _is_hidden_final_folder(path_value: Any) -> bool:
    """Prüft, ob das finale Pfadsegment (letzter Ordnername) mit '.' beginnt.

    Nur das letzte Segment wird geprüft – Zwischensegmente mit Punkt sind erlaubt:
      OK:      /app/Downloads           → letztes Segment 'Downloads'
      OK:      /app/.hidden/lokal       → letztes Segment 'lokal'
      FEHLER:  /app/.Downloads          → letztes Segment '.Downloads'
    """
    if not isinstance(path_value, str):
        return False

    raw = path_value.strip()
    if not raw:
        return False

    folder_name = Path(raw).name
    return bool(folder_name) and folder_name.startswith(".")


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge override into base recursively, keeping base keys as defaults."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _get_config_path(data_folder: Optional[str] = None) -> Path:
    """Return the path to config.yaml."""
    folder = Path(data_folder) if data_folder else DEFAULT_DATA_DIR
    return folder / "config.yaml"


def _ensure_dirs(cfg: dict) -> None:
    """Create necessary directories from config."""
    data_folder = cfg.get("data", {}).get("folder", str(DEFAULT_DATA_DIR))
    os.makedirs(data_folder, exist_ok=True)

    storage = cfg.get("storage", {})
    mode = storage.get("mode", "standard")
    download_path = storage.get("download_path", str(DEFAULT_DOWNLOAD_DIR))
    os.makedirs(download_path, exist_ok=True)

    if mode == "separate":
        for key in ["anime_path", "series_path"]:
            p = storage.get(key)
            if p:
                os.makedirs(p, exist_ok=True)
        if storage.get("anime_separate_movies"):
            p = storage.get("anime_movies_path")
            if p:
                os.makedirs(p, exist_ok=True)
        if storage.get("serien_separate_movies"):
            p = storage.get("serien_movies_path")
            if p:
                os.makedirs(p, exist_ok=True)


def validate_config(cfg: dict) -> List[str]:
    """Validate config and return list of error messages (empty = valid)."""
    errors = []

    # Server
    port = cfg.get("server", {}).get("port", 5050)
    if not isinstance(port, int) or not (1 <= port <= 65535):
        errors.append(f"server.port muss zwischen 1 und 65535 liegen, ist: {port}")

    # Languages
    langs = cfg.get("languages", [])
    if not isinstance(langs, list) or len(langs) == 0:
        errors.append("languages muss eine nicht-leere Liste sein")
    else:
        for lang in langs:
            if lang not in VALID_LANGUAGES:
                errors.append(f"Ungültige Sprache: '{lang}'. Erlaubt: {VALID_LANGUAGES}")

    # Domains
    domains_cfg = cfg.get("domains", {})
    if not isinstance(domains_cfg, dict):
        errors.append("domains muss ein Objekt sein")
    else:
        for platform in DEFAULT_DOMAINS:
            entry = domains_cfg.get(platform, {})
            if not isinstance(entry, dict):
                errors.append(f"domains.{platform} muss ein Objekt sein")
                continue

            canonical = entry.get("canonical", "")
            if not isinstance(canonical, str) or not canonical.strip():
                errors.append(f"domains.{platform}.canonical darf nicht leer sein")
            elif not _is_bare_host(canonical):
                errors.append(
                    f"domains.{platform}.canonical muss ein reiner Host sein "
                    f"(ohne Protokoll und ohne '/'), ist: '{canonical}'"
                )

            aliases = entry.get("aliases", [])
            if not _validate_string_list(aliases):
                errors.append(f"domains.{platform}.aliases muss eine Liste von Strings sein")
            else:
                for alias in aliases:
                    if not _is_bare_host(alias):
                        errors.append(
                            f"domains.{platform}.aliases: '{alias}' muss ein reiner Host sein "
                            f"(ohne Protokoll und ohne '/')"
                        )

    # Storage
    storage = cfg.get("storage", {})
    mode = storage.get("mode", "standard")
    if mode not in VALID_STORAGE_MODES:
        errors.append(f"storage.mode muss 'standard' oder 'separate' sein, ist: '{mode}'")

    film_naming_mode = storage.get("film_naming_mode", "local")
    if film_naming_mode not in VALID_FILM_NAMING_MODES:
        errors.append(f"storage.film_naming_mode muss 'local' oder 'jellyfin' sein, ist: '{film_naming_mode}'")

    download_path = storage.get("download_path", "")
    if not download_path or not isinstance(download_path, str):
        errors.append("storage.download_path darf nicht leer sein")
    elif _is_hidden_final_folder(download_path):
        errors.append("storage.download_path darf nicht mit '.' beginnen")

    if mode == "separate":
        final_targets = [
            ("storage.anime_path", storage.get("anime_path")),
            ("storage.series_path", storage.get("series_path")),
        ]
        if storage.get("anime_separate_movies"):
            final_targets.append(("storage.anime_movies_path", storage.get("anime_movies_path")))
        if storage.get("serien_separate_movies"):
            final_targets.append(("storage.serien_movies_path", storage.get("serien_movies_path")))

        for key, path_value in final_targets:
            if _is_hidden_final_folder(path_value):
                errors.append(f"{key} darf nicht mit '.' beginnen")

    # Download
    dl = cfg.get("download", {})
    min_free = dl.get("min_free_gb", 2.0)
    if not isinstance(min_free, (int, float)) or min_free < 0:
        errors.append(f"download.min_free_gb muss >= 0 sein, ist: {min_free}")

    autostart = dl.get("autostart_mode")
    if autostart is not None and autostart not in VALID_MODES:
        errors.append(f"download.autostart_mode ungültig: '{autostart}'")

    # Automation
    automation = cfg.get("automation", {})
    if not isinstance(automation.get("enabled", False), bool):
        errors.append("automation.enabled muss true oder false sein")

    for mode in AUTOMATION_MODES:
        mode_cfg = automation.get(mode, {})
        if not isinstance(mode_cfg, dict):
            errors.append(f"automation.{mode} muss ein Objekt sein")
            continue

        enabled = mode_cfg.get("enabled", False)
        if not isinstance(enabled, bool):
            errors.append(f"automation.{mode}.enabled muss true oder false sein")

        schedule = mode_cfg.get("schedule", "")
        if schedule and not isinstance(schedule, str):
            errors.append(f"automation.{mode}.schedule muss ein String sein")
        elif schedule:
            if croniter is None:
                errors.append(f"automation.{mode}.schedule kann nicht geprüft werden (croniter fehlt)")
            elif not croniter.is_valid(schedule):
                errors.append(f"automation.{mode}.schedule ist kein gültiger Cron-Ausdruck: '{schedule}'")

        interval_minutes = mode_cfg.get("interval_minutes", 0)
        if not isinstance(interval_minutes, int) or interval_minutes < 0:
            errors.append(f"automation.{mode}.interval_minutes muss eine ganze Zahl >= 0 sein")

        if enabled and not schedule and interval_minutes == 0:
            errors.append(f"automation.{mode}: Bei aktiviertem Modus muss schedule oder interval_minutes gesetzt sein")

        webhook = mode_cfg.get("discord_webhook", "")
        if not _is_valid_webhook_url(webhook):
            errors.append(f"automation.{mode}.discord_webhook muss mit http:// oder https:// beginnen")

        notify_on_empty = mode_cfg.get("notify_on_empty", False)
        if not isinstance(notify_on_empty, bool):
            errors.append(f"automation.{mode}.notify_on_empty muss true oder false sein")

        filter_mode = str(mode_cfg.get("filter_mode", "whitelist") or "whitelist").lower()
        if filter_mode not in ("whitelist", "blacklist", "off"):
            errors.append(f"automation.{mode}.filter_mode muss whitelist, blacklist oder off sein")

        whitelist = mode_cfg.get("whitelist", [])
        if not _validate_string_list(whitelist):
            errors.append(f"automation.{mode}.whitelist muss eine Liste von Strings sein")

        blacklist = mode_cfg.get("blacklist", [])
        if not _validate_string_list(blacklist):
            errors.append(f"automation.{mode}.blacklist muss eine Liste von Strings sein")

    # Logging
    logging_cfg = cfg.get("logging", {}) or {}
    # Fehlender Schluessel ist in Ordnung – _deep_merge setzt dann den Standard.
    # Ein GESETZTER, aber unbekannter Wert ist ein Fehler (auch "").
    level = logging_cfg.get("level", None)
    if level is not None and str(level).strip().lower() not in VALID_LOG_LEVELS:
        errors.append(f"logging.level muss einer von {VALID_LOG_LEVELS} sein")

    retention = logging_cfg.get("log_retention_days", 7)
    if not isinstance(retention, int) or not (1 <= retention <= 365):
        errors.append("logging.log_retention_days muss zwischen 1 und 365 liegen")

    return errors


def load_config(data_folder: Optional[str] = None) -> dict:
    """
    Load config from YAML file. Creates default config if not found.
    Merges missing keys from DEFAULT_CONFIG.
    """
    config_path = _get_config_path(data_folder)

    if not config_path.exists():
        os.makedirs(config_path.parent, exist_ok=True)
        save_config(DEFAULT_CONFIG.copy(), data_folder)
        return DEFAULT_CONFIG.copy()

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            user_cfg = yaml.safe_load(f) or {}
    except Exception:
        # Corrupted file → backup and recreate
        backup = config_path.with_suffix(".yaml.bak")
        shutil.copy2(config_path, backup)
        save_config(DEFAULT_CONFIG.copy(), data_folder)
        return DEFAULT_CONFIG.copy()

    # Merge defaults for missing keys
    merged = _deep_merge(DEFAULT_CONFIG, user_cfg)

    # Validate
    errors = validate_config(merged)
    if errors:
        print(f"[CONFIG-WARN] Validierungsfehler: {errors}")

    _ensure_dirs(merged)
    return merged


def save_config(cfg: dict, data_folder: Optional[str] = None) -> bool:
    """Atomic save of config to YAML file."""
    config_path = _get_config_path(data_folder)
    os.makedirs(config_path.parent, exist_ok=True)
    tmp_path = config_path.with_suffix(".yaml.tmp")

    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            yaml.dump(
                cfg,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )
        os.replace(tmp_path, config_path)
        return True
    except Exception as e:
        print(f"[CONFIG-ERROR] save_config: {e}")
        if tmp_path.exists():
            tmp_path.unlink()
        return False


def get_data_folder(cfg: Optional[dict] = None) -> str:
    """Return the data folder path from config or default."""
    if cfg:
        return cfg.get("data", {}).get("folder", str(DEFAULT_DATA_DIR))
    return str(DEFAULT_DATA_DIR)


def get_film_naming_mode(cfg: dict) -> str:
    """Return the configured film naming mode ('local' or 'jellyfin')."""
    return cfg.get("storage", {}).get("film_naming_mode", "local")


def get_download_path(cfg: dict, url: str, is_film: bool = False) -> str:
    """
    Determine the download base path for a given URL based on storage config.

    Args:
        cfg: Loaded config dict
        url: Series URL (determines anime vs series)
        is_film: Whether the download is a film/movie
    """
    storage = cfg.get("storage", {})
    mode = storage.get("mode", "standard")
    download_path = storage.get("download_path", str(DEFAULT_DOWNLOAD_DIR))

    if mode == "standard":
        return download_path

    # Separate mode
    from .domains import is_aniworld
    is_anime = is_aniworld(url)

    if is_anime:
        if is_film and storage.get("anime_separate_movies"):
            return storage.get("anime_movies_path", download_path)
        return storage.get("anime_path", download_path)
    else:
        if is_film and storage.get("serien_separate_movies"):
            return storage.get("serien_movies_path", download_path)
        return storage.get("series_path", download_path)
