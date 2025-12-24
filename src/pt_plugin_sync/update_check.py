from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass
from importlib import metadata
from typing import Iterable


REPO_API = "https://api.github.com/repos/eric-silverman/pro-tools-plugin-sync/releases/latest"
ASSET_PREFIX = "pro-tools-plugin-sync-"


@dataclass
class ReleaseInfo:
    version: str
    tag: str
    url: str
    asset_url: str | None
    notes: str


def current_version() -> str:
    try:
        return metadata.version("pt-plugin-sync")
    except metadata.PackageNotFoundError:
        return "0.0.0"


def _parse_version(text: str) -> tuple[int, int, int]:
    match = re.search(r"(\\d+)\\.(\\d+)\\.(\\d+)", text)
    if not match:
        return (0, 0, 0)
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def _asset_url(assets: Iterable[dict], version: str) -> str | None:
    expected = f"{ASSET_PREFIX}{version}.dmg"
    for asset in assets:
        if asset.get("name") == expected:
            return str(asset.get("browser_download_url") or "")
    return None


def latest_release() -> ReleaseInfo | None:
    request = urllib.request.Request(
        REPO_API,
        headers={"User-Agent": "pt-plugin-sync"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    tag = str(payload.get("tag_name") or "")
    version = tag.lstrip("v")
    if not version:
        return None
    notes = str(payload.get("body") or "").strip()
    url = str(payload.get("html_url") or "")
    assets = payload.get("assets") or []
    if not isinstance(assets, list):
        assets = []
    asset_url = _asset_url(assets, version)
    return ReleaseInfo(
        version=version,
        tag=tag,
        url=url,
        asset_url=asset_url,
        notes=notes,
    )


def is_update_available(current: str, latest: str) -> bool:
    return _parse_version(latest) > _parse_version(current)
