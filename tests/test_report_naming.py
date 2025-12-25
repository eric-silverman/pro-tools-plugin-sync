from __future__ import annotations

from pt_plugin_sync.report_naming import DIFF_FILENAME, SUMMARY_FILENAME, is_timestamped_report


def test_is_timestamped_report_filters_special_files() -> None:
    assert is_timestamped_report("Studio__20240101-120000.json") is True
    assert is_timestamped_report("diff__latest.json") is False
    assert is_timestamped_report("summary__latest.json") is False
    assert is_timestamped_report("Studio__latest.json") is False
    assert is_timestamped_report("notes.txt") is False
    assert is_timestamped_report(DIFF_FILENAME) is False
    assert is_timestamped_report(SUMMARY_FILENAME) is False
