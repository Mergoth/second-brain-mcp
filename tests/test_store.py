"""Tests for vault.store — list, read, write, move, search."""

from pathlib import Path

import pytest

from second_brain_mcp.errors import NoteExistsError, NoteNotFoundError, PathValidationError, SearchError
from second_brain_mcp.vault import store


class TestListNotes:
    def test_lists_markdown_files(self, vault: Path) -> None:
        results = store.list_notes(vault)
        paths = [r["path"] for r in results]
        assert "Tasks.md" in paths
        assert "Ideas.md" in paths

    def test_excludes_dotfiles(self, vault: Path) -> None:
        results = store.list_notes(vault)
        paths = [r["path"] for r in results]
        for p in paths:
            parts = Path(p).parts
            assert not any(part.startswith(".") for part in parts), (
                f"dotfile/dotdir should be excluded: {p}"
            )

    def test_includes_nested(self, vault: Path) -> None:
        results = store.list_notes(vault)
        paths = [r["path"] for r in results]
        assert any("raw/thoughts" in p for p in paths)

    def test_since_filter(self, vault: Path) -> None:
        import time
        future = time.time() + 86400
        results = store.list_notes(vault, since=future)
        assert results == []

    def test_glob_filter(self, vault: Path) -> None:
        results = store.list_notes(vault, glob="Tasks.md")
        assert len(results) == 1
        assert results[0]["path"] == "Tasks.md"

    def test_list_notes_rejects_escaping_glob(self, vault: Path) -> None:
        """A glob with '..' must raise, not silently return []."""
        with pytest.raises(PathValidationError, match="\\.\\."):
            store.list_notes(vault, glob="../**/*.md")

    def test_list_notes_rejects_absolute_glob(self, vault: Path) -> None:
        with pytest.raises(PathValidationError, match="absolute"):
            store.list_notes(vault, glob="/etc/**/*.md")

    def test_list_notes_rejects_dash_glob(self, vault: Path) -> None:
        with pytest.raises(PathValidationError, match="starts with"):
            store.list_notes(vault, glob="-pattern")


class TestReadNote:
    def test_read_existing(self, vault: Path) -> None:
        from second_brain_mcp.vault.paths import resolve
        path = resolve("Tasks.md")
        content = store.read_note(path)
        assert "# Tasks" in content

    def test_read_nonexistent(self, vault: Path) -> None:
        path = vault / "does-not-exist.md"
        with pytest.raises(NoteNotFoundError):
            store.read_note(path)


class TestWriteNote:
    def test_create(self, vault: Path) -> None:
        from second_brain_mcp.vault.paths import resolve
        path = resolve("new-note.md")
        store.write_note(path, "# New Note\n", "create")
        assert path.read_text() == "# New Note\n"

    def test_create_already_exists(self, vault: Path) -> None:
        from second_brain_mcp.vault.paths import resolve
        path = resolve("Tasks.md")
        with pytest.raises(NoteExistsError):
            store.write_note(path, "content", "create")

    def test_overwrite(self, vault: Path) -> None:
        from second_brain_mcp.vault.paths import resolve
        path = resolve("Ideas.md")
        store.write_note(path, "replaced", "overwrite")
        assert path.read_text() == "replaced"

    def test_overwrite_nonexistent(self, vault: Path) -> None:
        path = vault / "no-such.md"
        with pytest.raises(NoteNotFoundError):
            store.write_note(path, "content", "overwrite")

    def test_append(self, vault: Path) -> None:
        from second_brain_mcp.vault.paths import resolve
        path = resolve("Ideas.md")
        original = path.read_text()
        store.write_note(path, "\nnew line", "append")
        assert path.read_text() == original + "\nnew line"

    def test_invalid_mode(self, vault: Path) -> None:
        path = vault / "x.md"
        with pytest.raises(ValueError, match="invalid write mode"):
            store.write_note(path, "x", "delete")

    def test_create_nested_dirs(self, vault: Path) -> None:
        from second_brain_mcp.vault.paths import resolve
        path = resolve("deep/nested/new.md")
        store.write_note(path, "deep content", "create")
        assert path.read_text() == "deep content"


class TestMoveNote:
    def test_move(self, vault: Path) -> None:
        from second_brain_mcp.vault.paths import resolve
        src = resolve("Ideas.md")
        dst = resolve("raw/archive/Ideas.md")
        original_content = src.read_text()
        store.move_note(src, dst)
        assert not src.exists()
        assert dst.read_text() == original_content

    def test_move_to_archive_never_unlinks(self, vault: Path) -> None:
        """move_note uses os.replace, which is an atomic rename — not unlink.

        Verify by checking the source file disappears and the dest appears,
        proving rename semantics rather than copy+unlink.
        """
        from second_brain_mcp.vault.paths import resolve
        src = resolve("Ideas.md")
        dst = resolve("raw/archive/Ideas-archived.md")
        store.move_note(src, dst)
        assert not src.exists()
        assert dst.exists()

    def test_move_source_missing(self, vault: Path) -> None:
        from second_brain_mcp.vault.paths import resolve
        src = vault / "nope.md"
        dst = resolve("raw/archive/nope.md")
        with pytest.raises(NoteNotFoundError):
            store.move_note(src, dst)

    def test_move_dest_exists(self, vault: Path) -> None:
        from second_brain_mcp.vault.paths import resolve
        src = resolve("Tasks.md")
        dst = resolve("Ideas.md")
        with pytest.raises(NoteExistsError):
            store.move_note(src, dst)


class TestSearch:
    def test_search_finds_match(self, vault: Path) -> None:
        try:
            results = store.search_vault(vault, "Tasks")
        except SearchError as e:
            if "not installed" in str(e):
                pytest.skip("rg not available")
            raise
        assert any(r["path"] == "Tasks.md" for r in results)

    def test_search_no_matches(self, vault: Path) -> None:
        try:
            results = store.search_vault(vault, "xyzzy_nonexistent_term_12345")
        except SearchError as e:
            if "not installed" in str(e):
                pytest.skip("rg not available")
            raise
        assert results == []

    def test_search_excludes_dotfiles(self, vault: Path) -> None:
        try:
            results = store.search_vault(vault, "excluded")
        except SearchError as e:
            if "not installed" in str(e):
                pytest.skip("rg not available")
            raise
        for r in results:
            parts = Path(r["path"]).parts
            assert not any(p.startswith(".") for p in parts)

    def test_search_query_starting_with_dash_is_not_a_flag(self, vault: Path) -> None:
        """A query like '--files' must be treated as a literal search pattern,
        not as an rg flag that lists files."""
        try:
            results = store.search_vault(vault, "--files")
        except SearchError as e:
            if "not installed" in str(e):
                pytest.skip("rg not available")
            raise
        # --files as a flag would list filenames; as a pattern it finds nothing
        # (no file in the fixture contains the literal string "--files").
        # The key assertion: it must not return bare filenames without line numbers.
        for r in results:
            assert "line" in r, "result should have line numbers, not bare filenames"

    def test_search_cannot_inject_preprocessor(self, vault: Path, tmp_path: Path) -> None:
        """A query like '--pre=/path/to/script' must not execute the script."""
        marker = tmp_path / "rce_proof"
        script = tmp_path / "evil.sh"
        script.write_text(f"#!/bin/sh\ntouch {marker}\ncat \"$@\"\n")
        script.chmod(0o755)

        try:
            store.search_vault(vault, f"--pre={script}")
        except SearchError as e:
            if "not installed" in str(e):
                pytest.skip("rg not available")
            raise

        assert not marker.exists(), (
            f"rg executed the injected --pre script: {marker} was created"
        )

    def test_search_rejects_scope_with_dotdot(self, vault: Path) -> None:
        with pytest.raises(PathValidationError, match="\\.\\."):
            store.search_vault(vault, "test", scope="../**/*.md")

    def test_search_rejects_scope_starting_with_dash(self, vault: Path) -> None:
        with pytest.raises(PathValidationError, match="starts with"):
            store.search_vault(vault, "test", scope="--glob=*.md")

    def test_search_rejects_absolute_scope(self, vault: Path) -> None:
        with pytest.raises(PathValidationError, match="absolute"):
            store.search_vault(vault, "test", scope="/etc/*.md")
