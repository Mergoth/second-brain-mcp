"""RFC 9728 protected-resource metadata configuration (ADR-0003).

Builds the AuthSettings that the MCP SDK needs to serve the
``/.well-known/oauth-protected-resource`` endpoint and to populate the
``WWW-Authenticate`` header on 401 responses.

Imported only by __main__.py.
"""

from mcp.server.auth.settings import AuthSettings
from pydantic import AnyHttpUrl


def build_auth_settings(
    *,
    resource_url: str = "http://127.0.0.1:8000",
    issuer_url: str = "https://auth.example.com",
) -> AuthSettings:
    """Return AuthSettings wired for static-bearer verification.

    Parameters
    ----------
    resource_url:
        The URL that identifies this resource server. Used as the ``resource``
        value in the RFC 9728 metadata document and for the
        ``resource_metadata`` link in ``WWW-Authenticate``.
    issuer_url:
        The authorization server URL advertised in the metadata document.
        With a static bearer this is informational only — no token exchange
        actually happens.
    """
    return AuthSettings(
        issuer_url=AnyHttpUrl(issuer_url),
        resource_server_url=AnyHttpUrl(resource_url),
    )
