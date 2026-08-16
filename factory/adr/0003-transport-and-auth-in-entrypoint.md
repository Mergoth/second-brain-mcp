# ADR-0003: Transport and auth live in the entrypoint, never in tool code

Date: 2026-08-16
Status: proposed

## Context

`docs/initial_spec.md:60` calls the auth question the single biggest unknown — whether
Claude custom connectors accept a static bearer token, or whether OAuth 2.1 with dynamic
client registration is mandatory scope. It is unresolved and blocks phase 3.

The MCP Python SDK settles where the seam belongs: HTTP-based authorization does not extend
to stdio servers, which lack `Authorization` headers and so never consult a token verifier.
Auth is therefore structurally a property of the HTTP entrypoint, not of a tool.

Deferring the *answer* is fine. Deferring the *seam* is not — retrofitting auth through
five tool modules is the expensive version.

## Decision

`__main__.py` is the only module that selects a transport or wires authentication.
`server.py` builds the FastMCP object and registers tools. Nothing under `tools/` or
`vault/` imports anything transport- or auth-related. Phase 1 runs stdio with no auth;
phase 3 fills in the HTTP entrypoint without touching tool or storage code.

## Consequences

- Makes easy: phase 1→2 becomes a transport flag; phase 3 becomes one new entrypoint module.
- Makes hard: per-tool authorization rules. If those are ever needed they require a new ADR,
  because they would reintroduce the coupling this one removes.
- A build agent must never import transport or auth symbols inside `tools/` or `vault/`, and
  must not read request headers from tool code.
- The auth question stays open. This ADR decides where the answer lands, not what it is.
