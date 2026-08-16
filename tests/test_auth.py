"""Tests for auth.py — static bearer token verification and environment checks (ADR-0003)."""

import asyncio

import pytest

from second_brain_mcp.auth import StaticBearerVerifier, require_auth_token
from second_brain_mcp.errors import ConfigError


class TestStaticBearerVerifier:
    """Verify bearer tokens with constant-time comparison."""

    def test_accepts_correct_bearer(self) -> None:
        verifier = StaticBearerVerifier("secret-token-123")
        token = asyncio.run(verifier.verify_token("secret-token-123"))
        assert token is not None
        assert token.token == "secret-token-123"
        assert token.client_id == "static-bearer"

    def test_rejects_wrong_bearer(self) -> None:
        verifier = StaticBearerVerifier("secret-token-123")
        token = asyncio.run(verifier.verify_token("wrong-token"))
        assert token is None

    def test_rejects_missing_bearer(self) -> None:
        verifier = StaticBearerVerifier("secret-token-123")
        token = asyncio.run(verifier.verify_token(""))
        assert token is None


class TestRequireAuthToken:
    """The HTTP transport must refuse to start without MCP_AUTH_TOKEN."""

    def test_http_refuses_to_start_without_auth_token(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("MCP_AUTH_TOKEN", raising=False)
        with pytest.raises(ConfigError, match="MCP_AUTH_TOKEN is not set"):
            require_auth_token()

        monkeypatch.setenv("MCP_AUTH_TOKEN", "")
        with pytest.raises(ConfigError, match="MCP_AUTH_TOKEN is not set"):
            require_auth_token()

    def test_returns_token_when_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MCP_AUTH_TOKEN", "valid-secret")
        assert require_auth_token() == "valid-secret"
