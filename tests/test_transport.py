"""Tests for transport selection, Streamable HTTP app, and stdio fallback (ADR-0003)."""

import asyncio
from pathlib import Path

from starlette.testclient import TestClient

from second_brain_mcp.__main__ import _parse_args
from second_brain_mcp.auth import StaticBearerVerifier
from second_brain_mcp.metadata import build_auth_settings
from second_brain_mcp.server import create_server


def test_401_carries_www_authenticate_resource_metadata() -> None:
    verifier = StaticBearerVerifier("expected-secret-token")
    auth_settings = build_auth_settings(
        resource_url="http://127.0.0.1:8000",
        issuer_url="https://auth.example.com",
    )
    server = create_server(token_verifier=verifier, auth=auth_settings)
    app = server.streamable_http_app()
    client = TestClient(app)

    # 1. Unauthenticated request to /mcp endpoint gets 401 with WWW-Authenticate header
    response = client.post("/mcp", json={})
    assert response.status_code == 401
    www_auth = response.headers.get("www-authenticate", "")
    assert 'resource_metadata="http://127.0.0.1:8000/.well-known/oauth-protected-resource"' in www_auth

    # 2. Invalid bearer token gets 401 with WWW-Authenticate header
    response_invalid = client.post(
        "/mcp",
        json={},
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert response_invalid.status_code == 401
    www_auth_invalid = response_invalid.headers.get("www-authenticate", "")
    assert 'resource_metadata="http://127.0.0.1:8000/.well-known/oauth-protected-resource"' in www_auth_invalid

    # 3. Protected resource metadata endpoint serves valid JSON metadata without authentication
    meta_response = client.get("/.well-known/oauth-protected-resource")
    assert meta_response.status_code == 200
    meta_data = meta_response.json()
    assert meta_data["resource"] == "http://127.0.0.1:8000/"
    assert meta_data["authorization_servers"] == ["https://auth.example.com/"]


def test_stdio_still_works_without_auth(vault: Path) -> None:
    server = create_server()
    # stdio server has all tools registered and callable without auth credentials
    tools = asyncio.run(server.list_tools())
    tool_names = [t.name for t in tools]
    assert "list_notes" in tool_names
    assert "read_note" in tool_names
    assert "write_note" in tool_names
    assert "search_vault" in tool_names
    assert "move_note" in tool_names

    result = asyncio.run(server.call_tool("read_note", {"path": "Tasks.md"}))
    assert result is not None


def test_transport_cli_defaults_to_stdio() -> None:
    args = _parse_args([])
    assert args.transport == "stdio"


def test_transport_cli_accepts_http() -> None:
    args = _parse_args(["--transport", "http"])
    assert args.transport == "http"
