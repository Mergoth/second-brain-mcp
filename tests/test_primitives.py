"""Tests for tools.primitives — thin adapter layer over vault.store."""

from pathlib import Path

import pytest

from second_brain_mcp.tools import primitives


class TestPrimitiveListNotes:
    def test_returns_list(self, vault: Path) -> None:
        results = primitives.list_notes()
        assert isinstance(results, list)
        assert len(results) > 0

    def test_glob_filter(self, vault: Path) -> None:
        results = primitives.list_notes(glob="Tasks.md")
        assert len(results) == 1


class TestPrimitiveReadNote:
    def test_reads_content(self, vault: Path) -> None:
        content = primitives.read_note("Tasks.md")
        assert "# Tasks" in content


class TestPrimitiveWriteNote:
    def test_create_and_read(self, vault: Path) -> None:
        primitives.write_note("test-prim.md", "# Test\n", "create")
        content = primitives.read_note("test-prim.md")
        assert content == "# Test\n"


class TestPrimitiveMoveNote:
    def test_move(self, vault: Path) -> None:
        primitives.write_note("to-move.md", "move me", "create")
        result = primitives.move_note("to-move.md", "raw/archive/to-move.md")
        assert "moved" in result
        content = primitives.read_note("raw/archive/to-move.md")
        assert content == "move me"


class TestPrimitiveSearch:
    def test_search(self, vault: Path) -> None:
        from second_brain_mcp.errors import SearchError
        try:
            results = primitives.search_vault("Tasks")
        except SearchError as e:
            if "not installed" in str(e):
                pytest.skip("rg not available")
            raise
        assert isinstance(results, list)
