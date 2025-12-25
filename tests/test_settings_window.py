from __future__ import annotations

import importlib
import sys
import types


def _install_fake_pyobjc(monkeypatch):
    appkit = types.SimpleNamespace(
        NSAlert=object,
        NSApp=None,
        NSApplication=types.SimpleNamespace(sharedApplication=lambda: None),
        NSApplicationActivateAllWindows=1,
        NSApplicationActivateIgnoringOtherApps=2,
        NSApplicationActivationPolicyRegular=0,
        NSButton=object,
        NSNormalWindowLevel=0,
        NSRadioButton=object,
        NSRunningApplication=types.SimpleNamespace(currentApplication=lambda: types.SimpleNamespace(activateWithOptions_=lambda *_: None)),
        NSStackView=object,
        NSSwitchButton=object,
        NSThread=types.SimpleNamespace(isMainThread=lambda: True),
        NSTextField=object,
        NSView=object,
        NSWindow=object,
        NSWindowCollectionBehaviorCanJoinAllSpaces=1,
        NSWindowCollectionBehaviorMoveToActiveSpace=2,
        NSWindowStyleMaskClosable=1,
        NSWindowStyleMaskTitled=2,
        NSWorkspace=object,
    )
    foundation = types.SimpleNamespace(
        NSObject=type("NSObject", (), {"init": lambda self: self}),
        NSURL=object,
        NSLog=lambda *_args, **_kwargs: None,
    )
    pyobjc_tools = types.SimpleNamespace(AppHelper=types.SimpleNamespace(callAfter=lambda fn: fn()))
    objc = types.SimpleNamespace(
        python_method=lambda fn: fn,
        super=lambda cls, self: self,
    )
    dropbox = types.SimpleNamespace(DropboxOAuth2FlowNoRedirect=object)

    monkeypatch.setitem(sys.modules, "AppKit", appkit)
    monkeypatch.setitem(sys.modules, "Foundation", foundation)
    monkeypatch.setitem(sys.modules, "PyObjCTools", pyobjc_tools)
    monkeypatch.setitem(sys.modules, "objc", objc)
    monkeypatch.setitem(sys.modules, "dropbox", dropbox)


def test_settings_window_debug_state(monkeypatch, tmp_path) -> None:
    _install_fake_pyobjc(monkeypatch)
    if "pt_plugin_sync.settings_window" in sys.modules:
        del sys.modules["pt_plugin_sync.settings_window"]
    import pt_plugin_sync.settings_window as settings_window

    settings_window = importlib.reload(settings_window)
    controller = settings_window.SettingsWindowController().initWithOnSave_(lambda _cfg: None)
    assert controller.debug_state() == "window=None"
