from __future__ import annotations

import pathlib
from dataclasses import dataclass

from .config import Config
from .diffing import compute_diff, compute_update_summary
from .report_store import report_store_from_config
from .reporting import build_report
from .scanner import scan_plugins
from .update_report import open_update_report_if_needed


@dataclass
class ScanResult:
    diff: dict | None
    summary: dict | None
    update_count: int
    report_path: pathlib.Path | None


def _count_updates(summary: dict | None, machine_name: str) -> int:
    if not summary:
        return 0
    updates = summary.get("updates_by_machine", {}).get(machine_name, [])
    if not isinstance(updates, list):
        return 0
    return sum(1 for update in updates if isinstance(update, dict))


def perform_scan(config: Config, *, open_report: bool = True) -> ScanResult:
    plugins = scan_plugins(config.expanded_plugins_path(), config.hash_binaries)
    report = build_report(config, plugins)
    store = report_store_from_config(config)
    store.write_report(report)
    store.prune_reports(config.prune_days)
    reports = store.load_latest_reports()
    if not reports:
        return ScanResult(diff=None, summary=None, update_count=0, report_path=None)
    diff = compute_diff(reports)
    store.write_diff(diff)
    summary = compute_update_summary(reports)
    store.write_summary(summary)
    report_path = None
    if open_report:
        report_path = open_update_report_if_needed(config, summary)
    update_count = _count_updates(summary, config.machine_name)
    return ScanResult(
        diff=diff,
        summary=summary,
        update_count=update_count,
        report_path=report_path,
    )
