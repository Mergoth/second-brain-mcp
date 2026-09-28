# ADR-0006: Where owner identity comes from

Date: 2026-09-28
Status: proposed — records the options and the ranking, defers the choice

## Context

ADR-0004's owner check is one passphrase comparison. Everything else in `oauth.py` is plumbing
around it. That makes `MCP_OWNER_PASSWORD` the whole security boundary: a single shared secret,
no second factor, and a global lockout that an attacker can trip to deny the owner service.

The obvious idea — let Claude authenticate the owner, since the owner is already signed in to
claude.ai — does not work, and it is worth writing down why so it is not proposed again. The MCP
authorization spec assigns three roles: the MCP server is the resource server, the MCP client is
an OAuth client, and the authorization server issues tokens. Claude is the party *requesting*
authority. It never asserts identity to the server: no ID token, no signed claim about the human.
Anthropic is not an identity provider for third-party MCP servers. An inbound `/authorize` is an
anonymous browser hit, which is exactly why an owner check has to exist there at all.

A second fact constrains every network answer: the connection to a custom connector originates
from Anthropic's cloud, not from the user's device, on claude.ai, Desktop and mobile alike. A
server reachable only over a tailnet or VPN cannot be a connector at any tier. Public
reachability is a requirement, not a deployment style.

The passphrase can still be replaced by delegating authentication to a real identity provider.
The integration shape is the same whichever is chosen — redirect instead of rendering
`_login_form`, add a callback that verifies the assertion, check the identity against an
allowlist of one, resume at the existing code-minting path — so this is not a lock-in decision.

## Options

- **Synology SSO Server (DSM 7.2+).** OIDC provider on the box that already holds the vault and
  terminates TLS for it. No new domain, no new port, no new failure mode: if the NAS is down
  there is nothing to authorize. Costs exposing DSM's SSO endpoints publicly, which is a larger
  attack surface than a single passphrase page on a product line that is actively targeted.
- **Google or GitHub OIDC.** Strongest authentication and no self-hosted login surface, but adds
  an external dependency that can fail independently of the vault it guards.
- **Cloudflare Access.** Hardened edge, exposes nothing of DSM. Expensive *here* specifically:
  `mergoth.synology.me` is Synology's zone and cannot be delegated to Cloudflare, so it requires
  buying a domain; and Cloudflare's proxy does not carry port 1986, so the router forward, the
  DSM proxy entry, `MCP_RESOURCE_URL` and the registered connector URL all change.
- **Tailscale / VPN-only.** Rejected on the fact above: Anthropic's servers could not reach it.

## Decision

Deferred. The passphrase stays for now. Recorded ranking, cheapest first:

1. Restrict `/mcp`, `/token` and `/register` to Anthropic's published egress ranges at the DSM
   firewall, leaving `/authorize` and `/login` open because those are hit by the owner's browser.
   No code, no new infrastructure, and it removes the internet's reach to the token endpoints.
2. Synology SSO Server as IdP.
3. Cloudflare Access.

ADR-0005 is the prerequisite either way: swapping the passphrase for an IdP while a permanent,
audience-exempt bearer still exists would harden the front door and leave the back one open.

## Consequences

- The lockout DoS in ADR-0004 survives until an IdP lands; it is a denial-of-service on the
  owner, not a path in, so it is tolerable but not permanent.
- Whichever IdP is chosen, verify the discovery document first. DSM's OIDC implementation is
  minimal and third-party integrations report friction around scopes and claims — confirm a
  stable subject claim before writing the callback.
- A DSM OIDC `client_secret` would live on `/volume1`, where ACLs override umask (factory
  memory). Check the mode after writing it rather than trusting the umask.
