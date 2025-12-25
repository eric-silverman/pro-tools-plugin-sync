from __future__ import annotations

import threading

import builtins
import types

from pt_plugin_sync import daemon as daemon_module
from pt_plugin_sync.config import Config


def test_debounced_runner_triggers_action(monkeypatch) -> None:
    calls = []

    class FakeTimer:
        def __init__(self, _delay, action):
            self._action = action
            self.daemon = False

        def start(self):
            self._action()

        def cancel(self):
            return None

    monkeypatch.setattr(daemon_module.threading, "Timer", FakeTimer)
    runner = daemon_module.DebouncedRunner(1, lambda: calls.append("run"))
    runner.trigger()
    assert calls == ["run"]


def test_perform_scan_handles_pending(monkeypatch, tmp_path, capsys) -> None:
    config = Config(
        machine_name="Studio",
        plugins_path=str(tmp_path / "plugins"),
        reports_path=str(tmp_path / "reports"),
        reports_backend="local",
    )
    scan_lock = threading.Lock()
    pending = {"scan": False}
    calls = []

    class Result:
        diff = None

    def fake_scan(_config, open_report=True):
        calls.append(open_report)
        return Result()

    monkeypatch.setattr(daemon_module, "perform_scan", fake_scan)
    daemon_module._perform_scan(config, scan_lock, pending)
    assert calls == [True]


def test_debounced_runner_cancel(monkeypatch) -> None:
    class FakeTimer:
        def __init__(self, _delay, _action):
            self._cancelled = False

        def start(self):
            return None

        def cancel(self):
            self._cancelled = True

    monkeypatch.setattr(daemon_module.threading, "Timer", FakeTimer)
    runner = daemon_module.DebouncedRunner(1, lambda: None)
    runner.trigger()
    runner.cancel()


def test_run_daemon_fallback_without_watchdog(monkeypatch, tmp_path, capsys) -> None:
    config = Config(
        machine_name="Studio",
        plugins_path=str(tmp_path / "plugins"),
        reports_path=str(tmp_path / "reports"),
        reports_backend="local",
        scan_interval_seconds=1,
    )
    calls = []

    def fake_scan(_config, open_report=True):
        calls.append(open_report)
        return types.SimpleNamespace(diff=None)

    monkeypatch.setattr(daemon_module, "perform_scan", fake_scan)
    monkeypatch.setattr(daemon_module, "time", types.SimpleNamespace(time=lambda: 0, sleep=lambda _s: (_ for _ in ()).throw(KeyboardInterrupt())))

    def fake_import(name, *args, **kwargs):
        if name.startswith("watchdog"):
            raise ImportError("no watchdog")
        return builtins.__import__(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    daemon_module.run_daemon(config)
    output = capsys.readouterr().out
    assert "Watcher unavailable" in output
