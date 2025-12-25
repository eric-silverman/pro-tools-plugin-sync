from __future__ import annotations

import os
import pathlib
import socket
import subprocess
from dataclasses import dataclass
from typing import Iterable

try:
    import tomllib
except ImportError:  # pragma: no cover - Python <3.11
    tomllib = None

CONFIG_DIR = pathlib.Path("~/.config/pt-plugin-sync").expanduser()
CONFIG_PATH = CONFIG_DIR / "config.toml"

DEFAULT_PLUGINS_PATH = "/Library/Application Support/Avid/Audio/Plug-Ins"
DEFAULT_REPORTS_PATH = "~/Dropbox/Pro Tools Plugin Reports"
DEFAULT_REPORTS_BACKEND = "local"
DEFAULT_DROPBOX_REPORTS_PATH = "/Pro Tools Plugin Reports"
DEFAULT_SCAN_INTERVAL_SECONDS = 3600
DEFAULT_DEBOUNCE_SECONDS = 15
DEFAULT_HASH_BINARIES = False
DEFAULT_AUTO_UPDATE_DOWNLOAD = False


@dataclass
class Config:
    machine_name: str
    plugins_path: str
    reports_path: str
    reports_backend: str = DEFAULT_REPORTS_BACKEND
    dropbox_app_key: str | None = None
    dropbox_app_secret: str | None = None
    dropbox_refresh_token: str | None = None
    dropbox_reports_path: str | None = None
    scan_interval_seconds: int = DEFAULT_SCAN_INTERVAL_SECONDS
    debounce_seconds: int = DEFAULT_DEBOUNCE_SECONDS
    hash_binaries: bool = DEFAULT_HASH_BINARIES
    prune_days: int = 0
    auto_update_download: bool = DEFAULT_AUTO_UPDATE_DOWNLOAD

    def expanded_plugins_path(self) -> pathlib.Path:
        return pathlib.Path(os.path.expanduser(self.plugins_path))

    def expanded_reports_path(self) -> pathlib.Path:
        return pathlib.Path(os.path.expanduser(self.reports_path))


@dataclass
class ConfigValidation:
    ok: bool
    errors: list[str]


def _default_machine_name() -> str:
    try:
        result = subprocess.run(
            ["scutil", "--get", "ComputerName"],
            check=True,
            capture_output=True,
            text=True,
        )
        name = result.stdout.strip()
        if name:
            return name
    except Exception:
        pass
    return socket.gethostname()


def _sanitize_machine_name(name: str) -> str:
    return name.replace(os.sep, "-").strip() or "unknown-machine"


def _toml_escape(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _none_if_blank(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def default_config(machine_name: str | None = None) -> Config:
    return Config(
        machine_name=_sanitize_machine_name(machine_name or _default_machine_name()),
        plugins_path=os.path.expanduser(DEFAULT_PLUGINS_PATH),
        reports_path=os.path.expanduser(DEFAULT_REPORTS_PATH),
        reports_backend=DEFAULT_REPORTS_BACKEND,
        dropbox_reports_path=DEFAULT_DROPBOX_REPORTS_PATH,
        auto_update_download=DEFAULT_AUTO_UPDATE_DOWNLOAD,
    )


def load_config() -> Config | None:
    if not CONFIG_PATH.exists():
        return None
    if tomllib is None:
        raise RuntimeError("tomllib unavailable; use Python 3.11+")
    with CONFIG_PATH.open("rb") as handle:
        data = tomllib.load(handle)
    return Config(
        machine_name=str(data.get("machine_name", "")),
        plugins_path=str(data.get("plugins_path", "")),
        reports_path=str(data.get("reports_path", "")),
        reports_backend=str(data.get("reports_backend", DEFAULT_REPORTS_BACKEND)),
        dropbox_app_key=_none_if_blank(data.get("dropbox_app_key")),
        dropbox_app_secret=_none_if_blank(data.get("dropbox_app_secret")),
        dropbox_refresh_token=_none_if_blank(data.get("dropbox_refresh_token")),
        dropbox_reports_path=_none_if_blank(data.get("dropbox_reports_path")),
        scan_interval_seconds=int(data.get("scan_interval_seconds", DEFAULT_SCAN_INTERVAL_SECONDS)),
        debounce_seconds=int(data.get("debounce_seconds", DEFAULT_DEBOUNCE_SECONDS)),
        hash_binaries=bool(data.get("hash_binaries", DEFAULT_HASH_BINARIES)),
        prune_days=int(data.get("prune_days", 0)),
        auto_update_download=bool(
            data.get("auto_update_download", DEFAULT_AUTO_UPDATE_DOWNLOAD)
        ),
    )


def validate_config(config: Config) -> ConfigValidation:
    errors: list[str] = []
    backend = (config.reports_backend or DEFAULT_REPORTS_BACKEND).strip().lower()
    if not config.machine_name.strip():
        errors.append("machine_name is required")
    plugins_path = pathlib.Path(os.path.expanduser(config.plugins_path))
    if not plugins_path.exists() or not plugins_path.is_dir():
        errors.append(f"plugins_path does not exist: {plugins_path}")
    if backend == "local":
        reports_path = pathlib.Path(os.path.expanduser(config.reports_path))
        if not reports_path.exists() or not reports_path.is_dir():
            errors.append(f"reports_path does not exist: {reports_path}")
    elif backend == "dropbox":
        if not config.dropbox_app_key:
            errors.append("dropbox_app_key is required for dropbox backend")
        if not config.dropbox_app_secret:
            errors.append("dropbox_app_secret is required for dropbox backend")
        if not config.dropbox_refresh_token:
            errors.append("dropbox_refresh_token is required for dropbox backend")
        if not config.dropbox_reports_path:
            errors.append("dropbox_reports_path is required for dropbox backend")
    else:
        errors.append("reports_backend must be 'local' or 'dropbox'")
    if config.scan_interval_seconds <= 0:
        errors.append("scan_interval_seconds must be positive")
    if config.debounce_seconds < 0:
        errors.append("debounce_seconds must be >= 0")
    if config.prune_days < 0:
        errors.append("prune_days must be >= 0")
    return ConfigValidation(ok=not errors, errors=errors)


def write_config(config: Config) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        f"machine_name = {_toml_escape(config.machine_name)}",
        f"plugins_path = {_toml_escape(config.plugins_path)}",
        f"reports_path = {_toml_escape(config.reports_path)}",
        f"reports_backend = {_toml_escape(config.reports_backend)}",
        f"scan_interval_seconds = {int(config.scan_interval_seconds)}",
        f"debounce_seconds = {int(config.debounce_seconds)}",
        f"hash_binaries = {'true' if config.hash_binaries else 'false'}",
        f"prune_days = {int(config.prune_days)}",
        f"auto_update_download = {'true' if config.auto_update_download else 'false'}",
    ]
    if config.reports_backend.strip().lower() == "dropbox":
        if config.dropbox_app_key:
            lines.append(f"dropbox_app_key = {_toml_escape(config.dropbox_app_key)}")
        if config.dropbox_app_secret:
            lines.append(f"dropbox_app_secret = {_toml_escape(config.dropbox_app_secret)}")
        if config.dropbox_refresh_token:
            lines.append(
                f"dropbox_refresh_token = {_toml_escape(config.dropbox_refresh_token)}"
            )
        if config.dropbox_reports_path:
            lines.append(
                f"dropbox_reports_path = {_toml_escape(config.dropbox_reports_path)}"
            )
    CONFIG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _prompt_input(prompt: str, default: str | None = None) -> str:
    if default:
        prompt = f"{prompt} [{default}]: "
    else:
        prompt = f"{prompt}: "
    value = input(prompt).strip()
    return value or (default or "")


def _prompt_path(
    prompt: str,
    default: str,
    must_exist: bool,
    create_if_missing: bool = False,
) -> str:
    while True:
        value = _prompt_input(prompt, default)
        path = pathlib.Path(os.path.expanduser(value))
        if path.exists():
            if must_exist and not path.is_dir():
                print(f"Path is not a directory: {path}")
                continue
            return str(path)
        if create_if_missing:
            try:
                path.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                print(f"Failed to create {path}: {exc}")
                continue
            return str(path)
        if must_exist:
            print(f"Path does not exist: {path}")
            continue
        return str(path)


def run_setup(
    *,
    plugins_path: str | None = None,
    reports_path: str | None = None,
    machine_name: str | None = None,
    reports_backend: str | None = None,
    dropbox_app_key: str | None = None,
    dropbox_app_secret: str | None = None,
    dropbox_refresh_token: str | None = None,
    dropbox_reports_path: str | None = None,
    yes: bool = False,
    non_interactive: bool = False,
) -> Config:
    defaults = default_config(machine_name)
    selected_machine = _sanitize_machine_name(machine_name or defaults.machine_name)
    selected_backend = (reports_backend or defaults.reports_backend).strip().lower()

    if yes:
        if selected_backend not in {"local", "dropbox"}:
            raise ValueError("reports_backend must be 'local' or 'dropbox'")
        plugins_path = plugins_path or defaults.plugins_path
        reports_path = reports_path or defaults.reports_path
        dropbox_reports_path = dropbox_reports_path or defaults.dropbox_reports_path
        if selected_backend == "dropbox" and (
            not dropbox_app_key
            or not dropbox_app_secret
            or not dropbox_refresh_token
            or not dropbox_reports_path
        ):
            raise ValueError(
                "Dropbox setup requires app key, secret, refresh token, and reports path"
            )
    elif non_interactive:
        if selected_backend not in {"local", "dropbox"}:
            raise ValueError("reports_backend must be 'local' or 'dropbox'")
        if not plugins_path:
            raise ValueError(
                "Non-interactive setup requires --plugins-path"
            )
        if selected_backend == "local" and not reports_path:
            raise ValueError(
                "Non-interactive setup requires --reports-path for local backend"
            )
        if selected_backend == "dropbox" and (
            not dropbox_app_key
            or not dropbox_app_secret
            or not dropbox_refresh_token
            or not dropbox_reports_path
        ):
            raise ValueError(
                "Non-interactive dropbox setup requires app key, secret, refresh token, and reports path"
            )
    else:
        selected_machine = _sanitize_machine_name(
            _prompt_input("Machine name", selected_machine)
        )
        selected_backend = (
            _prompt_input("Reports backend (local/dropbox)", selected_backend)
            .strip()
            .lower()
        )
        if selected_backend not in {"local", "dropbox"}:
            raise ValueError("Reports backend must be 'local' or 'dropbox'")
        plugins_path = _prompt_path(
            "Plugins folder",
            plugins_path or defaults.plugins_path,
            must_exist=True,
        )
        if selected_backend == "local":
            reports_path = _prompt_path(
                "Reports folder",
                reports_path or defaults.reports_path,
                must_exist=False,
                create_if_missing=True,
            )
        else:
            dropbox_reports_path = _prompt_input(
                "Dropbox reports path",
                dropbox_reports_path or defaults.dropbox_reports_path or "",
            )
            dropbox_app_key = _prompt_input("Dropbox app key", dropbox_app_key)
            dropbox_app_secret = _prompt_input("Dropbox app secret", dropbox_app_secret)
            if not dropbox_refresh_token:
                from .dropbox_auth import run_dropbox_oauth

                dropbox_refresh_token = run_dropbox_oauth(
                    dropbox_app_key,
                    dropbox_app_secret,
                )

    plugins_path = plugins_path or defaults.plugins_path
    reports_path = reports_path or defaults.reports_path
    dropbox_reports_path = dropbox_reports_path or defaults.dropbox_reports_path

    plugins_path = os.path.expanduser(plugins_path)
    reports_path = os.path.expanduser(reports_path)

    plugins_dir = pathlib.Path(plugins_path)
    if not plugins_dir.exists() or not plugins_dir.is_dir():
        raise ValueError(f"Plugins path does not exist: {plugins_dir}")
    if selected_backend == "local":
        reports_dir = pathlib.Path(reports_path)
        if not reports_dir.exists():
            reports_dir.mkdir(parents=True, exist_ok=True)
        if not reports_dir.is_dir():
            raise ValueError(f"Reports path is not a directory: {reports_dir}")
    else:
        reports_dir = pathlib.Path(reports_path)

    config = Config(
        machine_name=selected_machine,
        plugins_path=str(plugins_dir),
        reports_path=str(reports_dir),
        reports_backend=selected_backend,
        dropbox_app_key=dropbox_app_key,
        dropbox_app_secret=dropbox_app_secret,
        dropbox_refresh_token=dropbox_refresh_token,
        dropbox_reports_path=dropbox_reports_path,
    )
    write_config(config)
    return config


def ensure_config(interactive: bool = True) -> Config:
    config = load_config()
    if config is None:
        if not interactive:
            raise RuntimeError("Config missing. Run pt-plugin-sync setup.")
        print("Configuration not found. Running setup...")
        return run_setup()
    validation = validate_config(config)
    if not validation.ok:
        if not interactive:
            raise RuntimeError("Invalid config: " + "; ".join(validation.errors))
        print("Configuration invalid:")
        for error in validation.errors:
            print(f"- {error}")
        print("Re-running setup...")
        return run_setup()
    return config


def config_paths() -> Iterable[pathlib.Path]:
    return [CONFIG_PATH]
