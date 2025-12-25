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


def test_config_from_form_rejects_invalid_backend() -> None:
    from pt_plugin_sync.settings_server import _config_from_form
    from pt_plugin_sync.config import default_config

    current = default_config("Studio")
    values = {
        "reports_backend": ["invalid"],
        "machine_name": ["Studio"],
        "plugins_path": [current.plugins_path],
        "reports_path": [current.reports_path],
        "scan_interval_seconds": [str(current.scan_interval_seconds)],
        "debounce_seconds": [str(current.debounce_seconds)],
        "prune_days": ["0"],
    }
    try:
        _config_from_form(values, current)
    except ValueError as exc:
        assert "reports_backend must be local or dropbox" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid reports_backend")


def test_dropbox_auth_requires_key_and_secret(temp_config_dir, tmp_path) -> None:
    from pt_plugin_sync.settings_server import SettingsServer
    from pt_plugin_sync.config import Config

    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    config = Config(
        machine_name="Studio",
        plugins_path=str(plugins_dir),
        reports_path=str(reports_dir),
        reports_backend="dropbox",
    )
    server = SettingsServer(config, lambda _cfg: None)
    url = server.start()
    try:
        status = _post_form(url, "/dropbox-auth", {})
        assert status == 200
    finally:
        server.stop()


def test_get_unknown_path_returns_404(temp_config_dir, tmp_path) -> None:
    from pt_plugin_sync.settings_server import SettingsServer
    from pt_plugin_sync.config import Config

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
    server = SettingsServer(config, lambda _cfg: None)
    url = server.start()
    try:
        parsed = urllib.parse.urlparse(url)
        conn = http.client.HTTPConnection(parsed.hostname, parsed.port)
        conn.request("GET", "/nope")
        response = conn.getresponse()
        response.read()
        conn.close()
        assert response.status == 404
    finally:
        server.stop()


def test_import_rejects_non_multipart(temp_config_dir, tmp_path) -> None:
    from pt_plugin_sync.settings_server import SettingsServer
    from pt_plugin_sync.config import Config

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
    server = SettingsServer(config, lambda _cfg: None)
    url = server.start()
    try:
        parsed = urllib.parse.urlparse(url)
        conn = http.client.HTTPConnection(parsed.hostname, parsed.port)
        conn.request(
            "POST",
            "/import",
            body="not-multipart",
            headers={"Content-Type": "text/plain"},
        )
        response = conn.getresponse()
        body = response.read().decode("utf-8")
        conn.close()
        assert response.status == 200
        assert "Expected multipart/form-data" in body
    finally:
        server.stop()


def test_import_rejects_invalid_toml(temp_config_dir, tmp_path) -> None:
    from pt_plugin_sync.settings_server import SettingsServer
    from pt_plugin_sync.config import Config

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
    server = SettingsServer(config, lambda _cfg: None)
    url = server.start()
    try:
        boundary = "----boundary"
        payload = (
            f"--{boundary}\r\n"
            "Content-Disposition: form-data; name=\"config_file\"; filename=\"config.toml\"\r\n"
            "Content-Type: text/plain\r\n\r\n"
            "not = [valid\n"
            f"--{boundary}--\r\n"
        ).encode("utf-8")
        parsed = urllib.parse.urlparse(url)
        conn = http.client.HTTPConnection(parsed.hostname, parsed.port)
        conn.request(
            "POST",
            "/import",
            body=payload,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        response = conn.getresponse()
        body = response.read().decode("utf-8")
        conn.close()
        assert response.status == 200
        assert "Failed to parse TOML" in body
    finally:
        server.stop()


def test_import_accepts_valid_toml(temp_config_dir, tmp_path) -> None:
    from pt_plugin_sync.settings_server import SettingsServer
    from pt_plugin_sync.config import Config

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
    server = SettingsServer(config, lambda _cfg: None)
    url = server.start()
    try:
        boundary = "----boundary"
        payload = (
            f"--{boundary}\r\n"
            "Content-Disposition: form-data; name=\"config_file\"; filename=\"config.toml\"\r\n"
            "Content-Type: text/plain\r\n\r\n"
            f"machine_name = \"Studio\"\n"
            f"plugins_path = \"{plugins_dir}\"\n"
            f"reports_path = \"{reports_dir}\"\n"
            "reports_backend = \"local\"\n"
            f"--{boundary}--\r\n"
        ).encode("utf-8")
        parsed = urllib.parse.urlparse(url)
        conn = http.client.HTTPConnection(parsed.hostname, parsed.port)
        conn.request(
            "POST",
            "/import",
            body=payload,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        response = conn.getresponse()
        response.read()
        conn.close()
        assert response.status == 303
    finally:
        server.stop()


def test_import_rejects_invalid_config_values(temp_config_dir, tmp_path) -> None:
    from pt_plugin_sync.settings_server import SettingsServer
    from pt_plugin_sync.config import Config

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
    server = SettingsServer(config, lambda _cfg: None)
    url = server.start()
    try:
        boundary = "----boundary"
        payload = (
            f"--{boundary}\r\n"
            "Content-Disposition: form-data; name=\"config_file\"; filename=\"config.toml\"\r\n"
            "Content-Type: text/plain\r\n\r\n"
            "machine_name = \"Studio\"\n"
            "plugins_path = \"/nope\"\n"
            "reports_path = \"/nope\"\n"
            "reports_backend = \"local\"\n"
            "scan_interval_seconds = -1\n"
            f"--{boundary}--\r\n"
        ).encode("utf-8")
        parsed = urllib.parse.urlparse(url)
        conn = http.client.HTTPConnection(parsed.hostname, parsed.port)
        conn.request(
            "POST",
            "/import",
            body=payload,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        response = conn.getresponse()
        body = response.read().decode("utf-8")
        conn.close()
        assert response.status == 200
        assert (
            "Configuration invalid" in body
            or "plugins_path does not exist" in body
            or "reports_path error" in body
            or "Read-only file system" in body
        )
    finally:
        server.stop()


def test_import_rejects_missing_dropbox_fields(temp_config_dir, tmp_path) -> None:
    from pt_plugin_sync.settings_server import SettingsServer
    from pt_plugin_sync.config import Config

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
    server = SettingsServer(config, lambda _cfg: None)
    url = server.start()
    try:
        boundary = "----boundary"
        payload = (
            f"--{boundary}\r\n"
            "Content-Disposition: form-data; name=\"config_file\"; filename=\"config.toml\"\r\n"
            "Content-Type: text/plain\r\n\r\n"
            "machine_name = \"Studio\"\n"
            f"plugins_path = \"{plugins_dir}\"\n"
            f"reports_path = \"{reports_dir}\"\n"
            "reports_backend = \"dropbox\"\n"
            f"--{boundary}--\r\n"
        ).encode("utf-8")
        parsed = urllib.parse.urlparse(url)
        conn = http.client.HTTPConnection(parsed.hostname, parsed.port)
        conn.request(
            "POST",
            "/import",
            body=payload,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        response = conn.getresponse()
        body = response.read().decode("utf-8")
        conn.close()
        assert response.status == 200
        assert "dropbox_app_key is required" in body
    finally:
        server.stop()


def test_extract_multipart_file_missing_field() -> None:
    from pt_plugin_sync.settings_server import _extract_multipart_file

    boundary = "----boundary"
    content_type = f"multipart/form-data; boundary={boundary}"
    body = (
        f"--{boundary}\r\n"
        "Content-Disposition: form-data; name=\"other\"; filename=\"config.toml\"\r\n"
        "Content-Type: text/plain\r\n\r\n"
        "machine_name = \"Studio\"\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")
    try:
        _extract_multipart_file(body, content_type, "config_file")
    except ValueError as exc:
        assert "No config_file provided" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing config_file")


def test_extract_multipart_file_rejects_wrong_content_type() -> None:
    from pt_plugin_sync.settings_server import _extract_multipart_file

    try:
        _extract_multipart_file(b"data", "text/plain", "config_file")
    except ValueError as exc:
        assert "Expected multipart/form-data" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid content-type")
