# second-brain-mcp

An MCP server that exposes an Obsidian vault to Claude — read, search, and write notes, capture
voice thoughts into the right folder with the right frontmatter, and manage `Tasks.md`.

Built so the vault's filing rules live in code rather than in a prompt that can be forgotten.

## Status

| Phase | State |
|---|---|
| 1. Local, stdio, five primitives | **Done**, 119 tests |
| 2. HTTP transport + bearer auth | **Done**, verified locally |
| 2b. Container image | **Done** — running on the NAS against a sandbox copy of the vault |
| 3. Expose via DDNS + reverse proxy | **Done** — verified from the public URL |
| 3b. OAuth for claude.ai connectors | **Done** — full flow verified from the public URL; not yet added in claude.ai |
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

All configuration is environment variables.

| Variable | Required for | Notes |
|---|---|---|
| `VAULT_PATH` | always | Absolute path to the vault root. Resolved and frozen at startup; never re-read. No default. |
| `MCP_AUTH_TOKEN` | `--transport http` | Static bearer token. Compared with `hmac.compare_digest`. No default. |
| `MCP_HOST` / `MCP_PORT` | `--transport http` | Bind address. Default `127.0.0.1:8000`; the image sets `0.0.0.0`. |
| `MCP_RESOURCE_URL` | `--transport http` off loopback | The MCP URL exactly as clients enter it, `/mcp` included — claude.ai requires the metadata `resource` to match. Defaults to the bind address only on loopback; otherwise the server refuses to start without it. |
| `MCP_ISSUER_URL` | optional | Authorization server URL. Defaults to the origin of `MCP_RESOURCE_URL`. |
| `MCP_OWNER_PASSWORD` | optional | Turns on the owner OAuth server (claude.ai connectors). The passphrase for the sign-in page; at least 12 characters. |
| `MCP_STATE_DIR` | with `MCP_OWNER_PASSWORD` | Writable directory for OAuth clients and token digests. Keep it outside the vault. |

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

### Running on the NAS (BlackNAS / `mergoth`, DS220+, DSM 7.2.1)

Layout on the NAS, under `/volume1/docker/second-brain-mcp/`:

| Path | What |
|---|---|
| `app/` | `pyproject.toml`, `uv.lock`, `src/`, `deploy/` pushed from this repo |
| `.env` | `VAULT_UID`, `VAULT_GID`, `HOST_VAULT_PATH`, `HOST_STATE_PATH`, `MCP_BIND`, `MCP_PUBLISH_PORT`, `MCP_RESOURCE_URL`, `MCP_AUTH_TOKEN`, `MCP_OWNER_PASSWORD`. Mode `600`. |
| `state/` | `oauth-state.json`: registered clients and SHA-256 digests of tokens. Mode `700`. |
| `vault-sandbox/` | `rsync -a` copy of `/volume1/homes/vlad/Notes/PersonalObsidian` — what the container mounts today |

The vault is owned `1026:100`, so the image is built with `UID=1026 GID=100` (compose passes
`VAULT_UID`/`VAULT_GID` as build args). Hardening: read-only rootfs, `cap_drop: ALL`,
`no-new-privileges`, non-root.

Public endpoint: `https://brain.mergoth.synology.me:1986/mcp`.

```
client → router :1986 → NAS :443 (DSM reverse proxy, TLS, HSTS, read timeout 86400)
       → http://localhost:8765 → container :8000
```

The container publishes on `127.0.0.1:8765` only (`MCP_BIND=127.0.0.1`), so the proxy is the one
way in. `MCP_RESOURCE_URL=https://brain.mergoth.synology.me:1986/mcp` — the external port must be
in it, because the router, not the proxy, maps 1986→443. The certificate is the existing Let's Encrypt
wildcard for `*.mergoth.synology.me`. Do not add a router forward for 8765.

Deploy an update from this repo (DSM intercepts a bare `rsync` over SSH and demands rsync-service
credentials, so wrap it in a shell command):

```bash
rsync -aR --exclude __pycache__ --rsync-path="mkdir -p /volume1/docker/second-brain-mcp/app && rsync" pyproject.toml uv.lock src deploy blacknas.local:/volume1/docker/second-brain-mcp/app/
```

```bash
ssh blacknas.local 'cd /volume1/docker/second-brain-mcp && /usr/local/bin/docker compose --env-file .env -f app/deploy/compose.yaml -p second-brain-mcp up -d --build'
```

### Connecting clients

**claude.ai, Desktop, Android, iOS** — add it once on the web, and the apps pick it up:

1. claude.ai → Customize → Connectors → **+** → *Add custom connector*.
2. URL `https://brain.mergoth.synology.me:1986/mcp`. Leave *Advanced settings* empty — Claude
   registers itself (DCR).
3. *Connect* opens the server's sign-in page. Enter `MCP_OWNER_PASSWORD`; you are sent back to
   Claude. Get the passphrase with
   `ssh blacknas.local 'grep ^MCP_OWNER_PASSWORD= /volume1/docker/second-brain-mcp/.env'`.

**Claude Code** — sends the static bearer as a header, no sign-in:

```bash
claude mcp add --transport http second-brain https://brain.mergoth.synology.me:1986/mcp --header "Authorization: Bearer <MCP_AUTH_TOKEN>"
```

**Revoke everything** (lost phone, leaked passphrase): change `MCP_OWNER_PASSWORD` in `.env`,
delete `state/oauth-state.json`, recreate the container. Every client must sign in again.

### What remains

1. Switch `HOST_VAULT_PATH` to the real vault once the sandbox has earned trust. Turn on a Btrfs
   snapshot schedule for the `homes` share first — the real vault has no git and no snapshots.
2. Add the connector in claude.ai and use it from Android.

### On auth

`docs/initial_spec.md` assumed custom connectors need OAuth, and ADR-0003 bet on a static bearer
instead. Anthropic's connector docs settled it (see `factory/adr/0004`): on personal plans a
custom connector authenticates with OAuth or not at all; fixed request headers are an
Owner-only beta for some organizations. So the HTTP entrypoint runs a single-owner OAuth server
(`oauth.py`) on top of the MCP SDK's protocol handlers, and keeps the static bearer for Claude
Code. Transport and auth are still confined to the entrypoint (ADR-0003).

## Known limitations

- Verified end to end through the public URL, including the full OAuth flow (DCR, sign-in, code
  exchange, refresh rotation). Not yet exercised by claude.ai itself.
- No token revocation endpoint: MCP SDK 2.0.0's revocation handler rejects public clients.
  Access tokens expire in an hour; revoke-all is deleting the state file (above).
- `list_notes(since)` filters on filesystem mtime, which on a Synology-synced folder is sync time,
  not edit time. The vault's `CLAUDE.md` says `created:` in frontmatter is the real recency anchor.
- No end-to-end test drives a JSON-RPC tool call over HTTP; tools are covered over stdio and via
  direct calls.
- `propose_wiki_page` from the original spec is deliberately not built — its arguments were never
  specified and it serves deep work at the desk, where nothing is blocked.
- Synology sync conflicts are not handled. Writes are atomic (temp file + `os.replace`), but there
  is no merge logic. The original spec cited conflict files as evidence this was urgent; there are
  none in `PersonalObsidian/`, so the risk is real but unproven and was not paid for.
