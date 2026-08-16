"""Vault root configuration — read once at startup, frozen forever.

VAULT_PATH is the only environment variable this module reads.
It has no default. The server refuses to start if it is unset, missing,
or not a directory. The resolved root is never re-read and is not settable
after startup.
"""

import os
from pathlib import Path

from second_brain_mcp.errors import ConfigError

_vault_root: Path | None = None


def init_vault_root() -> Path:
    """Resolve VAULT_PATH from the environment, freeze it, and return it.

    Raises ConfigError if VAULT_PATH is unset, empty, not a directory, or
    has already been initialized (double-init is a programming error).
    """
    global _vault_root

    if _vault_root is not None:
        raise ConfigError("vault root already initialized — cannot re-init")

    raw = os.environ.get("VAULT_PATH")
    if not raw:
        raise ConfigError("VAULT_PATH is not set — server refuses to start")

    root = Path(raw).resolve()
    if not root.is_dir():
        raise ConfigError(f"VAULT_PATH={raw!r} is not a directory")

    _vault_root = root
    return root


def get_vault_root() -> Path:
    """Return the frozen vault root. Raises ConfigError if not yet initialized."""
    if _vault_root is None:
        raise ConfigError("vault root not initialized — call init_vault_root() first")
    return _vault_root


def _reset_for_testing() -> None:
    """Reset the global root so tests can re-initialize. Test-only."""
    global _vault_root
    _vault_root = None
