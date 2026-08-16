"""Toolchain smoke tests.

These exist so `uv run --frozen pytest -q` is verifiably green before any build
round starts. pytest exits 5 on empty collection, which reads as a failed round,
so the suite must never be empty. Extend these; do not delete them.
"""

import sys


def test_python_is_at_least_3_11():
    """ADR-0001: system python3 is 3.9.6 and below the MCP SDK floor."""
    assert sys.version_info >= (3, 11), f"got {sys.version_info}"


def test_package_imports():
    import second_brain_mcp

    assert second_brain_mcp.__doc__


def test_mcp_sdk_available():
    import mcp

    assert mcp is not None
