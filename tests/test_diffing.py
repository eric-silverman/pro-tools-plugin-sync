from __future__ import annotations

import json

from pt_plugin_sync.diffing import (
    _version_key,
    _version_label,
    compute_diff,
    compute_update_summary,
    format_diff_summary,
    load_latest_reports,
    write_diff,
    write_summary,
)


def _report(machine: str, plugins: list[dict]) -> dict:
    return {"machine_name": machine, "plugins": plugins}


def test_compute_diff_detects_missing_and_mismatch() -> None:
    reports = {
        "A": _report(
            "A",
            [
                {"bundle_id": "com.example.alpha", "short_version": "1.0", "bundle_version": "1"},
                {"bundle_id": "com.example.beta", "short_version": "1.0", "bundle_version": "1"},
            ],
        ),
        "B": _report(
            "B",
            [
                {"bundle_id": "com.example.alpha", "short_version": "2.0", "bundle_version": "2"},
            ],
        ),
    }
    diff = compute_diff(reports)
    assert diff["machines"] == ["A", "B"]
    assert diff["missing"]["B"]
    assert diff["version_mismatches"]
    summary = format_diff_summary(diff)
    assert "Version mismatches" in summary


def test_load_latest_reports_and_write_diff(tmp_path) -> None:
    report_path = tmp_path / "Studio__latest.json"
    report_path.write_text(json.dumps(_report("Studio", [])), encoding="utf-8")
    reports = load_latest_reports(tmp_path)
    assert reports["Studio"]["machine_name"] == "Studio"

    diff_path = write_diff(tmp_path, {"machines": ["Studio"]})
    assert diff_path.exists()


def test_format_diff_summary_handles_no_reports() -> None:
    summary = format_diff_summary({"machines": []})
    assert summary == "No reports found."


def test_version_label_and_key() -> None:
    assert _version_label("1.2.3", "123") == "1.2.3 (123)"
    assert _version_label("1.2.3", "1.2.3") == "1.2.3"
    assert _version_label("unknown", "unknown") is None
    assert _version_key("1.2.3", "123") is not None
    assert _version_key("unknown", "unknown") is None


def test_compute_update_summary_marks_missing_and_outdated() -> None:
    reports = {
        "A": _report(
            "A",
            [
                {"bundle_id": "com.example.alpha", "short_version": "1.0", "bundle_version": "1"},
            ],
        ),
        "B": _report(
            "B",
            [
                {"bundle_id": "com.example.alpha", "short_version": "2.0", "bundle_version": "2"},
            ],
        ),
        "C": _report("C", []),
    }
    summary = compute_update_summary(reports)
    updates_a = summary["updates_by_machine"]["A"]
    updates_c = summary["updates_by_machine"]["C"]
    assert any(update["reason"] == "outdated" for update in updates_a)
    assert any(update["reason"] == "missing" for update in updates_c)


def test_write_summary_creates_file(tmp_path) -> None:
    path = write_summary(tmp_path, {"machines": ["Studio"]})
    assert path.exists()
