"""FastMCP server construction — builds the server object and registers tools.

No transport selection here — that belongs in __main__.py (ADR-0003).
"""

from mcp.server.mcpserver import MCPServer

from second_brain_mcp.tools import primitives


def create_server(**kwargs) -> MCPServer:
    """Create and return a configured MCPServer with all tools registered.

    Extra *kwargs* are forwarded to the MCPServer constructor so the
    entrypoint can inject auth settings without server.py importing auth
    types (ADR-0003).
    """
    mcp = MCPServer("second-brain-mcp", **kwargs)

    @mcp.tool()
    def list_notes(glob: str = "**/*.md", since: float | None = None) -> list[dict]:
        """List notes matching a glob pattern. Returns paths and mtimes only, no bodies.
        Excludes dotfiles and dotdirs."""
        return primitives.list_notes(glob=glob, since=since)

    @mcp.tool()
    def read_note(path: str) -> str:
        """Read the full content of a note at the given relative path."""
        return primitives.read_note(path)

    @mcp.tool()
    def write_note(path: str, content: str, mode: str) -> str:
        """Write content to a note. mode: 'create' | 'overwrite' | 'append'."""
        return primitives.write_note(path, content, mode)

    @mcp.tool()
    def search_vault(query: str, scope: str | None = None) -> list[dict]:
        """Search the vault using ripgrep. Returns matching lines with file paths."""
        return primitives.search_vault(query, scope=scope)

    @mcp.tool()
    def move_note(from_path: str, to_path: str) -> str:
        """Move a note from one path to another. Both paths are relative to vault root."""
        return primitives.move_note(from_path, to_path)

    return mcp
