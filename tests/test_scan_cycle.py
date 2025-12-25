from __future__ import annotations

import pathlib

from pt_plugin_sync.config import Config
from pt_plugin_sync.report_naming import DIFF_FILENAME, SUMMARY_FILENAME
from pt_plugin_sync import scan_cycle as scan_cycle_module
from pt_plugin_sync.scan_cycle import perform_scan


def _fixtures_path() -> pathlib.Path:
    return pathlib.Path(__file__).parent / "fixtures" / "plugins"


def test_perform_scan_writes_reports(tmp_path) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    config = Config(
        machine_name="Studio",
        plugins_path=str(_fixtures_path()),
        reports_path=str(reports_dir),
        reports_backend="local",
    )
    result = perform_scan(config, open_report=False)
    assert result.diff is not None
    assert result.summary is not None
    latest = reports_dir / "Studio__latest.json"
    assert latest.exists()
    assert (reports_dir / DIFF_FILENAME).exists()
    assert (reports_dir / SUMMARY_FILENAME).exists()


def test_perform_scan_update_count(tmp_path) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    config = Config(
        machine_name="Studio",
        plugins_path=str(_fixtures_path()),
        reports_path=str(reports_dir),
        reports_backend="local",
    )
    result = perform_scan(config, open_report=False)
    assert result.update_count >= 0


def test_count_updates_filters_invalid_entries() -> None:
    summary = {
        "updates_by_machine": {
            "Studio": ["bad", {"key": "ok"}, 123],
        }
    }
    count = scan_cycle_module._count_updates(summary, "Studio")
    assert count == 1


def test_count_updates_handles_missing_summary() -> None:
    assert scan_cycle_module._count_updates(None, "Studio") == 0
