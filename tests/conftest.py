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
