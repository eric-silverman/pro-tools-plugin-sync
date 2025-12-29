from __future__ import annotations

from pt_plugin_sync.combined_report import generate_combined_report_html


def test_generate_combined_report_html_contains_sections() -> None:
    reports = {
        "Studio": {
            "machine_name": "Studio",
            "scan_time": "2024-01-01T10:00:00Z",
            "plugins": [
                {
                    "bundle_name": "Alpha",
                    "bundle_id": "com.example.alpha",
                    "short_version": "1.0",
                    "bundle_version": "1",
                },
                {
                    "bundle_name": "Beta",
                    "bundle_id": "com.example.beta",
                    "short_version": None,
                    "bundle_version": None,
                },
            ],
        },
        "Rig": {
            "machine_name": "Rig",
            "scan_time": "2024-01-01T11:00:00Z",
            "plugins": [
                {
                    "bundle_name": "Alpha",
                    "bundle_id": "com.example.alpha",
                    "short_version": "2.0",
                    "bundle_version": "2",
                }
            ],
        },
    }
    summary = {
        "updates_by_machine": {
            "Studio": [
                {
                    "key": "com.example.alpha",
                    "bundle_name": "Alpha",
                    "current_version": "1.0",
                    "latest_version": "2.0",
                    "reason": "outdated",
                    "best_machine": "Rig",
                }
            ]
        }
    }
    diff = {"generated_at": "2024-01-01T12:00:00Z"}
    html = generate_combined_report_html(reports, summary, diff)
    assert "Plugin Sync Report" in html
    assert "Update Plan" in html
    assert "Version Comparison" in html
    assert "Show all plugins" in html
    assert "Alpha" in html
