# second-brain-mcp

An MCP server that exposes an Obsidian vault to Claude — read, search, and write notes, capture
voice thoughts into the right folder with the right frontmatter, and manage `Tasks.md`.

Built so the vault's filing rules live in code rather than in a prompt that can be forgotten.

## Status

| Phase | State |
|---|---|
| 1. Local, stdio, five primitives | **Done**, 119 tests |
| 2. HTTP transport + bearer auth | **Done**, verified locally |
| 2b. Container image | **Written but never built** — no Docker daemon on the dev machine |
| 3. Expose via DDNS + reverse proxy | **Not started** — needs NAS access, see [Deployment](#deployment) |
| 4. Semantic tools | **Done** |

## Quick start

Requires [`uv`](https://docs.astral.sh/uv/). Python comes from `uv`; the system `python3` is too old.

```bash
uv sync

# Point at a COPY of your vault first. Never the real one until you trust it.
rsync -a ~/Library/CloudStorage/SynologyDrive-Mergoth/Notes/PersonalObsidian/ /tmp/vault-copy/

VAULT_PATH=/tmp/vault-copy uv run python -m second_brain_mcp
```

That starts the stdio server. It will refuse to start without `VAULT_PATH` — there is no default,
deliberately, because a default is how a test run reaches the real vault.

### Connect it to Claude Desktop

```json
{
  "mcpServers": {
    "second-brain": {
      "command": "uv",
      "args": ["run", "--directory", "/Users/vladislav/work/second-brain-mcp",
               "python", "-m", "second_brain_mcp"],
      "env": { "VAULT_PATH": "/Users/vladislav/work/vault-sandbox/PersonalObsidian" }
    }
  }
}
```

### HTTP transport

```bash
VAULT_PATH=/tmp/vault-copy MCP_AUTH_TOKEN=$(openssl rand -hex 32) \
  uv run python -m second_brain_mcp --transport http
```

Serves on `127.0.0.1:8000`, MCP endpoint at `/mcp`. Every request needs
`Authorization: Bearer <token>`; unauthenticated requests get a `401` with a `WWW-Authenticate`
header pointing at `/.well-known/oauth-protected-resource` (RFC 9728).

## Configuration

All configuration is environment variables. None have defaults.

| Variable | Required for | Notes |
|---|---|---|
| `VAULT_PATH` | always | Absolute path to the vault root. Resolved and frozen at startup; never re-read. |
| `MCP_AUTH_TOKEN` | `--transport http` | Static bearer token. Compared with `hmac.compare_digest`. |

## Tools

### Primitives — no vault knowledge

| Tool | Signature |
|---|---|
| `list_notes` | `(glob="**/*.md", since=None)` — paths and mtimes, no bodies. Excludes dotfiles. |
| `read_note` | `(path)` |
| `write_note` | `(path, content, mode)` — `mode` is `create` \| `overwrite` \| `append` |
| `search_vault` | `(query, scope=None)` — ripgrep. Requires `rg` on PATH. |
| `move_note` | `(from_path, to_path)` — the only removal verb. There is no delete. |

### Semantic — encodes the vault's rules

| Tool | Signature |
|---|---|
| `capture_thought` | `(text, source, domain=None)` — writes `raw/thoughts/YYYY-MM-DD-HHMM-slug.md` with correct frontmatter. The voice-while-driving path. |
| `list_task_sections` | `()` — the `##` headers currently in `Tasks.md`, read live |
| `add_task` | `(text, section, priority=None, due=None, link=None)` |
| `get_tasks` | `(filter=None)` — structured tasks, flags overdue |
| `append_log` | `(line)` — appends to `meta/log.md` verbatim |

**`add_task` requires an explicit `section`** and raises listing the available ones if it doesn't
match. It does not guess and has no default section. This is deliberate: the vault's own
`CLAUDE.md` says *"Sections are a view, not a taxonomy. Re-sort when reality moves"*, so any
hardcoded section table would silently misfile tasks the next time you reorganise. Call
`list_task_sections()` first.

`add_task` never invents a date or priority, and reports back any marker it added that you did not
state.

`capture_thought` rejects a `domain` outside the closed list (`work` `finance` `legal` `health`
`trips` `home` `plants` `smart-home` `projects` `learning`) rather than inventing one.

## Security model

The server is a plain local-filesystem server. Its one real control is **path confinement**.

- Every caller-supplied path becomes a real path in exactly one function,
  `vault/paths.py::resolve()`. Nothing else in the package opens a file by a caller-supplied path.
- The vault root is resolved once at startup and frozen. It is not a tool argument and cannot be
  changed at runtime.
- `resolve()` takes **one** parameter. There is no bypass flag, no per-call root, no trusted-path
  list, no follow-symlinks toggle.
- Containment is checked by path ancestry, never string prefix — with root `/vault`, the sibling
  `/vault-evil` must not pass.
- Rejected: `..`, absolute paths, null bytes, empty paths, and symlinks that resolve outside the
  root *even when the link itself lives inside the vault*.
- Glob patterns and search scopes are validated too, and the search query goes to `rg` after `-e`
  so it can never be parsed as a flag.

That last point is not theoretical. An early build appended the caller's query to `rg` as a bare
positional argument, so a query of `--pre=<script>` executed arbitrary commands — with a
model-controlled argument, which is exactly the prompt-injection threat the design exists to stop.
See `factory/adr/0002-single-path-resolution-chokepoint.md`.

**No hard delete anywhere.** Archiving is `move_note` into `raw/archive/`.

Every mutation appends a line to `meta/audit.log` (machine-readable, append-only). That is
deliberately a different file from `meta/log.md`, which stays human-curated so an unexplained line
in it is still a usable tripwire.

## Development

```bash
uv run --frozen pytest -q     # 119 tests
uv run ruff check .
```

Tests run against a synthetic fixture vault copied into `tmp_path`. An autouse guard fails the
session if the resolved vault root is not under `tmp_path`, so the suite cannot reach a real vault.

Design documents:

- `factory/briefs/vault-mcp-server.md` — why it is built this way, and what was rejected
- `factory/adr/` — binding architecture decisions
- `specs/` — what each increment builds
- `docs/initial_spec.md` — the original design record

## Deployment

Phase 3 is not done. What remains is NAS and browser work, not code:

1. **Fix the advertised metadata URLs first — this is a blocker, not a nicety.**
   `__main__.py` calls `build_auth_settings()` with no arguments, so it advertises the defaults
   `resource_url="http://127.0.0.1:8000"` and `issuer_url="https://auth.example.com"`. Behind a
   reverse proxy those are wrong: a remote client is told the resource lives on loopback. Make both
   read from the environment (e.g. `MCP_RESOURCE_URL`, `MCP_ISSUER_URL`) before exposing anything.
2. Build the container. `deploy/Dockerfile` and `deploy/compose.yaml` are written — non-root user,
   read-only rootfs, `ripgrep` installed, port bound to `127.0.0.1` — but **have never been built
   or run**.
3. Resolve container UID vs. vault file ownership. `Tasks.md` and `meta/log.md` are mode `600` on
   the real vault, so a non-root container with a mismatched UID gets `EACCES` on exactly the two
   highest-value writes while reads of `raw/` keep working — a partial failure that looks like a
   tool bug.
4. DSM reverse proxy, Let's Encrypt cert, rate limit, auto-block on failed auth. Never publish the
   container port directly.
5. Register as a custom connector and test from Android.

### On auth

`docs/initial_spec.md` assumed custom connectors require OAuth 2.1 with dynamic client
registration. That is out of date: **DCR is deprecated** in the current MCP spec (Client ID
Metadata Documents replace it), and static bearer tokens are first-class on Anthropic's MCP client
surfaces. So this ships a static bearer.

The honest caveat: that is evidence about Anthropic's *API* surfaces. Whether the claude.ai
**custom connector UI** accepts a static bearer is a product question that needs a live test. If it
turns out to demand OAuth, `auth.py` is the only module that changes — transport and auth are
confined to the entrypoint by `factory/adr/0003`.

## Known limitations

- The container image is unbuilt and unverified.
- RFC 9728 metadata URLs are hardcoded defaults (see Deployment step 1).
- `list_notes(since)` filters on filesystem mtime, which on a Synology-synced folder is sync time,
  not edit time. The vault's `CLAUDE.md` says `created:` in frontmatter is the real recency anchor.
- No end-to-end test drives a JSON-RPC tool call over HTTP; tools are covered over stdio and via
  direct calls.
- `propose_wiki_page` from the original spec is deliberately not built — its arguments were never
  specified and it serves deep work at the desk, where nothing is blocked.
- Synology sync conflicts are not handled. Writes are atomic (temp file + `os.replace`), but there
  is no merge logic. The original spec cited conflict files as evidence this was urgent; there are
  none in `PersonalObsidian/`, so the risk is real but unproven and was not paid for.
