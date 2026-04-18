"""
AniLoader – Automatisierung und Scheduler.

Plant und startet Download-Laeufe fuer die Modi german/new/german_new,
wartet bei laufendem Download und versendet optionale Discord-Benachrichtigungen.
"""

import json
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import niquests
from croniter import croniter

from . import downloader
from .config import get_data_folder, load_config
from .logger import log

AUTOMATION_MODES = ("german", "new", "german_new")
MAX_HISTORY_ITEMS = 200


class AutomationManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._history_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._active_runs: Dict[str, Dict[str, Any]] = {}
        self._jobs: Dict[str, Dict[str, Any]] = {
            mode: {"next_run": None, "signature": None, "last_trigger": None}
            for mode in AUTOMATION_MODES
        }
        self._history: List[Dict[str, Any]] = []
        self._history_file: Optional[Path] = None

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._ensure_history_loaded()
            self._thread = threading.Thread(target=self._scheduler_loop, name="automation-scheduler", daemon=True)
            self._thread.start()
        log("[AUTOMATION] Scheduler gestartet")

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread and thread.is_alive():
            # Kurzes Warten, da Thread Daemon ist wird er beim Exit abgebrochen
            thread.join(timeout=0.5)
        log("[AUTOMATION] Scheduler gestoppt")

    def trigger_manual(self, mode: str) -> Tuple[bool, str]:
        if mode not in AUTOMATION_MODES:
            return False, f"Ungueltiger Modus: {mode}"
        if downloader.is_running():
            return False, "Download laeuft bereits"

        with self._lock:
            if mode in self._active_runs:
                return False, f"Automation-Lauf fuer {mode} laeuft bereits"

            run_id = uuid.uuid4().hex[:8]
            self._active_runs[mode] = {
                "run_id": run_id,
                "source": "manual",
                "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": "queued",
            }

        worker = threading.Thread(
            target=self._execute_mode,
            args=(mode, "manual", run_id),
            name=f"automation-manual-{mode}",
            daemon=True,
        )
        worker.start()
        return True, run_id

    def get_status(self) -> Dict[str, Any]:
        cfg = load_config()
        auto_cfg = cfg.get("automation", {})

        with self._lock:
            jobs = {}
            for mode in AUTOMATION_MODES:
                mode_cfg = auto_cfg.get(mode, {}) if isinstance(auto_cfg, dict) else {}
                interval_minutes = int(mode_cfg.get("interval_minutes", 0) or 0)
                schedule_type = "interval" if interval_minutes > 0 else "cron"
                next_run = self._jobs.get(mode, {}).get("next_run")
                jobs[mode] = {
                    "enabled": bool(mode_cfg.get("enabled", False)),
                    "schedule": mode_cfg.get("schedule", ""),
                    "interval_minutes": interval_minutes,
                    "schedule_type": schedule_type,
                    "next_run": next_run.strftime("%Y-%m-%d %H:%M:%S") if isinstance(next_run, datetime) else None,
                    "active": mode in self._active_runs,
                    "active_run": self._active_runs.get(mode),
                }

        return {
            "running": bool(self._thread and self._thread.is_alive()),
            "enabled": bool(auto_cfg.get("enabled", False)) if isinstance(auto_cfg, dict) else False,
            "jobs": jobs,
        }

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._history_lock:
            return list(reversed(self._history[-max(1, min(limit, 200)):]))

    def _scheduler_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                cfg = load_config()
                auto_cfg = cfg.get("automation", {}) if isinstance(cfg, dict) else {}
                enabled = bool(auto_cfg.get("enabled", False)) if isinstance(auto_cfg, dict) else False

                if not enabled:
                    self._clear_next_runs()
                    # Responsive sleep: check stop event multiple times during sleep
                    for _ in range(5):
                        if self._stop_event.is_set():
                            return
                        time.sleep(1)
                    continue

                now = datetime.now()
                for mode in AUTOMATION_MODES:
                    mode_cfg = auto_cfg.get(mode, {}) if isinstance(auto_cfg, dict) else {}
                    self._update_job_schedule(mode, mode_cfg, now)

                    if not bool(mode_cfg.get("enabled", False)):
                        continue

                    if self._is_mode_active(mode):
                        continue

                    next_run = self._jobs.get(mode, {}).get("next_run")
                    if isinstance(next_run, datetime) and now >= next_run:
                        run_id = uuid.uuid4().hex[:8]
                        with self._lock:
                            self._active_runs[mode] = {
                                "run_id": run_id,
                                "source": "scheduled",
                                "started_at": now.strftime("%Y-%m-%d %H:%M:%S"),
                                "status": "queued",
                            }
                        self._jobs[mode]["last_trigger"] = now
                        self._jobs[mode]["next_run"] = self._compute_next_run(mode_cfg, now)

                        worker = threading.Thread(
                            target=self._execute_mode,
                            args=(mode, "scheduled", run_id),
                            name=f"automation-scheduled-{mode}",
                            daemon=True,
                        )
                        worker.start()
            except Exception as exc:
                log(f"[AUTOMATION-ERROR] Scheduler-Loop: {exc}")

            # Responsive sleep: check stop event every second
            for _ in range(5):
                if self._stop_event.is_set():
                    return
                time.sleep(1)

    def _clear_next_runs(self) -> None:
        with self._lock:
            for mode in AUTOMATION_MODES:
                self._jobs[mode]["next_run"] = None
                self._jobs[mode]["signature"] = None

    def _update_job_schedule(self, mode: str, mode_cfg: Dict[str, Any], now: datetime) -> None:
        enabled = bool(mode_cfg.get("enabled", False))
        schedule = (mode_cfg.get("schedule") or "").strip()
        interval_minutes = int(mode_cfg.get("interval_minutes", 0) or 0)
        signature = f"{enabled}|{schedule}|{interval_minutes}"

        with self._lock:
            job = self._jobs[mode]
            changed = signature != job.get("signature")
            if changed:
                job["signature"] = signature
                job["next_run"] = self._compute_next_run(mode_cfg, now)
            elif enabled and not isinstance(job.get("next_run"), datetime):
                job["next_run"] = self._compute_next_run(mode_cfg, now)
            elif not enabled:
                job["next_run"] = None

    def _compute_next_run(self, mode_cfg: Dict[str, Any], now: datetime) -> Optional[datetime]:
        if not bool(mode_cfg.get("enabled", False)):
            return None

        interval_minutes = int(mode_cfg.get("interval_minutes", 0) or 0)
        schedule = (mode_cfg.get("schedule") or "").strip()

        if interval_minutes > 0:
            return now + timedelta(minutes=interval_minutes)

        if schedule:
            try:
                return croniter(schedule, now).get_next(datetime)
            except Exception as exc:
                log(f"[AUTOMATION-WARN] Ungueltiger Cron-Ausdruck '{schedule}': {exc}")
                return None

        return None

    def _is_mode_active(self, mode: str) -> bool:
        with self._lock:
            return mode in self._active_runs

    def _execute_mode(self, mode: str, source: str, run_id: str) -> None:
        try:
            self._set_run_status(mode, "waiting")
            while downloader.is_running() and not self._stop_event.is_set():
                time.sleep(2)

            if self._stop_event.is_set():
                self._set_run_status(mode, "cancelled")
                return

            self._set_run_status(mode, "starting")
            started = downloader.start_download(mode)
            if not started:
                # Race condition: sobald wieder frei ist erneut versuchen.
                for _ in range(15):
                    if self._stop_event.is_set():
                        self._set_run_status(mode, "cancelled")
                        return
                    if not downloader.is_running() and downloader.start_download(mode):
                        started = True
                        break
                    time.sleep(2)

            if not started:
                self._set_run_status(mode, "failed_to_start")
                self._append_history(
                    {
                        "id": run_id,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "mode": mode,
                        "source": source,
                        "downloaded_count": 0,
                        "failed_count": 0,
                        "status": "failed_to_start",
                    }
                )
                return

            # Der Download-Thread startet asynchron. Ohne diese Wartephase kann
            # der Automation-Lauf fälschlich sofort als "finished" mit 0/0 enden.
            baseline_finished_at = None
            last_baseline = downloader.get_last_run_result()
            if isinstance(last_baseline, dict):
                baseline_finished_at = last_baseline.get("finished_at")

            for _ in range(20):
                if self._stop_event.is_set():
                    self._set_run_status(mode, "cancelled")
                    return

                if downloader.is_running():
                    break

                current_last = downloader.get_last_run_result()
                current_finished_at = current_last.get("finished_at") if isinstance(current_last, dict) else None
                if current_finished_at and current_finished_at != baseline_finished_at:
                    break

                time.sleep(0.25)

            self._set_run_status(mode, "running")
            while downloader.is_running() and not self._stop_event.is_set():
                time.sleep(2)

            # Warten bis der Worker das Ergebnis sicher in _last_run_result geschrieben hat.
            for _ in range(20):
                if self._stop_event.is_set():
                    break
                current_last = downloader.get_last_run_result()
                current_finished_at = current_last.get("finished_at") if isinstance(current_last, dict) else None
                if current_finished_at and current_finished_at != baseline_finished_at:
                    break
                time.sleep(0.25)

            last = downloader.get_last_run_result()
            result = last.get("result") if isinstance(last, dict) else None
            if not isinstance(result, dict):
                result = {"downloaded": [], "failed": []}

            cfg = load_config()
            mode_cfg = cfg.get("automation", {}).get(mode, {})
            filtered = self._apply_filters(result, mode_cfg)

            self._send_discord_notification(mode, filtered, mode_cfg)

            history_item = {
                "id": run_id,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "mode": mode,
                "source": source,
                "downloaded_count": len(filtered.get("downloaded", [])),
                "failed_count": len(filtered.get("failed", [])),
                "status": "finished",
            }
            self._append_history(history_item)
            self._set_run_status(mode, "finished")

        except Exception as exc:
            log(f"[AUTOMATION-ERROR] Lauf fuer {mode} fehlgeschlagen: {exc}")
            self._set_run_status(mode, "error")
        finally:
            with self._lock:
                self._active_runs.pop(mode, None)

    def _set_run_status(self, mode: str, status: str) -> None:
        with self._lock:
            if mode in self._active_runs:
                self._active_runs[mode]["status"] = status

    def _ensure_history_loaded(self) -> None:
        cfg = load_config()
        data_folder = Path(get_data_folder(cfg))
        data_folder.mkdir(parents=True, exist_ok=True)
        self._history_file = data_folder / "automation_history.json"

        if not self._history_file.exists():
            self._history = []
            return

        try:
            raw = self._history_file.read_text(encoding="utf-8")
            data = json.loads(raw) if raw.strip() else []
            if isinstance(data, list):
                self._history = data[-MAX_HISTORY_ITEMS:]
            else:
                self._history = []
        except Exception as exc:
            log(f"[AUTOMATION-WARN] History konnte nicht geladen werden: {exc}")
            self._history = []

    def _append_history(self, item: Dict[str, Any]) -> None:
        with self._history_lock:
            self._history.append(item)
            self._history = self._history[-MAX_HISTORY_ITEMS:]
            self._write_history_locked()

    def _write_history_locked(self) -> None:
        if not self._history_file:
            self._ensure_history_loaded()
        if not self._history_file:
            return

        try:
            self._history_file.write_text(
                json.dumps(self._history, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            log(f"[AUTOMATION-WARN] History konnte nicht gespeichert werden: {exc}")

    def _apply_filters(self, result: Dict[str, Any], mode_cfg: Dict[str, Any]) -> Dict[str, Any]:
        downloaded = list(result.get("downloaded", [])) if isinstance(result.get("downloaded", []), list) else []
        failed = list(result.get("failed", [])) if isinstance(result.get("failed", []), list) else []

        filter_mode = str(mode_cfg.get("filter_mode", "whitelist") or "whitelist").lower()
        if filter_mode == "off":
            return {
                "downloaded": [item for item in downloaded if isinstance(item, dict)],
                "failed": [item for item in failed if isinstance(item, dict)],
                "german": result.get("german") if isinstance(result.get("german"), dict) else None,
                "new": result.get("new") if isinstance(result.get("new"), dict) else None,
            }

        whitelist = [str(v).strip().lower() for v in (mode_cfg.get("whitelist", []) or []) if str(v).strip()]
        blacklist = [str(v).strip().lower() for v in (mode_cfg.get("blacklist", []) or []) if str(v).strip()]

        def allowed(item: Dict[str, Any]) -> bool:
            title = str(item.get("title", "") or "").lower()
            url = str(item.get("url", "") or "").lower()
            haystack = f"{title} {url}"

            if any(token in haystack for token in blacklist):
                return False
            if not whitelist:
                return True
            return any(token in haystack for token in whitelist)

        return {
            "downloaded": [item for item in downloaded if isinstance(item, dict) and allowed(item)],
            "failed": [item for item in failed if isinstance(item, dict) and allowed(item)],
            "german": result.get("german") if isinstance(result.get("german"), dict) else None,
            "new": result.get("new") if isinstance(result.get("new"), dict) else None,
        }

    def _send_discord_notification(self, mode: str, result: Dict[str, Any], mode_cfg: Dict[str, Any]) -> None:
        webhook = str(mode_cfg.get("discord_webhook", "") or "").strip()
        if not webhook:
            return

        downloaded = result.get("downloaded", []) if isinstance(result.get("downloaded"), list) else []
        failed = result.get("failed", []) if isinstance(result.get("failed"), list) else []
        notify_on_empty = bool(mode_cfg.get("notify_on_empty", False))

        if not downloaded and not notify_on_empty:
            return

        payload = self._build_discord_payload(mode, downloaded, failed)
        if payload is None:
            return

        try:
            resp = niquests.post(webhook, json=payload, timeout=10)
            if resp.status_code >= 400:
                log(f"[AUTOMATION-WARN] Discord Webhook fuer {mode} antwortete mit HTTP {resp.status_code}")
        except Exception as exc:
            log(f"[AUTOMATION-WARN] Discord Webhook fuer {mode} fehlgeschlagen: {exc}")

    def _build_discord_payload(self, mode: str, downloaded: List[Dict[str, Any]], failed: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        color_map = {
            "german": 0x4A90E2,
            "new": 0x2ECC71,
            "german_new": 0x4A90E2,
        }
        title_map = {
            "german": "🇩🇪 Neue Deutsche Episoden",
            "new": "📺 Neue Episoden",
            "german_new": "🇩🇪 + 📺 German & Neu",
        }

        if mode == "german_new":
            return self._build_discord_payload_german_new(downloaded, failed, now, color_map[mode], title_map[mode])

        grouped = self._group_episodes_by_series(downloaded)
        fields = []
        for series, episodes in grouped.items():
            lines = [
                f"S{int(ep.get('season', 0)):02d}E{int(ep.get('episode', 0)):03d} ({ep.get('language', 'Unknown')})"
                for ep in episodes
            ]
            fields.append({"name": series[:256], "value": "\n".join(lines)[:1024], "inline": False})

        if not fields:
            fields.append({"name": "Ergebnis", "value": "Keine neuen Downloads in diesem Lauf.", "inline": False})

        fields.append(
            {
                "name": "Zusammenfassung",
                "value": f"Downloads: {len(downloaded)} | Fehlgeschlagen: {len(failed)}",
                "inline": False,
            }
        )

        return {
            "embeds": [
                {
                    "title": title_map.get(mode, "Automation-Lauf"),
                    "color": color_map.get(mode, 0x4A90E2),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "footer": {"text": f"AniLoader Automation • {now}"},
                    "fields": fields[:25],
                }
            ]
        }

    def _build_discord_payload_german_new(
        self,
        downloaded: List[Dict[str, Any]],
        failed: List[Dict[str, Any]],
        now: str,
        color: int,
        title: str,
    ) -> Dict[str, Any]:
        german_items = [ep for ep in downloaded if str(ep.get("language", "")).lower() == "german dub"]
        new_items = [ep for ep in downloaded if str(ep.get("language", "")).lower() != "german dub"]

        fields: List[Dict[str, Any]] = [
            {
                "name": "Sektionen",
                "value": f"German: {len(german_items)} | New/Fallback: {len(new_items)}",
                "inline": False,
            }
        ]

        german_grouped = self._group_episodes_by_series(german_items)
        for series, episodes in german_grouped.items():
            lines = [f"S{int(ep.get('season', 0)):02d}E{int(ep.get('episode', 0)):03d}" for ep in episodes]
            fields.append({"name": f"DE • {series}"[:256], "value": "\n".join(lines)[:1024], "inline": False})

        new_grouped = self._group_episodes_by_series(new_items)
        for series, episodes in new_grouped.items():
            lines = [
                f"S{int(ep.get('season', 0)):02d}E{int(ep.get('episode', 0)):03d} ({ep.get('language', 'Unknown')})"
                for ep in episodes
            ]
            fields.append({"name": f"NEW • {series}"[:256], "value": "\n".join(lines)[:1024], "inline": False})

        if len(fields) == 1:
            fields.append({"name": "Ergebnis", "value": "Keine neuen Downloads in diesem Lauf.", "inline": False})

        fields.append(
            {
                "name": "Zusammenfassung",
                "value": f"Downloads: {len(downloaded)} | Fehlgeschlagen: {len(failed)}",
                "inline": False,
            }
        )

        return {
            "embeds": [
                {
                    "title": title,
                    "color": color,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "footer": {"text": f"AniLoader Automation • {now}"},
                    "fields": fields[:25],
                }
            ]
        }

    def _group_episodes_by_series(self, episodes: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for ep in episodes:
            title = str(ep.get("title", "Unbekannt"))
            grouped.setdefault(title, []).append(ep)

        for key in grouped:
            grouped[key].sort(key=lambda x: (int(x.get("season", 0)), int(x.get("episode", 0))))
        return grouped


automation_manager = AutomationManager()


def start_scheduler() -> None:
    automation_manager.start()


def stop_scheduler() -> None:
    automation_manager.stop()


def get_scheduler_status() -> Dict[str, Any]:
    return automation_manager.get_status()


def trigger_mode(mode: str) -> Tuple[bool, str]:
    return automation_manager.trigger_manual(mode)


def get_history(limit: int = 20) -> List[Dict[str, Any]]:
    return automation_manager.get_history(limit=limit)
