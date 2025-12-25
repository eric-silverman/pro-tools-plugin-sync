from __future__ import annotations

import pathlib

from pt_plugin_sync.config import Config, default_config, load_config, validate_config, write_config


def test_default_config_uses_system_plugins_path() -> None:
    config = default_config()
    assert config.plugins_path == "/Library/Application Support/Avid/Audio/Plug-Ins"


def test_write_and_load_roundtrip(temp_config_dir) -> None:
    plugins_dir = pathlib.Path(temp_config_dir[0]) / "plugins"
    reports_dir = pathlib.Path(temp_config_dir[0]) / "reports"
    plugins_dir.mkdir()
    reports_dir.mkdir()
    config = Config(
        machine_name="Test",
        plugins_path=str(plugins_dir),
        reports_path=str(reports_dir),
        reports_backend="local",
        scan_interval_seconds=120,
        debounce_seconds=5,
        hash_binaries=True,
        prune_days=3,
        auto_update_download=True,
    )
    write_config(config)
    loaded = load_config()
    assert loaded is not None
    assert loaded.plugins_path == str(plugins_dir)
    assert loaded.reports_path == str(reports_dir)
    assert loaded.hash_binaries is True
    assert loaded.auto_update_download is True


def test_validate_config_requires_existing_plugins_path(temp_config_dir) -> None:
    plugins_dir = pathlib.Path(temp_config_dir[0]) / "missing"
    reports_dir = pathlib.Path(temp_config_dir[0]) / "reports"
    reports_dir.mkdir()
    config = Config(
        machine_name="Test",
        plugins_path=str(plugins_dir),
        reports_path=str(reports_dir),
        reports_backend="local",
    )
    validation = validate_config(config)
    assert validation.ok is False
    assert any("plugins_path does not exist" in error for error in validation.errors)


def test_validate_config_accepts_valid_paths(temp_config_dir) -> None:
    plugins_dir = pathlib.Path(temp_config_dir[0]) / "plugins"
    reports_dir = pathlib.Path(temp_config_dir[0]) / "reports"
    plugins_dir.mkdir()
    reports_dir.mkdir()
    config = Config(
        machine_name="Test",
        plugins_path=str(plugins_dir),
        reports_path=str(reports_dir),
        reports_backend="local",
    )
    validation = validate_config(config)
    assert validation.ok is True
