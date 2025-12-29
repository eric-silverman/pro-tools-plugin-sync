from __future__ import annotations

import html
import json
import pathlib
import shutil
import subprocess
from datetime import datetime, timezone

from .update_report import _action_text, _format_version, _sort_updates


COMBINED_HTML_LATEST_FILENAME = "report__latest.html"
COMBINED_JSON_LATEST_FILENAME = "report__latest.json"


def _version_label(plugin: dict) -> str:
    short_version = plugin.get("short_version") or "unknown"
    bundle_version = plugin.get("bundle_version") or "unknown"
    if short_version == "unknown" and bundle_version == "unknown":
        return "unknown"
    if short_version == "unknown":
        return bundle_version
    if bundle_version == "unknown" or short_version == bundle_version:
        return short_version
    return f"{short_version} ({bundle_version})"


def _plugin_key(plugin: dict) -> str | None:
    return plugin.get("bundle_id") or plugin.get("bundle_name")


def _combined_names(timestamp: str) -> tuple[str, str, str, str]:
    return (
        f"report__{timestamp}.html",
        COMBINED_HTML_LATEST_FILENAME,
        f"report__{timestamp}.json",
        COMBINED_JSON_LATEST_FILENAME,
    )


def build_combined_report_payload(
    reports: dict[str, dict],
    summary: dict,
    diff: dict,
) -> tuple[str, str, str, str]:
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    html_payload = generate_combined_report_html(reports, summary, diff)
    json_payload = json.dumps(
        {
            "generated_at": datetime.now(tz=timezone.utc).astimezone().isoformat(),
            "reports": reports,
            "summary": summary,
            "diff": diff,
        },
        indent=2,
        sort_keys=True,
    )
    timestamped_html, latest_html, timestamped_json, latest_json = _combined_names(timestamp)
    return html_payload, json_payload, latest_html, latest_json


def write_combined_report(
    reports_dir: pathlib.Path,
    reports: dict[str, dict],
    summary: dict,
    diff: dict,
) -> pathlib.Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    html_payload, json_payload, latest_html, latest_json = build_combined_report_payload(
        reports,
        summary,
        diff,
    )
    latest_html_path = reports_dir / latest_html
    latest_json_path = reports_dir / latest_json
    latest_html_path.write_text(html_payload, encoding="utf-8")
    latest_json_path.write_text(json_payload + "\n", encoding="utf-8")
    return latest_html_path


def open_report(path: pathlib.Path) -> None:
    if shutil.which("open") is None:
        return
    subprocess.run(["open", str(path)], capture_output=True, text=True)


def generate_combined_report_html(reports: dict[str, dict], summary: dict, diff: dict) -> str:
    machines = sorted(reports.keys())
    generated_at = diff.get("generated_at") or datetime.now(tz=timezone.utc).isoformat()

    def esc(value: object) -> str:
        return html.escape(str(value))

    plugin_maps: dict[str, dict[str, dict]] = {}
    all_keys: set[str] = set()
    for machine, report in reports.items():
        mapping = {}
        for plugin in report.get("plugins", []):
            key = _plugin_key(plugin)
            if not key:
                continue
            mapping[key] = plugin
        plugin_maps[machine] = mapping
        all_keys.update(mapping.keys())

    missing_keys: set[str] = set()
    unknown_keys: set[str] = set()
    mismatch_keys: set[str] = set()

    rows: list[str] = []
    sorted_keys = sorted(
        all_keys,
        key=lambda key: (plugin_maps.get(machines[0], {}).get(key, {}).get("bundle_name") or key).lower()
        if machines
        else key.lower(),
    )

    for key in sorted_keys:
        sample_plugin = next(
            (mapping.get(key) for mapping in plugin_maps.values() if key in mapping),
            None,
        )
        name = (
            sample_plugin.get("bundle_name")
            if sample_plugin
            else key
        ) or key
        versions: dict[str, str | None] = {}
        for machine in machines:
            plugin = plugin_maps.get(machine, {}).get(key)
            if not plugin:
                versions[machine] = None
                continue
            versions[machine] = _version_label(plugin)

        missing = any(version is None for version in versions.values())
        unknown = any(version == "unknown" for version in versions.values() if version is not None)
        known_versions = {
            version for version in versions.values() if version not in (None, "unknown")
        }
        mismatch = len(known_versions) > 1
        is_diff = missing or unknown or mismatch

        if missing:
            missing_keys.add(key)
        if unknown:
            unknown_keys.add(key)
        if mismatch:
            mismatch_keys.add(key)

        status_tags = []
        if missing:
            status_tags.append('<span class="tag tag-missing">Missing</span>')
        if mismatch:
            status_tags.append('<span class="tag tag-mismatch">Version mismatch</span>')
        if unknown:
            status_tags.append('<span class="tag tag-unknown">Unknown version</span>')
        status_html = "".join(status_tags) if status_tags else '<span class="tag">In sync</span>'

        cells = []
        for machine in machines:
            value = versions.get(machine)
            if value is None:
                cells.append('<td><span class="cell cell-missing">Missing</span></td>')
            elif value == "unknown":
                cells.append('<td><span class="cell cell-unknown">Unknown</span></td>')
            else:
                cells.append(f"<td><span class=\"cell cell-version\">{esc(value)}</span></td>")

        rows.append(
            "<tr "
            f"data-diff={'true' if is_diff else 'false'} "
            f"data-missing={'true' if missing else 'false'} "
            f"data-mismatch={'true' if mismatch else 'false'} "
            f"data-unknown={'true' if unknown else 'false'}>"
            f"<td class=\"plugin\">{esc(name)}</td>"
            f"<td class=\"status\">{status_html}</td>"
            f"{''.join(cells)}"
            "</tr>"
        )

    column_count = 2 + len(machines)
    rows_html = (
        "\n".join(rows)
        if rows
        else f"<tr><td colspan='{column_count}'>No reports found.</td></tr>"
    )

    machine_cards = []
    for machine in machines:
        scan_time = reports.get(machine, {}).get("scan_time", "Unknown")
        machine_cards.append(
            f"<div class=\"machine-card\">"
            f"<h4>{esc(machine)}</h4>"
            f"<p>Last scan: {esc(scan_time)}</p>"
            "</div>"
        )
    machine_cards_html = "\n".join(machine_cards) if machine_cards else "<p>No machines yet.</p>"

    updates_by_machine = summary.get("updates_by_machine", {})
    update_totals = {
        machine: len([u for u in updates if isinstance(u, dict)])
        for machine, updates in updates_by_machine.items()
        if isinstance(updates, list)
    }
    default_machine = machines[0] if machines else ""

    update_rows = {}
    for machine in machines:
        updates = _sort_updates(
            [u for u in updates_by_machine.get(machine, []) if isinstance(u, dict)]
        )
        rows = []
        for update in updates:
            name = update.get("bundle_name") or update.get("key") or "Unknown plugin"
            current_version = _format_version(update.get("current_version"))
            latest_version = _format_version(update.get("latest_version"))
            reason = update.get("reason") or "update"
            source = update.get("best_machine") or "Unknown"
            action = _action_text(update)
            rows.append(
                "<tr>"
                f"<td>{esc(name)}</td>"
                f"<td>{esc(current_version)}</td>"
                f"<td>{esc(latest_version)}</td>"
                f"<td>{esc(reason.replace('_', ' ').title())}</td>"
                f"<td>{esc(source)}</td>"
                f"<td>{esc(action)}</td>"
                "</tr>"
            )
        update_rows[machine] = "\n".join(rows) if rows else "<tr><td colspan='6'>All up to date.</td></tr>"

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Plugin Sync Report</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f3f1ea;
      --card: #ffffff;
      --ink: #1e2426;
      --muted: #5b6a70;
      --accent: #2f6b5c;
      --border: #e1ddd4;
      --shadow: rgba(25, 33, 38, 0.08);
      --missing: #d86c57;
      --mismatch: #d7a12f;
      --unknown: #5b73b5;
    }}
    * {{
      box-sizing: border-box;
    }}
    body {{
      margin: 0;
      font-family: "Space Grotesk", "Avenir Next", "Helvetica Neue", Helvetica, Arial, sans-serif;
      background:
        radial-gradient(circle at top left, #fff1d2 0%, transparent 45%),
        radial-gradient(circle at 20% 30%, rgba(47, 107, 92, 0.12) 0%, transparent 55%),
        linear-gradient(160deg, #f3f1ea 0%, #f7f4ee 45%, #ede9df 100%);
      color: var(--ink);
    }}
    .page {{
      max-width: 1200px;
      margin: 36px auto 64px;
      padding: 0 24px;
    }}
    .header {{
      padding: 28px 32px;
      border-radius: 22px;
      background: var(--card);
      border: 1px solid var(--border);
      box-shadow: 0 18px 40px var(--shadow);
      display: grid;
      gap: 18px;
      animation: rise 0.6s ease-out;
    }}
    .headline {{
      display: flex;
      justify-content: space-between;
      gap: 24px;
      align-items: flex-start;
      flex-wrap: wrap;
    }}
    h1 {{
      font-size: 30px;
      margin: 0 0 6px;
    }}
    .subtitle {{
      margin: 0;
      color: var(--muted);
      font-size: 14px;
    }}
    .summary {{
      display: flex;
      flex-wrap: wrap;
      gap: 14px;
      justify-content: flex-end;
      align-items: stretch;
    }}
    .summary-card {{
      flex: 1 1 160px;
    }}
    .summary-card {{
      padding: 14px 16px;
      border-radius: 16px;
      border: 1px solid var(--border);
      background: #fbfaf6;
      box-shadow: 0 10px 18px var(--shadow);
    }}
    .summary-card h3 {{
      margin: 0 0 6px;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
    }}
    .summary-card p {{
      margin: 0;
      font-size: 22px;
      font-weight: 700;
    }}
    .machine-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
    }}
    .machine-card {{
      padding: 12px 14px;
      border-radius: 14px;
      background: #f7f5ef;
      border: 1px dashed var(--border);
    }}
    .machine-card h4 {{
      margin: 0 0 6px;
      font-size: 14px;
    }}
    .machine-card p {{
      margin: 0;
      font-size: 12px;
      color: var(--muted);
    }}
    .filters {{
      margin-top: 18px;
      display: flex;
      flex-wrap: wrap;
      gap: 14px;
      align-items: center;
    }}
    .toggle {{
      display: flex;
      gap: 8px;
      align-items: center;
      padding: 10px 12px;
      border-radius: 999px;
      background: #f2f6f2;
      border: 1px solid var(--border);
      font-size: 13px;
      font-weight: 600;
    }}
    .filter-group {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }}
    .section {{
      margin-top: 28px;
      background: var(--card);
      border-radius: 20px;
      padding: 16px 18px;
      border: 1px solid var(--border);
      box-shadow: 0 12px 26px var(--shadow);
    }}
    .section-title {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin: 0 0 12px;
    }}
    .section-title h2 {{
      margin: 0;
      font-size: 18px;
    }}
    .table-wrap {{
      overflow-x: auto;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    thead th {{
      text-align: left;
      padding: 12px 10px;
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--muted);
      border-bottom: 1px solid var(--border);
      position: sticky;
      top: 0;
      background: var(--card);
    }}
    tbody td {{
      padding: 12px 10px;
      border-bottom: 1px solid var(--border);
      vertical-align: top;
    }}
    tbody tr:last-child td {{
      border-bottom: none;
    }}
    .plugin {{
      font-weight: 600;
    }}
    .status {{
      min-width: 180px;
    }}
    .tag {{
      display: inline-flex;
      align-items: center;
      padding: 4px 8px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      background: #edf3ef;
      color: var(--accent);
      margin: 0 6px 6px 0;
    }}
    .tag-missing {{
      background: rgba(216, 108, 87, 0.14);
      color: var(--missing);
    }}
    .tag-mismatch {{
      background: rgba(215, 161, 47, 0.16);
      color: #9a6b05;
    }}
    .tag-unknown {{
      background: rgba(91, 115, 181, 0.16);
      color: var(--unknown);
    }}
    .cell {{
      display: inline-flex;
      align-items: center;
      padding: 6px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 600;
      background: #f1f3f4;
      color: #2b3235;
    }}
    .cell-missing {{
      background: rgba(216, 108, 87, 0.16);
      color: var(--missing);
    }}
    .cell-unknown {{
      background: rgba(91, 115, 181, 0.16);
      color: var(--unknown);
    }}
    .machine-select {{
      display: flex;
      gap: 10px;
      align-items: center;
      font-size: 13px;
      color: var(--muted);
    }}
    select {{
      border-radius: 10px;
      border: 1px solid var(--border);
      padding: 6px 10px;
      background: #fff;
    }}
    .footer {{
      margin-top: 24px;
      text-align: center;
      color: var(--muted);
      font-size: 12px;
    }}
    @keyframes rise {{
      from {{
        opacity: 0;
        transform: translateY(18px);
      }}
      to {{
        opacity: 1;
        transform: translateY(0);
      }}
    }}
    @media (max-width: 720px) {{
      .headline {{
        flex-direction: column;
      }}
      .summary {{
        justify-content: flex-start;
      }}
      .status {{
        min-width: auto;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <section class="header">
      <div class="headline">
        <div>
          <h1>Plugin Sync Report</h1>
          <p class="subtitle">Generated {esc(generated_at)} · {len(machines)} machines</p>
        </div>
        <div class="summary">
          <div class="summary-card">
            <h3>Total Plugins</h3>
            <p>{len(all_keys)}</p>
          </div>
          <div class="summary-card">
            <h3>Differences</h3>
            <p>{len(missing_keys | unknown_keys | mismatch_keys)}</p>
          </div>
          <div class="summary-card">
            <h3>Missing</h3>
            <p>{len(missing_keys)}</p>
          </div>
          <div class="summary-card">
            <h3>Version Mismatches</h3>
            <p>{len(mismatch_keys)}</p>
          </div>
          <div class="summary-card">
            <h3>Unknown Versions</h3>
            <p>{len(unknown_keys)}</p>
          </div>
        </div>
      </div>
      <div>
        <h3>Machine snapshots</h3>
        <div class="machine-grid">
          {machine_cards_html}
        </div>
      </div>
      <div class="filters">
        <label class="toggle">
          <input type="checkbox" id="show-all">
          Show all plugins
        </label>
        <div class="filter-group">
          <label class="toggle">
            <input type="checkbox" id="filter-missing" checked>
            Missing
          </label>
          <label class="toggle">
            <input type="checkbox" id="filter-mismatch" checked>
            Version mismatch
          </label>
          <label class="toggle">
            <input type="checkbox" id="filter-unknown" checked>
            Unknown version
          </label>
        </div>
      </div>
    </section>

    <section class="section">
      <div class="section-title">
        <h2>Update Plan</h2>
        <div class="machine-select">
          <span>Machine</span>
          <select id="machine-select">
            {''.join(f"<option value='{esc(machine)}' {'selected' if machine == default_machine else ''}>{esc(machine)} ({update_totals.get(machine, 0)})</option>" for machine in machines)}
          </select>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Plugin</th>
              <th>Current</th>
              <th>Latest</th>
              <th>Reason</th>
              <th>Source</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody id="updates-table">
            {update_rows.get(default_machine, "<tr><td colspan='6'>All up to date.</td></tr>")}
          </tbody>
        </table>
      </div>
    </section>

    <section class="section">
      <div class="section-title">
        <h2>Version Comparison</h2>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Plugin</th>
              <th>Status</th>
              {''.join(f"<th>{esc(machine)}</th>" for machine in machines)}
            </tr>
          </thead>
          <tbody id="plugin-table">
            {rows_html}
          </tbody>
        </table>
      </div>
    </section>

    <div class="footer">pt-plugin-sync</div>
  </div>
  <script>
    const showAll = document.getElementById("show-all");
    const filterMissing = document.getElementById("filter-missing");
    const filterMismatch = document.getElementById("filter-mismatch");
    const filterUnknown = document.getElementById("filter-unknown");
    const rows = Array.from(document.querySelectorAll("#plugin-table tr"));
    const updatesByMachine = {json.dumps(update_rows)};
    const machineSelect = document.getElementById("machine-select");
    const updatesTable = document.getElementById("updates-table");

    function applyFilters() {{
      const showAllChecked = showAll.checked;
      const missingOn = filterMissing.checked;
      const mismatchOn = filterMismatch.checked;
      const unknownOn = filterUnknown.checked;

      rows.forEach((row) => {{
        const isDiff = row.dataset.diff === "true";
        const hasMissing = row.dataset.missing === "true";
        const hasMismatch = row.dataset.mismatch === "true";
        const hasUnknown = row.dataset.unknown === "true";

        let visible = showAllChecked || isDiff;
        if (visible) {{
          if (hasMissing && !missingOn) {{
            visible = false;
          }}
          if (hasMismatch && !mismatchOn) {{
            visible = false;
          }}
          if (hasUnknown && !unknownOn) {{
            visible = false;
          }}
          if (!showAllChecked && !hasMissing && !hasMismatch && !hasUnknown) {{
            visible = false;
          }}
        }}
        row.hidden = !visible;
      }});
    }}

    function updateMachineTable() {{
      const key = machineSelect.value;
      updatesTable.innerHTML = updatesByMachine[key] || "<tr><td colspan='6'>All up to date.</td></tr>";
    }}

    [showAll, filterMissing, filterMismatch, filterUnknown].forEach((control) => {{
      control.addEventListener("change", applyFilters);
    }});
    machineSelect.addEventListener("change", updateMachineTable);

    applyFilters();
    updateMachineTable();
  </script>
</body>
</html>
"""
