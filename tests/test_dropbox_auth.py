from __future__ import annotations

import builtins

import pytest

from pt_plugin_sync import dropbox_auth as dropbox_auth_module
from pt_plugin_sync.dropbox_auth import run_dropbox_oauth


def test_run_dropbox_oauth_returns_refresh_token(monkeypatch) -> None:
    class FakeFlow:
        def __init__(self, *_args, **_kwargs):
            pass

        def start(self):
            return "http://example.com/auth"

        def finish(self, _code):
            class Result:
                refresh_token = "refresh-token"

            return Result()

    monkeypatch.setattr(dropbox_auth_module, "DropboxOAuth2FlowNoRedirect", FakeFlow)
    monkeypatch.setattr(builtins, "input", lambda _prompt: "auth-code")
    refresh = run_dropbox_oauth("key", "secret")
    assert refresh == "refresh-token"


def test_run_dropbox_oauth_requires_code(monkeypatch) -> None:
    class FakeFlow:
        def __init__(self, *_args, **_kwargs):
            pass

        def start(self):
            return "http://example.com/auth"

        def finish(self, _code):
            class Result:
                refresh_token = "refresh-token"

            return Result()

    monkeypatch.setattr(dropbox_auth_module, "DropboxOAuth2FlowNoRedirect", FakeFlow)
    monkeypatch.setattr(builtins, "input", lambda _prompt: "")
    with pytest.raises(ValueError, match="Authorization code is required"):
        run_dropbox_oauth("key", "secret")


def test_run_dropbox_oauth_requires_refresh_token(monkeypatch) -> None:
    class FakeFlow:
        def __init__(self, *_args, **_kwargs):
            pass

        def start(self):
            return "http://example.com/auth"

        def finish(self, _code):
            class Result:
                refresh_token = None

            return Result()

    monkeypatch.setattr(dropbox_auth_module, "DropboxOAuth2FlowNoRedirect", FakeFlow)
    monkeypatch.setattr(builtins, "input", lambda _prompt: "auth-code")
    with pytest.raises(RuntimeError, match="did not return a refresh token"):
        run_dropbox_oauth("key", "secret")
