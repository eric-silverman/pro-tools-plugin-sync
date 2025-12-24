from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

import dropbox
from dropbox.files import WriteMode

from .config import Config
from .report_naming import ARCHIVE_DIR_NAME, DIFF_FILENAME, SUMMARY_FILENAME, is_timestamped_report


def _normalize_dropbox_path(path: str) -> str:
    normalized = path.strip()
    if not normalized:
        raise ValueError("Dropbox reports path is required.")
    if not normalized.startswith("/"):
        normalized = "/" + normalized
    return normalized.rstrip("/")


def _safe_machine_name(name: str) -> str:
    return name.replace("/", "-")


@dataclass
class DropboxReportStore:
    client: dropbox.Dropbox
    reports_path: str

    @classmethod
    def from_config(cls, config: Config) -> "DropboxReportStore":
        if not config.dropbox_app_key or not config.dropbox_app_secret:
            raise ValueError("Dropbox app key/secret missing from config.")
        if not config.dropbox_refresh_token:
            raise ValueError("Dropbox refresh token missing from config.")
        if not config.dropbox_reports_path:
            raise ValueError("Dropbox reports path missing from config.")
        client = dropbox.Dropbox(
            oauth2_refresh_token=config.dropbox_refresh_token,
            app_key=config.dropbox_app_key,
            app_secret=config.dropbox_app_secret,
        )
        reports_path = _normalize_dropbox_path(config.dropbox_reports_path)
        store = cls(client=client, reports_path=reports_path)
        store._ensure_folder()
        return store

    def write_report(self, report: dict) -> None:
        self._archive_old_scans()
        machine_name = _safe_machine_name(report.get("machine_name", "unknown"))
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
        timestamped = f"{machine_name}__{timestamp}.json"
        latest = f"{machine_name}__latest.json"
        payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
        self._upload_text(self._archive_path(timestamped), payload, overwrite=True)
        self._upload_text(latest, payload, overwrite=True)

    def write_diff(self, diff: dict) -> None:
        payload = json.dumps(diff, indent=2, sort_keys=True) + "\n"
        self._upload_text(DIFF_FILENAME, payload, overwrite=True)

    def write_summary(self, summary: dict) -> None:
        payload = json.dumps(summary, indent=2, sort_keys=True) + "\n"
        self._upload_text(SUMMARY_FILENAME, payload, overwrite=True)

    def load_latest_reports(self) -> dict[str, dict]:
        reports: dict[str, dict] = {}
        for entry in self._list_files_in(self.reports_path):
            if not entry.name.endswith("__latest.json"):
                continue
            if entry.name.startswith("diff__"):
                continue
            data = self._download_json(entry.path_lower)
            if not data:
                continue
            machine = data.get("machine_name")
            if machine:
                reports[machine] = data
        return reports

    def prune_reports(self, prune_days: int) -> None:
        if prune_days <= 0:
            return
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=prune_days)
        for entry in self._list_files_in(self.reports_path):
            if not is_timestamped_report(entry.name):
                continue
            if entry.client_modified < cutoff:
                self.client.files_delete_v2(entry.path_lower)
        archive_path = f"{self.reports_path}/{ARCHIVE_DIR_NAME}"
        for entry in self._list_files_in(archive_path):
            if not is_timestamped_report(entry.name):
                continue
            if entry.client_modified < cutoff:
                self.client.files_delete_v2(entry.path_lower)

    def _upload_text(self, name: str, payload: str, overwrite: bool) -> None:
        path = f"{self.reports_path}/{name}"
        mode = WriteMode("overwrite") if overwrite else WriteMode("add")
        self.client.files_upload(payload.encode("utf-8"), path, mode=mode)

    def _download_json(self, path: str) -> dict | None:
        _, response = self.client.files_download(path)
        try:
            return json.loads(response.content.decode("utf-8"))
        except json.JSONDecodeError:
            return None

    def _list_files_in(self, path: str) -> Iterable[dropbox.files.FileMetadata]:
        result = self.client.files_list_folder(path)
        for entry in result.entries:
            if isinstance(entry, dropbox.files.FileMetadata):
                yield entry
        while result.has_more:
            result = self.client.files_list_folder_continue(result.cursor)
            for entry in result.entries:
                if isinstance(entry, dropbox.files.FileMetadata):
                    yield entry

    def _ensure_folder(self) -> None:
        try:
            self.client.files_get_metadata(self.reports_path)
        except dropbox.exceptions.ApiError:
            self.client.files_create_folder_v2(self.reports_path)

    def _archive_path(self, name: str) -> str:
        return f"{ARCHIVE_DIR_NAME}/{name}"

    def _ensure_archive_folder(self) -> None:
        archive_path = f"{self.reports_path}/{ARCHIVE_DIR_NAME}"
        try:
            self.client.files_get_metadata(archive_path)
        except dropbox.exceptions.ApiError:
            self.client.files_create_folder_v2(archive_path)

    def _archive_old_scans(self) -> None:
        self._ensure_archive_folder()
        for entry in self._list_files_in(self.reports_path):
            if not is_timestamped_report(entry.name):
                continue
            destination = f"{self.reports_path}/{ARCHIVE_DIR_NAME}/{entry.name}"
            try:
                self.client.files_move_v2(entry.path_lower, destination, autorename=True)
            except dropbox.exceptions.ApiError:
                continue
