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
    with open(last_run, "w", encoding="utf-8") as f:
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
        with open(last_run, "a", encoding="utf-8") as f:
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
        with open(last_run, "w", encoding="utf-8") as f:
            ts = time.strftime("[%Y-%m-%d %H:%M:%S]")
            f.write(f"{ts} === Neuer Lauf gestartet ===\n")
