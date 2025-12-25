from __future__ import annotations

from pt_plugin_sync.config import Config
from pt_plugin_sync import update_report as update_report_module
from pt_plugin_sync.update_report import generate_update_report_html, open_update_report_if_needed


def test_generate_update_report_html_contains_counts() -> None:
    summary = {
        "generated_at": "2024-01-01T00:00:00Z",
        "updates_by_machine": {
            "Studio": [
                {
                    "key": "alpha",
                    "bundle_name": "Alpha",
                    "current_version": "1.0",
                    "latest_version": "2.0",
                    "reason": "outdated",
                    "best_machine": "Rig",
                },
                {
                    "key": "beta",
                    "bundle_name": "Beta",
                    "current_version": None,
                    "latest_version": "1.0",
                    "reason": "missing",
                    "best_machine": "Rig",
                },
                {
                    "key": "gamma",
                    "bundle_name": "Gamma",
                    "current_version": "unknown",
                    "latest_version": "unknown",
                    "reason": "unknown_version",
                },
            ]
        },
    }
    html = generate_update_report_html(summary, "Studio")
    assert "Total Updates" in html
    assert ">3<" in html
    assert "Missing" in html
    assert "Outdated" in html
    assert "Unknown Version" in html
    assert "Update from Rig to version 2.0." in html
    assert "Install from Rig (version 1.0)." in html


def test_generate_update_report_html_with_empty_updates() -> None:
    summary = {"updates_by_machine": {"Studio": []}}
    html = generate_update_report_html(summary, "Studio")
    assert "All up to date." in html


def test_action_text_variants() -> None:
    from pt_plugin_sync.update_report import _action_text

    assert _action_text({"reason": "missing", "latest_version": "1.0"}) == "Install version 1.0."
    assert _action_text({"reason": "outdated", "latest_version": "2.0"}) == "Update to version 2.0."
    assert (
        _action_text({"reason": "missing", "best_machine": "Rig"})
        == "Install from Rig (latest version)."
    )
    assert _action_text({"reason": "unknown_version", "best_machine": "Rig"}) == "Verify version against Rig."


def test_updates_for_machine_filters_non_dict() -> None:
    from pt_plugin_sync.update_report import _updates_for_machine

    summary = {"updates_by_machine": {"Studio": ["bad", {"key": "ok"}]}}
    updates = _updates_for_machine(summary, "Studio")
    assert updates == [{"key": "ok"}]


def test_sort_updates_orders_by_reason_and_name() -> None:
    from pt_plugin_sync.update_report import _sort_updates

    updates = [
        {"reason": "outdated", "bundle_name": "Beta"},
        {"reason": "missing", "bundle_name": "Alpha"},
        {"reason": "unknown_version", "bundle_name": "Gamma"},
    ]
    sorted_updates = _sort_updates(updates)
    assert [item["bundle_name"] for item in sorted_updates] == ["Alpha", "Beta", "Gamma"]


def test_generate_update_report_html_handles_missing_fields() -> None:
    summary = {
        "updates_by_machine": {
            "Studio": [
                {
                    "key": "unknown.plugin",
                    "current_version": None,
                    "latest_version": None,
                    "reason": "missing",
                }
            ]
        }
    }
    html = generate_update_report_html(summary, "Studio")
    assert "unknown.plugin" in html
    assert "Missing" in html


def test_open_update_report_if_needed_no_updates(tmp_path, monkeypatch) -> None:
    config = Config(
        machine_name="Studio",
        plugins_path=str(tmp_path / "plugins"),
        reports_path=str(tmp_path / "reports"),
        reports_backend="local",
    )
    summary = {"updates_by_machine": {"Studio": []}}
    monkeypatch.setattr(update_report_module, "_open_report", lambda _path: None)
    result = open_update_report_if_needed(config, summary)
    assert result is None


def test_open_update_report_if_needed_generates_report(tmp_path, monkeypatch) -> None:
    config = Config(
        machine_name="Studio",
        plugins_path=str(tmp_path / "plugins"),
        reports_path=str(tmp_path / "reports"),
        reports_backend="local",
    )
    summary = {
        "updates_by_machine": {
            "Studio": [
                {"key": "alpha", "current_version": "1", "latest_version": "2", "reason": "outdated"}
            ]
        }
    }
    opened = {}

    def fake_open(path):
        opened["path"] = path

    monkeypatch.setattr(update_report_module, "_open_report", fake_open)
    result = open_update_report_if_needed(config, summary)
    assert result is not None
    assert opened["path"] == result
