from __future__ import annotations

import html
import pathlib
from datetime import datetime, timezone


COMPARISON_LATEST_FILENAME = "comparison__latest.html"


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


def _comparison_names(timestamp: str) -> tuple[str, str]:
    return (f"comparison__{timestamp}.html", COMPARISON_LATEST_FILENAME)


def build_comparison_report_payload(reports: dict[str, dict]) -> tuple[str, str, str]:
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    html_payload = generate_comparison_report_html(reports)
    timestamped, latest = _comparison_names(timestamp)
    return html_payload, timestamped, latest


def write_comparison_report(reports_dir: pathlib.Path, reports: dict[str, dict]) -> pathlib.Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    html_payload, timestamped_name, latest_name = build_comparison_report_payload(reports)
    timestamped = reports_dir / timestamped_name
    latest = reports_dir / latest_name
    timestamped.write_text(html_payload, encoding="utf-8")
    latest.write_text(html_payload, encoding="utf-8")
    return latest


def generate_comparison_report_html(reports: dict[str, dict]) -> str:
    machines = sorted(reports.keys())
    generated_at = datetime.now(tz=timezone.utc).astimezone().isoformat()

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

    rows: list[str] = []
    total_plugins = len(all_keys)
    missing_count = 0
    mismatch_count = 0
    unknown_count = 0
    diff_count = 0

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
            missing_count += 1
        if unknown:
            unknown_count += 1
        if mismatch:
            mismatch_count += 1
        if is_diff:
            diff_count += 1

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
    total_machines = len(machines)

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

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Plugin Sync Comparison</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f3f1ea;
      --card: #ffffff;
      --ink: #1e2426;
      --muted: #5b6a70;
      --accent: #2f6b5c;
      --accent-bright: #1c8e7a;
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
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 14px;
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
    .table-section {{
      margin-top: 28px;
      background: var(--card);
      border-radius: 20px;
      padding: 16px 18px;
      border: 1px solid var(--border);
      box-shadow: 0 12px 26px var(--shadow);
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
          <h1>Plugin Sync Comparison</h1>
          <p class="subtitle">Generated {esc(generated_at)} · {total_machines} machines</p>
        </div>
        <div class="summary">
          <div class="summary-card">
            <h3>Total Plugins</h3>
            <p>{total_plugins}</p>
          </div>
          <div class="summary-card">
            <h3>Differences</h3>
            <p>{diff_count}</p>
          </div>
          <div class="summary-card">
            <h3>Missing</h3>
            <p>{missing_count}</p>
          </div>
          <div class="summary-card">
            <h3>Version Mismatches</h3>
            <p>{mismatch_count}</p>
          </div>
          <div class="summary-card">
            <h3>Unknown Versions</h3>
            <p>{unknown_count}</p>
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

    <section class="table-section">
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

    [showAll, filterMissing, filterMismatch, filterUnknown].forEach((control) => {{
      control.addEventListener("change", applyFilters);
    }});

    applyFilters();
  </script>
</body>
</html>
"""
