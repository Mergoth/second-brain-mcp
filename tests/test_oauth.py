"""End-to-end tests for the single-owner OAuth server (ADR-0004).

Drives the real Starlette app the entrypoint builds, the way claude.ai does: discovery,
dynamic client registration, /authorize, the passphrase page, code exchange, refresh.
"""

import asyncio
import base64
import hashlib
import secrets
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from starlette.testclient import TestClient

from second_brain_mcp.__main__ import HttpSettings, build_http_server
from second_brain_mcp.oauth import MAX_FAILURES, OwnerOAuthProvider

BASE = "http://127.0.0.1:8000"
RESOURCE = f"{BASE}/mcp"
CALLBACK = "https://claude.ai/api/mcp/auth_callback"
PASSWORD = "correct horse battery"
STATIC = "static-bearer-token-for-claude-code"
MCP_HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "0"},
    },
}


@pytest.fixture
def state_dir(tmp_path: Path) -> Path:
    d = tmp_path / "state"
    d.mkdir()
    return d


@pytest.fixture
def client(state_dir: Path, monkeypatch: pytest.MonkeyPatch):
    # No brute-force sleep in tests; the lockout counter is what is under test.
    monkeypatch.setattr(OwnerOAuthProvider.__init__, "__kwdefaults__", {"failure_delay": 0.0})
    http = HttpSettings("127.0.0.1", 8000, RESOURCE, BASE, PASSWORD, state_dir)
    app = build_http_server(STATIC, http).streamable_http_app()
    with TestClient(app, base_url=BASE, follow_redirects=False) as c:
        yield c


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode()).digest()
    return verifier, base64.urlsafe_b64encode(digest).decode().rstrip("=")


def _register(c: TestClient, name: str = "Claude") -> str:
    r = c.post(
        "/register",
        json={
            "client_name": name,
            "redirect_uris": [CALLBACK],
            "token_endpoint_auth_method": "none",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["scope"] == "vault"
    return r.json()["client_id"]


def _authorize(c: TestClient, client_id: str, challenge: str, resource: str = RESOURCE):
    return c.get(
        "/authorize",
        params={
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": CALLBACK,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": "st4te",
            "scope": "vault",
            "resource": resource,
        },
    )


def _login_txn(c: TestClient, client_id: str, challenge: str) -> str:
    r = _authorize(c, client_id, challenge)
    assert r.status_code == 302
    location = r.headers["location"]
    assert location.startswith(f"{BASE}/login?txn=")
    return parse_qs(urlparse(location).query)["txn"][0]


def _sign_in(c: TestClient) -> tuple[str, dict]:
    """Full authorization-code flow; returns (client_id, token response)."""
    client_id = _register(c)
    verifier, challenge = _pkce()
    txn = _login_txn(c, client_id, challenge)
    r = c.post("/login", data={"txn": txn, "password": PASSWORD})
    assert r.status_code == 302, r.text
    redirect = urlparse(r.headers["location"])
    assert f"{redirect.scheme}://{redirect.netloc}{redirect.path}" == CALLBACK
    query = parse_qs(redirect.query)
    assert query["state"] == ["st4te"]
    r = c.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "code": query["code"][0],
            "redirect_uri": CALLBACK,
            "client_id": client_id,
            "code_verifier": verifier,
            "resource": RESOURCE,
        },
    )
    assert r.status_code == 200, r.text
    return client_id, {**r.json(), "code": query["code"][0], "verifier": verifier}


def _initialize(c: TestClient, token: str):
    return c.post("/mcp", json=INITIALIZE, headers={**MCP_HEADERS, "Authorization": f"Bearer {token}"})


# ---- discovery ---------------------------------------------------------------------------


def test_unauthenticated_mcp_points_at_path_scoped_resource_metadata(client: TestClient) -> None:
    r = client.post("/mcp", json=INITIALIZE, headers=MCP_HEADERS)
    assert r.status_code == 401
    assert (
        f'resource_metadata="{BASE}/.well-known/oauth-protected-resource/mcp"'
        in r.headers["www-authenticate"]
    )


def test_protected_resource_metadata_matches_the_url_the_user_enters(client: TestClient) -> None:
    meta = client.get("/.well-known/oauth-protected-resource/mcp").json()
    assert meta["resource"] == RESOURCE
    assert meta["authorization_servers"] == [BASE]
    assert meta["scopes_supported"] == ["vault"]


def test_authorization_server_metadata(client: TestClient) -> None:
    meta = client.get("/.well-known/oauth-authorization-server").json()
    assert meta["issuer"] == BASE
    assert meta["authorization_endpoint"] == f"{BASE}/authorize"
    assert meta["token_endpoint"] == f"{BASE}/token"
    assert meta["registration_endpoint"] == f"{BASE}/register"
    assert meta["code_challenge_methods_supported"] == ["S256"]
    assert "refresh_token" in meta["grant_types_supported"]
    assert "revocation_endpoint" not in meta


# ---- the owner check ---------------------------------------------------------------------


def test_login_page_escapes_client_name_and_shows_redirect_host(client: TestClient) -> None:
    client_id = _register(client, name="<script>alert(1)</script>")
    txn = _login_txn(client, client_id, _pkce()[1])
    r = client.get("/login", params={"txn": txn})
    assert r.status_code == 200
    assert "<script>alert(1)" not in r.text
    assert "&lt;script&gt;" in r.text
    assert "claude.ai" in r.text
    assert r.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]


def test_wrong_passphrase_does_not_redirect(client: TestClient) -> None:
    txn = _login_txn(client, _register(client), _pkce()[1])
    r = client.post("/login", data={"txn": txn, "password": "not the passphrase"})
    assert r.status_code == 401
    assert "location" not in r.headers
    assert "Wrong passphrase" in r.text


def test_unknown_txn_is_rejected(client: TestClient) -> None:
    r = client.post("/login", data={"txn": "made-up", "password": PASSWORD})
    assert r.status_code == 400
    assert "location" not in r.headers


def test_lockout_after_repeated_failures_blocks_even_the_right_passphrase(
    client: TestClient,
) -> None:
    txn = _login_txn(client, _register(client), _pkce()[1])
    for _ in range(MAX_FAILURES):
        client.post("/login", data={"txn": txn, "password": "wrong wrong wrong"})
    r = client.post("/login", data={"txn": txn, "password": PASSWORD})
    assert r.status_code == 429
    assert "location" not in r.headers


def test_authorize_rejects_a_foreign_resource(client: TestClient) -> None:
    r = _authorize(client, _register(client), _pkce()[1], resource="https://evil.example/mcp")
    assert r.status_code == 302
    query = parse_qs(urlparse(r.headers["location"]).query)
    assert query["error"] == ["invalid_target"]


# ---- tokens ------------------------------------------------------------------------------


def test_full_flow_grants_a_working_access_token(client: TestClient) -> None:
    _, tokens = _sign_in(client)
    assert tokens["token_type"] == "Bearer"
    assert tokens["scope"] == "vault"
    assert tokens["expires_in"] == 3600
    assert tokens["refresh_token"]
    assert _initialize(client, tokens["access_token"]).status_code == 200


def test_authorization_code_is_single_use(client: TestClient) -> None:
    client_id, tokens = _sign_in(client)
    r = client.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "code": tokens["code"],
            "redirect_uri": CALLBACK,
            "client_id": client_id,
            "code_verifier": tokens["verifier"],
        },
    )
    assert r.status_code == 400
    assert r.json()["error"] == "invalid_grant"


def test_refresh_rotates_and_kills_the_old_pair(client: TestClient) -> None:
    client_id, old = _sign_in(client)
    r = client.post(
        "/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": old["refresh_token"],
            "client_id": client_id,
        },
    )
    assert r.status_code == 200, r.text
    new = r.json()
    assert new["access_token"] != old["access_token"]
    assert new["refresh_token"] != old["refresh_token"]

    assert _initialize(client, new["access_token"]).status_code == 200
    assert _initialize(client, old["access_token"]).status_code == 401
    reused = client.post(
        "/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": old["refresh_token"],
            "client_id": client_id,
        },
    )
    assert reused.status_code == 400
    assert reused.json()["error"] == "invalid_grant"


def test_static_bearer_still_works_for_claude_code(client: TestClient) -> None:
    assert _initialize(client, STATIC).status_code == 200


def test_garbage_bearer_is_rejected(client: TestClient) -> None:
    assert _initialize(client, "nope").status_code == 401


# ---- storage -----------------------------------------------------------------------------


def test_tokens_survive_a_restart_and_are_stored_only_as_digests(
    client: TestClient, state_dir: Path
) -> None:
    _, tokens = _sign_in(client)
    raw = (state_dir / "oauth-state.json").read_text()
    assert tokens["access_token"] not in raw
    assert tokens["refresh_token"] not in raw

    restarted = OwnerOAuthProvider(
        owner_password=PASSWORD,
        static_token=STATIC,
        resource_url=RESOURCE,
        issuer_url=BASE,
        state_dir=state_dir,
    )
    loaded = asyncio.run(restarted.load_access_token(tokens["access_token"]))
    assert loaded is not None
    assert loaded.subject == "owner"


def test_missing_state_dir_refuses_to_start(tmp_path: Path) -> None:
    from second_brain_mcp.errors import ConfigError

    with pytest.raises(ConfigError, match="MCP_STATE_DIR"):
        OwnerOAuthProvider(
            owner_password=PASSWORD,
            static_token=STATIC,
            resource_url=RESOURCE,
            issuer_url=BASE,
            state_dir=tmp_path / "does-not-exist",
        )
