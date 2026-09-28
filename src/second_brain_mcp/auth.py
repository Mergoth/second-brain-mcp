"""Static bearer-token verification (ADR-0003).

Reads MCP_AUTH_TOKEN from the environment. No default — if the variable is
unset or empty the HTTP entrypoint must refuse to start.  Token comparison
uses hmac.compare_digest, never ``==``, to avoid timing side-channels.

This module is imported only by __main__.py. Nothing under tools/ or vault/
may reference it.
"""

import hmac
import os

from mcp.server.auth.provider import AccessToken, TokenVerifier

from second_brain_mcp.errors import ConfigError


def require_auth_token() -> str:
    """Return MCP_AUTH_TOKEN from the environment, or raise ConfigError."""
    token = os.environ.get("MCP_AUTH_TOKEN")
    if not token:
        raise ConfigError("MCP_AUTH_TOKEN is not set — HTTP transport refuses to start")
    return token


def resolve_static_token(*, oauth_enabled: bool) -> str | None:
    """Return the static bearer, or None when OAuth alone is enough (ADR-0005).

    The static token never expires and cannot be rotated, so it is the weakest credential
    the server accepts. Once the owner OAuth server is running it is optional: leaving
    MCP_AUTH_TOKEN unset drops the standing bearer entirely. Without OAuth it remains the
    only way in, so it stays mandatory.
    """
    token = os.environ.get("MCP_AUTH_TOKEN")
    if token:
        return token
    if oauth_enabled:
        return None
    raise ConfigError("MCP_AUTH_TOKEN is not set — HTTP transport refuses to start")


class StaticBearerVerifier(TokenVerifier):
    """Verify bearer tokens against a static secret using constant-time comparison."""

    def __init__(self, expected_token: str) -> None:
        self._expected = expected_token

    async def verify_token(self, token: str) -> AccessToken | None:
        """Return an AccessToken if *token* matches, else None."""
        if hmac.compare_digest(token.encode(), self._expected.encode()):
            return AccessToken(
                token=token,
                client_id="static-bearer",
                scopes=[],
            )
        return None
