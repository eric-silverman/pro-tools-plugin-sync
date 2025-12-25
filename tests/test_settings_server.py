from __future__ import annotations

import http.client
import pathlib
import urllib.parse

from pt_plugin_sync.config import Config, load_config
from pt_plugin_sync import settings_server as settings_server_module
from pt_plugin_sync.settings_server import SettingsServer


def _post_form(url: str, path: str, data: dict[str, str]) -> int:
    parsed = urllib.parse.urlparse(url)
    body = urllib.parse.urlencode(data)
    conn = http.client.HTTPConnection(parsed.hostname, parsed.port)
    conn.request(
        "POST",
        path,
        body=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Content-Length": str(len(body)),
        },
    )
    response = conn.getresponse()
    response.read()
    conn.close()
    return response.status


def _get(url: str, path: str) -> str:
    parsed = urllib.parse.urlparse(url)
    conn = http.client.HTTPConnection(parsed.hostname, parsed.port)
    conn.request("GET", path)
    response = conn.getresponse()
    body = response.read().decode("utf-8")
    conn.close()
    return body


def test_settings_save_updates_config_and_server_state(temp_config_dir, tmp_path) -> None:
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
    saved: list[Config] = []
    server = SettingsServer(config, saved.append)
    url = server.start()
    try:
        new_plugins_dir = tmp_path / "plugins-next"
        new_plugins_dir.mkdir()
        status = _post_form(
            url,
            "/save",
            {
                "machine_name": "Studio",
                "plugins_path": str(new_plugins_dir),
                "reports_path": str(reports_dir),
                "reports_backend": "local",
                "scan_interval_seconds": "3600",
                "debounce_seconds": "15",
                "prune_days": "0",
            },
        )
        assert status == 303
        assert server._config.plugins_path == str(new_plugins_dir)
        loaded = load_config()
        assert loaded is not None
        assert loaded.plugins_path == str(new_plugins_dir)
        assert saved and saved[-1].plugins_path == str(new_plugins_dir)
    finally:
        server.stop()


def test_dropbox_auth_flow_updates_refresh_token(temp_config_dir, tmp_path, monkeypatch) -> None:
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
        dropbox_reports_path="/Reports",
    )
    server = SettingsServer(config, lambda _cfg: None)
    url = server.start()
    try:
        monkeypatch.setattr(
            settings_server_module,
            "_dropbox_authorize_url",
            lambda *_: "http://example.com",
        )
        monkeypatch.setattr(
            settings_server_module, "_dropbox_finish_auth", lambda *_: "refresh-token"
        )

        body = _get(url, "/dropbox-auth-start")
        assert "http://example.com" in body

        status = _post_form(
            url,
            "/dropbox-finish",
            {"dropbox_app_key": "key", "dropbox_app_secret": "secret", "auth_code": "code"},
        )
        assert status == 303
        assert server._config.dropbox_refresh_token == "refresh-token"
    finally:
        server.stop()
