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
from ..database import init_db, refresh_titles
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
    cleanup_old_logs(days=7)
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
