"""RFC 9728 protected-resource and RFC 8414 authorization-server configuration (ADR-0003/0004).

Builds the AuthSettings that the MCP SDK needs to serve the
``/.well-known/oauth-protected-resource`` endpoint, populate the ``WWW-Authenticate``
header on 401 responses and, with ``oauth=True``, run the authorization server.

Imported only by __main__.py and oauth.py.
"""

from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions

# The only scope. Advertised and granted by default so a client that requests what the
# metadata lists is never refused for a scope it did not register.
SCOPE = "vault"


def build_auth_settings(
    *,
    resource_url: str = "http://127.0.0.1:8000/mcp",
    issuer_url: str = "http://127.0.0.1:8000",
    oauth: bool = False,
) -> AuthSettings:
    """Return AuthSettings for static-bearer verification, or for the owner OAuth server.

    Parameters
    ----------
    resource_url:
        The MCP endpoint URL exactly as clients enter it, including the ``/mcp`` path.
        claude.ai requires the metadata ``resource`` to equal it.
    issuer_url:
        The authorization server URL. Passed as a string so AuthSettings preserves it
        verbatim — RFC 8414 issuer comparison is exact, and a stray trailing slash breaks it.
    oauth:
        Enable dynamic client registration and the ``vault`` scope.

    Revocation (RFC 7009) is deliberately not advertised: in MCP SDK 2.0.0 its request model
    requires ``client_secret`` even for public clients, so Claude — a public client — would get
    a 400. Owner-side revocation is deleting the state file (ADR-0004).
    """
    if not oauth:
        return AuthSettings(issuer_url=issuer_url, resource_server_url=resource_url)
    return AuthSettings(
        issuer_url=issuer_url,
        resource_server_url=resource_url,
        client_registration_options=ClientRegistrationOptions(
            enabled=True, valid_scopes=[SCOPE], default_scopes=[SCOPE]
        ),
        required_scopes=[SCOPE],
    )
