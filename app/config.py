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
    "storage": {
        "mode": "standard",  # standard | separate
        "download_path": str(DEFAULT_DOWNLOAD_DIR),
        "anime_path": str(BASE_DIR / "Anime"),
        "series_path": str(BASE_DIR / "Serien"),
        "anime_movies_path": str(BASE_DIR / "Anime-Filme"),
        "serien_movies_path": str(BASE_DIR / "Serien-Filme"),
        "anime_separate_movies": False,
        "serien_separate_movies": False,
    },
    "download": {
        "min_free_gb": 2.0,
        "autostart_mode": None,  # null | default | german | new | check
        "timeout_seconds": 900,
    },
    "data": {
        "folder": str(DEFAULT_DATA_DIR),
    },
}

VALID_LANGUAGES = ["German Dub", "German Sub", "English Dub", "English Sub"]
VALID_MODES = [None, "default", "german", "new", "check"]
VALID_STORAGE_MODES = ["standard", "separate"]


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

    # Storage
    storage = cfg.get("storage", {})
    mode = storage.get("mode", "standard")
    if mode not in VALID_STORAGE_MODES:
        errors.append(f"storage.mode muss 'standard' oder 'separate' sein, ist: '{mode}'")

    download_path = storage.get("download_path", "")
    if not download_path or not isinstance(download_path, str):
        errors.append("storage.download_path darf nicht leer sein")

    # Download
    dl = cfg.get("download", {})
    min_free = dl.get("min_free_gb", 2.0)
    if not isinstance(min_free, (int, float)) or min_free < 0:
        errors.append(f"download.min_free_gb muss >= 0 sein, ist: {min_free}")

    autostart = dl.get("autostart_mode")
    if autostart is not None and autostart not in VALID_MODES:
        errors.append(f"download.autostart_mode ungültig: '{autostart}'")

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
    is_anime = "aniworld.to" in url

    if is_anime:
        if is_film and storage.get("anime_separate_movies"):
            return storage.get("anime_movies_path", download_path)
        return storage.get("anime_path", download_path)
    else:
        if is_film and storage.get("serien_separate_movies"):
            return storage.get("serien_movies_path", download_path)
        return storage.get("series_path", download_path)
