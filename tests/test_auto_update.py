from __future__ import annotations

import pathlib

from pt_plugin_sync.auto_update import find_app_bundle, find_app_in_mount


def test_find_app_bundle_walks_parents(tmp_path) -> None:
    app_root = tmp_path / "Pro Tools Plugin Sync.app"
    exe_path = app_root / "Contents" / "MacOS" / "Pro Tools Plugin Sync"
    exe_path.parent.mkdir(parents=True)
    exe_path.write_text("", encoding="utf-8")
    found = find_app_bundle(str(exe_path))
    assert found == app_root


def test_find_app_in_mount_prefers_root(tmp_path) -> None:
    app_root = tmp_path / "Example.app"
    app_root.mkdir()
    nested = tmp_path / "Nested" / "Other.app"
    nested.mkdir(parents=True)
    found = find_app_in_mount(tmp_path)
    assert isinstance(found, pathlib.Path)
    assert found.name == "Example.app"
