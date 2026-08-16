# HTTP transport and bearer auth

Slug: `vault-http-transport`
Written: 2026-08-16
Brief: `factory/briefs/vault-mcp-server.md`

Increment 2 of 4. Done: `vault-primitives-stdio`. Later: `vault-semantic-tools`, then deployment.

## Problem

The server runs only over stdio, so nothing outside the local process can reach it. Phase 2 of
`docs/initial_spec.md:72` needs Streamable HTTP; phase 3 needs auth. ADR-0003 already puts both in
the entrypoint, so this increment fills that hole without touching `tools/` or `vault/`.

## Solution

A second entrypoint path that serves the same `MCPServer` over Streamable HTTP, with static bearer
token auth and RFC 9728 protected-resource metadata. Plus the container artifacts.

- `auth.py` — NEW. Verifies the `Authorization: Bearer <token>` header against `MCP_AUTH_TOKEN`
  from the environment, in constant time. No default; if the variable is unset the HTTP entrypoint
  refuses to start. Unauthenticated requests get `401` with a `WWW-Authenticate` header carrying
  `resource_metadata`, per RFC 9728.
- `metadata.py` — NEW. Serves `/.well-known/oauth-protected-resource`. Normative if MCP
  authorization is implemented at all, and the piece `docs/initial_spec.md` never mentions.
- `__main__.py` — extended. `--transport stdio|http` (default `stdio`). The **only** module that
  imports either of the two above. Tool and vault code stays untouched.
- `deploy/Dockerfile` — NEW. Non-root, read-only rootfs, `/vault` the only writable mount,
  `ripgrep` installed (it will not be in a slim base image).
- `deploy/compose.yaml` — NEW. Binds the container port to loopback only, never published
  directly (`docs/initial_spec.md:63`).

## Scope

In:
- Streamable HTTP transport over the existing server object
- Static bearer auth, constant-time compare, no default token
- RFC 9728 protected-resource metadata endpoint
- Dockerfile and compose file
- Tests for: auth accept/reject, missing-token startup refusal, 401 carries `WWW-Authenticate`,
  metadata document shape, and that tool behaviour is identical across both transports

Out:
- OAuth 2.1, dynamic client registration, Client ID Metadata Documents. DCR is deprecated
  (ADR-0003 amendment) and a static bearer is accepted by Anthropic's MCP client surfaces.
  Revisit only if a live claude.ai connector test rejects the bearer.
- TLS, DDNS, DSM reverse proxy, Let's Encrypt — those are NAS configuration, not code.
- Rate limiting and IP autoblock — `docs/initial_spec.md:63` puts those in the DSM proxy.
- The semantic tools (increment 3).

## Assumptions

- Static bearer is the auth mode. If the connector UI turns out to demand OAuth, `auth.py` is the
  only module that changes — that is the whole point of ADR-0003.
- The token comes from `MCP_AUTH_TOKEN`, same no-default discipline as `VAULT_PATH`.
- HTTP binds `127.0.0.1` by default. Exposing it is the reverse proxy's job.
- Container runs as a fixed non-root UID. Note `Tasks.md` and `meta/log.md` are mode 600 on the
  real vault, so UID mapping will matter at deploy time — flagged, not solved here.

## Notes

- **The Docker build cannot be verified on this machine right now** — `docker info` reports the
  daemon is not running. Write the Dockerfile and compose file, but treat every Docker-related
  done criterion as unverified until someone starts Docker and runs the build. Do not claim the
  image works. Everything else in this increment is verifiable locally.
- Auth must not be reachable from tool code: `grep` for auth imports under `tools/` and `vault/`
  is a done criterion, enforcing ADR-0003.
- Compare tokens with `hmac.compare_digest`, never `==`.
- The SDK cannot consult a token verifier over stdio at all, so the stdio path stays unauthenticated
  by design. That is not a gap; it is ADR-0003's reasoning.
