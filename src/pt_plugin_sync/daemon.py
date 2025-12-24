from __future__ import annotations

import threading
import time
from typing import Callable

from .config import Config
from .diffing import format_diff_summary
from .scan_cycle import perform_scan


class DebouncedRunner:
    def __init__(self, delay_seconds: int, action: Callable[[], None]) -> None:
        self._delay_seconds = max(delay_seconds, 0)
        self._action = action
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None

    def trigger(self) -> None:
        with self._lock:
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(self._delay_seconds, self._action)
            self._timer.daemon = True
            self._timer.start()

    def cancel(self) -> None:
        with self._lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None


def _perform_scan(config: Config, scan_lock: threading.Lock, pending: dict) -> None:
    if not scan_lock.acquire(blocking=False):
        pending["scan"] = True
        return
    try:
        while True:
            pending["scan"] = False
            try:
                result = perform_scan(config, open_report=True)
                if result.diff:
                    print(format_diff_summary(result.diff))
            except Exception as exc:
                print(f"Scan failed: {exc}")
            if not pending.get("scan"):
                break
    finally:
        scan_lock.release()


def run_daemon(config: Config) -> None:
    scan_lock = threading.Lock()
    pending: dict[str, bool] = {"scan": False}
    last_scan_time = 0.0

    def scan_action() -> None:
        nonlocal last_scan_time
        _perform_scan(config, scan_lock, pending)
        last_scan_time = time.time()

    scan_action()

    debouncer = DebouncedRunner(config.debounce_seconds, scan_action)

    observer = None
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer

        class Handler(FileSystemEventHandler):
            def on_any_event(self, event):  # type: ignore[override]
                debouncer.trigger()

        observer = Observer()
        observer.schedule(Handler(), str(config.expanded_plugins_path()), recursive=False)
        observer.start()
        print("Filesystem watcher enabled.")
    except Exception as exc:
        print(f"Watcher unavailable, using periodic scans only: {exc}")

    try:
        while True:
            time.sleep(1)
            if time.time() - last_scan_time >= config.scan_interval_seconds:
                scan_action()
    except KeyboardInterrupt:
        print("Shutting down daemon...")
    finally:
        debouncer.cancel()
        if observer:
            observer.stop()
            observer.join(timeout=5)
