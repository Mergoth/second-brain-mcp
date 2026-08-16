# ADR-0001: Python with uv, pytest, and the MCP Python SDK

Date: 2026-08-16
Status: proposed

## Context

`docs/initial_spec.md` never names a language. The only artifact implying one was
`factory.env`, which was byte-identical to `factory-engine/factory.env.example` — so
`TEST_CMD="pytest -q"` was an unedited template default, not a decision. With nothing
written down, each build round re-decides the stack and the next round decides
differently, against `MAX_ROUNDS="3"`.

The machine constrains the choice: system `python3` is 3.9.6, below the MCP Python SDK's
3.10 floor, and `pytest` is not on PATH. `uv 0.11.27` is installed and can supply the
interpreter.

## Decision

We use Python 3.11+ with the MCP Python SDK for the server, `uv` for dependency and
interpreter management, and pytest for tests. `TEST_CMD` is `uv run --frozen pytest -q`.
`uv.lock` is committed.

The server class is `MCPServer`, from `mcp.server.mcpserver`. This ADR originally said
`FastMCP`; SDK 2.0 removed `mcp.server.fastmcp` entirely, verified 2026-08-16 by import
against the pinned lock. `run(transport="stdio")` is unchanged.

## Consequences

- Makes easy: one server object serves both stdio and streamable-http, so phase 1→2 is an
  entrypoint change rather than a rewrite.
- Forbids: invoking bare `pytest` or system `python3` — both fail, one of them confusingly.
- A build agent must never add a dependency without updating `uv.lock`, because `--frozen`
  fails the whole test command on a stale lock.
- pytest exits 5 on empty collection, so a round that writes source without a test reads as
  a failure. Every round ships at least one test.
