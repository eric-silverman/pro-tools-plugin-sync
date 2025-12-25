from __future__ import annotations

import json
import os
import time

from pt_plugin_sync.config import Config
from pt_plugin_sync.reporting import build_report, prune_reports, write_report
from pt_plugin_sync.scanner import PluginInfo


def test_write_report_creates_latest_and_timestamped(tmp_path) -> None:
    config = Config(
        machine_name="Studio",
        plugins_path=str(tmp_path / "plugins"),
        reports_path=str(tmp_path / "reports"),
        reports_backend="local",
    )
    plugins = [
        PluginInfo(
            bundle_name="Alpha.aaxplugin",
            bundle_id="com.example.alpha",
            short_version="1.0",
            bundle_version="1",
            mtime=123.0,
            binary_hash=None,
        )
    ]
    report = build_report(config, plugins)
    timestamped, latest = write_report(tmp_path, report)
    assert timestamped.exists()
    assert latest.exists()
    data = json.loads(latest.read_text(encoding="utf-8"))
    assert data["machine_name"] == "Studio"


def test_prune_reports_removes_old_files(tmp_path) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    old_report = reports_dir / "Studio__20000101-000000.json"
    old_report.write_text("{}", encoding="utf-8")
    old_report.touch()
    old_timestamp = 946684800  # 2000-01-01
    os.utime(old_report, (old_timestamp, old_timestamp))
    prune_reports(reports_dir, prune_days=1)
    assert not old_report.exists()


def test_prune_reports_skips_recent_files(tmp_path) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    recent_report = reports_dir / "Studio__20000101-000001.json"
    recent_report.write_text("{}", encoding="utf-8")
    now = time.time()
    os.utime(recent_report, (now, now))
    prune_reports(reports_dir, prune_days=1)
    assert recent_report.exists()


def test_write_report_sanitizes_machine_name(tmp_path) -> None:
    config = Config(
        machine_name="Studio/A",
        plugins_path=str(tmp_path / "plugins"),
        reports_path=str(tmp_path / "reports"),
        reports_backend="local",
    )
    plugins = [
        PluginInfo(
            bundle_name="Alpha.aaxplugin",
            bundle_id="com.example.alpha",
            short_version="1.0",
            bundle_version="1",
            mtime=123.0,
            binary_hash=None,
        )
    ]
    report = build_report(config, plugins)
    timestamped, latest = write_report(tmp_path, report)
    assert "Studio-A" in timestamped.name
    assert "Studio-A" in latest.name
