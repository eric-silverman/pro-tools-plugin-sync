from __future__ import annotations

import json
import pathlib
from datetime import datetime, timezone
from typing import Iterable

from .config import Config
from .report_naming import ARCHIVE_DIR_NAME, is_timestamped_report
from .scanner import PluginInfo


def build_report(config: Config, plugins: Iterable[PluginInfo]) -> dict:
    scan_time = datetime.now(tz=timezone.utc).astimezone().isoformat()
    return {
        "machine_name": config.machine_name,
        "scan_time": scan_time,
        "root_path": str(config.expanded_plugins_path()),
        "plugins": [
            {
                "bundle_name": plugin.bundle_name,
                "bundle_id": plugin.bundle_id,
                "short_version": plugin.short_version or "unknown",
                "bundle_version": plugin.bundle_version or "unknown",
                "mtime": plugin.mtime,
                **({"binary_hash": plugin.binary_hash} if plugin.binary_hash else {}),
            }
            for plugin in plugins
        ],
    }


def _safe_machine_name(name: str) -> str:
    return name.replace("/", "-")


def _archive_dir(reports_dir: pathlib.Path) -> pathlib.Path:
    return reports_dir / ARCHIVE_DIR_NAME


def _move_old_scans(reports_dir: pathlib.Path) -> None:
    archive_dir = _archive_dir(reports_dir)
    archive_dir.mkdir(parents=True, exist_ok=True)
    for path in reports_dir.iterdir():
        if not path.is_file():
            continue
        if not is_timestamped_report(path.name):
            continue
        destination = archive_dir / path.name
        if destination.exists():
            try:
                destination.unlink()
            except OSError:
                continue
        try:
            path.replace(destination)
        except OSError:
            continue


def write_report(reports_dir: pathlib.Path, report: dict) -> tuple[pathlib.Path, pathlib.Path]:
    reports_dir.mkdir(parents=True, exist_ok=True)
    _move_old_scans(reports_dir)
    machine_name = _safe_machine_name(report.get("machine_name", "unknown"))
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    timestamped = _archive_dir(reports_dir) / f"{machine_name}__{timestamp}.json"
    latest = reports_dir / f"{machine_name}__latest.json"
    with timestamped.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    with latest.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return timestamped, latest


def prune_reports(reports_dir: pathlib.Path, prune_days: int) -> None:
    if prune_days <= 0:
        return
    cutoff = datetime.now(tz=timezone.utc).timestamp() - (prune_days * 86400)
    for root in (reports_dir, _archive_dir(reports_dir)):
        if not root.exists():
            continue
        for path in root.glob("*.json"):
            if not is_timestamped_report(path.name):
                continue
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
            except OSError:
                continue
