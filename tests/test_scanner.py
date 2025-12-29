from __future__ import annotations

import pathlib

from pt_plugin_sync.scanner import scan_plugins


def _fixtures_path() -> pathlib.Path:
    return pathlib.Path(__file__).parent / "fixtures" / "plugins"


def test_scan_plugins_reads_metadata() -> None:
    plugins = scan_plugins(_fixtures_path(), hash_binaries=False)
    names = [plugin.bundle_name for plugin in plugins]
    assert names == [
        "Alpha.aaxplugin",
        "Beta.aaxplugin",
        "Betazz.aaxplugin",
        "Gamma.aaxplugin",
    ]

    alpha = plugins[0]
    assert alpha.bundle_id == "com.example.alpha"
    assert alpha.short_version == "1.2.3"
    assert alpha.bundle_version == "123"

    beta = plugins[1]
    assert beta.bundle_id == "com.example.beta"
    assert beta.short_version is None
    assert beta.bundle_version == "200"

    betazz = plugins[2]
    assert betazz.bundle_id == "com.example.beta"
    assert betazz.short_version is None
    assert betazz.bundle_version == "200"

    gamma = plugins[3]
    assert gamma.bundle_id == "com.example.gamma"
    assert gamma.short_version == "2.0.0"
    assert gamma.bundle_version == "2000"


def test_scan_plugins_hashes_binaries() -> None:
    plugins = scan_plugins(_fixtures_path(), hash_binaries=True)
    hashes = [plugin.binary_hash for plugin in plugins]
    assert all(value for value in hashes)


def test_scan_plugins_returns_empty_for_missing_path(tmp_path) -> None:
    missing = tmp_path / "missing"
    plugins = scan_plugins(missing, hash_binaries=False)
    assert plugins == []


def test_scan_plugins_raises_permission_error(monkeypatch, tmp_path) -> None:
    target = tmp_path / "plugins"
    target.mkdir()

    monkeypatch.setattr("pt_plugin_sync.scanner.os.access", lambda _p, _m: False)

    def fake_scandir(_path):
        raise PermissionError("nope")

    monkeypatch.setattr("pt_plugin_sync.scanner.os.scandir", fake_scandir)
    try:
        scan_plugins(target, hash_binaries=False)
    except PermissionError as exc:
        assert "Permission denied" in str(exc)
    else:
        raise AssertionError("Expected PermissionError")
