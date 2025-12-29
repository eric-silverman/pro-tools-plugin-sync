from __future__ import annotations

import pathlib
import shutil
import subprocess
import threading
import tempfile
import sys
import tempfile
from datetime import datetime
from dataclasses import dataclass

import rumps

from .config import (
    CONFIG_DIR,
    CONFIG_PATH,
    Config,
    default_config,
    load_config,
    validate_config,
    write_config,
)
from .daemon import DebouncedRunner
from .launchd import (
    install_menubar_launchagent,
    is_menubar_launchagent_installed,
    uninstall_launchagent,
    uninstall_menubar_launchagent,
    LOG_DIR,
)
from .scan_cycle import perform_scan
from .combined_report import COMBINED_HTML_LATEST_FILENAME
from .auto_update import find_app_bundle, install_update
from .update_check import current_version, is_update_available, latest_release

@dataclass
class IconPaths:
    idle: str | None
    scanning: str | None
    updates: str | None


class IconAssets:
    def __init__(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.paths = IconPaths(
            idle=self._write_resource("icons8-check-mark-50.png"),
            scanning=self._write_resource("icons8-sync-50.png"),
            updates=self._write_resource("icons8-attention-50.png"),
        )

    def _write_resource(self, name: str) -> str | None:
        try:
            from importlib import resources

            data = resources.files("pt_plugin_sync.resources").joinpath(name).read_bytes()
        except Exception:
            return None
        target = pathlib.Path(self._temp_dir.name) / name
        target.write_bytes(data)
        return str(target)


class MenuState:
    IDLE = "idle"
    SCANNING = "scanning"
    UPDATES = "updates"


class ReleaseState:
    UNKNOWN = "unknown"
    UP_TO_DATE = "up_to_date"
    UPDATE_AVAILABLE = "update_available"


class MenuBarApp(rumps.App):
    def __init__(self, config: Config) -> None:
        super().__init__("PT", quit_button=None)
        self.config = config
        self._icon_assets = IconAssets()
        self._state = MenuState.IDLE
        self._release_state = ReleaseState.UNKNOWN
        self._scan_lock = threading.Lock()
        self._pending_scan = False
        self._last_summary: dict | None = None
        self._last_update_count = 0
        self._last_report_path: pathlib.Path | None = None
        self._last_scan_time: datetime | None = None
        self._current_version = current_version()
        self._latest_release_version: str | None = None
        self._observer = None
        self._debouncer: DebouncedRunner | None = None
        self._timer: rumps.Timer | None = None
        self._settings_server = None
        self._report_temp_dir: tempfile.TemporaryDirectory | None = None

        self._status_item = rumps.MenuItem("Status: Idle")
        self._last_scan_item = rumps.MenuItem("Last Scan: Never")
        self._version_item = rumps.MenuItem(f"App Version: {self._current_version}")
        self._release_item = rumps.MenuItem("Release: Checking...")
        self._scan_item = rumps.MenuItem("Scan Now", callback=self._on_scan)
        self._open_report_item = rumps.MenuItem("Open Report", callback=self._on_open_report)
        self._open_reports_item = rumps.MenuItem(
            "Open Reports Folder", callback=self._on_open_reports_folder
        )
        self._settings_item = rumps.MenuItem("Settings...", callback=self._on_open_settings)
        self._dropbox_auth_item = rumps.MenuItem(
            "Authorize Dropbox...", callback=self._on_authorize_dropbox
        )
        self._edit_config_item = rumps.MenuItem("Edit Config File...", callback=self._on_edit_config)
        self._reload_config_item = rumps.MenuItem(
            "Reload Config", callback=self._on_reload_config
        )
        self._updates_item = rumps.MenuItem(
            "Check for Updates...", callback=self._on_check_updates
        )
        self._auto_update_item = rumps.MenuItem(
            "Install Updates Automatically", callback=self._on_toggle_auto_update
        )
        self._start_login_item = rumps.MenuItem(
            "Start at Login", callback=self._on_toggle_login
        )
        self._uninstall_item = rumps.MenuItem("Uninstall...", callback=self._on_uninstall)
        self._quit_item = rumps.MenuItem("Quit", callback=self._on_quit)

        self.menu = [
            self._status_item,
            self._last_scan_item,
            self._version_item,
            self._release_item,
            None,
            self._scan_item,
            self._open_report_item,
            self._open_reports_item,
            None,
            self._settings_item,
            self._dropbox_auth_item,
            self._edit_config_item,
            self._reload_config_item,
            self._updates_item,
            self._auto_update_item,
            self._start_login_item,
            self._uninstall_item,
            None,
            self._quit_item,
        ]

        self._apply_state(MenuState.IDLE)
        self._update_release_items()
        self._update_start_login_item()
        self._update_auto_update_item()
        self._setup_timer()
        self._setup_watcher()
        self._warn_if_invalid_config()
        self._start_update_check()

    def _setup_timer(self) -> None:
        if self._timer:
            self._timer.stop()
        self._timer = rumps.Timer(self._on_timer, self.config.scan_interval_seconds)
        self._timer.start()

    def _setup_watcher(self) -> None:
        self._teardown_watcher()
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer

            outer = self

            class Handler(FileSystemEventHandler):
                def on_any_event(self, event):  # type: ignore[override]
                    if outer._debouncer:
                        outer._debouncer.trigger()

            self._debouncer = DebouncedRunner(self.config.debounce_seconds, self._on_scan)
            self._observer = Observer()
            self._observer.schedule(
                Handler(), str(self.config.expanded_plugins_path()), recursive=False
            )
            self._observer.start()
        except Exception:
            self._observer = None
            self._debouncer = None

    def _teardown_watcher(self) -> None:
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
        if self._debouncer:
            self._debouncer.cancel()
            self._debouncer = None

    def _apply_state(self, state: str) -> None:
        self._state = state
        if state == MenuState.SCANNING:
            self.title = "PT*"
            self._status_item.title = "Status: Scanning"
            icon = self._icon_assets.paths.scanning
        elif state == MenuState.UPDATES:
            self.title = "PT!"
            self._status_item.title = f"Status: Updates ({self._last_update_count})"
            icon = self._icon_assets.paths.updates
        else:
            self.title = "PT"
            self._status_item.title = "Status: Idle"
            icon = self._icon_assets.paths.idle
        if icon:
            self.icon = icon
            self.template = True

    def _update_release_items(self) -> None:
        current = self._current_version
        if self._release_state == ReleaseState.UPDATE_AVAILABLE:
            latest = self._latest_release_version or "unknown"
            self._release_item.title = f"Release: Update Available (v{latest})"
        elif self._release_state == ReleaseState.UP_TO_DATE:
            self._release_item.title = f"Release: Up to date (v{current})"
        else:
            self._release_item.title = "Release: Checking..."
        self._version_item.title = f"App Version: {current}"

    def _update_last_scan_item(self) -> None:
        if self._last_scan_time is None:
            self._last_scan_item.title = "Last Scan: Never"
            return
        stamp = self._last_scan_time.strftime("%Y-%m-%d %H:%M")
        self._last_scan_item.title = f"Last Scan: {stamp}"

    def _update_start_login_item(self) -> None:
        self._start_login_item.state = 1 if is_menubar_launchagent_installed() else 0

    def _update_auto_update_item(self) -> None:
        self._auto_update_item.state = 1 if self.config.auto_update_download else 0

    def _on_timer(self, _timer: rumps.Timer) -> None:
        self._on_scan()

    def _on_scan(self, _sender=None) -> None:
        if not self._scan_lock.acquire(blocking=False):
            self._pending_scan = True
            return
        thread = threading.Thread(target=self._scan_worker)
        thread.daemon = True
        thread.start()

    def _scan_worker(self) -> None:
        self._apply_state(MenuState.SCANNING)
        try:
            result = perform_scan(self.config, open_report=True)
            self._last_summary = result.summary
            self._last_update_count = result.update_count
            self._last_report_path = result.report_path
            self._last_scan_time = datetime.now()
            self._update_last_scan_item()
            if result.update_count > 0:
                self._apply_state(MenuState.UPDATES)
            else:
                self._apply_state(MenuState.IDLE)
        except Exception as exc:
            self._apply_state(MenuState.IDLE)
            self._last_scan_time = datetime.now()
            self._update_last_scan_item()
            if isinstance(exc, PermissionError) or (
                isinstance(exc, OSError) and exc.errno in (1, 13)
            ):
                self._alert_scan_permissions()
            else:
                rumps.alert("Scan failed", str(exc))
        finally:
            self._scan_lock.release()
            if self._pending_scan:
                self._pending_scan = False
                self._on_scan()

    def _on_open_report(self, _sender=None) -> None:
        if self.config.reports_backend != "local":
            try:
                from .dropbox_store import DropboxReportStore
            except Exception as exc:
                rumps.alert("Dropbox unavailable", str(exc))
                return
            try:
                store = DropboxReportStore.from_config(self.config)
                html_payload = store.download_latest_report_html()
            except Exception as exc:
                rumps.alert("Report unavailable", str(exc))
                return
            if not html_payload:
                rumps.alert("No report yet", "Run a scan first.")
                return
            if self._report_temp_dir is None:
                self._report_temp_dir = tempfile.TemporaryDirectory()
            target = pathlib.Path(self._report_temp_dir.name) / COMBINED_HTML_LATEST_FILENAME
            target.write_text(html_payload, encoding="utf-8")
            _open_path(str(target))
            return
        latest = self.config.expanded_reports_path() / COMBINED_HTML_LATEST_FILENAME
        if latest.exists():
            _open_path(str(latest))
            return
        if not self._last_summary:
            rumps.alert("No report yet", "Run a scan first.")
            return
        result = perform_scan(self.config, open_report=True)
        self._last_summary = result.summary
        self._last_update_count = result.update_count
        self._last_report_path = result.report_path
        if result.report_path and result.report_path.exists():
            _open_path(str(result.report_path))
            return
        if result.update_count == 0:
            rumps.alert("No updates needed", "All plugins are up to date.")

    def _on_open_reports_folder(self, _sender=None) -> None:
        if self.config.reports_backend != "local":
            rumps.alert(
                "Reports in Dropbox",
                "Open the Dropbox folder to view reports.",
            )
            return
        reports_path = self.config.expanded_reports_path()
        _open_path(str(reports_path))

    def _on_open_settings(self, _sender=None) -> None:
        if not CONFIG_PATH.exists():
            write_config(default_config())
        server = self._ensure_settings_server()
        if not server:
            return
        if server.is_running():
            if server.url:
                _open_path(server.url)
            return
        url = server.start()
        _open_path(url)

    def _on_authorize_dropbox(self, _sender=None) -> None:
        if not self.config.dropbox_app_key or not self.config.dropbox_app_secret:
            rumps.alert(
                "Dropbox setup",
                "Enter the Dropbox app key and secret in Settings first.",
            )
            self._on_open_settings()
            return
        server = self._ensure_settings_server()
        if not server:
            return
        url = server.dropbox_auth_url()
        _open_path(url)

    def _ensure_settings_server(self):
        if self._settings_server is None:
            try:
                from .settings_server import SettingsServer
            except Exception as exc:
                rumps.alert("Settings unavailable", str(exc))
                return None
            self._settings_server = SettingsServer(self.config, self._apply_settings)
        return self._settings_server

    def _on_edit_config(self, _sender=None) -> None:
        if not CONFIG_PATH.exists():
            write_config(default_config())
        _open_path(str(CONFIG_PATH), app="TextEdit")

    def _on_reload_config(self, _sender=None) -> None:
        config = load_config()
        if config is None:
            rumps.alert("Config missing", "Open Edit Config... to create it.")
            return
        validation = validate_config(config)
        if not validation.ok:
            rumps.alert("Configuration invalid", "\n".join(validation.errors))
        self._apply_settings(config)

    def _apply_settings(self, updated: Config) -> None:
        self.config = updated
        self._setup_timer()
        self._setup_watcher()
        self._update_auto_update_item()

    def _warn_if_invalid_config(self) -> None:
        validation = validate_config(self.config)
        if not validation.ok:
            rumps.alert("Configuration invalid", "\n".join(validation.errors))

    def _on_toggle_login(self, _sender=None) -> None:
        if is_menubar_launchagent_installed():
            uninstall_menubar_launchagent()
        else:
            install_menubar_launchagent(self.config)
        self._update_start_login_item()

    def _on_quit(self, _sender=None) -> None:
        self._teardown_watcher()
        rumps.quit_application()

    def _on_uninstall(self, _sender=None) -> None:
        prompt = rumps.Window(
            "Type UNINSTALL to remove app settings and login items.",
            default_text="",
            ok="Uninstall",
            cancel="Cancel",
        ).run()
        if not prompt.clicked or prompt.text.strip() != "UNINSTALL":
            return
        uninstall_menubar_launchagent()
        uninstall_launchagent()
        if CONFIG_PATH.exists():
            CONFIG_PATH.unlink()
        if CONFIG_DIR.exists():
            try:
                CONFIG_DIR.rmdir()
            except OSError:
                pass
        if LOG_DIR.exists():
            shutil.rmtree(LOG_DIR, ignore_errors=True)
        rumps.alert("Uninstalled", "Login items and settings removed.")
        self._on_quit()

    def _alert_scan_permissions(self) -> None:
        path = self.config.expanded_plugins_path()
        rumps.alert(
            "Scan blocked by permissions",
            "The app cannot read your plug-ins folder.\n\n"
            f"Folder: {path}\n\n"
            "Fix options:\n"
            "1) System Settings → Privacy & Security → Full Disk Access.\n"
            "   Enable “Pro Tools Plugin Sync”, then relaunch the app.\n"
            "2) Move the plug-ins folder out of Desktop/Documents and update Settings.",
        )


    def _on_toggle_auto_update(self, _sender=None) -> None:
        updated = Config(
            machine_name=self.config.machine_name,
            plugins_path=self.config.plugins_path,
            reports_path=self.config.reports_path,
            reports_backend=self.config.reports_backend,
            dropbox_app_key=self.config.dropbox_app_key,
            dropbox_app_secret=self.config.dropbox_app_secret,
            dropbox_refresh_token=self.config.dropbox_refresh_token,
            dropbox_reports_path=self.config.dropbox_reports_path,
            scan_interval_seconds=self.config.scan_interval_seconds,
            debounce_seconds=self.config.debounce_seconds,
            hash_binaries=self.config.hash_binaries,
            prune_days=self.config.prune_days,
            auto_update_download=not self.config.auto_update_download,
        )
        write_config(updated)
        self.config = updated
        self._update_auto_update_item()

    def _start_update_check(self) -> None:
        thread = threading.Thread(target=self._check_updates, kwargs={"show_no_updates": False})
        thread.daemon = True
        thread.start()

    def _on_check_updates(self, _sender=None) -> None:
        thread = threading.Thread(target=self._check_updates, kwargs={"show_no_updates": True})
        thread.daemon = True
        thread.start()

    def _check_updates(self, *, show_no_updates: bool) -> None:
        try:
            release = latest_release()
            if not release:
                self._release_state = ReleaseState.UNKNOWN
                self._latest_release_version = None
                self._update_release_items()
                if show_no_updates:
                    rumps.alert("Update check failed", "No release information available.")
                return
            current = current_version()
            if not is_update_available(current, release.version):
                self._current_version = current
                self._latest_release_version = release.version
                self._release_state = ReleaseState.UP_TO_DATE
                self._update_release_items()
                if show_no_updates:
                    rumps.alert("Up to date", f"Version {current} is current.")
                return
            self._current_version = current
            self._latest_release_version = release.version
            self._release_state = ReleaseState.UPDATE_AVAILABLE
            self._update_release_items()
            message = f"Version {release.version} is available (you have {current})."
            notes = _format_release_notes(release.notes)
            if notes:
                message += f"\n\nNotes:\n{notes}"
            if release.asset_url:
                message += "\n\nInstall the latest update now?"
            if self.config.auto_update_download and release.asset_url:
                self._run_auto_update(release.asset_url)
                return
            if release.asset_url:
                prompt = rumps.alert("Update available", message, ok="Install", cancel="Later")
            else:
                prompt = rumps.alert("Update available", message, ok="Open Release", cancel="Later")
            if prompt == 1:
                if release.asset_url:
                    self._run_auto_update(release.asset_url)
                elif release.url:
                    _open_path(release.url)
        except Exception as exc:
            self._release_state = ReleaseState.UNKNOWN
            self._latest_release_version = None
            self._update_release_items()
            if show_no_updates:
                rumps.alert("Update check failed", str(exc))

    def _run_auto_update(self, asset_url: str) -> None:
        rumps.alert(
            "Updating",
            "Downloading and installing the latest version. The app will relaunch.",
        )
        bundle_path = find_app_bundle(sys.argv[0])
        try:
            install_update(asset_url, bundle_path)
        except Exception as exc:
            rumps.alert("Update failed", str(exc))
            return
        rumps.quit_application()


def _ensure_config() -> Config:
    config = load_config()
    if config is not None:
        return config
    config = default_config()
    write_config(config)
    return config


def run_menubar() -> None:
    app = MenuBarApp(_ensure_config())
    app.run()


def _open_path(path: str, app: str | None = None) -> None:
    if shutil.which("open") is None:
        return
    if app:
        subprocess.run(["open", "-a", app, path], capture_output=True, text=True)
    else:
        subprocess.run(["open", path], capture_output=True, text=True)


def _format_release_notes(notes: str) -> str:
    if not notes:
        return ""
    lines = [line.strip() for line in notes.splitlines() if line.strip()]
    if not lines:
        return ""
    max_lines = 6
    trimmed = lines[:max_lines]
    if len(lines) > max_lines:
        trimmed.append("...")
    return "\n".join(trimmed)
