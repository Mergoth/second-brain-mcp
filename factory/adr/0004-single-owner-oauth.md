# ADR-0004: Single-owner OAuth authorization server in the HTTP entrypoint

Date: 2026-09-28
Status: accepted

## Context

ADR-0003 left the auth answer open and bet on a static bearer. The live answer, from Anthropic's
connector docs (claude.com/docs/connectors/building/authentication, read 2026-09-28):

- Custom connectors on personal plans authenticate with OAuth (DCR or CIMD) or not at all.
- `static_headers` (a fixed bearer entered once) exists, but only for organization Owners, in a
  beta limited to some organizations. A personal account never sees the field.
- The Claude mobile apps use connectors added on web/Desktop; they share the hosted client and
  the callback `https://claude.ai/api/mcp/auth_callback`.

Authless is not an option: the server reads and writes a personal vault.

## Decision

The HTTP entrypoint runs its own authorization server with exactly one resource owner.

- The MCP SDK (`mcp.server.auth`) implements the protocol: RFC 8414/9728 metadata, open DCR,
  PKCE S256, code and refresh exchange. `oauth.py` implements only the provider:
  a passphrase page (`MCP_OWNER_PASSWORD`) and token storage.
- `/authorize` redirects to `/login`; the correct passphrase mints a single-use code bound to
  the client, redirect URI, PKCE challenge and RFC 8707 resource.
- Access tokens live 1 h; refresh tokens 90 days and rotate on every use — the old pair dies.
- Tokens are persisted only as SHA-256 digests in `$MCP_STATE_DIR/oauth-state.json`, outside
  the vault so they are never synced. Codes and pending logins stay in memory.
- 5 wrong passphrases in 15 min lock sign-in for 15 min; each failure also waits 1 s.
- One scope, `vault`, advertised and granted by default.
- `MCP_AUTH_TOKEN` still verifies as a bearer, so Claude Code keeps working unchanged.
- OAuth is on only when `MCP_OWNER_PASSWORD` is set; then `MCP_STATE_DIR` is required.

`MCP_RESOURCE_URL` must now be the MCP endpoint including `/mcp`: claude.ai requires the
metadata `resource` to equal the URL the user enters.

## Consequences

- Makes easy: the phone app works via a connector added once on claude.ai.
- Registration is open (that is how Claude registers), so it is capped at 50 clients; clients
  holding a live refresh token are never evicted.
- The lockout is global, not per source IP — behind the reverse proxy every request has the
  proxy's address. An attacker can lock the owner out for 15 min; accepted for one user.
- No RFC 7009 revocation endpoint. SDK 2.0.0's revocation model requires `client_secret` even
  for public clients, so Claude's disconnect call would get a 400; advertising a broken
  endpoint is worse than none. Owner-side revoke-all: delete `oauth-state.json`, restart.
  Revisit when the SDK fixes it.
- Still true from ADR-0003: nothing under `tools/` or `vault/` imports auth.
