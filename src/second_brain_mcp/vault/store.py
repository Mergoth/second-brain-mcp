"""Vault store — list, read, write, move, search over already-resolved paths.

Every function here operates on paths that have already passed through
vault.paths.resolve(). Writes are atomic (temp file + os.replace).
No hard-delete operations anywhere in this module.
"""

import datetime
import fnmatch
import os
import subprocess
import tempfile
from pathlib import Path

from second_brain_mcp.config import get_vault_root
from second_brain_mcp.errors import (
    NoteExistsError,
    NoteNotFoundError,
    PathConfinementError,
    PathValidationError,
    SearchError,
)
from second_brain_mcp.vault import audit


def _is_dotfile(path: Path, root: Path) -> bool:
    """Check if any component of the relative path starts with a dot."""
    try:
        rel = path.relative_to(root)
    except ValueError:
        raise PathConfinementError(
            f"path {path} is outside vault root {root}"
        )
    return any(part.startswith(".") for part in rel.parts)


def list_notes(
    root: Path, glob: str = "**/*.md", since: float | None = None
) -> list[dict[str, str | float]]:
    """List notes matching glob, excluding dotfiles/dotdirs.

    Returns a list of dicts with 'path' (relative to root) and 'mtime'.
    """
    _validate_glob(glob)
    results: list[dict[str, str | float]] = []
    for path in sorted(root.glob(glob)):
        if not path.is_file():
            continue
        resolved = path.resolve()
        if resolved != root and root not in resolved.parents:
            continue
        if _is_dotfile(path, root):
            continue
        mtime = path.stat().st_mtime
        if since is not None and mtime < since:
            continue
        rel = str(path.relative_to(root))
        results.append({"path": rel, "mtime": mtime})
    return results


def _validate_glob(glob: str) -> None:
    """Reject glob patterns that could escape the vault root."""
    if not glob:
        raise PathValidationError("glob pattern is empty")
    if Path(glob).is_absolute():
        raise PathValidationError(f"absolute glob patterns are rejected: {glob!r}")
    if ".." in Path(glob).parts:
        raise PathValidationError(f"glob pattern contains '..': {glob!r}")
    if glob.startswith("-"):
        raise PathValidationError(f"glob pattern starts with '-': {glob!r}")


def read_note(resolved_path: Path) -> str:
    """Read and return the full text content of a note."""
    if not resolved_path.is_file():
        raise NoteNotFoundError(f"note not found: {resolved_path}")
    with open(resolved_path, "r", encoding="utf-8") as f:
        return f.read()


def write_note(resolved_path: Path, content: str, mode: str) -> None:
    """Write content to a note. Mode is 'create', 'overwrite', or 'append'.

    Writes are atomic for create/overwrite (temp file + os.replace).
    Append is not atomic but is append-only.
    """
    root = get_vault_root()

    if mode == "create":
        if resolved_path.exists():
            raise NoteExistsError(f"note already exists: {resolved_path}")
        resolved_path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(resolved_path, content)
        audit.append(root, "create", resolved_path)

    elif mode == "overwrite":
        if not resolved_path.exists():
            raise NoteNotFoundError(f"note not found for overwrite: {resolved_path}")
        _atomic_write(resolved_path, content)
        audit.append(root, "overwrite", resolved_path)

    elif mode == "append":
        if not resolved_path.exists():
            raise NoteNotFoundError(f"note not found for append: {resolved_path}")
        with open(resolved_path, "a", encoding="utf-8") as f:
            f.write(content)
        audit.append(root, "append", resolved_path)

    else:
        raise ValueError(f"invalid write mode: {mode!r} (must be create|overwrite|append)")


def move_note(from_path: Path, to_path: Path) -> None:
    """Move a note. Both paths must already be resolved."""
    root = get_vault_root()

    if not from_path.is_file():
        raise NoteNotFoundError(f"source not found: {from_path}")
    if to_path.exists():
        raise NoteExistsError(f"destination already exists: {to_path}")

    to_path.parent.mkdir(parents=True, exist_ok=True)
    os.replace(from_path, to_path)
    audit.append(root, "move", from_path, to_path)


def search_vault(
    root: Path, query: str, scope: str | None = None, timeout: float = 10.0
) -> list[dict[str, str | int]]:
    """Search the vault using ripgrep. Returns matches with path, line number, text.

    Raises SearchError if rg is not found or times out.
    """
    if scope is not None:
        if scope.startswith("-"):
            raise PathValidationError(f"scope starts with '-': {scope!r}")
        if ".." in Path(scope).parts:
            raise PathValidationError(f"scope contains '..': {scope!r}")
        if Path(scope).is_absolute():
            raise PathValidationError(f"absolute scope is rejected: {scope!r}")

    cmd = ["rg", "--no-heading", "--line-number", "--color=never", "--no-hidden"]
    if scope:
        cmd.extend(["--glob", scope])
    # Exclude dotfiles/dotdirs
    cmd.extend(["--glob", "!.*"])
    # -e treats query as a pattern, not a flag, even if it starts with '-'
    cmd.extend(["-e", query])
    # -- ends option parsing so root path is never interpreted as a flag
    cmd.extend(["--", str(root)])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(root),
        )
    except FileNotFoundError:
        raise SearchError(
            "ripgrep (rg) is not installed — search_vault requires rg on PATH"
        )
    except subprocess.TimeoutExpired:
        raise SearchError(f"search timed out after {timeout}s")

    if result.returncode not in (0, 1):
        # rg exit 1 = no matches (not an error), exit 2 = actual error
        raise SearchError(f"rg failed (exit {result.returncode}): {result.stderr.strip()}")

    matches: list[dict[str, str | int]] = []
    for line in result.stdout.splitlines():
        # Format: /path/to/file:linenum:text
        parts = line.split(":", 2)
        if len(parts) < 3:
            continue
        filepath = parts[0]
        try:
            rel = str(Path(filepath).relative_to(root))
        except ValueError:
            continue
        # Skip dotfiles in results too
        if any(part.startswith(".") for part in Path(rel).parts):
            continue
        matches.append({
            "path": rel,
            "line": int(parts[1]),
            "text": parts[2],
        })
    return matches


def _atomic_write(path: Path, content: str) -> None:
    """Write content atomically: temp file in same dir, then os.replace."""
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    except BaseException:
        # Clean up temp file on failure — but never delete the target.
        # os.replace on the temp is fine; it's our temp, not a note.
        try:
            os.replace(tmp, tmp + ".failed")
        except OSError:
            pass
        raise
