"""Entrypoint — transport selection lives here and nowhere else (ADR-0003).

``--transport stdio`` (default): runs over stdio, no auth.
``--transport http``: runs Streamable HTTP with static bearer auth.
"""

import argparse

from second_brain_mcp.config import init_vault_root
from second_brain_mcp.server import create_server


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
        # Lazy imports — auth and metadata are only needed for HTTP (ADR-0003).
        from second_brain_mcp.auth import StaticBearerVerifier, require_auth_token
        from second_brain_mcp.metadata import build_auth_settings

        token = require_auth_token()
        verifier = StaticBearerVerifier(token)
        auth_settings = build_auth_settings()

        server = create_server(token_verifier=verifier, auth=auth_settings)
        server.run(
            transport="streamable-http",
            host="127.0.0.1",
            port=8000,
        )


if __name__ == "__main__":
    main()
