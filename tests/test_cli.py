from __future__ import annotations

from pt_plugin_sync import cli as cli_module
from pt_plugin_sync.config import Config


def test_setup_command_calls_run_setup(monkeypatch) -> None:
    captured = {}

    def fake_run_setup(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(cli_module, "run_setup", fake_run_setup)
    parser = cli_module.build_parser()
    args = parser.parse_args(
        [
            "setup",
            "--plugins-path",
            "/Plugins",
            "--reports-path",
            "/Reports",
            "--machine-name",
            "Studio",
            "--reports-backend",
            "local",
        ]
    )
    assert cli_module._cmd_setup(args) == 0
    assert captured["plugins_path"] == "/Plugins"
    assert captured["reports_path"] == "/Reports"
    assert captured["machine_name"] == "Studio"


def test_setup_command_handles_validation_error(monkeypatch, capsys) -> None:
    def fake_run_setup(**_kwargs):
        raise ValueError("bad input")

    monkeypatch.setattr(cli_module, "run_setup", fake_run_setup)
    parser = cli_module.build_parser()
    args = parser.parse_args(["setup"])
    assert cli_module._cmd_setup(args) == 1
    assert "Setup failed: bad input" in capsys.readouterr().out


def test_scan_command_calls_perform_scan(monkeypatch) -> None:
    class Result:
        diff = None

    called = {}

    def fake_perform_scan(config, open_report):
        called["config"] = config
        called["open_report"] = open_report
        return Result()

    monkeypatch.setattr(cli_module, "ensure_config", lambda interactive=True: "config")
    monkeypatch.setattr(cli_module, "perform_scan", fake_perform_scan)
    args = cli_module.build_parser().parse_args(["scan"])
    assert cli_module._cmd_scan(args) == 0
    assert called["config"] == "config"
    assert called["open_report"] is True


def test_diff_command_no_reports(monkeypatch, capsys) -> None:
    class Store:
        def load_latest_reports(self):
            return {}

    monkeypatch.setattr(cli_module, "ensure_config", lambda interactive=True: "config")
    monkeypatch.setattr(cli_module, "report_store_from_config", lambda _cfg: Store())
    args = cli_module.build_parser().parse_args(["diff"])
    assert cli_module._cmd_diff(args) == 1
    assert "No reports found in reports folder." in capsys.readouterr().out


def test_dropbox_auth_requires_config(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli_module, "load_config", lambda: None)
    args = cli_module.build_parser().parse_args(["dropbox-auth"])
    assert cli_module._cmd_dropbox_auth(args) == 1
    assert "Config missing" in capsys.readouterr().out


def test_dropbox_auth_writes_refresh_token(monkeypatch, tmp_path) -> None:
    plugins_dir = tmp_path / "plugins"
    reports_dir = tmp_path / "reports"
    plugins_dir.mkdir()
    reports_dir.mkdir()
    config = Config(
        machine_name="Studio",
        plugins_path=str(plugins_dir),
        reports_path=str(reports_dir),
        reports_backend="local",
        dropbox_app_key="key",
        dropbox_app_secret="secret",
    )
    captured: dict[str, Config] = {}

    monkeypatch.setattr(cli_module, "load_config", lambda: config)
    monkeypatch.setattr(cli_module, "run_dropbox_oauth", lambda *_: "refresh-token")

    def fake_write_config(updated: Config) -> None:
        captured["config"] = updated

    monkeypatch.setattr(cli_module, "write_config", fake_write_config)
    args = cli_module.build_parser().parse_args(["dropbox-auth"])
    assert cli_module._cmd_dropbox_auth(args) == 0
    saved = captured["config"]
    assert saved.dropbox_refresh_token == "refresh-token"
    assert saved.reports_backend == "dropbox"
