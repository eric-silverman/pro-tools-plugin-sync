from __future__ import annotations

import pathlib

import pytest

from pt_plugin_sync import config as config_module


@pytest.fixture
def temp_config_dir(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_path = config_dir / "config.toml"
    monkeypatch.setattr(config_module, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config_module, "CONFIG_PATH", config_path)
    return config_dir, config_path


def pytest_terminal_summary(terminalreporter, exitstatus, config) -> None:
    if exitstatus != 0:
        return
    modules = sorted(
        {report.nodeid.split("::", 1)[0] for report in terminalreporter.stats.get("passed", [])}
    )
    descriptions = {
        "tests/test_cli.py": "CLI commands: setup, scan, diff, and Dropbox auth flows.",
        "tests/test_config.py": "Config defaults, validation, and read/write round-trips.",
        "tests/test_config_setup.py": "Setup flows and ensure_config error handling.",
        "tests/test_daemon.py": "Daemon debounce logic and scan triggering.",
        "tests/test_diffing.py": "Diff generation, summaries, and report loading/writing.",
        "tests/test_dropbox_auth.py": "Dropbox OAuth flow success and error paths.",
        "tests/test_dropbox_store.py": "Dropbox report store path handling and uploads.",
        "tests/test_launchd.py": "LaunchAgent plist generation and uninstall behavior.",
        "tests/test_menubar.py": "Menu bar actions, UI state changes, and update checks.",
        "tests/test_report_naming.py": "Report filename classification logic.",
        "tests/test_report_store.py": "Local report store read/write integration.",
        "tests/test_reporting.py": "Report generation, writing, and pruning.",
        "tests/test_scan_cycle.py": "End-to-end scan cycle writes outputs.",
        "tests/test_scanner.py": "Plugin scanning metadata and hashing.",
        "tests/test_settings_server.py": "Settings web UI saves and Dropbox auth flow.",
        "tests/test_settings_window.py": "Settings window controller smoke test (stubbed).",
        "tests/test_update_check.py": "Update check parsing and comparison logic.",
        "tests/test_update_report.py": "HTML update report content and opening behavior.",
    }
    terminalreporter.write_line("")
    terminalreporter.write_line("Test coverage summary:")
    for module in modules:
        description = descriptions.get(module, "Test module executed.")
        terminalreporter.write_line(f"- {module}: {description}")
