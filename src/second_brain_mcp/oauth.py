"""Single-owner OAuth 2.1 authorization server (ADR-0004).

claude.ai custom connectors on personal plans authenticate only with OAuth, so the HTTP
entrypoint runs a tiny authorization server of its own: the owner signs in once with a
passphrase and Claude receives rotating access/refresh tokens. The MCP SDK implements the
protocol (discovery, dynamic client registration, PKCE, code and token exchange); this module
holds only the owner check and token storage.

The static MCP_AUTH_TOKEN keeps working as a bearer for clients that can send a header
(Claude Code). Imported only by __main__.py (ADR-0003).
"""

import asyncio
import hashlib
import hmac
import html
import json
import logging
import os
import secrets
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    TokenError,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from second_brain_mcp.errors import ConfigError
from second_brain_mcp.metadata import SCOPE

log = logging.getLogger(__name__)

LOGIN_PATH = "/login"
STATIC_CLIENT_ID = "static-bearer"
OWNER = "owner"

ACCESS_TTL = 3600
REFRESH_TTL = 90 * 86400
CODE_TTL = 300
LOGIN_TTL = 600
MAX_FAILURES = 5
LOCKOUT_SECONDS = 900
MAX_CLIENTS = 50
MAX_PENDING = 100

_SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'"
    ),
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
}


def _digest(token: str) -> str:
    """Tokens are stored only as SHA-256 digests; the state file never holds a usable token."""
    return hashlib.sha256(token.encode()).hexdigest()


def _normalize(url: str) -> str:
    return url.rstrip("/")


@dataclass
class _PendingLogin:
    client_id: str
    params: AuthorizationParams
    expires_at: float


class OwnerOAuthProvider(OAuthAuthorizationServerProvider[AuthorizationCode, RefreshToken, AccessToken]):
    """Authorization server with exactly one resource owner, authenticated by passphrase."""

    def __init__(
        self,
        *,
        owner_password: str,
        static_token: str,
        resource_url: str,
        issuer_url: str,
        state_dir: Path,
        failure_delay: float = 1.0,
    ) -> None:
        if not state_dir.is_dir():
            raise ConfigError(f"MCP_STATE_DIR={str(state_dir)!r} is not a directory")
        self._password = owner_password.encode()
        self._static = static_token.encode()
        self._resource = _normalize(resource_url)
        self._issuer = _normalize(issuer_url)
        self._state_path = state_dir / "oauth-state.json"
        self._failure_delay = failure_delay

        # Short-lived, in memory only: a restart just means signing in again.
        self._pending: dict[str, _PendingLogin] = {}
        self._codes: dict[str, AuthorizationCode] = {}
        self._failures: list[float] = []
        self._locked_until = 0.0

        # Durable: registered clients and token digests.
        self._clients: dict[str, OAuthClientInformationFull] = {}
        self._access: dict[str, dict[str, Any]] = {}
        self._refresh: dict[str, dict[str, Any]] = {}
        self._load()

    # ---- persistence -------------------------------------------------------------------

    def _load(self) -> None:
        if not self._state_path.exists():
            return
        try:
            state = json.loads(self._state_path.read_text())
            self._clients = {
                cid: OAuthClientInformationFull.model_validate(info)
                for cid, info in state.get("clients", {}).items()
            }
        except (OSError, ValueError) as exc:
            raise ConfigError(f"cannot read OAuth state {self._state_path}: {exc}") from exc
        self._access = state.get("access", {})
        self._refresh = state.get("refresh", {})

    def _save(self) -> None:
        now = time.time()
        self._access = {d: r for d, r in self._access.items() if r["expires_at"] > now}
        self._refresh = {d: r for d, r in self._refresh.items() if r["expires_at"] > now}
        state = {
            "clients": {
                cid: info.model_dump(mode="json", exclude_none=True)
                for cid, info in self._clients.items()
            },
            "access": self._access,
            "refresh": self._refresh,
        }
        # Same atomic-write rule as the vault: temp file in the same directory, then replace.
        fd, tmp = tempfile.mkstemp(dir=self._state_path.parent, prefix=".oauth-state-")
        try:
            with os.fdopen(fd, "w") as fh:
                json.dump(state, fh)
            os.replace(tmp, self._state_path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    # ---- client registration -----------------------------------------------------------

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        return self._clients.get(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        # Registration is open by design (that is how Claude registers itself), so cap it.
        # A client holding a live refresh token is never evicted.
        assert client_info.client_id is not None
        self._clients[client_info.client_id] = client_info
        if len(self._clients) > MAX_CLIENTS:
            in_use = {r["client_id"] for r in self._refresh.values()}
            evictable = sorted(
                (c for c in self._clients.values() if c.client_id not in in_use),
                key=lambda c: c.client_id_issued_at or 0,
            )
            for client in evictable[: len(self._clients) - MAX_CLIENTS]:
                del self._clients[client.client_id]  # type: ignore[arg-type]
        self._save()

    # ---- authorization: the owner check ------------------------------------------------

    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        if params.resource is not None and _normalize(params.resource) != self._resource:
            raise AuthorizeError("invalid_target", f"unknown resource {params.resource!r}")
        now = time.time()
        self._pending = {t: p for t, p in self._pending.items() if p.expires_at > now}
        while len(self._pending) >= MAX_PENDING:
            self._pending.pop(next(iter(self._pending)))
        txn = secrets.token_urlsafe(32)
        assert client.client_id is not None
        self._pending[txn] = _PendingLogin(client.client_id, params, now + LOGIN_TTL)
        return f"{self._issuer}{LOGIN_PATH}?txn={txn}"

    async def login(self, request: Request) -> Response:
        """GET renders the passphrase form; POST checks it and redirects back with a code."""
        if request.method == "POST":
            form = await request.form()
            txn = form.get("txn")
        else:
            form = None
            txn = request.query_params.get("txn")

        pending = self._pending.get(txn) if isinstance(txn, str) else None
        if pending is None or pending.expires_at < time.time():
            return _page("This sign-in link has expired. Start again from Claude.", status=400)
        client = self._clients.get(pending.client_id)
        if client is None:
            return _page("Unknown client. Start again from Claude.", status=400)
        assert isinstance(txn, str)

        if form is None:
            return _login_form(txn, client, pending.params)

        now = time.time()
        if now < self._locked_until:
            minutes = int((self._locked_until - now) // 60) + 1
            return _page(f"Too many failed attempts. Try again in {minutes} minutes.", status=429)

        password = form.get("password")
        if not isinstance(password, str) or not hmac.compare_digest(
            password.encode(), self._password
        ):
            self._record_failure(now)
            if self._failure_delay:
                await asyncio.sleep(self._failure_delay)
            return _login_form(txn, client, pending.params, error="Wrong passphrase.", status=401)

        del self._pending[txn]
        self._failures.clear()
        code = secrets.token_urlsafe(32)
        self._codes = {c: a for c, a in self._codes.items() if a.expires_at > now}
        self._codes[code] = AuthorizationCode(
            code=code,
            scopes=pending.params.scopes or [SCOPE],
            expires_at=now + CODE_TTL,
            client_id=pending.client_id,
            code_challenge=pending.params.code_challenge,
            redirect_uri=pending.params.redirect_uri,
            redirect_uri_provided_explicitly=pending.params.redirect_uri_provided_explicitly,
            resource=pending.params.resource,
            subject=OWNER,
        )
        log.warning("owner signed in; client=%s", client.client_name or client.client_id)
        return RedirectResponse(
            construct_redirect_uri(
                str(pending.params.redirect_uri), code=code, state=pending.params.state
            ),
            status_code=302,
            headers={"Cache-Control": "no-store"},
        )

    def _record_failure(self, now: float) -> None:
        self._failures = [t for t in self._failures if t > now - LOCKOUT_SECONDS] + [now]
        log.warning("owner sign-in failed (%d recent)", len(self._failures))
        if len(self._failures) >= MAX_FAILURES:
            self._locked_until = now + LOCKOUT_SECONDS
            self._failures.clear()
            log.warning("owner sign-in locked for %d s", LOCKOUT_SECONDS)

    # ---- codes and tokens --------------------------------------------------------------

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        code = self._codes.get(authorization_code)
        return code if code is not None and code.client_id == client.client_id else None

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        if self._codes.pop(authorization_code.code, None) is None:
            raise TokenError("invalid_grant", "authorization code already used")
        assert client.client_id is not None
        return self._issue(client.client_id, authorization_code.scopes, authorization_code.resource)

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        record = self._refresh.get(_digest(refresh_token))
        if record is None or record["client_id"] != client.client_id:
            return None
        return RefreshToken(
            token=refresh_token,
            client_id=record["client_id"],
            scopes=record["scopes"],
            expires_at=record["expires_at"],
            subject=OWNER,
        )

    async def exchange_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: RefreshToken, scopes: list[str]
    ) -> OAuthToken:
        # Rotation: the presented refresh token and every access token it minted die here.
        digest = _digest(refresh_token.token)
        record = self._refresh.pop(digest, None)
        if record is None:
            raise TokenError("invalid_grant", "refresh token already used")
        self._drop_access_minted_by(digest)
        assert client.client_id is not None
        return self._issue(client.client_id, scopes, record.get("resource"))

    def _issue(self, client_id: str, scopes: list[str], resource: str | None) -> OAuthToken:
        access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        now = int(time.time())
        refresh_digest = _digest(refresh)
        self._refresh[refresh_digest] = {
            "client_id": client_id,
            "scopes": scopes,
            "expires_at": now + REFRESH_TTL,
            "resource": resource,
        }
        self._access[_digest(access)] = {
            "client_id": client_id,
            "scopes": scopes,
            "expires_at": now + ACCESS_TTL,
            "resource": resource,
            "refresh": refresh_digest,
        }
        self._save()
        return OAuthToken(
            access_token=access,
            token_type="Bearer",
            expires_in=ACCESS_TTL,
            scope=" ".join(scopes),
            refresh_token=refresh,
        )

    def _drop_access_minted_by(self, refresh_digest: str) -> None:
        self._access = {d: r for d, r in self._access.items() if r.get("refresh") != refresh_digest}

    async def load_access_token(self, token: str) -> AccessToken | None:
        if hmac.compare_digest(token.encode(), self._static):
            return AccessToken(token=token, client_id=STATIC_CLIENT_ID, scopes=[SCOPE])
        record = self._access.get(_digest(token))
        if record is None or record["expires_at"] < time.time():
            return None
        # Audience check: a token minted for another resource is not valid here.
        if record.get("resource") and _normalize(record["resource"]) != self._resource:
            return None
        return AccessToken(
            token=token,
            client_id=record["client_id"],
            scopes=record["scopes"],
            expires_at=record["expires_at"],
            resource=record.get("resource"),
            subject=OWNER,
        )

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        digest = _digest(token.token)
        if isinstance(token, RefreshToken):
            refresh_digest: str | None = digest
        else:
            record = self._access.pop(digest, None)
            refresh_digest = record.get("refresh") if record else None
        if refresh_digest:
            self._refresh.pop(refresh_digest, None)
            self._drop_access_minted_by(refresh_digest)
        self._save()


# ---- HTML ----------------------------------------------------------------------------------

_STYLE = """
body{font:16px/1.5 system-ui,-apple-system,sans-serif;max-width:26rem;margin:10vh auto;padding:0 1.25rem;color:#1f2328;background:#f6f8fa}
main{background:#fff;border:1px solid #d0d7de;border-radius:12px;padding:1.5rem}
h1{font-size:1.25rem;margin:0 0 .75rem}p{margin:.5rem 0}
.meta{color:#57606a;font-size:.9rem}.warn{color:#9a6700}.err{color:#cf222e}
input{width:100%;box-sizing:border-box;font:inherit;padding:.6rem .75rem;margin:.75rem 0;border:1px solid #d0d7de;border-radius:8px}
button{width:100%;font:inherit;font-weight:600;padding:.6rem;border:0;border-radius:8px;background:#1f883d;color:#fff}
"""


def _page(body: str, *, status: int = 200) -> HTMLResponse:
    return HTMLResponse(
        f"<!doctype html><meta charset=utf-8>"
        f'<meta name=viewport content="width=device-width,initial-scale=1">'
        f"<title>Second brain</title><style>{_STYLE}</style><main>{body}</main>",
        status_code=status,
        headers=_SECURITY_HEADERS,
    )


def _login_form(
    txn: str,
    client: OAuthClientInformationFull,
    params: AuthorizationParams,
    *,
    error: str | None = None,
    status: int = 200,
) -> HTMLResponse:
    # Client name and redirect URI come from open registration: escape both, and show the
    # redirect host so a sign-in that would not return to Claude is visible (MCP auth spec).
    name = html.escape(client.client_name or "An unnamed client")
    host = urlparse(str(params.redirect_uri)).hostname or "?"
    trusted = host in ("claude.ai", "localhost", "127.0.0.1")
    warning = (
        ""
        if trusted
        else f'<p class=warn>This will not return to claude.ai. Continue only if you expect '
        f"{html.escape(host)}.</p>"
    )
    err = f"<p class=err>{html.escape(error)}</p>" if error else ""
    return _page(
        f"<h1>Allow access to your vault?</h1>"
        f"<p><b>{name}</b> is asking to read and write your notes.</p>"
        f"<p class=meta>Returns to <b>{html.escape(host)}</b></p>{warning}{err}"
        f'<form method=post action="{LOGIN_PATH}">'
        f'<input type=hidden name=txn value="{html.escape(txn)}">'
        f'<input type=password name=password autocomplete=current-password '
        f'placeholder="Passphrase" required autofocus>'
        f"<button type=submit>Allow</button></form>",
        status=status,
    )
