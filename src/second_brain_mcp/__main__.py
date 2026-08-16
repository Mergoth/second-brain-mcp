"""Entrypoint — transport selection lives here and nowhere else (ADR-0003).

This increment: stdio only. Later increments add HTTP without touching tools.
"""

from second_brain_mcp.config import init_vault_root
from second_brain_mcp.server import create_server


def main() -> None:
    init_vault_root()
    server = create_server()
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
