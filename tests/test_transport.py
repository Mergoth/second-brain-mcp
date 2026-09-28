"""Tests for transport selection, Streamable HTTP app, and stdio fallback (ADR-0003)."""

import asyncio
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from second_brain_mcp.__main__ import _http_settings, _parse_args
from second_brain_mcp.auth import StaticBearerVerifier
from second_brain_mcp.errors import ConfigError
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
    assert meta_data["resource"] == "http://127.0.0.1:8000"
    assert meta_data["authorization_servers"] == ["https://auth.example.com"]


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


def test_http_settings_default_to_loopback() -> None:
    s = _http_settings({})
    assert (s.host, s.port) == ("127.0.0.1", 8000)
    assert s.resource_url == "http://127.0.0.1:8000/mcp"
    assert s.issuer_url == "http://127.0.0.1:8000"
    assert s.owner_password is None


def test_http_settings_default_issuer_is_the_resource_origin() -> None:
    s = _http_settings({"MCP_HOST": "0.0.0.0", "MCP_RESOURCE_URL": "https://b.example:1986/mcp"})
    assert s.issuer_url == "https://b.example:1986"


def test_http_settings_owner_password_requires_state_dir() -> None:
    with pytest.raises(ConfigError, match="MCP_STATE_DIR"):
        _http_settings({"MCP_OWNER_PASSWORD": "long enough passphrase"})


def test_http_settings_reject_short_owner_password() -> None:
    with pytest.raises(ConfigError, match="at least 12"):
        _http_settings({"MCP_OWNER_PASSWORD": "short", "MCP_STATE_DIR": "/state"})


def test_http_settings_read_oauth_config() -> None:
    s = _http_settings({"MCP_OWNER_PASSWORD": "long enough passphrase", "MCP_STATE_DIR": "/state"})
    assert s.owner_password == "long enough passphrase"
    assert str(s.state_dir) == "/state"


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.1.99"])
def test_http_settings_require_resource_url_off_loopback(host: str) -> None:
    with pytest.raises(ConfigError, match="MCP_RESOURCE_URL"):
        _http_settings({"MCP_HOST": host})


def test_http_settings_read_advertised_urls_from_env() -> None:
    s = _http_settings(
        {
            "MCP_HOST": "0.0.0.0",
            "MCP_PORT": "8765",
            "MCP_RESOURCE_URL": "https://brain.example.net",
            "MCP_ISSUER_URL": "https://issuer.example.net",
        }
    )
    assert (s.host, s.port) == ("0.0.0.0", 8765)
    assert s.resource_url == "https://brain.example.net"
    assert s.issuer_url == "https://issuer.example.net"


def test_http_settings_reject_non_integer_port() -> None:
    with pytest.raises(ConfigError, match="MCP_PORT"):
        _http_settings({"MCP_PORT": "eighty"})
