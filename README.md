# pt-plugin-sync

Sync and compare Pro Tools AAX plugin versions across machines by writing reports to a shared folder or using the Dropbox API.

## Requirements
- Python 3.11+
- Access to the Pro Tools plug-ins folder

## Installation (macOS app via DMG)
1) Download the latest DMG release.
2) Open the DMG and drag `Pro Tools Plugin Sync.app` into `Applications`.
3) Launch the app from `Applications`.
4) If macOS says the app is damaged or blocked:
   - Control-click the app in `Applications`, choose “Open”, then confirm.
   - Or run `Fix Gatekeeper.command` from the DMG after copying the app to `Applications`.
5) When the menu bar icon appears, open `Settings...` to complete setup.
Optional CLI install (from the DMG):
1) Double-click `Install CLI.command`.
2) Activate the CLI: `source ~/.pt-plugin-sync-cli/bin/activate`
3) Confirm it works: `pt-plugin-sync --help`

## Installation (from source / CLI)
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```
Or use the setup helper:
```bash
./scripts/setup.sh
```
After install, confirm the CLI is available:
```bash
pt-plugin-sync --help
```
If the command is not found, ensure your virtualenv is active or run
`python -m pt_plugin_sync.cli --help` from the project directory.

## Setup (first run)
Decide on a shared reports folder before you begin:
- Local/shared: a folder synced by Dropbox/iCloud/SMB between machines.
- Dropbox API: a Dropbox app with API access (for headless or server-friendly access).

You can configure via the menu bar app or the CLI. Both write `~/.config/pt-plugin-sync/config.toml`.

### Menu bar app setup (DMG)
1) Click the menu bar icon and choose `Settings...`.
2) Confirm or change the plug-ins folder (default: `/Library/Application Support/Avid/Audio/Plug-Ins`).
3) Choose the reports folder (default: `~/Dropbox/Pro Tools Plugin Reports`).
4) Confirm the machine name (used in report filenames).
5) If using Dropbox API access, enter the app key/secret and click `Authorize Dropbox...`.
6) Click Save, then choose `Scan Now` to verify the first report.

### CLI setup
Run interactive setup:
```bash
pt-plugin-sync setup
```
You will be prompted for:
- Plug-ins folder (press Enter for the default).
- Reports folder (must be shared with other machines).
- Machine name (used in report filenames).
- Reports backend (local filesystem or Dropbox API).

Defaults:
- Plugins: `/Library/Application Support/Avid/Audio/Plug-Ins`
- Reports: `~/Dropbox/Pro Tools Plugin Reports`

Non-interactive:
```bash
pt-plugin-sync setup --yes
pt-plugin-sync setup --plugins-path "/path/to/Plug-Ins" --reports-path "/path/to/Reports" --machine-name "STUDIO-MAC" --non-interactive
```

### Dropbox API setup (headless refresh)
1) Create an app in the [Dropbox Developer Console](https://www.dropbox.com/developers/apps)
2) Click "Create app", choose "Scoped access", then choose either "App folder" or "Full Dropbox".
3) In the app's settings, enable "Short-lived access tokens" and save.
4) In the app's permissions, grant scopes: `files.content.read`, `files.content.write`, `files.metadata.read`, `files.metadata.write`.
5) Copy the App key (and App secret if prompted) from the app settings in the [Dropbox Developer Console](https://www.dropbox.com/developers/apps)
6) Run setup and complete the one-time OAuth flow:
```bash
pt-plugin-sync setup --reports-backend dropbox
```
If you are using the menu bar app, open `Settings...`, enter the app key/secret, then click
`Authorize Dropbox...` to generate the refresh token without the CLI.

Re-auth (if you need a new refresh token):
```bash
pt-plugin-sync dropbox-auth
```

Config is stored at `~/.config/pt-plugin-sync/config.toml`.

Optional config keys:
- `hash_binaries` (default `false`) to hash plugin binaries for stricter comparisons.
- `prune_days` (default `0`) to delete timestamped reports older than N days.
- `reports_backend` (`local` or `dropbox`) to control where reports live.

### Verify setup across machines
1) On the first machine, run `Scan Now` (menu bar) or `pt-plugin-sync scan`.
2) Open the reports folder and confirm you see `<machine_name>__latest.json`.
3) Repeat setup on the second machine, pointing at the same reports folder.
4) Run another scan and confirm `diff__latest.json` and `summary__latest.json` are updated.
5) If updates are needed, open the generated `updates__<machine>__latest.html` report.

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
