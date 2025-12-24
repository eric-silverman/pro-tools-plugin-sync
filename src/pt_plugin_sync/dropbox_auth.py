from __future__ import annotations

import os
import sys
from typing import Iterable

from dropbox import DropboxOAuth2FlowNoRedirect


DROPBOX_OAUTH_SCOPES: list[str] = [
    "files.content.write",
    "files.content.read",
    "files.metadata.read",
    "files.metadata.write",
]


def _format_scopes(scopes: Iterable[str]) -> str:
    return ", ".join(scopes)


def _terminal_link(url: str, label: str | None = None) -> str:
    label = label or url
    return f"\033]8;;{url}\033\\{label}\033]8;;\033\\"


def _format_authorize_url(url: str) -> str:
    if sys.stdout.isatty() and os.environ.get("TERM"):
        return _terminal_link(url, url)
    return url


def run_dropbox_oauth(app_key: str, app_secret: str) -> str:
    flow = DropboxOAuth2FlowNoRedirect(
        app_key,
        app_secret,
        token_access_type="offline",
        scope=DROPBOX_OAUTH_SCOPES,
    )
    authorize_url = flow.start()
    print("1) Visit the Dropbox authorization URL:")
    print(_format_authorize_url(authorize_url))
    print(f"Scopes requested: {_format_scopes(DROPBOX_OAUTH_SCOPES)}")
    auth_code = input("2) Enter the authorization code: ").strip()
    if not auth_code:
        raise ValueError("Authorization code is required.")
    oauth_result = flow.finish(auth_code)
    if not oauth_result.refresh_token:
        raise RuntimeError(
            "Dropbox did not return a refresh token. Ensure the app uses short-lived tokens."
        )
    return oauth_result.refresh_token
