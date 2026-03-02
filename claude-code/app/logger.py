"""
AniLoader – Logging-System.

Schreibt Logs in:
  - data/last_run.txt       (aktueller Lauf, wird bei neuem Start als .bak kopiert)
  - data/all_logs.txt       (Gesamt-History, 7-Tage-Cleanup)
  - stdout                  (Konsole)
"""

import os
import shutil
import threading
import time
from pathlib import Path

_log_lock = threading.Lock()
_data_folder: str = ""
_run_log_lines: list = []


def init_logger(data_folder: str) -> None:
    """Initialisiert das Logging-System und erstellt ein Backup des letzten Laufs."""
    global _data_folder
    _data_folder = data_folder
    os.makedirs(data_folder, exist_ok=True)

    last_run = Path(data_folder) / "last_run.txt"
    last_run_bak = Path(data_folder) / "last_run.bak.txt"

    # Backup des letzten Laufs erstellen
    if last_run.exists():
        shutil.copy2(last_run, last_run_bak)

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

    try:
        # all_logs.txt (gesamte History)
        all_logs = Path(_data_folder) / "all_logs.txt"
        with open(all_logs, "a", encoding="utf-8") as f:
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
    """Gibt alle Log-Einträge zurück."""
    if not _data_folder:
        return "\n".join(_run_log_lines)
    all_logs = Path(_data_folder) / "all_logs.txt"
    if all_logs.exists():
        return all_logs.read_text(encoding="utf-8")
    return "Keine Logs vorhanden."


def cleanup_old_logs(days: int = 7) -> int:
    """
    Entfernt Log-Einträge älter als `days` Tage aus all_logs.txt.
    Gibt die Anzahl entfernter Zeilen zurück.
    """
    if not _data_folder:
        return 0

    all_logs = Path(_data_folder) / "all_logs.txt"
    if not all_logs.exists():
        return 0

    try:
        cutoff = time.time() - (days * 86400)
        lines = all_logs.read_text(encoding="utf-8").splitlines()
        kept = []
        removed = 0

        for line in lines:
            # Format: [2025-03-02 14:30:00] message
            if line.startswith("[") and "]" in line:
                try:
                    ts_str = line[1 : line.index("]")]
                    ts = time.mktime(time.strptime(ts_str, "%Y-%m-%d %H:%M:%S"))
                    if ts < cutoff:
                        removed += 1
                        continue
                except (ValueError, OverflowError):
                    pass
            kept.append(line)

        if removed > 0:
            with open(all_logs, "w", encoding="utf-8") as f:
                f.write("\n".join(kept) + "\n" if kept else "")

        return removed
    except Exception as e:
        print(f"[LOG-ERROR] cleanup_old_logs: {e}")
        return 0


def start_new_run() -> None:
    """Startet einen neuen Log-Lauf (Backup + Reset)."""
    global _run_log_lines
    with _log_lock:
        _run_log_lines = []

    if _data_folder:
        last_run = Path(_data_folder) / "last_run.txt"
        last_run_bak = Path(_data_folder) / "last_run.bak.txt"
        if last_run.exists():
            shutil.copy2(last_run, last_run_bak)
        with open(last_run, "w", encoding="utf-8") as f:
            ts = time.strftime("[%Y-%m-%d %H:%M:%S]")
            f.write(f"{ts} === Neuer Lauf gestartet ===\n")
