"""Tests for vault.audit — append-only machine audit log."""

from pathlib import Path

from second_brain_mcp.vault import audit


class TestAudit:
    def test_append_creates_file(self, vault: Path) -> None:
        audit.append(vault, "test-op", vault / "Tasks.md")
        audit_path = vault / audit.AUDIT_FILENAME
        assert audit_path.exists()
        lines = audit_path.read_text().splitlines()
        assert len(lines) == 1
        parts = lines[0].split("\t")
        assert len(parts) == 3
        assert parts[1] == "test-op"

    def test_append_is_additive(self, vault: Path) -> None:
        audit.append(vault, "op1", vault / "a.md")
        audit.append(vault, "op2", vault / "b.md")
        lines = (vault / audit.AUDIT_FILENAME).read_text().splitlines()
        assert len(lines) == 2

    def test_append_multi_path(self, vault: Path) -> None:
        audit.append(vault, "move", vault / "a.md", vault / "b.md")
        line = (vault / audit.AUDIT_FILENAME).read_text().strip()
        parts = line.split("\t")
        assert len(parts) == 4  # timestamp, op, path1, path2
