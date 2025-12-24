from __future__ import annotations

import argparse
import sys

from .config import ensure_config, load_config, run_setup, write_config
from .daemon import run_daemon
from .diffing import compute_diff, compute_update_summary, format_diff_summary
from .dropbox_auth import run_dropbox_oauth
from .launchd import (
    install_launchagent,
    install_menubar_launchagent,
    uninstall_launchagent,
    uninstall_menubar_launchagent,
)
from .menubar import run_menubar
from .report_store import report_store_from_config
from .scan_cycle import perform_scan


def _cmd_setup(args: argparse.Namespace) -> int:
    try:
        run_setup(
            plugins_path=args.plugins_path,
            reports_path=args.reports_path,
            machine_name=args.machine_name,
            reports_backend=args.reports_backend,
            dropbox_app_key=args.dropbox_app_key,
            dropbox_app_secret=args.dropbox_app_secret,
            dropbox_refresh_token=args.dropbox_refresh_token,
            dropbox_reports_path=args.dropbox_reports_path,
            yes=args.yes,
            non_interactive=args.non_interactive,
        )
    except ValueError as exc:
        print(f"Setup failed: {exc}")
        return 1
    print("Setup complete.")
    return 0


def _cmd_scan(_: argparse.Namespace) -> int:
    config = ensure_config(interactive=True)
    result = perform_scan(config, open_report=True)
    if result.diff:
        print(format_diff_summary(result.diff))
    return 0


def _cmd_diff(_: argparse.Namespace) -> int:
    config = ensure_config(interactive=True)
    store = report_store_from_config(config)
    reports = store.load_latest_reports()
    if not reports:
        print("No reports found in reports folder.")
        return 1
    diff = compute_diff(reports)
    store.write_diff(diff)
    summary = compute_update_summary(reports)
    store.write_summary(summary)
    print(format_diff_summary(diff))
    return 0


def _cmd_daemon(_: argparse.Namespace) -> int:
    config = ensure_config(interactive=True)
    run_daemon(config)
    return 0


def _cmd_menubar(_: argparse.Namespace) -> int:
    run_menubar()
    return 0


def _cmd_install(_: argparse.Namespace) -> int:
    config = ensure_config(interactive=True)
    install_launchagent(config)
    return 0


def _cmd_uninstall(_: argparse.Namespace) -> int:
    uninstall_launchagent()
    return 0


def _cmd_install_menubar(_: argparse.Namespace) -> int:
    config = ensure_config(interactive=True)
    install_menubar_launchagent(config)
    return 0


def _cmd_uninstall_menubar(_: argparse.Namespace) -> int:
    uninstall_menubar_launchagent()
    return 0


def _cmd_dropbox_auth(_: argparse.Namespace) -> int:
    config = load_config()
    if config is None:
        print("Config missing. Run pt-plugin-sync setup first.")
        return 1
    app_key = config.dropbox_app_key or input("Dropbox app key: ").strip()
    app_secret = config.dropbox_app_secret or input("Dropbox app secret: ").strip()
    if not app_key or not app_secret:
        print("Dropbox app key and secret are required.")
        return 1
    refresh_token = run_dropbox_oauth(app_key, app_secret)
    config.dropbox_app_key = app_key
    config.dropbox_app_secret = app_secret
    config.dropbox_refresh_token = refresh_token
    if not config.dropbox_reports_path:
        config.dropbox_reports_path = "/Pro Tools Plugin Reports"
    config.reports_backend = "dropbox"
    write_config(config)
    print("Dropbox OAuth complete.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pt-plugin-sync")
    subparsers = parser.add_subparsers(dest="command", required=True)

    setup_parser = subparsers.add_parser("setup", help="Configure plugin sync settings")
    setup_parser.add_argument("--plugins-path", help="Path to the AAX plug-ins folder")
    setup_parser.add_argument("--reports-path", help="Path to the shared reports folder")
    setup_parser.add_argument("--machine-name", help="Override the machine name")
    setup_parser.add_argument(
        "--reports-backend",
        choices=["local", "dropbox"],
        help="Store reports locally or via Dropbox API",
    )
    setup_parser.add_argument("--dropbox-app-key", help="Dropbox app key")
    setup_parser.add_argument("--dropbox-app-secret", help="Dropbox app secret")
    setup_parser.add_argument("--dropbox-refresh-token", help="Dropbox refresh token")
    setup_parser.add_argument("--dropbox-reports-path", help="Dropbox reports folder path")
    setup_parser.add_argument("--yes", action="store_true", help="Accept defaults without prompting")
    setup_parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Fail if required values are missing",
    )
    setup_parser.set_defaults(func=_cmd_setup)

    scan_parser = subparsers.add_parser("scan", help="Scan plugins and write reports")
    scan_parser.set_defaults(func=_cmd_scan)

    diff_parser = subparsers.add_parser("diff", help="Generate a diff from latest reports")
    diff_parser.set_defaults(func=_cmd_diff)

    daemon_parser = subparsers.add_parser("daemon", help="Run the background daemon")
    daemon_parser.set_defaults(func=_cmd_daemon)

    menubar_parser = subparsers.add_parser("menubar", help="Run the menu bar app")
    menubar_parser.set_defaults(func=_cmd_menubar)

    install_parser = subparsers.add_parser(
        "install-launchagent", help="Install and load the LaunchAgent"
    )
    install_parser.set_defaults(func=_cmd_install)

    uninstall_parser = subparsers.add_parser(
        "uninstall-launchagent", help="Unload and remove the LaunchAgent"
    )
    uninstall_parser.set_defaults(func=_cmd_uninstall)

    install_menubar_parser = subparsers.add_parser(
        "install-menubar", help="Install and load the menu bar LaunchAgent"
    )
    install_menubar_parser.set_defaults(func=_cmd_install_menubar)

    uninstall_menubar_parser = subparsers.add_parser(
        "uninstall-menubar", help="Unload and remove the menu bar LaunchAgent"
    )
    uninstall_menubar_parser.set_defaults(func=_cmd_uninstall_menubar)

    dropbox_auth_parser = subparsers.add_parser(
        "dropbox-auth", help="Authorize Dropbox and store a refresh token"
    )
    dropbox_auth_parser.set_defaults(func=_cmd_dropbox_auth)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    exit_code = args.func(args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
