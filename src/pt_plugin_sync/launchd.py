from __future__ import annotations

import os
import pathlib
import plistlib
import subprocess
import sys

from .config import Config

PLIST_PATH = pathlib.Path("~/Library/LaunchAgents/com.eric.pt-plugin-sync.plist").expanduser()
MENUBAR_PLIST_PATH = pathlib.Path(
    "~/Library/LaunchAgents/com.eric.pt-plugin-sync.menubar.plist"
).expanduser()
LOG_DIR = pathlib.Path("~/Library/Logs/pt-plugin-sync").expanduser()


def _program_arguments() -> list[str]:
    return [sys.executable, "-m", "pt_plugin_sync.cli", "daemon"]


def _menubar_arguments() -> list[str]:
    return [sys.executable, "-m", "pt_plugin_sync.cli", "menubar"]


def write_plist(config: Config) -> pathlib.Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    plist = {
        "Label": "com.eric.pt-plugin-sync",
        "ProgramArguments": _program_arguments(),
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(LOG_DIR / "stdout.log"),
        "StandardErrorPath": str(LOG_DIR / "stderr.log"),
        "EnvironmentVariables": {
            "PATH": os.environ.get("PATH", ""),
        },
    }
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PLIST_PATH.open("wb") as handle:
        plistlib.dump(plist, handle)
    return PLIST_PATH


def write_menubar_plist(config: Config) -> pathlib.Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    plist = {
        "Label": "com.eric.pt-plugin-sync.menubar",
        "ProgramArguments": _menubar_arguments(),
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(LOG_DIR / "menubar-stdout.log"),
        "StandardErrorPath": str(LOG_DIR / "menubar-stderr.log"),
        "EnvironmentVariables": {
            "PATH": os.environ.get("PATH", ""),
        },
    }
    MENUBAR_PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MENUBAR_PLIST_PATH.open("wb") as handle:
        plistlib.dump(plist, handle)
    return MENUBAR_PLIST_PATH


def _launchctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["launchctl", *args], capture_output=True, text=True)


def install_launchagent(config: Config) -> None:
    write_plist(config)
    uid = os.getuid()
    result = _launchctl("bootstrap", f"gui/{uid}", str(PLIST_PATH))
    if result.returncode != 0:
        print("launchctl bootstrap failed. Try:")
        print(f"launchctl bootstrap gui/{uid} {PLIST_PATH}")
        print(result.stderr.strip())
    else:
        print("LaunchAgent installed and loaded.")


def uninstall_launchagent() -> None:
    uid = os.getuid()
    result = _launchctl("bootout", f"gui/{uid}", str(PLIST_PATH))
    if result.returncode != 0:
        print("launchctl bootout failed. Try:")
        print(f"launchctl bootout gui/{uid} {PLIST_PATH}")
        print(result.stderr.strip())
    if PLIST_PATH.exists():
        PLIST_PATH.unlink()
    print("LaunchAgent removed.")


def is_menubar_launchagent_installed() -> bool:
    return MENUBAR_PLIST_PATH.exists()


def install_menubar_launchagent(config: Config) -> None:
    write_menubar_plist(config)
    uid = os.getuid()
    result = _launchctl("bootstrap", f"gui/{uid}", str(MENUBAR_PLIST_PATH))
    if result.returncode != 0:
        print("launchctl bootstrap failed. Try:")
        print(f"launchctl bootstrap gui/{uid} {MENUBAR_PLIST_PATH}")
        print(result.stderr.strip())
    else:
        print("Menu bar LaunchAgent installed and loaded.")


def uninstall_menubar_launchagent() -> None:
    uid = os.getuid()
    result = _launchctl("bootout", f"gui/{uid}", str(MENUBAR_PLIST_PATH))
    if result.returncode != 0:
        print("launchctl bootout failed. Try:")
        print(f"launchctl bootout gui/{uid} {MENUBAR_PLIST_PATH}")
        print(result.stderr.strip())
    if MENUBAR_PLIST_PATH.exists():
        MENUBAR_PLIST_PATH.unlink()
    print("Menu bar LaunchAgent removed.")
