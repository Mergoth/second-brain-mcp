"""MCP tool adapters — thin wrappers that call vault.store, never each other.

Each function is registered as an MCP tool via server.py. They call
vault.paths.resolve() for path arguments and delegate to vault.store.
"""

from second_brain_mcp.config import get_vault_root
from second_brain_mcp.vault import paths, store


def list_notes(glob: str = "**/*.md", since: float | None = None) -> list[dict]:
    """List notes matching a glob pattern. Returns paths and mtimes, no bodies.

    Excludes dotfiles and dotdirs. Optional `since` filters by mtime (epoch).
    """
    root = get_vault_root()
    return store.list_notes(root, glob=glob, since=since)


def read_note(path: str) -> str:
    """Read the full content of a note at the given relative path."""
    resolved = paths.resolve(path)
    return store.read_note(resolved)


def write_note(path: str, content: str, mode: str) -> str:
    """Write content to a note. Mode: 'create', 'overwrite', or 'append'."""
    resolved = paths.resolve(path)
    store.write_note(resolved, content, mode)
    return f"{mode}d {path}"


def search_vault(query: str, scope: str | None = None) -> list[dict]:
    """Search the vault using ripgrep. Returns matching lines with paths."""
    root = get_vault_root()
    return store.search_vault(root, query, scope=scope)


def move_note(from_path: str, to_path: str) -> str:
    """Move a note. Both paths resolved independently per ADR-0002."""
    from_resolved = paths.resolve(from_path)
    to_resolved = paths.resolve(to_path)
    store.move_note(from_resolved, to_resolved)
    return f"moved {from_path} -> {to_path}"
