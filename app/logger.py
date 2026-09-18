"""
AniLoader – Logging-System.

Schreibt Logs in:
  - data/last_run.txt       (aktueller Lauf)
  - data/logs/              (archivierte Läufe mit Timestamp)
  - stdout                  (Konsole)
"""

import os
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path

_log_lock = threading.Lock()
_data_folder: str = ""
_run_log_lines: list = []


def init_logger(data_folder: str) -> None:
    """Initialisiert das Logging-System und archiviert den letzten Lauf mit Timestamp."""
    global _data_folder
    _data_folder = data_folder
    os.makedirs(data_folder, exist_ok=True)

    logs_folder = Path(data_folder) / "logs"
    logs_folder.mkdir(exist_ok=True)

    last_run = Path(data_folder) / "last_run.txt"
    last_run_bak = Path(data_folder) / "last_run.bak.txt"

    # Bereinigung: Entferne alte .bak Datei (Migration zum neuen System)
    if last_run_bak.exists():
        try:
            last_run_bak.unlink()
        except Exception as e:
            print(f"[LOG-WARNING] Konnte alte .bak Datei nicht löschen: {e}")

    # Archiviere den letzten Lauf mit Timestamp (falls vorhanden)
    if last_run.exists() and last_run.stat().st_size > 0:
        # Timestamp aus der letzten Änderung der Datei erstellen
        mod_time = last_run.stat().st_mtime
        timestamp = datetime.fromtimestamp(mod_time).strftime("%Y%m%d_%H%M%S")
        archived_log = logs_folder / f"run_{timestamp}.txt"
        
        # Archivieren mit einem eindeutigen Namen, falls bereits existiert
        counter = 1
        while archived_log.exists():
            archived_log = logs_folder / f"run_{timestamp}_{counter}.txt"
            counter += 1
        
        shutil.move(str(last_run), str(archived_log))

    # Neuen Lauf starten
    with open(last_run, "w", encoding="utf-8", newline="\n") as f:
        ts = time.strftime("[%Y-%m-%d %H:%M:%S]")
        f.write(f"{ts} === Neuer Lauf gestartet ===\n")


def log(msg: str) -> None:
    """Thread-safe Log-Eintrag in alle Ziele."""
    ts = time.strftime("[%Y-%m-%d %H:%M:%S]")
    line = f"{ts} {msg}"

    with _log_lock:
        _run_log_lines.append(line)
        print(line, flush=True)

    if not _data_folder:
        return

    try:
        # last_run.txt (aktueller Lauf)
        last_run = Path(_data_folder) / "last_run.txt"
        # newline="\n": sonst schreibt Windows CRLF und jede Logzeile endet im
        # Web-View (split('\n')) mit einem \r – und Docker/Windows-Logs weichen ab.
        with open(last_run, "a", encoding="utf-8", newline="\n") as f:
            f.write(line + "\n")
    except Exception:
        pass


def get_last_run_log() -> str:
    """Gibt den Log des letzten/aktuellen Laufs zurück."""
    if not _data_folder:
        return "\n".join(_run_log_lines)
    last_run = Path(_data_folder) / "last_run.txt"
    if last_run.exists():
        return last_run.read_text(encoding="utf-8")
    return "Kein Log vorhanden."


def get_log_from_offset(offset: int = 0) -> tuple:
    """
    Gibt Logzeilen ab einer Zeilennummer zurück.

    Returns:
        (lines: list[str], total_line_count: int)
    """
    if _data_folder:
        last_run = Path(_data_folder) / "last_run.txt"
        if last_run.exists():
            try:
                all_lines = last_run.read_text(encoding="utf-8").splitlines()
                total = len(all_lines)
                return all_lines[max(0, offset):], total
            except Exception:
                pass
    with _log_lock:
        snapshot = list(_run_log_lines)
    total = len(snapshot)
    return snapshot[max(0, offset):], total


# ──────────────────────── Byte-Offset-Lesen (inkrementell, kein Ganzdatei-Read) ────────────────────────

_LOG_CHUNK_BYTES = 256 * 1024  # Standard-Blockgröße für Tail-/Backfill-Reads


def _resolve_log_path(filename=None):
    """Pfad zur aktuellen (filename=None) oder einer archivierten Logdatei.

    Für Archiv-Dateien streng auf ``logs/run_*.txt`` begrenzt (kein Path-Traversal).
    Gibt None zurück, wenn unzulässig.
    """
    if not _data_folder:
        return None
    if filename is None:
        return Path(_data_folder) / "last_run.txt"
    if ("/" in filename) or ("\\" in filename) or (".." in filename):
        return None
    if not (filename.startswith("run_") and filename.endswith(".txt")):
        return None
    logs_dir = (Path(_data_folder) / "logs").resolve()
    candidate = (logs_dir / filename).resolve()
    try:
        candidate.relative_to(logs_dir)
    except ValueError:
        return None
    return candidate


def read_log_slice(filename=None, *, after=None, before=None, tail_bytes=None) -> dict:
    """Liest einen Ausschnitt einer Logdatei per BYTE-Offset – ohne die ganze Datei zu lesen.

    Genau ein Modus:
      - ``tail_bytes=N`` : die letzten ~N Bytes (neueste Zeilen) – initiales Laden.
      - ``after=B``      : neue Bytes ab Offset B bis Dateiende – Live-Tailing.
      - ``before=B``     : ~_LOG_CHUNK_BYTES Bytes VOR Offset B (ältere Zeilen) – Backfill.

    Alle Ausschnitte sind zeilenbündig (keine angeschnittene Zeile am Anfang).

    Returns:
        {"text": str, "start": int, "end": int, "size": int, "bof": bool, "eof": bool}
        start/end = Byte-Offsets des zurückgegebenen Bereichs.
    """
    empty = {"text": "", "start": 0, "end": 0, "size": 0, "bof": True, "eof": True}
    path = _resolve_log_path(filename)
    if path is None or not path.exists():
        return empty

    try:
        size = path.stat().st_size
        with open(path, "rb") as f:
            if after is not None:
                # after stammt aus einem vorherigen `end` (= Zeilenende) → bereits zeilenbündig.
                start = min(max(0, int(after)), size)
                f.seek(start)
                data = f.read()
                end = size
            elif before is not None:
                end = min(max(0, int(before)), size)
                start = max(0, end - _LOG_CHUNK_BYTES)
                if start > 0:
                    f.seek(start)
                    f.readline()          # angeschnittene erste Zeile verwerfen
                    start = f.tell()
                f.seek(start)
                data = f.read(max(0, end - start))
            else:
                nbytes = int(tail_bytes) if (tail_bytes and int(tail_bytes) > 0) else _LOG_CHUNK_BYTES
                start = max(0, size - nbytes)
                if start > 0:
                    f.seek(start)
                    f.readline()          # angeschnittene erste Zeile verwerfen
                    start = f.tell()
                f.seek(start)
                data = f.read()
                end = size

        return {
            "text": data.decode("utf-8", errors="replace"),
            "start": start,
            "end": end,
            "size": size,
            "bof": start <= 0,
            "eof": end >= size,
        }
    except Exception as e:
        print(f"[LOG-ERROR] read_log_slice: {e}")
        return empty


def get_all_logs() -> str:
    """Gibt alle Log-Einträge zurück (aus last_run.txt)."""
    return get_last_run_log()


def cleanup_old_logs(days: int = 7) -> int:
    """
    Entfernt archivierte Log-Dateien älter als `days` Tage aus data/logs/.
    Gibt die Anzahl entfernter Dateien zurück.
    """
    if not _data_folder:
        return 0

    removed_count = 0
    cutoff = time.time() - (days * 86400)
    
    # Bereinige archivierte Log-Dateien aus data/logs/
    logs_folder = Path(_data_folder) / "logs"
    if logs_folder.exists():
        try:
            for log_file in logs_folder.glob("run_*.txt"):
                # Prüfe ob die Datei älter als X Tage ist
                if log_file.stat().st_mtime < cutoff:
                    try:
                        log_file.unlink()
                        removed_count += 1
                    except Exception as e:
                        print(f"[LOG-ERROR] Konnte {log_file.name} nicht löschen: {e}")
        except Exception as e:
            print(f"[LOG-ERROR] cleanup logs folder: {e}")
    
    return removed_count


def start_new_run() -> None:
    """Startet einen neuen Log-Lauf (Archivierung + Reset)."""
    global _run_log_lines
    with _log_lock:
        _run_log_lines = []

    if _data_folder:
        logs_folder = Path(_data_folder) / "logs"
        logs_folder.mkdir(exist_ok=True)
        
        last_run = Path(_data_folder) / "last_run.txt"
        
        # Archiviere den aktuellen Log mit Timestamp (falls vorhanden)
        if last_run.exists() and last_run.stat().st_size > 0:
            # Timestamp aus der letzten Änderung der Datei erstellen
            mod_time = last_run.stat().st_mtime
            timestamp = datetime.fromtimestamp(mod_time).strftime("%Y%m%d_%H%M%S")
            archived_log = logs_folder / f"run_{timestamp}.txt"
            
            # Archivieren mit einem eindeutigen Namen, falls bereits existiert
            counter = 1
            while archived_log.exists():
                archived_log = logs_folder / f"run_{timestamp}_{counter}.txt"
                counter += 1
            
            shutil.move(str(last_run), str(archived_log))
        
        # Neuen Lauf starten
        with open(last_run, "w", encoding="utf-8", newline="\n") as f:
            ts = time.strftime("[%Y-%m-%d %H:%M:%S]")
            f.write(f"{ts} === Neuer Lauf gestartet ===\n")
