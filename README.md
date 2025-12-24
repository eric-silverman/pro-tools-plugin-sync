# pt-plugin-sync

Sync and compare Pro Tools AAX plugin versions across machines by writing reports to a shared folder or using the Dropbox API.

## Requirements
- Python 3.11+
- Access to the Pro Tools plug-ins folder

## Install
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```
Or use the setup helper:
```bash
./scripts/setup.sh
```

## Setup (first run)
Run interactive setup:
```bash
pt-plugin-sync setup
```

Defaults:
- Plugins: `~/Library/Application Support/Avid/Audio/Plug-Ins`
- Reports: `~/Dropbox/Pro Tools Plugin Reports`

Non-interactive:
```bash
pt-plugin-sync setup --yes
pt-plugin-sync setup --plugins-path "/path/to/Plug-Ins" --reports-path "/path/to/Reports" --machine-name "STUDIO-MAC" --non-interactive
```

Dropbox API setup (headless refresh):
1) Create an app in the [Dropbox Developer Console](https://www.dropbox.com/developers/apps)
2) Click "Create app", choose "Scoped access", then choose either "App folder" or "Full Dropbox".
3) In the app's settings, enable "Short-lived access tokens" and save.
4) In the app's permissions, grant scopes: `files.content.read`, `files.content.write`, `files.metadata.read`, `files.metadata.write`.
5) Copy the App key (and App secret if prompted) from the app settings in the [Dropbox Developer Console](https://www.dropbox.com/developers/apps)
6) Run setup and complete the one-time OAuth flow:
```bash
pt-plugin-sync setup --reports-backend dropbox
```

Re-auth (if you need a new refresh token):
```bash
pt-plugin-sync dropbox-auth
```

Config is stored at `~/.config/pt-plugin-sync/config.toml`.

Optional config keys:
- `hash_binaries` (default `false`) to hash plugin binaries for stricter comparisons.
- `prune_days` (default `0`) to delete timestamped reports older than N days.
- `reports_backend` (`local` or `dropbox`) to control where reports live.

## Run once
```bash
pt-plugin-sync scan
```
This writes a timestamped report and `<machine_name>__latest.json`, generates `diff__latest.json`,
and creates `summary__latest.json` plus an `updates__<machine>__latest.html` report for any machine
that needs updates. The HTML report opens automatically on the machine that just scanned.

## Run as a daemon
```bash
pt-plugin-sync daemon
```
The daemon watches for changes and performs hourly scans. It debounces rapid changes.

## Menu bar app (macOS)
```bash
pt-plugin-sync menubar
```
The menu bar app watches the plug-ins folder, runs periodic scans, and updates its icon
when a scan is in progress or updates are needed. Use the “Start at Login” menu item
to auto-launch on sign-in.
Use “Check for Updates…” in the menu to download the latest release.

## Install LaunchAgent
```bash
pt-plugin-sync install-launchagent
```
Logs are written to `~/Library/Logs/pt-plugin-sync/`.

Menu bar auto-start:
```bash
pt-plugin-sync install-menubar
```
Uninstall:
```bash
pt-plugin-sync uninstall-menubar
```

Verify:
```bash
launchctl list | rg pt-plugin-sync
```

Uninstall:
```bash
pt-plugin-sync uninstall-launchagent
```

## Troubleshooting
- If watching is unavailable, the daemon falls back to periodic scans.
- Ensure the reports folder is shared between machines (Dropbox or similar).
- If the plug-ins folder is unreadable, the scan skips files and continues.
- If you want to preview the update report layout, open `docs/example_update_report.html`.

## Development
Run tests with:
```bash
./scripts/test.sh
```

Fixture plugin binaries are executable. If permissions are lost (for example, after copying or zipping),
restore them with:
```bash
chmod +x tests/fixtures/plugins/*/Contents/MacOS/*
```
