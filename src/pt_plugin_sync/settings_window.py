from __future__ import annotations

import pathlib

from AppKit import (
    NSAlert,
    NSApp,
    NSApplication,
    NSApplicationActivateAllWindows,
    NSApplicationActivateIgnoringOtherApps,
    NSApplicationActivationPolicyRegular,
    NSButton,
    NSNormalWindowLevel,
    NSRadioButton,
    NSRunningApplication,
    NSStackView,
    NSSwitchButton,
    NSThread,
    NSTextField,
    NSView,
    NSWindow,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorMoveToActiveSpace,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskTitled,
    NSWorkspace,
)
from Foundation import NSObject, NSURL, NSLog
from PyObjCTools import AppHelper
from objc import python_method, super as objc_super
from dropbox import DropboxOAuth2FlowNoRedirect

from .config import Config, validate_config, write_config
from .dropbox_auth import DROPBOX_OAUTH_SCOPES


class SettingsWindowController(NSObject):
    def initWithOnSave_(self, on_save):
        self = objc_super(SettingsWindowController, self).init()
        if self is None:
            return None
        self._on_save = on_save
        self._window = None
        self._config: Config | None = None
        self._fields: dict[str, NSTextField] = {}
        self._checkboxes: dict[str, NSButton] = {}
        self._local_stack = None
        self._dropbox_stack = None
        self._backend_local = None
        self._backend_dropbox = None
        return self

    def present_(self, config: Config) -> None:
        self._config = config
        if NSThread.isMainThread():
            self._present()
            return
        AppHelper.callAfter(self._present)

    @python_method
    def _present(self) -> None:
        try:
            NSLog("Settings window present called")
            app = NSApplication.sharedApplication()
            app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
            app.unhide_(None)
            if self._window is None:
                self._build_window()
            self._populate()
            self._window.setHidesOnDeactivate_(False)
            self._window.makeKeyAndOrderFront_(None)
            self._window.orderFront_(None)
            self._window.orderFrontRegardless_()
            self._window.setIsVisible_(True)
            self._window.displayIfNeeded()
            app.activateIgnoringOtherApps_(True)
            NSRunningApplication.currentApplication().activateWithOptions_(
                NSApplicationActivateIgnoringOtherApps | NSApplicationActivateAllWindows
            )
            NSLog(
                "Settings window visible=%d key=%d",
                self._window.isVisible(),
                self._window.isKeyWindow(),
            )
        except Exception as exc:
            NSLog("Settings window error: %@", str(exc))

    @python_method
    def debug_state(self) -> str:
        if self._window is None:
            return "window=None"
        try:
            frame = self._window.frame()
            return (
                f"window=exists visible={self._window.isVisible()} "
                f"key={self._window.isKeyWindow()} "
                f"frame=({frame.origin.x},{frame.origin.y},{frame.size.width},{frame.size.height})"
            )
        except Exception as exc:
            return f"window=exists error={exc}"

    @python_method
    def _build_window(self) -> None:
        rect = ((0, 0), (560, 600))
        self._window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            rect,
            NSWindowStyleMaskTitled | NSWindowStyleMaskClosable,
            2,
            False,
        )
        self._window.setTitle_("pt-plugin-sync Settings")
        self._window.setReleasedWhenClosed_(False)
        self._window.setLevel_(NSNormalWindowLevel)
        self._window.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorMoveToActiveSpace
        )
        self._window.center()
        content = self._window.contentView()

        root = NSStackView.alloc().initWithFrame_(content.bounds())
        root.setVertical_(True)
        root.setSpacing_(12)
        root.setEdgeInsets_((10, 12, 12, 12))
        root.setAutoresizingMask_(1 << 1 | 1 << 4)
        content.addSubview_(root)

        root.addArrangedSubview_(self._label("General"))
        root.addArrangedSubview_(self._row("Machine name", "machine_name"))
        root.addArrangedSubview_(self._row("Plugins folder", "plugins_path"))
        root.addArrangedSubview_(self._row("Scan interval (sec)", "scan_interval_seconds"))
        root.addArrangedSubview_(self._row("Debounce (sec)", "debounce_seconds"))

        root.addArrangedSubview_(self._label("Storage"))
        backend_row = NSStackView.alloc().initWithFrame_(((0, 0), (520, 24)))
        backend_row.setVertical_(False)
        backend_row.setSpacing_(10)
        backend_row.addArrangedSubview_(self._label("Reports backend"))
        self._backend_local = self._radio("Local")
        self._backend_dropbox = self._radio("Dropbox")
        backend_row.addArrangedSubview_(self._backend_local)
        backend_row.addArrangedSubview_(self._backend_dropbox)
        root.addArrangedSubview_(backend_row)

        self._local_stack = NSStackView.alloc().initWithFrame_(((0, 0), (520, 60)))
        self._local_stack.setVertical_(True)
        self._local_stack.setSpacing_(8)
        self._local_stack.addArrangedSubview_(self._row("Reports folder", "reports_path"))
        root.addArrangedSubview_(self._local_stack)

        self._dropbox_stack = NSStackView.alloc().initWithFrame_(((0, 0), (520, 140)))
        self._dropbox_stack.setVertical_(True)
        self._dropbox_stack.setSpacing_(8)
        self._dropbox_stack.addArrangedSubview_(
            self._row("Dropbox reports path", "dropbox_reports_path")
        )
        self._dropbox_stack.addArrangedSubview_(self._row("Dropbox app key", "dropbox_app_key"))
        self._dropbox_stack.addArrangedSubview_(
            self._row("Dropbox app secret", "dropbox_app_secret")
        )
        self._dropbox_stack.addArrangedSubview_(
            self._row("Dropbox refresh token", "dropbox_refresh_token")
        )
        auth_row = NSStackView.alloc().initWithFrame_(((0, 0), (520, 28)))
        auth_row.setVertical_(False)
        auth_row.setSpacing_(8)
        auth_row.addArrangedSubview_(self._label(" "))
        auth_button = NSButton.alloc().initWithFrame_(((0, 0), (160, 24)))
        auth_button.setTitle_("Authorize Dropbox...")
        auth_button.setTarget_(self)
        auth_button.setAction_("onAuthorizeDropbox:")
        auth_row.addArrangedSubview_(auth_button)
        self._dropbox_stack.addArrangedSubview_(auth_row)
        root.addArrangedSubview_(self._dropbox_stack)

        root.addArrangedSubview_(self._label("Advanced"))
        root.addArrangedSubview_(self._row("Prune reports (days)", "prune_days"))
        root.addArrangedSubview_(self._checkbox_row("Hash binaries", "hash_binaries"))
        root.addArrangedSubview_(
            self._checkbox_row("Download updates automatically", "auto_update_download")
        )

        buttons = NSStackView.alloc().initWithFrame_(((0, 0), (520, 30)))
        buttons.setVertical_(False)
        buttons.setSpacing_(8)
        buttons.setDistribution_(3)
        cancel_button = NSButton.alloc().initWithFrame_(((0, 0), (100, 24)))
        cancel_button.setTitle_("Cancel")
        cancel_button.setTarget_(self)
        cancel_button.setAction_("onCancel:")
        save_button = NSButton.alloc().initWithFrame_(((0, 0), (100, 24)))
        save_button.setTitle_("Save")
        save_button.setTarget_(self)
        save_button.setAction_("onSave:")
        buttons.addArrangedSubview_(cancel_button)
        buttons.addArrangedSubview_(save_button)
        root.addArrangedSubview_(buttons)

    @python_method
    def _populate(self) -> None:
        if not self._config:
            return
        self._set_field("machine_name", self._config.machine_name)
        self._set_field("plugins_path", self._config.plugins_path)
        self._set_field("scan_interval_seconds", str(self._config.scan_interval_seconds))
        self._set_field("debounce_seconds", str(self._config.debounce_seconds))
        self._set_field("reports_path", self._config.reports_path)
        self._set_field(
            "dropbox_reports_path", self._config.dropbox_reports_path or "/Pro Tools Plugin Reports"
        )
        self._set_field("dropbox_app_key", self._config.dropbox_app_key or "")
        self._set_field("dropbox_app_secret", self._config.dropbox_app_secret or "")
        self._set_field("dropbox_refresh_token", self._config.dropbox_refresh_token or "")
        self._set_field("prune_days", str(self._config.prune_days))
        self._set_checkbox("hash_binaries", self._config.hash_binaries)
        self._set_checkbox("auto_update_download", self._config.auto_update_download)
        backend = (self._config.reports_backend or "local").lower()
        if backend == "dropbox":
            self._backend_dropbox.setState_(1)
            self._backend_local.setState_(0)
        else:
            self._backend_local.setState_(1)
            self._backend_dropbox.setState_(0)
        self._apply_backend_visibility()

    @python_method
    def _apply_backend_visibility(self) -> None:
        use_dropbox = self._backend_dropbox.state() == 1
        self._dropbox_stack.setHidden_(not use_dropbox)
        self._local_stack.setHidden_(use_dropbox)

    @python_method
    def _label(self, text: str) -> NSTextField:
        label = NSTextField.labelWithString_(text)
        label.setAlignment_(0)
        return label

    @python_method
    def _row(self, label: str, key: str) -> NSView:
        row = NSStackView.alloc().initWithFrame_(((0, 0), (520, 26)))
        row.setVertical_(False)
        row.setSpacing_(8)
        row.addArrangedSubview_(self._label(label))
        field = NSTextField.alloc().initWithFrame_(((0, 0), (360, 24)))
        field.setStringValue_("")
        row.addArrangedSubview_(field)
        self._fields[key] = field
        return row

    @python_method
    def _radio(self, title: str) -> NSButton:
        button = NSButton.alloc().initWithFrame_(((0, 0), (100, 18)))
        button.setButtonType_(NSRadioButton)
        button.setTitle_(title)
        button.setTarget_(self)
        button.setAction_("onBackendChanged:")
        return button

    @python_method
    def _checkbox_row(self, label: str, key: str) -> NSView:
        row = NSStackView.alloc().initWithFrame_(((0, 0), (520, 26)))
        row.setVertical_(False)
        row.setSpacing_(8)
        row.addArrangedSubview_(self._label(label))
        checkbox = NSButton.alloc().initWithFrame_(((0, 0), (200, 18)))
        checkbox.setButtonType_(NSSwitchButton)
        checkbox.setTitle_("")
        row.addArrangedSubview_(checkbox)
        self._checkboxes[key] = checkbox
        return row

    @python_method
    def _set_field(self, key: str, value: str) -> None:
        field = self._fields.get(key)
        if field:
            field.setStringValue_(value)

    @python_method
    def _get_field(self, key: str) -> str:
        field = self._fields.get(key)
        if not field:
            return ""
        return str(field.stringValue()).strip()

    @python_method
    def _set_checkbox(self, key: str, value: bool) -> None:
        checkbox = self._checkboxes.get(key)
        if checkbox:
            checkbox.setState_(1 if value else 0)

    @python_method
    def _get_checkbox(self, key: str) -> bool:
        checkbox = self._checkboxes.get(key)
        if not checkbox:
            return False
        return checkbox.state() == 1

    @python_method
    def _alert(self, title: str, message: str) -> None:
        alert = NSAlert.alloc().init()
        alert.setMessageText_(title)
        alert.setInformativeText_(message)
        alert.runModal()

    def onBackendChanged_(self, _sender) -> None:
        if self._backend_local.state() == 1:
            self._backend_dropbox.setState_(0)
        elif self._backend_dropbox.state() == 1:
            self._backend_local.setState_(0)
        self._apply_backend_visibility()

    def onAuthorizeDropbox_(self, _sender) -> None:
        app_key = self._get_field("dropbox_app_key")
        app_secret = self._get_field("dropbox_app_secret")
        if not app_key or not app_secret:
            self._alert("Dropbox setup", "App key and secret are required.")
            return
        flow = DropboxOAuth2FlowNoRedirect(
            app_key,
            app_secret,
            token_access_type="offline",
            scope=DROPBOX_OAUTH_SCOPES,
        )
        authorize_url = flow.start()
        NSWorkspace.sharedWorkspace().openURL_(NSURL.URLWithString_(authorize_url))
        alert = NSAlert.alloc().init()
        alert.setMessageText_("Dropbox authorization")
        alert.setInformativeText_("Paste the authorization code from your browser.")
        code_field = NSTextField.alloc().initWithFrame_(((0, 0), (360, 24)))
        alert.setAccessoryView_(code_field)
        alert.addButtonWithTitle_("Save")
        alert.addButtonWithTitle_("Cancel")
        response = alert.runModal()
        if response != 1000:
            return
        auth_code = str(code_field.stringValue()).strip()
        if not auth_code:
            self._alert("Dropbox setup", "Authorization code is required.")
            return
        try:
            result = flow.finish(auth_code)
        except Exception as exc:
            self._alert("Dropbox setup", str(exc))
            return
        if not result.refresh_token:
            self._alert(
                "Dropbox setup",
                "Dropbox did not return a refresh token. Ensure short-lived tokens are enabled.",
            )
            return
        self._set_field("dropbox_refresh_token", result.refresh_token)

    def onCancel_(self, _sender) -> None:
        if self._window:
            self._window.orderOut_(None)

    def onSave_(self, _sender) -> None:
        backend = "dropbox" if self._backend_dropbox.state() == 1 else "local"
        try:
            interval = int(self._get_field("scan_interval_seconds") or "0")
        except ValueError:
            self._alert("Invalid settings", "Scan interval must be a number.")
            return
        try:
            debounce_seconds = int(self._get_field("debounce_seconds") or "0")
        except ValueError:
            self._alert("Invalid settings", "Debounce must be a number.")
            return
        try:
            prune_days = int(self._get_field("prune_days") or "0")
        except ValueError:
            self._alert("Invalid settings", "Prune days must be a number.")
            return
        updated = Config(
            machine_name=self._get_field("machine_name"),
            plugins_path=self._get_field("plugins_path"),
            reports_path=self._get_field("reports_path"),
            reports_backend=backend,
            dropbox_app_key=self._get_field("dropbox_app_key") or None,
            dropbox_app_secret=self._get_field("dropbox_app_secret") or None,
            dropbox_refresh_token=self._get_field("dropbox_refresh_token") or None,
            dropbox_reports_path=self._get_field("dropbox_reports_path") or None,
            scan_interval_seconds=interval,
            debounce_seconds=debounce_seconds,
            hash_binaries=self._get_checkbox("hash_binaries"),
            prune_days=prune_days,
            auto_update_download=self._get_checkbox("auto_update_download"),
        )
        if backend == "local":
            reports_dir = pathlib.Path(updated.reports_path).expanduser()
            reports_dir.mkdir(parents=True, exist_ok=True)
        validation = validate_config(updated)
        if not validation.ok:
            self._alert("Invalid settings", "\n".join(validation.errors))
            return
        write_config(updated)
        if self._window:
            self._window.orderOut_(None)
        self._on_save(updated)
