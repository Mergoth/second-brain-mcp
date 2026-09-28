# ADR-0005: Reduce the standing credential

Date: 2026-09-28
Status: accepted

## Context

ADR-0004 shipped the owner OAuth server but kept the ADR-0003 static bearer beside it, and a
review of the result found two ways the server holds more standing authority than it needs.

1. `MCP_AUTH_TOKEN` was checked first in `load_access_token` and returned an `AccessToken` with
   neither `expires_at` nor `resource`. The MCP spec requires a server to reject tokens not
   issued for it; the static bearer was the one credential exempt from that check. It also
   never expires and cannot be rotated, so a leak is permanent until someone notices and
   restarts the container with a new value.
2. Refresh rotation was implemented, but rotation alone does not survive theft. Whichever
   holder redeems a stolen token first gets a live pair; the loser's replay is the only thing
   that fails. RFC 9700 requires the reuse signal to revoke the whole chain.

## Decision

The static bearer stays supported but stops being privileged, and refresh reuse is fatal to
the token family.

- `load_access_token` returns the static bearer bound to `resource_url`, so it faces the same
  audience validation as every OAuth token.
- `MCP_AUTH_TOKEN` becomes optional once `MCP_OWNER_PASSWORD` is set (`resolve_static_token`).
  Leaving it unset drops the standing bearer entirely and makes OAuth the only way in. Without
  OAuth it remains mandatory, because it is then the only way in.
- Every token carries a `family`, minted at sign-in and carried across rotations. Spent refresh
  digests are remembered in `consumed` until they would have expired.
- Presenting a spent refresh token revokes every access and refresh token in its family. The
  owner's next call fails and a real sign-in is required — the correct outcome, because at that
  point the chain is known to be compromised.

Detection lives in `load_refresh_token`, not `exchange_refresh_token`: the SDK rejects the grant
as soon as the loader returns `None`, so the exchange method never sees a replay.

## Consequences

- Makes easy: turning the server OAuth-only. Unset `MCP_AUTH_TOKEN` and the standing credential
  is gone; nothing else changes.
- Claude Code loses its header-based path if the token is dropped, so that is left to the owner
  rather than forced here. It is still the weakest credential the server accepts.
- A replayed refresh token now logs the owner out rather than silently leaving two live chains.
  Expected to be rare; if it starts firing, that is the signal it exists to give.
- `oauth-state.json` gains a `consumed` map. Entries are pruned on save once past expiry, so it
  is bounded by the refresh TTL, not by usage.
- State files written before this ADR have no `family`; those records are simply never matched
  by a family revocation. They age out at their own TTL.
