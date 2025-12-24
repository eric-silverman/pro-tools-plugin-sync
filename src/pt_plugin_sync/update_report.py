from __future__ import annotations

import html
import pathlib
import shutil
import subprocess
from datetime import datetime, timezone
from typing import Iterable

from .config import Config


_REASON_LABELS = {
    "missing": "Missing",
    "outdated": "Outdated",
    "unknown_version": "Unknown version",
}

_REASON_ORDER = {
    "missing": 0,
    "outdated": 1,
    "unknown_version": 2,
}


def _updates_for_machine(summary: dict, machine_name: str) -> list[dict]:
    updates = summary.get("updates_by_machine", {}).get(machine_name, [])
    if not isinstance(updates, list):
        return []
    return [update for update in updates if isinstance(update, dict)]


def _action_text(update: dict) -> str:
    best_machine = update.get("best_machine")
    latest_version = update.get("latest_version")
    reason = update.get("reason")

    target = "latest version"
    if latest_version:
        target = f"version {latest_version}"

    if reason == "missing":
        if best_machine:
            return f"Install from {best_machine} ({target})."
        return f"Install {target}."
    if reason == "outdated":
        if best_machine:
            return f"Update from {best_machine} to {target}."
        return f"Update to {target}."
    if best_machine:
        return f"Verify version against {best_machine}."
    return "Verify version manually."


def _format_version(value: str | None) -> str:
    if not value:
        return "missing"
    return value


def _sort_updates(updates: Iterable[dict]) -> list[dict]:
    def sort_key(update: dict) -> tuple[int, str]:
        reason = update.get("reason", "")
        label = update.get("bundle_name") or update.get("key") or ""
        return (_REASON_ORDER.get(reason, 99), label.lower())

    return sorted(updates, key=sort_key)


def generate_update_report_html(summary: dict, machine_name: str) -> str:
    updates = _sort_updates(_updates_for_machine(summary, machine_name))
    total = len(updates)
    missing = sum(1 for update in updates if update.get("reason") == "missing")
    outdated = sum(1 for update in updates if update.get("reason") == "outdated")
    unknown = sum(1 for update in updates if update.get("reason") == "unknown_version")
    generated_at = summary.get("generated_at") or datetime.now(tz=timezone.utc).isoformat()
    sources = sorted(
        {update.get("best_machine") for update in updates if update.get("best_machine")}
    )
    source_text = ", ".join(sources) if sources else "Unknown"

    def esc(value: object) -> str:
        return html.escape(str(value))

    rows = []
    for update in updates:
        name = update.get("bundle_name") or update.get("key") or "Unknown plugin"
        current_version = _format_version(update.get("current_version"))
        latest_version = _format_version(update.get("latest_version"))
        reason = _REASON_LABELS.get(update.get("reason"), "Update needed")
        source = update.get("best_machine") or "Unknown"
        action = _action_text(update)
        rows.append(
            "<tr>"
            f"<td>{esc(name)}</td>"
            f"<td>{esc(current_version)}</td>"
            f"<td>{esc(latest_version)}</td>"
            f"<td>{esc(reason)}</td>"
            f"<td>{esc(source)}</td>"
            f"<td>{esc(action)}</td>"
            "</tr>"
        )

    rows_html = "\n".join(rows) if rows else "<tr><td colspan='6'>All up to date.</td></tr>"

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Plugin Update Report</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f4ef;
      --card: #ffffff;
      --accent: #2e5d68;
      --muted: #5a6b71;
      --border: #e2dfd6;
      --shadow: rgba(25, 33, 38, 0.08);
    }}
    body {{
      margin: 0;
      font-family: "Avenir Next", "Helvetica Neue", Helvetica, Arial, sans-serif;
      background: radial-gradient(circle at top, #fff6e5, #f6f4ef 55%);
      color: #1d2427;
    }}
    .page {{
      max-width: 1100px;
      margin: 40px auto 60px;
      padding: 0 24px;
    }}
    .header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      gap: 16px;
      padding: 24px 28px;
      background: var(--card);
      border-radius: 20px;
      box-shadow: 0 12px 30px var(--shadow);
      border: 1px solid var(--border);
    }}
    .title {{
      font-size: 28px;
      font-weight: 700;
      margin: 0 0 6px;
    }}
    .subtitle {{
      color: var(--muted);
      margin: 0;
      font-size: 14px;
    }}
    .status {{
      text-align: right;
      font-size: 15px;
      color: var(--accent);
      font-weight: 600;
    }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 16px;
      margin-top: 24px;
    }}
    .summary-card {{
      background: var(--card);
      border-radius: 16px;
      padding: 16px 18px;
      border: 1px solid var(--border);
      box-shadow: 0 6px 16px var(--shadow);
    }}
    .summary-card h3 {{
      margin: 0 0 6px;
      font-size: 13px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--muted);
    }}
    .summary-card p {{
      margin: 0;
      font-size: 22px;
      font-weight: 700;
    }}
    .section {{
      margin-top: 28px;
      background: var(--card);
      border-radius: 20px;
      padding: 20px 24px 10px;
      border: 1px solid var(--border);
      box-shadow: 0 10px 26px var(--shadow);
    }}
    .section h2 {{
      margin: 0 0 12px;
      font-size: 18px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    thead th {{
      text-align: left;
      color: var(--muted);
      font-size: 12px;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      border-bottom: 1px solid var(--border);
      padding: 10px 8px;
    }}
    tbody td {{
      border-bottom: 1px solid var(--border);
      padding: 12px 8px;
      vertical-align: top;
    }}
    tbody tr:last-child td {{
      border-bottom: none;
    }}
    .footer {{
      margin-top: 24px;
      text-align: center;
      color: var(--muted);
      font-size: 12px;
    }}
    @media (max-width: 720px) {{
      .header {{
        flex-direction: column;
        align-items: flex-start;
      }}
      .status {{
        text-align: left;
      }}
      table {{
        font-size: 13px;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <div class="header">
      <div>
        <h1 class="title">Plugin Update Report</h1>
        <p class="subtitle">Machine: {esc(machine_name)} | Generated: {esc(generated_at)}</p>
        <p class="subtitle">Latest versions sourced from: {esc(source_text)}</p>
      </div>
      <div class="status">{total} updates needed</div>
    </div>
    <div class="summary">
      <div class="summary-card">
        <h3>Total Updates</h3>
        <p>{total}</p>
      </div>
      <div class="summary-card">
        <h3>Missing</h3>
        <p>{missing}</p>
      </div>
      <div class="summary-card">
        <h3>Outdated</h3>
        <p>{outdated}</p>
      </div>
      <div class="summary-card">
        <h3>Unknown Version</h3>
        <p>{unknown}</p>
      </div>
    </div>
    <div class="section">
      <h2>Recommended Actions</h2>
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
        <tbody>
          {rows_html}
        </tbody>
      </table>
    </div>
    <div class="footer">pt-plugin-sync</div>
  </div>
</body>
</html>
"""


def write_update_report(
    reports_dir: pathlib.Path,
    summary: dict,
    machine_name: str,
) -> pathlib.Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    safe_machine = machine_name.replace("/", "-")
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    timestamped = reports_dir / f"updates__{safe_machine}__{timestamp}.html"
    latest = reports_dir / f"updates__{safe_machine}__latest.html"
    html_payload = generate_update_report_html(summary, machine_name)
    timestamped.write_text(html_payload, encoding="utf-8")
    latest.write_text(html_payload, encoding="utf-8")
    return latest


def _open_report(path: pathlib.Path) -> None:
    if shutil.which("open") is None:
        return
    subprocess.run(["open", str(path)], capture_output=True, text=True)


def open_update_report_if_needed(config: Config, summary: dict) -> pathlib.Path | None:
    updates = _updates_for_machine(summary, config.machine_name)
    if not updates:
        return None
    report_path = write_update_report(config.expanded_reports_path(), summary, config.machine_name)
    _open_report(report_path)
    return report_path
