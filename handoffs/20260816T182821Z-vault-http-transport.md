# Handoff: vault-http-transport

Spec: `specs/vault-http-transport.md`
Created: 20260816T182821Z

## Goal

Serve the existing MCPServer over Streamable HTTP with static bearer auth and RFC 9728
protected-resource metadata, plus container artifacts. Transport and auth live only in the
entrypoint — `tools/` and `vault/` are not touched. All 70 existing tests keep passing.

Read `factory/adr/0003` first, including its 2026-08-16 auth-research amendment — it decides
this build. Conventions are in `factory/context.md`; module breakdown is in the spec.

Difficulty: normal
<!-- the seam already exists from increment 1; this fills it. Auth comparison and the 401
     challenge shape are the parts to get exactly right. -->

## Files to touch

- `src/second_brain_mcp/auth.py` - NEW. Bearer verification, `hmac.compare_digest`, `MCP_AUTH_TOKEN`, no default.
- `src/second_brain_mcp/metadata.py` - NEW. RFC 9728 protected-resource document.
- `src/second_brain_mcp/__main__.py` - extend with `--transport stdio|http`, default stdio. Only importer of the two above.
- `deploy/Dockerfile`, `deploy/compose.yaml` - NEW. Non-root, read-only rootfs, `/vault` the only writable mount, `rg` installed, port bound to loopback.
- `tests/test_auth.py`, `tests/test_metadata.py`, `tests/test_transport.py` - NEW.

## Tests to run

```
uv run --frozen pytest -q
```

Must pass — all 70 existing tests, plus:
- `test_rejects_missing_bearer`
- `test_rejects_wrong_bearer`
- `test_accepts_correct_bearer`
- `test_http_refuses_to_start_without_auth_token`
- `test_401_carries_www_authenticate_resource_metadata`
- `test_protected_resource_metadata_lists_authorization_servers`
- `test_stdio_still_works_without_auth`

## Done criteria

- [ ] `uv run --frozen pytest -q` exits 0 and collects more than the previous 70 tests
- [ ] `grep -rniE "auth|bearer|token|http|transport" src/second_brain_mcp/tools/ src/second_brain_mcp/vault/` returns no matches (ADR-0003)
- [ ] `grep -rn "MCP_AUTH_TOKEN" src/` shows it only in `auth.py`, with no default value
- [ ] `grep -rn "compare_digest" src/second_brain_mcp/auth.py` matches; `grep -n "== *token\|token *==" src/second_brain_mcp/auth.py` does not
- [ ] `uv run python -m second_brain_mcp --transport http` with `MCP_AUTH_TOKEN` unset exits non-zero with a named error
- [ ] `deploy/Dockerfile` contains a `USER` line that is not root and installs `ripgrep`
- [ ] `deploy/compose.yaml` binds the port to `127.0.0.1` only
- [ ] Default transport is still stdio when `--transport` is omitted

**Docker is NOT verifiable here** — `docker info` reports the daemon is down. Write the artifacts,
do not claim the image builds, and say so in the walkthrough under `not covered`.

---

<!-- factory-check appends "## Check <timestamp>" blocks below this line -->

## Check 20260816T183340Z

Status: Needs fix
Tests: 70 passed in 0.80s — **unchanged from the previous increment; zero tests were added**
Walkthrough: absent
Round: 1, model claude-opus-4-6-thinking

**The run was truncated and still exited 0.** `handoffs/logs-20260816T182841Z-vault-http-transport.txt`
ends mid-sentence at "Now create the deploy files:" with no `RESULT:`, no `CHANGED:`, and no
`WALKTHROUGH:` block, yet the log records `agy exit code: 0`. PRINCIPLES #3 exactly — the run,
not the report, is the evidence.

Done criteria:
- [ ] **FAILED** — test count is 70, identical to before; the criterion requires more than 70
- [ ] **FAILED** — none of the 7 named tests exist. `tests/test_auth.py`, `tests/test_metadata.py`,
      `tests/test_transport.py` were never created
- [x] transport/auth absent from `tools/` and `vault/` — grep clean, ADR-0003 holds
- [x] `MCP_AUTH_TOKEN` only in `auth.py`, no default
- [x] `hmac.compare_digest` present at `auth.py:35`; no naive `==` comparison
- [x] `--transport http` with `MCP_AUTH_TOKEN` unset exits **1** with a named `ConfigError`
- [x] `deploy/Dockerfile` has `USER mcp` and installs `ripgrep`
- [x] `deploy/compose.yaml` binds `127.0.0.1:8000:8000`, `read_only: true`
- [x] default transport is still stdio

What I verified by hand, since agy produced no report:
- `StaticBearerVerifier` accepts the correct token, rejects a wrong one, rejects empty
- `__main__.py` lazy-imports `auth` and `metadata` only on the HTTP path, keeping ADR-0003 intact
- The SDK supplies the `/.well-known/oauth-protected-resource` route and the `WWW-Authenticate`
  challenge; `metadata.build_auth_settings` configures it rather than reimplementing it

So the **code looks right and is untested**. That is the whole failure: nothing here is proven by a
test, and a passing suite that never exercises auth is not evidence auth works.

Red flags:
- Truncated run reporting success (above). Not agy's code quality — its output was cut off.
- No other red flags: `specs/` and `factory-engine/` untouched, no tests deleted or weakened, no
  secrets or absolute local paths added.

### Next fix

Write only the tests — the source files from round 1 are correct, do not rewrite them.

- `tests/test_auth.py`: `test_accepts_correct_bearer`, `test_rejects_wrong_bearer`,
  `test_rejects_missing_bearer`, `test_http_refuses_to_start_without_auth_token`. Drive
  `StaticBearerVerifier` directly with `asyncio` / `anyio`; it is an async `verify_token`.
- `tests/test_metadata.py`: `test_protected_resource_metadata_lists_authorization_servers` —
  assert on what `metadata.build_auth_settings()` returns.
- `tests/test_transport.py`: `test_401_carries_www_authenticate_resource_metadata` and
  `test_stdio_still_works_without_auth`. Use `starlette.testclient.TestClient` over the app from
  `server.create_server(...).streamable_http_app()` — TestClient is already available; the project
  has `httpx2`, not `httpx`, so do not add an httpx dependency.
- Do not add dependencies. If you believe one is needed, stop and say so instead of editing
  `pyproject.toml`.
- Docker remains unverifiable on this machine (daemon down) — do not write a test that runs a build.

## Check 20260816T183723Z

Status: Success
Tests: 81 passed in 0.92s (70 -> 81, 11 added, none removed or weakened)
Walkthrough: n/a — round 2 was scoped to tests; judged on the diff and my own runs
Round: 2, model claude-opus-4-6-thinking

All 7 named tests exist and pass. Source files from round 1 were left alone as instructed, and
no dependency was added — `pyproject.toml` and `uv.lock` are unmodified.

Verified by execution rather than by reading the tests, because the round-1 assertions would also
pass on a server that 401s everything:
- no token -> **401**; wrong token -> **401**; **correct token passes auth** (reaches the MCP
  session manager and returns 421 for a protocol reason, not 401)
- `/.well-known/oauth-protected-resource` -> **200**, body
  `{"resource": ..., "authorization_servers": [...], "bearer_methods_supported": ["header"]}` —
  the RFC 9728 shape the source spec never mentioned
- `--transport http` with `MCP_AUTH_TOKEN` unset exits **1** with a named `ConfigError`

Done criteria: all met. ADR-0003 holds — `grep -rniE "auth|bearer|token|http|transport"` over
`tools/` and `vault/` returns nothing; `__main__.py` lazy-imports `auth` and `metadata` on the
HTTP path only.

Red flags: none. No tests skipped or weakened (no `skip`/`xfail` in the new files), `specs/` and
`factory-engine/` untouched, no secrets or absolute local paths added.

Not covered, honestly:
- **The Docker image is unbuilt and unverified** — the daemon is down on this machine. `Dockerfile`
  and `compose.yaml` are written and statically correct (`USER mcp`, `ripgrep` installed,
  `read_only: true`, port bound to `127.0.0.1`) but nothing has run them.
- Container UID vs. the real vault's mode-600 `Tasks.md` and `meta/log.md` is still unresolved and
  will bite at deploy time.
- No test drives a full JSON-RPC tool call over HTTP end to end; tools are covered over stdio.
