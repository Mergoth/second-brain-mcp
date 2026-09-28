"""Entrypoint — transport selection lives here and nowhere else (ADR-0003).

``--transport stdio`` (default): runs over stdio, no auth.
``--transport http``: runs Streamable HTTP with static bearer auth, plus the single-owner
OAuth server when ``MCP_OWNER_PASSWORD`` is set (ADR-0004).
"""

import argparse
import ipaddress
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from second_brain_mcp.config import init_vault_root
from second_brain_mcp.errors import ConfigError
from second_brain_mcp.server import create_server

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

MIN_OWNER_PASSWORD_LENGTH = 12


@dataclass(frozen=True)
class HttpSettings:
    host: str
    port: int
    resource_url: str
    issuer_url: str
    owner_password: str | None = None
    state_dir: Path | None = None


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _origin(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _http_settings(env: dict[str, str] | None = None) -> HttpSettings:
    """Read the HTTP bind address, advertised URLs and OAuth settings from the environment.

    ``MCP_RESOURCE_URL`` is the MCP endpoint as clients enter it, ``/mcp`` included. It
    defaults to the bind address only when bound to loopback. Bound to anything else, the
    server sits behind a proxy and a loopback default would tell remote clients the resource
    lives on 127.0.0.1 — so it is required. ``MCP_ISSUER_URL`` defaults to its origin.
    """
    env = os.environ if env is None else env
    host = env.get("MCP_HOST") or "127.0.0.1"
    raw_port = env.get("MCP_PORT") or "8000"
    try:
        port = int(raw_port)
    except ValueError:
        raise ConfigError(f"MCP_PORT={raw_port!r} is not an integer") from None

    resource_url = env.get("MCP_RESOURCE_URL")
    if not resource_url:
        if not _is_loopback(host):
            raise ConfigError(
                f"MCP_RESOURCE_URL is not set — required when MCP_HOST={host!r} is not loopback"
            )
        resource_url = f"http://{host}:{port}/mcp"
    issuer_url = env.get("MCP_ISSUER_URL") or _origin(resource_url)

    owner_password = env.get("MCP_OWNER_PASSWORD") or None
    state_dir = None
    if owner_password is not None:
        if len(owner_password) < MIN_OWNER_PASSWORD_LENGTH:
            raise ConfigError(
                f"MCP_OWNER_PASSWORD must be at least {MIN_OWNER_PASSWORD_LENGTH} characters"
            )
        raw_state = env.get("MCP_STATE_DIR")
        if not raw_state:
            raise ConfigError("MCP_STATE_DIR is not set — required when MCP_OWNER_PASSWORD is set")
        state_dir = Path(raw_state)
    return HttpSettings(host, port, resource_url, issuer_url, owner_password, state_dir)


def build_http_server(token: str, http: HttpSettings) -> "MCPServer":
    """Wire auth onto the server: static bearer only, or static bearer plus owner OAuth."""
    from second_brain_mcp.metadata import build_auth_settings

    if http.owner_password is None:
        from second_brain_mcp.auth import StaticBearerVerifier

        return create_server(
            token_verifier=StaticBearerVerifier(token),
            auth=build_auth_settings(resource_url=http.resource_url, issuer_url=http.issuer_url),
        )

    from second_brain_mcp.oauth import LOGIN_PATH, OwnerOAuthProvider

    assert http.state_dir is not None
    provider = OwnerOAuthProvider(
        owner_password=http.owner_password,
        static_token=token,
        resource_url=http.resource_url,
        issuer_url=http.issuer_url,
        state_dir=http.state_dir,
    )
    server = create_server(
        auth_server_provider=provider,
        auth=build_auth_settings(
            resource_url=http.resource_url, issuer_url=http.issuer_url, oauth=True
        ),
    )
    server.custom_route(LOGIN_PATH, methods=["GET", "POST"])(provider.login)
    return server


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="second-brain-mcp",
        description="MCP server for an Obsidian vault.",
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "http"),
        default="stdio",
        help="Transport protocol (default: stdio).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    init_vault_root()

    if args.transport == "stdio":
        server = create_server()
        server.run(transport="stdio")
    else:
        # Lazy imports — auth is only needed for HTTP (ADR-0003).
        from second_brain_mcp.auth import require_auth_token

        http = _http_settings()
        server = build_http_server(require_auth_token(), http)
        server.run(
            transport="streamable-http",
            host=http.host,
            port=http.port,
        )


if __name__ == "__main__":
    main()
