from __future__ import annotations

from pt_plugin_sync.config import Config
from pt_plugin_sync.report_store import LocalReportStore, report_store_from_config


def test_report_store_from_config_local(tmp_path) -> None:
    config = Config(
        machine_name="Studio",
        plugins_path=str(tmp_path / "plugins"),
        reports_path=str(tmp_path / "reports"),
        reports_backend="local",
    )
    store = report_store_from_config(config)
    assert isinstance(store, LocalReportStore)


def test_local_report_store_writes_and_reads_reports(tmp_path) -> None:
    reports_dir = tmp_path / "reports"
    store = LocalReportStore(reports_dir)
    store.write_report({"machine_name": "Studio", "plugins": []})
    reports = store.load_latest_reports()
    assert "Studio" in reports
