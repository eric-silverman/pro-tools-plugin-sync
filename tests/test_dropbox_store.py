from __future__ import annotations

from pt_plugin_sync import dropbox_store as dropbox_store_module
from pt_plugin_sync.config import Config
from pt_plugin_sync.dropbox_store import DropboxReportStore


def test_normalize_dropbox_path() -> None:
    assert dropbox_store_module._normalize_dropbox_path("Reports") == "/Reports"
    assert dropbox_store_module._normalize_dropbox_path("/Reports/") == "/Reports"


def test_normalize_dropbox_path_rejects_empty() -> None:
    try:
        dropbox_store_module._normalize_dropbox_path("  ")
    except ValueError as exc:
        assert "Dropbox reports path is required." in str(exc)
    else:
        raise AssertionError("Expected ValueError for empty path")


def test_from_config_requires_tokens() -> None:
    config = Config(
        machine_name="Studio",
        plugins_path="/Plugins",
        reports_path="/Reports",
        reports_backend="dropbox",
    )
    try:
        DropboxReportStore.from_config(config)
    except ValueError as exc:
        assert "Dropbox app key/secret missing" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing Dropbox credentials")


def test_write_report_uploads_payload(monkeypatch, tmp_path) -> None:
    uploads = []

    class FakeClient:
        def files_upload(self, data, path, mode=None):
            uploads.append((path, data))

    store = DropboxReportStore(client=FakeClient(), reports_path="/Reports")
    monkeypatch.setattr(store, "_archive_old_scans", lambda: None)
    store.write_report({"machine_name": "Studio", "plugins": []})
    assert any(path.endswith("__latest.json") for path, _ in uploads)


def test_dropbox_prune_reports_skips_when_disabled(monkeypatch) -> None:
    calls = []

    class FakeClient:
        def files_delete_v2(self, _path):
            calls.append(_path)

    store = DropboxReportStore(client=FakeClient(), reports_path="/Reports")
    monkeypatch.setattr(store, "_list_files_in", lambda _path: [])
    store.prune_reports(prune_days=0)
    assert calls == []


def test_archive_path_builds_subdir() -> None:
    store = DropboxReportStore(client=object(), reports_path="/Reports")
    assert store._archive_path("file.json") == "old scans/file.json"


def test_list_files_in_handles_pagination(monkeypatch) -> None:
    class FakeFileMetadata:
        def __init__(self, name, path_lower=None):
            self.name = name
            self.path_lower = path_lower or f"/reports/{name}"

    class FakeResult:
        def __init__(self, entries, has_more, cursor):
            self.entries = entries
            self.has_more = has_more
            self.cursor = cursor

    class FakeClient:
        def __init__(self):
            self.calls = 0

        def files_list_folder(self, _path):
            return FakeResult([FakeFileMetadata("a.json"), object()], True, "cursor")

        def files_list_folder_continue(self, _cursor):
            return FakeResult([FakeFileMetadata("b.json")], False, "")

    store = DropboxReportStore(client=FakeClient(), reports_path="/Reports")
    monkeypatch.setattr(dropbox_store_module.dropbox.files, "FileMetadata", FakeFileMetadata)
    names = [entry.name for entry in store._list_files_in("/Reports")]
    assert names == ["a.json", "b.json"]


def test_prune_reports_deletes_old_entries(monkeypatch) -> None:
    deleted = []

    class FakeEntry:
        def __init__(self, name, client_modified):
            self.name = name
            self.client_modified = client_modified
            self.path_lower = f"/reports/{name}"

    class FakeClient:
        def files_delete_v2(self, path):
            deleted.append(path)

    fixed_now = dropbox_store_module.datetime(2024, 1, 10, tzinfo=dropbox_store_module.timezone.utc)
    old = fixed_now - dropbox_store_module.timedelta(days=3)
    recent = fixed_now

    class FakeDatetime:
        @staticmethod
        def now(tz=None):
            return fixed_now

    store = DropboxReportStore(client=FakeClient(), reports_path="/Reports")
    monkeypatch.setattr(dropbox_store_module, "datetime", FakeDatetime)

    def fake_list(path):
        if "old scans" in path:
            return [FakeEntry("Studio__20240101-000000.json", old)]
        return [
            FakeEntry("Studio__20240102-000000.json", old),
            FakeEntry("Studio__latest.json", recent),
        ]

    monkeypatch.setattr(store, "_list_files_in", fake_list)
    store.prune_reports(prune_days=1)
    assert "/reports/Studio__20240102-000000.json" in deleted
    assert "/reports/Studio__20240101-000000.json" in deleted


def test_download_json_handles_invalid_json(monkeypatch) -> None:
    class FakeResponse:
        content = b"not-json"

    class FakeClient:
        def files_download(self, _path):
            return None, FakeResponse()

    store = DropboxReportStore(client=FakeClient(), reports_path="/Reports")
    result = store._download_json("/Reports/file.json")
    assert result is None


def test_ensure_folder_creates_when_missing(monkeypatch) -> None:
    calls = []

    class FakeClient:
        def files_get_metadata(self, _path):
            raise dropbox_store_module.dropbox.exceptions.ApiError("id", "not found", None)

        def files_create_folder_v2(self, path):
            calls.append(path)

    class FakeApiError(Exception):
        pass

    monkeypatch.setattr(dropbox_store_module.dropbox.exceptions, "ApiError", FakeApiError)
    store = DropboxReportStore(client=FakeClient(), reports_path="/Reports")
    store._ensure_folder()
    assert calls == ["/Reports"]
