"""Tests for config.py — startup, VAULT_PATH handling, no-default enforcement."""

import os
from pathlib import Path

import pytest

from second_brain_mcp.config import _reset_for_testing, get_vault_root, init_vault_root
from second_brain_mcp.errors import ConfigError


class TestConfigRefusesWithoutVaultPath:
    """The server must refuse to start if VAULT_PATH is unset."""

    def test_config_refuses_to_start_without_vault_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _reset_for_testing()
        monkeypatch.delenv("VAULT_PATH", raising=False)
        with pytest.raises(ConfigError, match="VAULT_PATH is not set"):
            init_vault_root()

    def test_config_refuses_empty_vault_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _reset_for_testing()
        monkeypatch.setenv("VAULT_PATH", "")
        with pytest.raises(ConfigError, match="VAULT_PATH is not set"):
            init_vault_root()

    def test_config_refuses_nonexistent_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _reset_for_testing()
        monkeypatch.setenv("VAULT_PATH", str(tmp_path / "does-not-exist"))
        with pytest.raises(ConfigError, match="not a directory"):
            init_vault_root()

    def test_config_refuses_file_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        f = tmp_path / "afile.txt"
        f.write_text("not a dir")
        _reset_for_testing()
        monkeypatch.setenv("VAULT_PATH", str(f))
        with pytest.raises(ConfigError, match="not a directory"):
            init_vault_root()


class TestConfigFreezes:
    """Once initialized, the root is frozen."""

    def test_double_init_raises(self, vault: Path) -> None:
        # Already initialized by the autouse fixture
        with pytest.raises(ConfigError, match="already initialized"):
            init_vault_root()

    def test_get_before_init_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _reset_for_testing()
        with pytest.raises(ConfigError, match="not initialized"):
            get_vault_root()

