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

from ..config import get_data_folder, load_config
from ..database import init_db, import_aniloader_txt, refresh_titles
from ..logger import cleanup_old_logs, init_logger, log

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
    init_db(data_folder)
    
    # AniLoader.txt importieren (wie im alten AniLoader)
    try:
        import_result = import_aniloader_txt(data_folder)
        if import_result["total_lines"] > 0:
            log(f"[SERVER] AniLoader.txt Import: {import_result['imported']} importiert, {import_result['duplicates']} Duplikate, {import_result['errors']} Fehler")
    except Exception as e:
        log(f"[SERVER-ERROR] AniLoader.txt Import fehlgeschlagen: {e}")
    
    # Log-Bereinigung mit konfiguriertem Wert
    log_retention_days = cfg.get("logging", {}).get("log_retention_days", 7)
    cleanup_old_logs(days=log_retention_days)
    log(f"[SERVER] Log-Bereinigung durchgeführt (>{log_retention_days} Tage alte Einträge entfernt)")
    
    log("[SERVER] AniLoader gestartet")

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
    if autostart and autostart in ("default", "german", "new", "check"):
        from ..downloader import start_download
        log(f"[AUTOSTART] Starte Modus: {autostart}")
        start_download(autostart)

    yield

    log("[SERVER] AniLoader wird beendet")


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
