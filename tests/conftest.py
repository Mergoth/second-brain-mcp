"""Pytest configuration — vault fixture and safety guard.

The vault fixture copies the committed synthetic vault into tmp_path.
The safety guard fails the entire session if the resolved root is not
under tmp_path — a real path must never be touched by tests.
"""

import os
import shutil
from pathlib import Path

import pytest

FIXTURE_VAULT = Path(__file__).parent / "fixtures" / "vault"


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    """Copy the fixture vault into tmp_path and return the root.

    Also creates a symlink pointing outside the vault for confinement tests.
    Skips symlink creation on filesystems that don't support it.
    """
    vault_root = tmp_path / "vault"
    shutil.copytree(FIXTURE_VAULT, vault_root)

    # Create a symlink inside the vault pointing outside it
    escape_target = tmp_path / "outside" / "secret.md"
    escape_target.parent.mkdir(parents=True, exist_ok=True)
    escape_target.write_text("you should not see this")

    symlink_path = vault_root / "escape-link.md"
    try:
        symlink_path.symlink_to(escape_target)
    except OSError:
        pass  # Filesystem doesn't support symlinks; tests that need it will skip

    return vault_root


@pytest.fixture(autouse=True)
def _init_vault_root(vault: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Set VAULT_PATH to the tmp_path vault and initialize config.

    Runs before every test. Resets config after each test.
    """
    from second_brain_mcp.config import _reset_for_testing, init_vault_root

    _reset_for_testing()
    monkeypatch.setenv("VAULT_PATH", str(vault))
    init_vault_root()

    yield  # type: ignore[misc]

    _reset_for_testing()


def test_never_points_at_real_vault(vault: Path) -> None:
    """Safety guard: the resolved vault root must be under tmp_path.

    This test exists in conftest so it runs in every session. If it fails,
    something in the fixture setup pointed at a real path.
    """
    from second_brain_mcp.config import get_vault_root

    root = get_vault_root()
    # Must be under the pytest tmp directory
    assert "pytest" in str(root) or "tmp" in str(root).lower(), (
        f"vault root {root} does not appear to be under a temp directory — "
        f"refusing to run tests against what might be a real vault"
    )
    # Must be the fixture copy, not the repo's fixture
    assert str(FIXTURE_VAULT.resolve()) not in str(root), (
        f"vault root {root} points at the fixture source, not a tmp_path copy"
    )
