from __future__ import annotations

import json
import pathlib
import re
from datetime import datetime, timezone

from .report_naming import DIFF_FILENAME, SUMMARY_FILENAME

def load_latest_reports(reports_dir: pathlib.Path) -> dict[str, dict]:
    reports: dict[str, dict] = {}
    for path in reports_dir.glob("*__latest.json"):
        if path.name.startswith("diff__"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        machine = data.get("machine_name")
        if not machine:
            continue
        reports[machine] = data
    return reports


def _plugin_map(report: dict) -> dict[str, dict]:
    plugins = report.get("plugins", [])
    mapping: dict[str, dict] = {}
    for plugin in plugins:
        key = plugin.get("bundle_id") or plugin.get("bundle_name")
        if not key:
            continue
        mapping[key] = plugin
    return mapping


def compute_diff(reports: dict[str, dict]) -> dict:
    machines = sorted(reports.keys())
    plugin_maps = {machine: _plugin_map(report) for machine, report in reports.items()}
    all_keys: set[str] = set()
    for mapping in plugin_maps.values():
        all_keys.update(mapping.keys())

    missing: dict[str, list[dict]] = {machine: [] for machine in machines}
    unknown_versions: dict[str, list[dict]] = {machine: [] for machine in machines}
    counts: dict[str, dict] = {}

    for machine, mapping in plugin_maps.items():
        unknown_count = 0
        for key in all_keys:
            if key not in mapping:
                sample_plugin = next(
                    (m.get(key) for m in plugin_maps.values() if key in m),
                    None,
                )
                missing[machine].append(
                    {
                        "key": key,
                        "bundle_name": sample_plugin.get("bundle_name") if sample_plugin else None,
                        "bundle_id": sample_plugin.get("bundle_id") if sample_plugin else None,
                    }
                )
                continue
            plugin = mapping[key]
            short_version = plugin.get("short_version") or "unknown"
            bundle_version = plugin.get("bundle_version") or "unknown"
            if short_version == "unknown" and bundle_version == "unknown":
                unknown_count += 1
                unknown_versions[machine].append(
                    {
                        "key": key,
                        "bundle_name": plugin.get("bundle_name"),
                        "bundle_id": plugin.get("bundle_id"),
                    }
                )
        counts[machine] = {
            "total": len(mapping),
            "unknown_versions": unknown_count,
        }

    version_mismatches: list[dict] = []
    for key in sorted(all_keys):
        versions_by_machine: dict[str, dict] = {}
        for machine, mapping in plugin_maps.items():
            plugin = mapping.get(key)
            if not plugin:
                continue
            versions_by_machine[machine] = {
                "short_version": plugin.get("short_version") or "unknown",
                "bundle_version": plugin.get("bundle_version") or "unknown",
            }
        if len(versions_by_machine) <= 1:
            continue
        unique_versions = {
            (data["short_version"], data["bundle_version"]) for data in versions_by_machine.values()
        }
        if len(unique_versions) > 1:
            sample_plugin = next(
                (mapping.get(key) for mapping in plugin_maps.values() if key in mapping),
                None,
            )
            version_mismatches.append(
                {
                    "key": key,
                    "bundle_name": sample_plugin.get("bundle_name") if sample_plugin else None,
                    "bundle_id": sample_plugin.get("bundle_id") if sample_plugin else None,
                    "versions": versions_by_machine,
                }
            )

    diff = {
        "generated_at": datetime.now(tz=timezone.utc).astimezone().isoformat(),
        "machines": machines,
        "missing": missing,
        "version_mismatches": version_mismatches,
        "unknown_versions": unknown_versions,
        "counts": counts,
    }
    return diff


def format_diff_summary(diff: dict) -> str:
    lines: list[str] = []
    machines = diff.get("machines", [])
    if not machines:
        return "No reports found."

    lines.append("Plugin sync diff summary:")
    for machine in machines:
        count = diff.get("counts", {}).get(machine, {})
        lines.append(
            f"- {machine}: {count.get('total', 0)} plugins, "
            f"{count.get('unknown_versions', 0)} unknown versions"
        )

    missing = diff.get("missing", {})
    for machine in machines:
        missing_list = missing.get(machine, [])
        if missing_list:
            lines.append(f"- Missing on {machine}: {len(missing_list)}")

    mismatches = diff.get("version_mismatches", [])
    if mismatches:
        lines.append(f"- Version mismatches: {len(mismatches)}")

    unknown = diff.get("unknown_versions", {})
    for machine in machines:
        unknown_list = unknown.get(machine, [])
        if unknown_list:
            lines.append(f"- Unknown versions on {machine}: {len(unknown_list)}")

    return "\n".join(lines)


def write_diff(reports_dir: pathlib.Path, diff: dict) -> pathlib.Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / DIFF_FILENAME
    with path.open("w", encoding="utf-8") as handle:
        json.dump(diff, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return path


def _version_tokens(value: str) -> tuple[tuple[int, object], ...]:
    tokens = re.findall(r"\d+|[A-Za-z]+", value)
    parsed: list[tuple[int, object]] = []
    for token in tokens:
        if token.isdigit():
            parsed.append((0, int(token)))
        else:
            parsed.append((1, token.lower()))
    return tuple(parsed)


def _version_label(short_version: str, bundle_version: str) -> str | None:
    if short_version == "unknown" and bundle_version == "unknown":
        return None
    if short_version == "unknown":
        return bundle_version
    if bundle_version == "unknown" or short_version == bundle_version:
        return short_version
    return f"{short_version} ({bundle_version})"


def _version_key(short_version: str, bundle_version: str) -> tuple[tuple[int, object], ...] | None:
    if short_version != "unknown":
        return _version_tokens(short_version)
    if bundle_version != "unknown":
        return _version_tokens(bundle_version)
    return None


def compute_update_summary(reports: dict[str, dict]) -> dict:
    machines = sorted(reports.keys())
    plugin_maps = {machine: _plugin_map(report) for machine, report in reports.items()}
    all_keys: set[str] = set()
    for mapping in plugin_maps.values():
        all_keys.update(mapping.keys())

    updates_by_machine: dict[str, list[dict]] = {machine: [] for machine in machines}
    updates_by_plugin: dict[str, dict] = {}

    for key in sorted(all_keys):
        sample_plugin = next(
            (mapping.get(key) for mapping in plugin_maps.values() if key in mapping),
            None,
        )
        bundle_name = sample_plugin.get("bundle_name") if sample_plugin else None
        bundle_id = sample_plugin.get("bundle_id") if sample_plugin else None

        versions_by_machine: dict[str, dict] = {}
        for machine, mapping in plugin_maps.items():
            plugin = mapping.get(key)
            if not plugin:
                continue
            short_version = plugin.get("short_version") or "unknown"
            bundle_version = plugin.get("bundle_version") or "unknown"
            versions_by_machine[machine] = {
                "short_version": short_version,
                "bundle_version": bundle_version,
                "version_key": _version_key(short_version, bundle_version),
                "label": _version_label(short_version, bundle_version),
            }

        best_machine = None
        best_key = None
        for machine, data in versions_by_machine.items():
            key_value = data["version_key"]
            if key_value is None:
                continue
            if best_key is None or key_value > best_key:
                best_key = key_value
                best_machine = machine

        best_version = None
        if best_machine is not None:
            best_version = versions_by_machine[best_machine]["label"]

        for machine in machines:
            mapping = plugin_maps.get(machine, {})
            plugin = mapping.get(key)
            if not plugin:
                updates_by_machine[machine].append(
                    {
                        "key": key,
                        "bundle_name": bundle_name,
                        "bundle_id": bundle_id,
                        "current_version": None,
                        "latest_version": best_version,
                        "best_machine": best_machine,
                        "reason": "missing",
                    }
                )
                continue
            data = versions_by_machine.get(machine)
            if not data:
                continue
            if data["version_key"] is None:
                updates_by_machine[machine].append(
                    {
                        "key": key,
                        "bundle_name": bundle_name,
                        "bundle_id": bundle_id,
                        "current_version": data["label"],
                        "latest_version": best_version,
                        "best_machine": best_machine,
                        "reason": "unknown_version",
                    }
                )
                continue
            if best_key is not None and data["version_key"] < best_key:
                updates_by_machine[machine].append(
                    {
                        "key": key,
                        "bundle_name": bundle_name,
                        "bundle_id": bundle_id,
                        "current_version": data["label"],
                        "latest_version": best_version,
                        "best_machine": best_machine,
                        "reason": "outdated",
                    }
                )

        for machine in machines:
            machine_updates = updates_by_machine[machine]
            if not machine_updates:
                continue
            matching = [update for update in machine_updates if update["key"] == key]
            if not matching:
                continue
            entry = updates_by_plugin.setdefault(
                key,
                {
                    "bundle_name": bundle_name,
                    "bundle_id": bundle_id,
                    "latest_version": best_version,
                    "best_machine": best_machine,
                    "machines": [],
                },
            )
            for update in matching:
                entry["machines"].append(
                    {
                        "machine": machine,
                        "current_version": update["current_version"],
                        "reason": update["reason"],
                    }
                )

    return {
        "generated_at": datetime.now(tz=timezone.utc).astimezone().isoformat(),
        "machines": machines,
        "updates_by_machine": updates_by_machine,
        "updates_by_plugin": updates_by_plugin,
    }


def write_summary(reports_dir: pathlib.Path, summary: dict) -> pathlib.Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / SUMMARY_FILENAME
    with path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return path
