from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Protocol

from .config import Config
from .diffing import load_latest_reports as load_local_reports
from .diffing import write_diff as write_local_diff
from .diffing import write_summary as write_local_summary
from .reporting import prune_reports as prune_local_reports
from .reporting import write_report as write_local_report


class ReportStore(Protocol):
    def write_report(self, report: dict) -> None:
        raise NotImplementedError

    def write_diff(self, diff: dict) -> None:
        raise NotImplementedError

    def write_summary(self, summary: dict) -> None:
        raise NotImplementedError

    def load_latest_reports(self) -> dict[str, dict]:
        raise NotImplementedError

    def prune_reports(self, prune_days: int) -> None:
        raise NotImplementedError


@dataclass
class LocalReportStore:
    reports_dir: pathlib.Path

    def write_report(self, report: dict) -> None:
        write_local_report(self.reports_dir, report)

    def write_diff(self, diff: dict) -> None:
        write_local_diff(self.reports_dir, diff)

    def write_summary(self, summary: dict) -> None:
        write_local_summary(self.reports_dir, summary)

    def load_latest_reports(self) -> dict[str, dict]:
        return load_local_reports(self.reports_dir)

    def prune_reports(self, prune_days: int) -> None:
        prune_local_reports(self.reports_dir, prune_days)


def report_store_from_config(config: Config) -> ReportStore:
    backend = (config.reports_backend or "local").strip().lower()
    if backend == "local":
        return LocalReportStore(config.expanded_reports_path())
    if backend == "dropbox":
        from .dropbox_store import DropboxReportStore

        return DropboxReportStore.from_config(config)
    raise ValueError(f"Unsupported reports backend: {config.reports_backend}")
