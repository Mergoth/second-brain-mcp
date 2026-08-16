"""Append-only machine audit log.

Every mutation (write, move) appends one line. The format is strict and
parseable: ISO-8601 timestamp, tab, operation, tab, path(s).

This writes to ``meta/audit.log`` inside the vault. ``meta/log.md`` is
the human-curated file and is NOT written by this module.
"""

import datetime
from pathlib import Path

AUDIT_FILENAME = "meta/audit.log"


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def append(root: Path, operation: str, *paths: Path) -> None:
    """Append one audit line. Called by store after each mutation."""
    audit_path = root / AUDIT_FILENAME
    _ensure_parent(audit_path)
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    path_strs = "\t".join(str(p) for p in paths)
    line = f"{ts}\t{operation}\t{path_strs}\n"
    with open(audit_path, "a", encoding="utf-8") as f:
        f.write(line)
