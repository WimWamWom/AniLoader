"""
AniLoader – API-Endpunkte.

Alle REST-Endpunkte für die Web-UI und das Tampermonkey-Skript.
"""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates

from .. import database as db
from .. import automation, downloader, scraper
from ..config import (
    get_data_folder,
    get_download_path,
    load_config,
    save_config,
    validate_config,
)
from ..file_manager import count_episodes_on_disk, get_free_space_gb
from ..logger import get_all_logs, get_last_run_log, log

router = APIRouter()

# Templates
TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "web" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

# In-Memory-Cache für Poster-URLs (vermeidet wiederholte HTTP-Requests)
_poster_cache: dict = {}


# ──────────────────────── Hilfsfunktionen ────────────────────────


def _data_folder() -> str:
    cfg = load_config()
    return get_data_folder(cfg)


# ──────────────────────── Web-UI ────────────────────────


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Haupt-Webinterface."""
    return templates.TemplateResponse("index.html", {"request": request})


# ──────────────────────── Health / Status ────────────────────────


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/status")
async def get_status():
    """Aktueller Download-Status."""
    return downloader.get_status()


@router.get("/automation/status")
async def get_automation_status():
    """Status des Automation-Schedulers inkl. nächster Ausführungen."""
    return automation.get_scheduler_status()


@router.post("/automation/trigger/{mode}")
async def trigger_automation(mode: str):
    """Startet einen manuellen Automation-Lauf für den Modus."""
    if mode not in ("german", "new", "german_new"):
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Ungültiger Modus"},
        )

    if downloader.is_running():
        return JSONResponse(
            status_code=409,
            content={"status": "error", "message": "Download läuft bereits"},
        )

    ok, info = automation.trigger_mode(mode)
    if ok:
        return {"status": "ok", "mode": mode, "run_id": info}

    return JSONResponse(
        status_code=409,
        content={"status": "error", "message": info},
    )


@router.get("/automation/history")
async def get_automation_history(limit: int = Query(20, ge=1, le=200)):
    """Gibt die letzten Automation-Läufe zurück."""
    return {"history": automation.get_history(limit=limit)}


@router.get("/series")
async def get_all_series(q: Optional[str] = None):
    """Gibt alle Serien aus der Datenbank zurück für die Filterlisten-Auswahl."""
    data_folder = _data_folder()
    series = db.get_all_anime(
        data_folder,
        include_deleted=False,
        search=q,
        sort_by="title",
        sort_dir="ASC"
    )
    return {"series": [{"title": s["title"], "url": s["url"]} for s in series]}


# ──────────────────────── Download-Steuerung ────────────────────────


@router.post("/start_download")
async def start_download(request: Request):
    """Startet den Download mit einem bestimmten Modus."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    mode = body.get("mode", "default")

    if downloader.start_download(mode):
        return {"status": "ok", "mode": mode}
    return JSONResponse(
        status_code=409,
        content={"status": "error", "message": "Download läuft bereits"},
    )


@router.get("/start_download")
async def start_download_get(mode: str = Query("default")):
    """Startet den Download (GET-Variante für einfache Aufrufe)."""
    if downloader.start_download(mode):
        return {"status": "ok", "mode": mode}
    return JSONResponse(
        status_code=409,
        content={"status": "error", "message": "Download läuft bereits"},
    )


@router.post("/stop_download")
async def stop_download():
    """Stoppt den Download nach der aktuellen Episode."""
    if downloader.request_stop():
        return {"status": "ok", "message": "Stop angefordert"}
    return JSONResponse(
        status_code=400,
        content={"status": "error", "message": "Kein Download aktiv"},
    )


# ──────────────────────── Datenbank ────────────────────────


@router.get("/database")
async def get_database(
    q: Optional[str] = None,
    sort: str = "id",
    sort_by: Optional[str] = None,  # Alias für sort
    dir: str = "ASC",
    order: Optional[str] = None,    # Alias für dir
    include_deleted: bool = False,
    complete: Optional[str] = None,  # "1" | "0" | "deleted"
    deutsch: Optional[str] = None,   # "1" | "0"
):
    """Gibt die Datenbank zurück (gefiltert, sortiert)."""
    data_folder = _data_folder()
    entries = db.get_all_anime(
        data_folder,
        include_deleted=include_deleted,
        search=q,
        sort_by=sort_by or sort,
        sort_dir=(order or dir).upper(),
        complete=complete,
        deutsch=deutsch,
    )
    return entries


@router.get("/database/stats")
async def get_database_stats():
    """Datenbank-Statistiken."""
    return db.get_db_stats(_data_folder())


# ──────────────────────── Anime/Serie CRUD ────────────────────────


@router.post("/export")
async def export_anime(request: Request):
    """Fügt eine URL zur Datenbank hinzu (Tampermonkey-kompatibel)."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"status": "error"})

    url = body.get("url", "").strip()
    if not url or ("aniworld.to" not in url and "s.to" not in url):
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Ungültige URL"},
        )

    data_folder = _data_folder()

    # Titel holen
    title = scraper.get_series_title(url)
    anime_id = db.add_anime(data_folder, url, title)

    if anime_id:
        return {"status": "ok", "id": anime_id, "title": title}
    return {"status": "ok", "message": "Bereits vorhanden"}


@router.post("/add_link")
async def add_link(request: Request):
    """Fügt einen Link zur Datenbank hinzu."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"status": "error"})

    url = body.get("url", "").strip()
    if not url or ("aniworld.to" not in url and "s.to" not in url):
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Ungültige URL (nur aniworld.to und s.to)"},
        )

    data_folder = _data_folder()
    title = scraper.get_series_title(url)
    anime_id = db.add_anime(data_folder, url, title)

    return {"status": "ok", "id": anime_id, "title": title or url}


@router.delete("/anime/{anime_id}")
async def delete_anime(anime_id: int, hard: bool = False):
    """Löscht einen Eintrag (soft oder hard)."""
    data_folder = _data_folder()
    if db.delete_anime(data_folder, anime_id, hard=hard):
        return {"status": "ok"}
    return JSONResponse(status_code=404, content={"status": "error"})


@router.post("/anime/{anime_id}/restore")
async def restore_anime(anime_id: int):
    """Stellt einen gelöschten Eintrag wieder her."""
    data_folder = _data_folder()
    if db.restore_anime(data_folder, anime_id):
        return {"status": "ok"}
    return JSONResponse(status_code=404, content={"status": "error"})


@router.put("/anime/{anime_id}")
async def update_anime(anime_id: int, request: Request):
    """Aktualisiert Felder eines Eintrags."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"status": "error"})

    data_folder = _data_folder()
    if db.update_anime(data_folder, anime_id, **body):
        return {"status": "ok"}
    return JSONResponse(status_code=400, content={"status": "error"})


# ──────────────────────── Datei-Upload ────────────────────────


@router.post("/upload_txt")
async def upload_txt(file: UploadFile = File(...)):
    """Importiert URLs aus einer hochgeladenen TXT-Datei."""
    content = await file.read()
    text = content.decode("utf-8", errors="replace")
    data_folder = _data_folder()
    added = db.import_txt(data_folder, text)
    log(f"[IMPORT] {added} neue Einträge aus TXT-Upload")
    return {"status": "ok", "added": added}


# ──────────────────────── Suche ────────────────────────


@router.post("/search")
async def search(request: Request):
    """Sucht nach Serien/Animes."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"status": "error"})

    query = body.get("query", "").strip()
    platform = body.get("platform", "both")  # aniworld | sto | both

    if not query:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Suchbegriff fehlt"},
        )

    # Optionales Limit (für Live-Suche)
    limit = body.get("limit")
    log_search = not (limit and isinstance(limit, int) and limit > 0)

    try:
        results = scraper.search_anime(query, platform, log_search=log_search)
    except Exception as e:
        log(f"[SUCHE-ERROR] {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Suche fehlgeschlagen"},
        )

    if limit and isinstance(limit, int) and limit > 0:
        results = results[:limit]

    return {"status": "ok", "results": results}


# ──────────────────────── Konfiguration ────────────────────────


@router.get("/config")
async def get_config():
    """Gibt die aktuelle Konfiguration zurück."""
    return load_config()


@router.post("/config")
async def update_config(request: Request):
    """Aktualisiert die Konfiguration."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"status": "error"})

    errors = validate_config(body)
    if errors:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "errors": errors},
        )

    if save_config(body):
        log("[CONFIG] Konfiguration aktualisiert")
        return {"status": "ok"}
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "Speichern fehlgeschlagen"},
    )


# ──────────────────────── Titel-Refresh ────────────────────────


@router.post("/refresh_titles")
async def api_refresh_titles():
    """Aktualisiert alle Titel in der Datenbank anhand der Webseiten."""
    folder = _data_folder()
    try:
        result = db.refresh_titles(folder)
        return {"status": "ok", **result}
    except Exception as e:
        log(f"[API-ERROR] Titel-Refresh: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)},
        )


# ──────────────────────── Disk ────────────────────────


@router.get("/disk")
async def disk_info():
    """Gibt Speicherplatz-Informationen zurück."""
    cfg = load_config()
    download_path = cfg.get("storage", {}).get("download_path", ".")
    free_gb = get_free_space_gb(download_path)
    return {"free_gb": round(free_gb, 2), "path": download_path}


# ──────────────────────── Ordner-Browser ────────────────────────


@router.post("/browse")
async def browse_directories(request: Request):
    """Listet Unterordner eines Pfades auf (für den Ordner-Picker)."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    raw_path = body.get("path", "").strip()

    # Startpunkt bestimmen
    if not raw_path:
        # Plattformabhängig: Windows -> Laufwerke, Linux -> /
        import platform as _plat

        if _plat.system() == "Windows":
            import string

            drives = []
            for letter in string.ascii_uppercase:
                dp = Path(f"{letter}:\\")
                if dp.exists():
                    drives.append(
                        {"name": f"{letter}:\\", "path": f"{letter}:\\", "is_drive": True}
                    )
            return {"path": "", "parent": None, "dirs": drives}
        else:
            raw_path = "/"

    target = Path(raw_path).resolve()

    if not target.exists() or not target.is_dir():
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": f"Ordner existiert nicht: {raw_path}"},
        )

    # Elternverzeichnis
    parent = str(target.parent) if target.parent != target else None

    # Unterordner auflisten (nur Verzeichnisse, keine versteckten)
    dirs = []
    try:
        for entry in sorted(target.iterdir(), key=lambda e: e.name.lower()):
            if entry.is_dir() and not entry.name.startswith("."):
                dirs.append({"name": entry.name, "path": str(entry), "is_drive": False})
    except PermissionError:
        pass  # Kein Zugriff – leere Liste zurückgeben

    return {"path": str(target), "parent": parent, "dirs": dirs}


# ──────────────────────── Poster ────────────────────────


@router.get("/poster")
async def get_poster(url: str = Query(...)):
    """Gibt die Poster-URL für eine Serie zurück."""
    if not url or ("aniworld.to" not in url and "s.to" not in url):
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Ungültige URL"},
        )

    # Cache prüfen
    if url in _poster_cache:
        return {"poster_url": _poster_cache[url]}

    try:
        poster_url = scraper.get_poster_url(url)
        # Cache speichern (auch None-Werte, um wiederholte Requests zu vermeiden)
        _poster_cache[url] = poster_url
        return {"poster_url": poster_url}
    except Exception as e:
        log(f"[API-ERROR] Poster-Fehler für {url}: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Poster konnte nicht geladen werden"},
        )


@router.get("/proxy_poster")
async def proxy_poster(url: str = Query(...)):
    """Lädt ein Poster-Bild über einen Proxy und gibt es zurück."""
    if not url.startswith(("http://", "https://")):
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Ungültige Bild-URL"},
        )

    try:
        import niquests
        
        # HTTP-Request mit korrekten Headers
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
            "Referer": "https://aniworld.to/" if "aniworld.to" in url else "https://s.to/",
        }
        
        resp = niquests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        
        # Content-Type aus Response übernehmen oder fallback
        content_type = resp.headers.get("Content-Type", "image/jpeg")
        
        return Response(content=resp.content, media_type=content_type)
        
    except Exception as e:
        log(f"[API-ERROR] Proxy-Poster-Fehler für {url}: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Bild konnte nicht geladen werden"},
        )


# ──────────────────────── Logs ────────────────────────


@router.get("/logs")
async def get_logs():
    """Alle Logs."""
    return {"logs": get_all_logs()}


@router.get("/last_run")
async def last_run():
    """Log des aktuellen/letzten Laufs."""
    return {"log": get_last_run_log()}


@router.get("/archived_logs")
async def get_archived_logs():
    """Liste aller archivierten Log-Dateien."""
    from ..config import get_data_folder, load_config
    from pathlib import Path
    
    cfg = load_config()
    data_folder = get_data_folder(cfg)
    logs_folder = Path(data_folder) / "logs"
    
    if not logs_folder.exists():
        return {"archived_logs": []}
    
    logs = []
    for log_file in sorted(logs_folder.glob("run_*.txt"), key=lambda x: x.stat().st_mtime, reverse=True):
        logs.append({
            "filename": log_file.name,
            "timestamp": log_file.stat().st_mtime,
            "size": log_file.stat().st_size
        })
    
    return {"archived_logs": logs}


@router.get("/archived_logs/{filename}")
async def get_archived_log_content(filename: str):
    """Inhalt einer spezifischen archivierten Log-Datei."""
    from ..config import get_data_folder, load_config
    from pathlib import Path
    
    # Sicherheitscheck: Nur run_*.txt Dateien erlauben
    if not filename.startswith("run_") or not filename.endswith(".txt"):
        raise HTTPException(status_code=400, detail="Ungültiger Dateiname")
    
    cfg = load_config()
    data_folder = get_data_folder(cfg)
    log_file = Path(data_folder) / "logs" / filename
    
    if not log_file.exists():
        raise HTTPException(status_code=404, detail="Log-Datei nicht gefunden")
    
    try:
        content = log_file.read_text(encoding="utf-8")
        return {"filename": filename, "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Lesen der Datei: {e}")


# ──────────────────────── Episoden-Counts ────────────────────────


@router.get("/counts/{anime_id}")
async def episode_counts(anime_id: int):
    """Zählt heruntergeladene Episoden für eine Serie."""
    data_folder = _data_folder()
    anime = db.get_anime_by_id(data_folder, anime_id)
    if not anime:
        return JSONResponse(status_code=404, content={"status": "error"})

    cfg = load_config()
    counts = count_episodes_on_disk(cfg, anime["url"], anime.get("folder_name"))
    return counts


# ──────────────────────── Export ────────────────────────


@router.get("/export/database")
async def export_database():
    """Exportiert die komplette SQLite-Datenbank als Download."""
    data_folder = _data_folder()
    db_path = Path(data_folder) / "AniLoader.db"
    
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="Datenbank nicht gefunden")
    
    return FileResponse(
        path=str(db_path),
        filename="AniLoader.db",
        media_type="application/vnd.sqlite3",
        headers={"Content-Disposition": "attachment; filename=AniLoader.db"}
    )


@router.get("/export/links")
async def export_links():
    """Exportiert alle Links als AniLoader.txt Download."""
    data_folder = _data_folder()
    backup_path = Path(data_folder) / "AniLoader.txt.bak"
    
    if not backup_path.exists():
        # Fallback: Erstelle AniLoader.txt.bak aus Datenbank
        try:
            db.regenerate_aniloader_backup(data_folder)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Backup-Erstellung fehlgeschlagen: {e}")
    
    if not backup_path.exists():
        raise HTTPException(status_code=404, detail="Keine Links zum Export vorhanden")
    
    return FileResponse(
        path=str(backup_path),
        filename="AniLoader.txt",
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=AniLoader.txt"}
    )
