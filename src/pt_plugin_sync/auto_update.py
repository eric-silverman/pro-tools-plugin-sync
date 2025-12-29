from __future__ import annotations

import os
import pathlib
import plistlib
import subprocess
import tempfile
import urllib.parse
import urllib.request


def find_app_bundle(executable_path: str) -> pathlib.Path | None:
    path = pathlib.Path(executable_path).resolve()
    for parent in [path, *path.parents]:
        if parent.suffix == ".app":
            return parent
    return None


def download_dmg(url: str, target_dir: pathlib.Path) -> pathlib.Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    name = pathlib.Path(urllib.parse.urlparse(url).path).name or "pt-plugin-sync.dmg"
    if not name.endswith(".dmg"):
        name = f"{name}.dmg"
    target = target_dir / name
    with urllib.request.urlopen(url, timeout=30) as response:
        target.write_bytes(response.read())
    return target


def mount_dmg(dmg_path: pathlib.Path) -> pathlib.Path:
    result = subprocess.run(
        [
            "hdiutil",
            "attach",
            "-nobrowse",
            "-readonly",
            "-plist",
            str(dmg_path),
        ],
        check=True,
        capture_output=True,
    )
    payload = plistlib.loads(result.stdout)
    entities = payload.get("system-entities", [])
    for entity in entities:
        mount_point = entity.get("mount-point")
        if mount_point:
            return pathlib.Path(mount_point)
    raise RuntimeError("Unable to mount DMG.")


def detach_dmg(mount_point: pathlib.Path) -> None:
    subprocess.run(
        ["hdiutil", "detach", str(mount_point), "-quiet"],
        capture_output=True,
    )


def find_app_in_mount(mount_point: pathlib.Path) -> pathlib.Path | None:
    for candidate in mount_point.glob("*.app"):
        return candidate
    for candidate in mount_point.glob("*/**/*.app"):
        return candidate
    return None


def install_update(
    asset_url: str,
    app_bundle: pathlib.Path | None,
    *,
    current_pid: int | None = None,
) -> None:
    mount_point: pathlib.Path | None = None
    with tempfile.TemporaryDirectory() as tmp_dir:
        dmg_path = download_dmg(asset_url, pathlib.Path(tmp_dir))
        try:
            mount_point = mount_dmg(dmg_path)
            app_source = find_app_in_mount(mount_point)
            if not app_source:
                raise RuntimeError("No app bundle found in update image.")
            destination = app_bundle or (pathlib.Path("/Applications") / app_source.name)
            if not os.access(destination.parent, os.W_OK):
                raise RuntimeError(f"Destination not writable: {destination.parent}")
            script_path = pathlib.Path(tmp_dir) / "pt-plugin-sync-update.sh"
            script_path.write_text(
                "#!/bin/sh\n"
                "set -e\n"
                "PID=\"$1\"\n"
                "MOUNT=\"$2\"\n"
                "APP_SRC=\"$3\"\n"
                "APP_DEST=\"$4\"\n"
                "while kill -0 \"$PID\" 2>/dev/null; do\n"
                "  sleep 1\n"
                "done\n"
                "/usr/bin/ditto \"$APP_SRC\" \"$APP_DEST\"\n"
                "hdiutil detach \"$MOUNT\" -quiet || true\n"
                "open \"$APP_DEST\"\n",
                encoding="utf-8",
            )
            os.chmod(script_path, 0o755)
            pid = current_pid or os.getpid()
            subprocess.Popen(
                [
                    "/bin/sh",
                    str(script_path),
                    str(pid),
                    str(mount_point),
                    str(app_source),
                    str(destination),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            if mount_point:
                detach_dmg(mount_point)
            raise
