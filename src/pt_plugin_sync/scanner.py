from __future__ import annotations

import dataclasses
import hashlib
import os
import pathlib
import plistlib
from dataclasses import dataclass
from typing import Iterable


@dataclass
class PluginInfo:
    bundle_name: str
    bundle_id: str | None
    short_version: str | None
    bundle_version: str | None
    mtime: float
    binary_hash: str | None = None


def _hash_bundle_binaries(bundle_path: pathlib.Path) -> str | None:
    macos_dir = bundle_path / "Contents" / "MacOS"
    if not macos_dir.exists() or not macos_dir.is_dir():
        return None
    hasher = hashlib.sha256()
    files = sorted([p for p in macos_dir.iterdir() if p.is_file()])
    if not files:
        return None
    for file_path in files:
        hasher.update(file_path.name.encode("utf-8"))
        with file_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
    return hasher.hexdigest()


def _read_info_plist(bundle_path: pathlib.Path) -> dict:
    plist_path = bundle_path / "Contents" / "Info.plist"
    if not plist_path.exists():
        return {}
    try:
        with plist_path.open("rb") as handle:
            return plistlib.load(handle)
    except Exception:
        return {}


def scan_plugins(root_path: pathlib.Path, hash_binaries: bool = False) -> list[PluginInfo]:
    plugins: list[PluginInfo] = []
    if not root_path.exists() or not root_path.is_dir():
        return plugins
    if not os.access(root_path, os.R_OK | os.X_OK):
        raise PermissionError(f"Permission denied reading plug-ins folder: {root_path}")
    try:
        with os.scandir(root_path) as entries:
            for entry in entries:
                try:
                    if not entry.is_dir():
                        continue
                    if not entry.name.endswith(".aaxplugin"):
                        continue
                    bundle_path = pathlib.Path(entry.path)
                    info = _read_info_plist(bundle_path)
                    bundle_id = info.get("CFBundleIdentifier") or None
                    short_version = info.get("CFBundleShortVersionString") or None
                    bundle_version = info.get("CFBundleVersion") or None
                    try:
                        mtime = bundle_path.stat().st_mtime
                    except OSError:
                        mtime = 0
                    binary_hash = _hash_bundle_binaries(bundle_path) if hash_binaries else None
                    plugins.append(
                        PluginInfo(
                            bundle_name=entry.name,
                            bundle_id=bundle_id,
                            short_version=short_version,
                            bundle_version=bundle_version,
                            mtime=mtime,
                            binary_hash=binary_hash,
                        )
                    )
                except OSError:
                    continue
    except PermissionError as exc:
        raise PermissionError(
            f"Permission denied reading plug-ins folder: {root_path}"
        ) from exc
    plugins.sort(key=lambda item: item.bundle_name.lower())
    return plugins


def plugin_key(plugin: PluginInfo) -> str:
    return plugin.bundle_id or plugin.bundle_name


def plugin_version_tuple(plugin: PluginInfo) -> tuple[str, str]:
    return (
        plugin.short_version or "unknown",
        plugin.bundle_version or "unknown",
    )
