"""Path resolution chokepoint — the only place a caller-supplied path becomes real.

ADR-0002: every caller-supplied path passes through resolve(). It takes exactly
one parameter (the user path), fully resolves symlinks, and checks ancestry
against the frozen vault root. There is no bypass flag, no per-call root, no
trusted-path list.
"""

from pathlib import Path

from second_brain_mcp.config import get_vault_root
from second_brain_mcp.errors import PathConfinementError, PathValidationError


def resolve(user_path: str) -> Path:
    """Resolve a caller-supplied relative path to a real path inside the vault.

    Raises PathValidationError for structurally invalid inputs.
    Raises PathConfinementError if the resolved path escapes the vault root.
    """
    if not user_path:
        raise PathValidationError("path is empty")

    if "\x00" in user_path:
        raise PathValidationError("path contains null byte")

    if Path(user_path).is_absolute():
        raise PathValidationError(f"absolute paths are rejected: {user_path!r}")

    # Reject paths that contain .. components before resolution.
    # This catches both naive traversal and sneaky constructions.
    parts = Path(user_path).parts
    if ".." in parts:
        raise PathValidationError(f"path contains '..': {user_path!r}")

    root = get_vault_root()
    candidate = (root / user_path).resolve()

    # Ancestry check: candidate must be root itself or a child of root.
    # We use Path.parents, NOT string prefix, to avoid /vault matching /vault-evil.
    if candidate != root and root not in candidate.parents:
        raise PathConfinementError(
            f"path {user_path!r} resolves to {candidate} which is outside vault root {root}"
        )

    return candidate
