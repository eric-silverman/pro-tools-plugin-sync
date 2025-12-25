from __future__ import annotations

import json

from pt_plugin_sync import update_check as update_check_module
from pt_plugin_sync.update_check import is_update_available, latest_release


def test_parse_version() -> None:
    assert update_check_module._parse_version("v1.2.3") == (1, 2, 3)
    assert update_check_module._parse_version("version 0.0.1") == (0, 0, 1)
    assert update_check_module._parse_version("nope") == (0, 0, 0)


def test_is_update_available() -> None:
    assert is_update_available("1.0.0", "1.0.1") is True
    assert is_update_available("1.2.0", "1.1.9") is False


def test_latest_release_parses_payload(monkeypatch) -> None:
    payload = {
        "tag_name": "v2.1.0",
        "html_url": "https://example.com/release",
        "body": "Notes",
        "assets": [
            {
                "name": "pro-tools-plugin-sync-2.1.0.dmg",
                "browser_download_url": "https://example.com/asset",
            }
        ],
    }

    class FakeResponse:
        def __init__(self, data: bytes):
            self._data = data

        def read(self):
            return self._data

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_urlopen(_request, timeout=10):
        return FakeResponse(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(update_check_module.urllib.request, "urlopen", fake_urlopen)
    release = latest_release()
    assert release is not None
    assert release.version == "2.1.0"
    assert release.asset_url == "https://example.com/asset"
    assert release.url == "https://example.com/release"


def test_asset_url_missing_returns_none() -> None:
    assets = [{"name": "other.dmg", "browser_download_url": "https://example.com/other"}]
    assert update_check_module._asset_url(assets, "1.2.3") is None


def test_latest_release_missing_version_returns_none(monkeypatch) -> None:
    payload = {"tag_name": "", "assets": []}

    class FakeResponse:
        def __init__(self, data: bytes):
            self._data = data

        def read(self):
            return self._data

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_urlopen(_request, timeout=10):
        return FakeResponse(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(update_check_module.urllib.request, "urlopen", fake_urlopen)
    assert latest_release() is None


def test_latest_release_handles_non_list_assets(monkeypatch) -> None:
    payload = {"tag_name": "v1.0.0", "assets": {"name": "bad"}}

    class FakeResponse:
        def __init__(self, data: bytes):
            self._data = data

        def read(self):
            return self._data

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_urlopen(_request, timeout=10):
        return FakeResponse(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(update_check_module.urllib.request, "urlopen", fake_urlopen)
    release = latest_release()
    assert release is not None
    assert release.asset_url is None


def test_current_version_defaults_when_missing(monkeypatch) -> None:
    def fake_version(_name):
        raise update_check_module.metadata.PackageNotFoundError

    monkeypatch.setattr(update_check_module.metadata, "version", fake_version)
    assert update_check_module.current_version() == "0.0.0"
