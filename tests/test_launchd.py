from __future__ import annotations

import pathlib
import plistlib
import sys

from pt_plugin_sync.config import Config
from pt_plugin_sync import launchd as launchd_module


def _config(tmp_path: pathlib.Path) -> Config:
    return Config(
        machine_name="Studio",
        plugins_path=str(tmp_path / "plugins"),
        reports_path=str(tmp_path / "reports"),
        reports_backend="local",
    )


def test_write_plist_creates_expected_plist(tmp_path, monkeypatch) -> None:
    plist_path = tmp_path / "agent.plist"
    log_dir = tmp_path / "logs"
    monkeypatch.setattr(launchd_module, "PLIST_PATH", plist_path)
    monkeypatch.setattr(launchd_module, "LOG_DIR", log_dir)

    path = launchd_module.write_plist(_config(tmp_path))
    assert path == plist_path
    assert plist_path.exists()
    data = plistlib.loads(plist_path.read_bytes())
    assert data["ProgramArguments"][0] == sys.executable
    assert data["Label"] == "com.eric.pt-plugin-sync"


def test_write_menubar_plist_creates_expected_plist(tmp_path, monkeypatch) -> None:
    plist_path = tmp_path / "menubar.plist"
    log_dir = tmp_path / "logs"
    monkeypatch.setattr(launchd_module, "MENUBAR_PLIST_PATH", plist_path)
    monkeypatch.setattr(launchd_module, "LOG_DIR", log_dir)

    path = launchd_module.write_menubar_plist(_config(tmp_path))
    assert path == plist_path
    data = plistlib.loads(plist_path.read_bytes())
    assert data["ProgramArguments"][0] == sys.executable
    assert data["Label"] == "com.eric.pt-plugin-sync.menubar"


def test_uninstall_launchagent_removes_plist(tmp_path, monkeypatch, capsys) -> None:
    plist_path = tmp_path / "agent.plist"
    plist_path.write_bytes(plistlib.dumps({"Label": "com.eric.pt-plugin-sync"}))
    monkeypatch.setattr(launchd_module, "PLIST_PATH", plist_path)

    def fake_launchctl(*_args):
        return launchd_module.subprocess.CompletedProcess(
            args=["launchctl"], returncode=0, stdout="", stderr=""
        )

    monkeypatch.setattr(launchd_module, "_launchctl", fake_launchctl)
    launchd_module.uninstall_launchagent()
    assert not plist_path.exists()
    assert "LaunchAgent removed." in capsys.readouterr().out


def test_install_launchagent_calls_launchctl(tmp_path, monkeypatch, capsys) -> None:
    plist_path = tmp_path / "agent.plist"
    log_dir = tmp_path / "logs"
    monkeypatch.setattr(launchd_module, "PLIST_PATH", plist_path)
    monkeypatch.setattr(launchd_module, "LOG_DIR", log_dir)

    calls = []

    def fake_launchctl(*args):
        calls.append(args)
        return launchd_module.subprocess.CompletedProcess(
            args=["launchctl"], returncode=0, stdout="", stderr=""
        )

    monkeypatch.setattr(launchd_module, "_launchctl", fake_launchctl)
    launchd_module.install_launchagent(_config(tmp_path))
    assert calls
