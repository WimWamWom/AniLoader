"""
AniLoader – FastAPI Server-Erstellung und -Konfiguration.
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..automation import start_scheduler, stop_scheduler
from ..config import get_data_folder, load_config
from ..database import init_db, import_aniloader_txt, refresh_titles
from ..file_manager import ensure_aniloader_txt
from ..logger import (
    cleanup_old_logs, get_level_name, init_logger, log,
    start_cleanup_scheduler, stop_cleanup_scheduler,
)
from ..logger import set_level as set_log_level

# Pfade für Web-UI
BASE_DIR = Path(__file__).resolve().parent.parent.parent
WEB_DIR = BASE_DIR / "web"
STATIC_DIR = WEB_DIR / "static"
TEMPLATE_DIR = WEB_DIR / "templates"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/Shutdown Lifecycle."""
    cfg = load_config()
    data_folder = get_data_folder(cfg)

    init_logger(data_folder)
    # Level VOR allen weiteren log()-Aufrufen setzen, sonst landen die ersten
    # Startmeldungen noch mit der Standardstufe im Log.
    set_log_level(cfg.get("logging", {}).get("level", "info"))
    init_db(data_folder)
    
    # AniLoader.txt erstellen falls nicht vorhanden
    ensure_aniloader_txt(data_folder)
    
    # AniLoader.txt importieren (wie im alten AniLoader)
    try:
        import_result = import_aniloader_txt(data_folder)
        if import_result["total_lines"] > 0:
            log(f"[SERVER] AniLoader.txt Import: {import_result['imported']} importiert, {import_result['duplicates']} Duplikate, {import_result['errors']} Fehler")
    except Exception as e:
        log(f"[SERVER-ERROR] AniLoader.txt Import fehlgeschlagen: {e}")
    
    # Log-Bereinigung: einmal jetzt, danach periodisch im laufenden Betrieb.
    # Die Aufbewahrungsdauer wird bei jedem Durchlauf frisch gelesen, damit eine
    # Änderung in den Einstellungen ohne Neustart greift.
    def _retention_days() -> int:
        return load_config().get("logging", {}).get("log_retention_days", 7)

    log_retention_days = _retention_days()
    removed = cleanup_old_logs(days=log_retention_days)
    log(f"[SERVER] Log-Bereinigung: {removed} Datei(en) älter als {log_retention_days} Tage entfernt")
    start_cleanup_scheduler(_retention_days)
    
    log(f"[SERVER] AniLoader gestartet (Log-Level: {get_level_name()})")

    # Titel bei Start aktualisieren
    if cfg.get("download", {}).get("refresh_titles", False):
        log("[SERVER] Titel-Refresh aktiviert – aktualisiere Datenbank-Titel...")
        try:
            result = refresh_titles(data_folder)
            log(f"[SERVER] Titel-Refresh fertig: {result['updated']} aktualisiert, {result['unchanged']} unverändert, {result['failed']} fehlgeschlagen")
        except Exception as e:
            log(f"[SERVER-ERROR] Titel-Refresh fehlgeschlagen: {e}")

    # Autostart prüfen
    autostart = cfg.get("download", {}).get("autostart_mode")
    if autostart and autostart in ("default", "german", "new", "check", "german_new"):
        from ..downloader import start_download
        log(f"[AUTOSTART] Starte Modus: {autostart}")
        start_download(autostart)

    # Automation Scheduler starten
    try:
        start_scheduler()
    except Exception as e:
        log(f"[SERVER-ERROR] Automation-Scheduler Start fehlgeschlagen: {e}")

    yield

    # Automation Scheduler stoppen
    try:
        stop_scheduler()
    except Exception as e:
        log(f"[SERVER-ERROR] Automation-Scheduler Stop fehlgeschlagen: {e}")

    # Bereinigungs-Thread stoppen – sonst bleibt er bis zum Prozessende liegen
    try:
        stop_cleanup_scheduler()
    except Exception as e:
        log(f"[SERVER-ERROR] Log-Bereinigung Stop fehlgeschlagen: {e}")

    log("[SERVER] AniLoader beendet")


def create_app() -> FastAPI:
    """Erstellt und konfiguriert die FastAPI-Anwendung."""
    app = FastAPI(
        title="AniLoader",
        description="Anime & Serien Download Management",
        version="2.0.0",
        lifespan=lifespan,
    )

    # CORS für Tampermonkey
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

    # Static Files
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # API Routes
    from .routes import router
    app.include_router(router)

    return app
