from __future__ import annotations

import pathlib

import pytest

from pt_plugin_sync.config import Config, ensure_config, run_setup, write_config


def test_run_setup_yes_creates_reports_dir(temp_config_dir, tmp_path) -> None:
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    reports_dir = tmp_path / "reports"
    config = run_setup(
        plugins_path=str(plugins_dir),
        reports_path=str(reports_dir),
        machine_name="Studio",
        reports_backend="local",
        yes=True,
    )
    assert reports_dir.exists()
    assert config.plugins_path == str(plugins_dir)
    assert config.reports_path == str(reports_dir)


def test_run_setup_non_interactive_requires_plugins_path(temp_config_dir) -> None:
    with pytest.raises(ValueError, match="Non-interactive setup requires --plugins-path"):
        run_setup(
            reports_backend="local",
            non_interactive=True,
        )


def test_run_setup_non_interactive_dropbox_requires_credentials(temp_config_dir) -> None:
    with pytest.raises(ValueError, match="Non-interactive dropbox setup requires app key"):
        run_setup(
            reports_backend="dropbox",
            plugins_path="/Library/Application Support/Avid/Audio/Plug-Ins",
            non_interactive=True,
        )


def test_ensure_config_missing_non_interactive_raises(temp_config_dir) -> None:
    with pytest.raises(RuntimeError, match="Config missing"):
        ensure_config(interactive=False)


def test_ensure_config_invalid_non_interactive_raises(temp_config_dir, tmp_path) -> None:
    config = Config(
        machine_name="Studio",
        plugins_path=str(tmp_path / "missing"),
        reports_path=str(tmp_path / "reports"),
        reports_backend="local",
    )
    write_config(config)
    with pytest.raises(RuntimeError, match="Invalid config"):
        ensure_config(interactive=False)
