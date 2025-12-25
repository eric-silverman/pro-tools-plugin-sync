from __future__ import annotations

import json

from pt_plugin_sync.diffing import compute_diff, format_diff_summary, load_latest_reports, write_diff


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
