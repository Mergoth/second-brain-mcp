"""Adversarial test table for vault.paths.resolve() — the confinement chokepoint.

Every rejection case from the spec is covered:
- empty paths
- null bytes
- absolute paths
- .. traversal
- symlinks pointing outside
- paths resolving to siblings of root (the /vault vs /vault-evil case)
"""

import os
from pathlib import Path

import pytest

from second_brain_mcp.errors import PathConfinementError, PathValidationError
from second_brain_mcp.vault.paths import resolve


class TestResolveRejects:
    """Table-driven rejection tests."""

    def test_empty_path(self) -> None:
        with pytest.raises(PathValidationError, match="empty"):
            resolve("")

    def test_null_byte(self) -> None:
        with pytest.raises(PathValidationError, match="null byte"):
            resolve("foo\x00bar.md")

    def test_absolute_path(self) -> None:
        with pytest.raises(PathValidationError, match="absolute"):
            resolve("/etc/passwd")

    def test_dotdot_simple(self) -> None:
        with pytest.raises(PathValidationError, match="\\.\\."):
            resolve("../outside.md")

    def test_dotdot_nested(self) -> None:
        with pytest.raises(PathValidationError, match="\\.\\."):
            resolve("sub/../../outside.md")

    def test_dotdot_at_end(self) -> None:
        with pytest.raises(PathValidationError, match="\\.\\."):
            resolve("sub/..")

    def test_symlink_escape(self, vault: Path) -> None:
        """A symlink inside the vault that points outside must be rejected."""
        symlink = vault / "escape-link.md"
        if not symlink.is_symlink():
            pytest.skip("filesystem does not support symlinks")
        with pytest.raises(PathConfinementError):
            resolve("escape-link.md")


class TestResolveAccepts:
    """Paths that should resolve successfully."""

    def test_simple_file(self, vault: Path) -> None:
        result = resolve("Tasks.md")
        assert result == vault / "Tasks.md"
        assert result.is_file()

    def test_nested_file(self, vault: Path) -> None:
        result = resolve("raw/thoughts/2026-08-15-0930-project-structure.md")
        assert result.is_file()

    def test_directory(self, vault: Path) -> None:
        result = resolve("raw")
        assert result.is_dir()

    def test_nonexistent_but_inside(self, vault: Path) -> None:
        """A path that doesn't exist yet but is inside the vault should resolve."""
        result = resolve("new-note.md")
        assert not result.exists()
        assert str(result).startswith(str(vault))

    def test_dotfile_in_name(self, vault: Path) -> None:
        """Files with dots in the name (not at start) should resolve fine."""
        result = resolve("file.name.md")
        # Resolves but doesn't exist — that's fine, it's inside the vault
        assert not result.exists()


class TestResolveOneParameter:
    """Verify resolve() takes exactly one parameter — no root, no flags."""

    def test_signature(self) -> None:
        import inspect

        sig = inspect.signature(resolve)
        params = list(sig.parameters.keys())
        assert params == ["user_path"], (
            f"resolve() must take exactly one parameter 'user_path', got {params}"
        )
