"""Named exception types for the second-brain-mcp server.

Every rejection — path, config, storage — uses a specific type so callers
(and tests) never have to match on message strings.
"""


class VaultError(Exception):
    """Base for all vault errors."""


class PathConfinementError(VaultError):
    """A caller-supplied path resolved outside the vault root."""


class PathValidationError(VaultError):
    """A caller-supplied path is structurally invalid (empty, absolute, null bytes, etc.)."""


class NoteNotFoundError(VaultError):
    """The resolved path does not exist on disk."""


class NoteExistsError(VaultError):
    """A create-mode write targets a path that already exists."""


class ConfigError(VaultError):
    """Server configuration is invalid or missing."""


class SearchError(VaultError):
    """A search operation failed (e.g. rg not found, timeout)."""
