from __future__ import annotations

ARCHIVE_DIR_NAME = "old scans"
DIFF_FILENAME = "diff__latest.json"
SUMMARY_FILENAME = "summary__latest.json"


def is_timestamped_report(name: str) -> bool:
    if not name.endswith(".json"):
        return False
    if name.endswith("__latest.json"):
        return False
    if name.startswith("diff__") or name.startswith("summary__"):
        return False
    return "__" in name
