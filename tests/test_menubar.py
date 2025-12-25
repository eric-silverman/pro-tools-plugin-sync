from __future__ import annotations

import importlib
import sys
import types

from pt_plugin_sync.config import Config


class _FakeMenuItem:
    def __init__(self, title, callback=None):
        self.title = title
        self.callback = callback
        self.state = 0


class _FakeTimer:
    def __init__(self, _callback, _interval):
        self._callback = _callback
        self._interval = _interval
        self._running = False

    def start(self):
        self._running = True

    def stop(self):
        self._running = False


class _FakeApp:
    def __init__(self, title, quit_button=None):
        self.title = title
        self.quit_button = quit_button
        self.menu = []
        self.icon = None
        self.template = False

    def run(self):
        return None


def _install_fake_rumps(monkeypatch):
    fake_rumps = types.SimpleNamespace(
        App=_FakeApp,
        MenuItem=_FakeMenuItem,
        Timer=_FakeTimer,
        alert=lambda *args, **kwargs: 0,
        Window=lambda *args, **kwargs: types.SimpleNamespace(run=lambda: types.SimpleNamespace(clicked=False, text="")),
        quit_application=lambda: None,
    )
    monkeypatch.setitem(sys.modules, "rumps", fake_rumps)


def _load_menubar(monkeypatch):
    _install_fake_rumps(monkeypatch)
    if "pt_plugin_sync.menubar" in sys.modules:
        del sys.modules["pt_plugin_sync.menubar"]
    import pt_plugin_sync.menubar as menubar_module
    return importlib.reload(menubar_module)


def test_format_release_notes_trims(monkeypatch) -> None:
    menubar_module = _load_menubar(monkeypatch)
    _format_release_notes = menubar_module._format_release_notes
    notes = "\n".join([f"Line {idx}" for idx in range(10)])
    trimmed = _format_release_notes(notes)
    assert trimmed.count("\n") == 6
    assert trimmed.endswith("...")


def test_latest_html_report_picks_newest(tmp_path, monkeypatch) -> None:
    menubar_module = _load_menubar(monkeypatch)
    _latest_html_report = menubar_module._latest_html_report
    first = tmp_path / "a.html"
    second = tmp_path / "b.html"
    first.write_text("a", encoding="utf-8")
    second.write_text("b", encoding="utf-8")
    first.touch()
    second.touch()
    newest = _latest_html_report(tmp_path)
    assert newest == second


def test_menu_state_updates_titles(monkeypatch, tmp_path) -> None:
    menubar_module = _load_menubar(monkeypatch)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_timer", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_watcher", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_start_update_check", lambda self: None)
    monkeypatch.setattr(menubar_module.IconAssets, "_write_resource", lambda self, name: None)
    monkeypatch.setattr(menubar_module, "current_version", lambda: "1.0.0")
    config = Config(
        machine_name="Studio",
        plugins_path=str(tmp_path / "plugins"),
        reports_path=str(tmp_path / "reports"),
        reports_backend="local",
    )
    app = menubar_module.MenuBarApp(config)
    app._last_update_count = 2
    app._apply_state(menubar_module.MenuState.UPDATES)
    assert app.title == "PT!"
    assert "Updates (2)" in app._status_item.title


def test_toggle_auto_update_writes_config(monkeypatch, tmp_path) -> None:
    menubar_module = _load_menubar(monkeypatch)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_timer", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_watcher", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_start_update_check", lambda self: None)
    monkeypatch.setattr(menubar_module.IconAssets, "_write_resource", lambda self, name: None)
    monkeypatch.setattr(menubar_module, "current_version", lambda: "1.0.0")
    captured = {}

    def fake_write_config(config):
        captured["config"] = config

    monkeypatch.setattr(menubar_module, "write_config", fake_write_config)
    config = Config(
        machine_name="Studio",
        plugins_path=str(tmp_path / "plugins"),
        reports_path=str(tmp_path / "reports"),
        reports_backend="local",
    )
    app = menubar_module.MenuBarApp(config)
    app._on_toggle_auto_update()
    assert captured["config"].auto_update_download is True


def test_open_reports_folder_calls_open(monkeypatch, tmp_path) -> None:
    menubar_module = _load_menubar(monkeypatch)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_timer", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_watcher", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_start_update_check", lambda self: None)
    monkeypatch.setattr(menubar_module.IconAssets, "_write_resource", lambda self, name: None)
    monkeypatch.setattr(menubar_module, "current_version", lambda: "1.0.0")
    opened = {}

    def fake_open(path, app=None):
        opened["path"] = path
        opened["app"] = app

    monkeypatch.setattr(menubar_module, "_open_path", fake_open)
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    config = Config(
        machine_name="Studio",
        plugins_path=str(tmp_path / "plugins"),
        reports_path=str(reports_dir),
        reports_backend="local",
    )
    app = menubar_module.MenuBarApp(config)
    app._on_open_reports_folder()
    assert opened["path"] == str(reports_dir)


def test_open_latest_html_alerts_when_missing(monkeypatch, tmp_path) -> None:
    menubar_module = _load_menubar(monkeypatch)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_timer", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_watcher", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_start_update_check", lambda self: None)
    monkeypatch.setattr(menubar_module.IconAssets, "_write_resource", lambda self, name: None)
    monkeypatch.setattr(menubar_module, "current_version", lambda: "1.0.0")
    alerts = []

    def fake_alert(title, message):
        alerts.append((title, message))
        return 0

    menubar_module.rumps.alert = fake_alert
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    config = Config(
        machine_name="Studio",
        plugins_path=str(plugins_dir),
        reports_path=str(reports_dir),
        reports_backend="local",
    )
    app = menubar_module.MenuBarApp(config)
    app._on_open_latest_html()
    assert alerts and "No HTML reports found" in alerts[0][0]


def test_open_latest_html_opens_when_present(monkeypatch, tmp_path) -> None:
    menubar_module = _load_menubar(monkeypatch)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_timer", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_watcher", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_start_update_check", lambda self: None)
    monkeypatch.setattr(menubar_module.IconAssets, "_write_resource", lambda self, name: None)
    monkeypatch.setattr(menubar_module, "current_version", lambda: "1.0.0")
    opened = {}

    def fake_open(path, app=None):
        opened["path"] = path

    monkeypatch.setattr(menubar_module, "_open_path", fake_open)
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    report = reports_dir / "updates__Studio__latest.html"
    report.write_text("report", encoding="utf-8")
    config = Config(
        machine_name="Studio",
        plugins_path=str(tmp_path / "plugins"),
        reports_path=str(reports_dir),
        reports_backend="local",
    )
    app = menubar_module.MenuBarApp(config)
    app._on_open_latest_html()
    assert opened["path"] == str(report)


def test_open_report_uses_existing_latest(monkeypatch, tmp_path) -> None:
    menubar_module = _load_menubar(monkeypatch)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_timer", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_watcher", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_start_update_check", lambda self: None)
    monkeypatch.setattr(menubar_module.IconAssets, "_write_resource", lambda self, name: None)
    monkeypatch.setattr(menubar_module, "current_version", lambda: "1.0.0")
    opened = {}

    def fake_open(path, app=None):
        opened["path"] = path

    monkeypatch.setattr(menubar_module, "_open_path", fake_open)
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    report = reports_dir / "updates__Studio__latest.html"
    report.write_text("report", encoding="utf-8")
    config = Config(
        machine_name="Studio",
        plugins_path=str(tmp_path / "plugins"),
        reports_path=str(reports_dir),
        reports_backend="local",
    )
    app = menubar_module.MenuBarApp(config)
    app._on_open_report()
    assert opened["path"] == str(report)


def test_open_report_alerts_without_summary(monkeypatch, tmp_path) -> None:
    menubar_module = _load_menubar(monkeypatch)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_timer", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_watcher", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_start_update_check", lambda self: None)
    monkeypatch.setattr(menubar_module.IconAssets, "_write_resource", lambda self, name: None)
    monkeypatch.setattr(menubar_module, "current_version", lambda: "1.0.0")
    alerts = []

    def fake_alert(title, message):
        alerts.append((title, message))
        return 0

    menubar_module.rumps.alert = fake_alert
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    config = Config(
        machine_name="Studio",
        plugins_path=str(plugins_dir),
        reports_path=str(reports_dir),
        reports_backend="local",
    )
    app = menubar_module.MenuBarApp(config)
    app._on_open_report()
    assert alerts and "No update report yet" in alerts[0][0]


def test_authorize_dropbox_requires_credentials(monkeypatch, tmp_path) -> None:
    menubar_module = _load_menubar(monkeypatch)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_timer", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_watcher", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_start_update_check", lambda self: None)
    monkeypatch.setattr(menubar_module.IconAssets, "_write_resource", lambda self, name: None)
    monkeypatch.setattr(menubar_module, "current_version", lambda: "1.0.0")
    opened_settings = []

    def fake_open_settings(self):
        opened_settings.append(True)

    monkeypatch.setattr(menubar_module.MenuBarApp, "_on_open_settings", fake_open_settings)
    alerts = []

    def fake_alert(title, message):
        alerts.append((title, message))
        return 0

    menubar_module.rumps.alert = fake_alert
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    config = Config(
        machine_name="Studio",
        plugins_path=str(plugins_dir),
        reports_path=str(reports_dir),
        reports_backend="local",
    )
    app = menubar_module.MenuBarApp(config)
    app._on_authorize_dropbox()
    assert alerts and "Dropbox setup" in alerts[0][0]
    assert opened_settings


def test_authorize_dropbox_opens_auth_url(monkeypatch, tmp_path) -> None:
    menubar_module = _load_menubar(monkeypatch)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_timer", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_watcher", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_start_update_check", lambda self: None)
    monkeypatch.setattr(menubar_module.IconAssets, "_write_resource", lambda self, name: None)
    monkeypatch.setattr(menubar_module, "current_version", lambda: "1.0.0")
    opened = {}

    def fake_open(path, app=None):
        opened["path"] = path

    monkeypatch.setattr(menubar_module, "_open_path", fake_open)

    class FakeServer:
        def dropbox_auth_url(self):
            return "http://localhost/auth"

    monkeypatch.setattr(menubar_module.MenuBarApp, "_ensure_settings_server", lambda self: FakeServer())
    config = Config(
        machine_name="Studio",
        plugins_path=str(tmp_path / "plugins"),
        reports_path=str(tmp_path / "reports"),
        reports_backend="local",
        dropbox_app_key="key",
        dropbox_app_secret="secret",
    )
    app = menubar_module.MenuBarApp(config)
    app._on_authorize_dropbox()
    assert opened["path"] == "http://localhost/auth"


def test_check_updates_auto_download(monkeypatch, tmp_path) -> None:
    menubar_module = _load_menubar(monkeypatch)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_timer", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_watcher", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_start_update_check", lambda self: None)
    monkeypatch.setattr(menubar_module.IconAssets, "_write_resource", lambda self, name: None)
    monkeypatch.setattr(menubar_module, "current_version", lambda: "1.0.0")
    monkeypatch.setattr(menubar_module, "is_update_available", lambda *_: True)

    class Release:
        version = "1.0.1"
        asset_url = "http://example.com/asset"
        url = "http://example.com/release"
        notes = "Notes"

    monkeypatch.setattr(menubar_module, "latest_release", lambda: Release())
    opened = {}

    def fake_open(path, app=None):
        opened["path"] = path

    monkeypatch.setattr(menubar_module, "_open_path", fake_open)
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    config = Config(
        machine_name="Studio",
        plugins_path=str(plugins_dir),
        reports_path=str(reports_dir),
        reports_backend="local",
        auto_update_download=True,
    )
    app = menubar_module.MenuBarApp(config)
    app._check_updates(show_no_updates=False)
    assert opened["path"] == "http://example.com/asset"


def test_check_updates_up_to_date_alerts(monkeypatch, tmp_path) -> None:
    menubar_module = _load_menubar(monkeypatch)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_timer", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_watcher", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_start_update_check", lambda self: None)
    monkeypatch.setattr(menubar_module.IconAssets, "_write_resource", lambda self, name: None)
    monkeypatch.setattr(menubar_module, "current_version", lambda: "1.0.0")
    monkeypatch.setattr(menubar_module, "is_update_available", lambda *_: False)

    class Release:
        version = "1.0.0"
        asset_url = None
        url = "http://example.com/release"
        notes = ""

    monkeypatch.setattr(menubar_module, "latest_release", lambda: Release())
    alerts = []

    def fake_alert(title, message, ok=None, cancel=None):
        alerts.append((title, message))
        return 0

    menubar_module.rumps.alert = fake_alert
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    config = Config(
        machine_name="Studio",
        plugins_path=str(plugins_dir),
        reports_path=str(reports_dir),
        reports_backend="local",
        auto_update_download=False,
    )
    app = menubar_module.MenuBarApp(config)
    app._check_updates(show_no_updates=True)
    assert alerts and "Up to date" in alerts[0][0]


def test_open_path_no_open_command(monkeypatch, tmp_path) -> None:
    menubar_module = _load_menubar(monkeypatch)
    monkeypatch.setattr(menubar_module.shutil, "which", lambda _name: None)
    result = menubar_module._open_path(str(tmp_path))
    assert result is None


def test_open_reports_folder_dropbox_alerts(monkeypatch, tmp_path) -> None:
    menubar_module = _load_menubar(monkeypatch)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_timer", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_watcher", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_start_update_check", lambda self: None)
    monkeypatch.setattr(menubar_module.IconAssets, "_write_resource", lambda self, name: None)
    monkeypatch.setattr(menubar_module, "current_version", lambda: "1.0.0")
    alerts = []

    def fake_alert(title, message):
        alerts.append((title, message))
        return 0

    menubar_module.rumps.alert = fake_alert
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    config = Config(
        machine_name="Studio",
        plugins_path=str(plugins_dir),
        reports_path=str(reports_dir),
        reports_backend="dropbox",
        dropbox_app_key="key",
        dropbox_app_secret="secret",
        dropbox_refresh_token="token",
        dropbox_reports_path="/Reports",
    )
    app = menubar_module.MenuBarApp(config)
    app._on_open_reports_folder()
    assert alerts and "Reports in Dropbox" in alerts[0][0]


def test_open_latest_html_dropbox_alerts(monkeypatch, tmp_path) -> None:
    menubar_module = _load_menubar(monkeypatch)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_timer", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_watcher", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_start_update_check", lambda self: None)
    monkeypatch.setattr(menubar_module.IconAssets, "_write_resource", lambda self, name: None)
    monkeypatch.setattr(menubar_module, "current_version", lambda: "1.0.0")
    alerts = []

    def fake_alert(title, message):
        alerts.append((title, message))
        return 0

    menubar_module.rumps.alert = fake_alert
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    config = Config(
        machine_name="Studio",
        plugins_path=str(plugins_dir),
        reports_path=str(reports_dir),
        reports_backend="dropbox",
        dropbox_app_key="key",
        dropbox_app_secret="secret",
        dropbox_refresh_token="token",
        dropbox_reports_path="/Reports",
    )
    app = menubar_module.MenuBarApp(config)
    app._on_open_latest_html()
    assert alerts and "Reports in Dropbox" in alerts[0][0]


def test_open_report_dropbox_alerts(monkeypatch, tmp_path) -> None:
    menubar_module = _load_menubar(monkeypatch)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_timer", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_watcher", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_start_update_check", lambda self: None)
    monkeypatch.setattr(menubar_module.IconAssets, "_write_resource", lambda self, name: None)
    monkeypatch.setattr(menubar_module, "current_version", lambda: "1.0.0")
    alerts = []

    def fake_alert(title, message):
        alerts.append((title, message))
        return 0

    menubar_module.rumps.alert = fake_alert
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    config = Config(
        machine_name="Studio",
        plugins_path=str(plugins_dir),
        reports_path=str(reports_dir),
        reports_backend="dropbox",
        dropbox_app_key="key",
        dropbox_app_secret="secret",
        dropbox_refresh_token="token",
        dropbox_reports_path="/Reports",
    )
    app = menubar_module.MenuBarApp(config)
    app._on_open_report()
    assert alerts and "Reports in Dropbox" in alerts[0][0]


def test_reload_config_alerts_invalid(monkeypatch, tmp_path) -> None:
    menubar_module = _load_menubar(monkeypatch)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_timer", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_watcher", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_start_update_check", lambda self: None)
    monkeypatch.setattr(menubar_module.IconAssets, "_write_resource", lambda self, name: None)
    monkeypatch.setattr(menubar_module, "current_version", lambda: "1.0.0")
    alerts = []

    def fake_alert(title, message):
        alerts.append((title, message))
        return 0

    menubar_module.rumps.alert = fake_alert
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    config = Config(
        machine_name="Studio",
        plugins_path=str(tmp_path / "missing"),
        reports_path=str(reports_dir),
        reports_backend="local",
    )
    monkeypatch.setattr(menubar_module, "load_config", lambda: config)
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    app = menubar_module.MenuBarApp(
        Config(
            machine_name="Studio",
            plugins_path=str(plugins_dir),
            reports_path=str(reports_dir),
            reports_backend="local",
        )
    )
    app._on_reload_config()
    assert alerts and "Configuration invalid" in alerts[0][0]


def test_edit_config_opens_textedit(monkeypatch, tmp_path) -> None:
    menubar_module = _load_menubar(monkeypatch)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_timer", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_watcher", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_start_update_check", lambda self: None)
    monkeypatch.setattr(menubar_module.IconAssets, "_write_resource", lambda self, name: None)
    monkeypatch.setattr(menubar_module, "current_version", lambda: "1.0.0")
    opened = {}

    def fake_open(path, app=None):
        opened["path"] = path
        opened["app"] = app

    monkeypatch.setattr(menubar_module, "_open_path", fake_open)
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    config = Config(
        machine_name="Studio",
        plugins_path=str(plugins_dir),
        reports_path=str(reports_dir),
        reports_backend="local",
    )
    app = menubar_module.MenuBarApp(config)
    monkeypatch.setattr(menubar_module, "CONFIG_PATH", tmp_path / "config.toml")
    monkeypatch.setattr(menubar_module, "write_config", lambda _cfg: None)
    app._on_edit_config()
    assert opened["app"] == "TextEdit"


def test_uninstall_removes_files_and_quits(monkeypatch, tmp_path) -> None:
    menubar_module = _load_menubar(monkeypatch)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_timer", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_watcher", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_start_update_check", lambda self: None)
    monkeypatch.setattr(menubar_module.IconAssets, "_write_resource", lambda self, name: None)
    monkeypatch.setattr(menubar_module, "current_version", lambda: "1.0.0")
    monkeypatch.setattr(menubar_module, "uninstall_menubar_launchagent", lambda: None)
    monkeypatch.setattr(menubar_module, "uninstall_launchagent", lambda: None)
    quit_called = {}

    def fake_quit():
        quit_called["yes"] = True

    menubar_module.rumps.quit_application = fake_quit
    menubar_module.rumps.alert = lambda *_args, **_kwargs: 0
    menubar_module.rumps.Window = lambda *_args, **_kwargs: types.SimpleNamespace(
        run=lambda: types.SimpleNamespace(clicked=True, text="UNINSTALL")
    )

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_path = config_dir / "config.toml"
    config_path.write_text("data", encoding="utf-8")
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "stdout.log").write_text("log", encoding="utf-8")
    monkeypatch.setattr(menubar_module, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(menubar_module, "CONFIG_PATH", config_path)
    monkeypatch.setattr(menubar_module, "LOG_DIR", log_dir)

    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    config = Config(
        machine_name="Studio",
        plugins_path=str(plugins_dir),
        reports_path=str(reports_dir),
        reports_backend="local",
    )
    app = menubar_module.MenuBarApp(config)
    app._on_uninstall()
    assert not config_path.exists()
    assert not log_dir.exists()
    assert quit_called.get("yes") is True


def test_uninstall_cancel_does_not_delete(monkeypatch, tmp_path) -> None:
    menubar_module = _load_menubar(monkeypatch)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_timer", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_watcher", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_start_update_check", lambda self: None)
    monkeypatch.setattr(menubar_module.IconAssets, "_write_resource", lambda self, name: None)
    monkeypatch.setattr(menubar_module, "current_version", lambda: "1.0.0")
    menubar_module.rumps.Window = lambda *_args, **_kwargs: types.SimpleNamespace(
        run=lambda: types.SimpleNamespace(clicked=False, text="")
    )
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_path = config_dir / "config.toml"
    config_path.write_text("data", encoding="utf-8")
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    monkeypatch.setattr(menubar_module, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(menubar_module, "CONFIG_PATH", config_path)
    monkeypatch.setattr(menubar_module, "LOG_DIR", log_dir)
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    config = Config(
        machine_name="Studio",
        plugins_path=str(plugins_dir),
        reports_path=str(reports_dir),
        reports_backend="local",
    )
    app = menubar_module.MenuBarApp(config)
    app._on_uninstall()
    assert config_path.exists()


def test_uninstall_keeps_config_dir_when_not_empty(monkeypatch, tmp_path) -> None:
    menubar_module = _load_menubar(monkeypatch)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_timer", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_watcher", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_start_update_check", lambda self: None)
    monkeypatch.setattr(menubar_module.IconAssets, "_write_resource", lambda self, name: None)
    monkeypatch.setattr(menubar_module, "current_version", lambda: "1.0.0")
    monkeypatch.setattr(menubar_module, "uninstall_menubar_launchagent", lambda: None)
    monkeypatch.setattr(menubar_module, "uninstall_launchagent", lambda: None)
    menubar_module.rumps.alert = lambda *_args, **_kwargs: 0
    menubar_module.rumps.Window = lambda *_args, **_kwargs: types.SimpleNamespace(
        run=lambda: types.SimpleNamespace(clicked=True, text="UNINSTALL")
    )

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_path = config_dir / "config.toml"
    config_path.write_text("data", encoding="utf-8")
    (config_dir / "extra.txt").write_text("keep", encoding="utf-8")
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    monkeypatch.setattr(menubar_module, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(menubar_module, "CONFIG_PATH", config_path)
    monkeypatch.setattr(menubar_module, "LOG_DIR", log_dir)

    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    config = Config(
        machine_name="Studio",
        plugins_path=str(plugins_dir),
        reports_path=str(reports_dir),
        reports_backend="local",
    )
    app = menubar_module.MenuBarApp(config)
    app._on_uninstall()
    assert config_dir.exists()


def test_uninstall_launchagent_failure_still_cleans(monkeypatch, tmp_path) -> None:
    menubar_module = _load_menubar(monkeypatch)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_timer", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_setup_watcher", lambda self: None)
    monkeypatch.setattr(menubar_module.MenuBarApp, "_start_update_check", lambda self: None)
    monkeypatch.setattr(menubar_module.IconAssets, "_write_resource", lambda self, name: None)
    monkeypatch.setattr(menubar_module, "current_version", lambda: "1.0.0")
    monkeypatch.setattr(menubar_module, "uninstall_menubar_launchagent", lambda: None)

    def fail_uninstall():
        raise RuntimeError("launchd error")

    monkeypatch.setattr(menubar_module, "uninstall_launchagent", fail_uninstall)
    menubar_module.rumps.alert = lambda *_args, **_kwargs: 0
    menubar_module.rumps.Window = lambda *_args, **_kwargs: types.SimpleNamespace(
        run=lambda: types.SimpleNamespace(clicked=True, text="UNINSTALL")
    )

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_path = config_dir / "config.toml"
    config_path.write_text("data", encoding="utf-8")
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    monkeypatch.setattr(menubar_module, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(menubar_module, "CONFIG_PATH", config_path)
    monkeypatch.setattr(menubar_module, "LOG_DIR", log_dir)

    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    config = Config(
        machine_name="Studio",
        plugins_path=str(plugins_dir),
        reports_path=str(reports_dir),
        reports_backend="local",
    )
    app = menubar_module.MenuBarApp(config)
    try:
        app._on_uninstall()
    except RuntimeError:
        pass
    assert config_path.exists()
