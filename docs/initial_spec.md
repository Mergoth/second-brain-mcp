
# Second-brain MCP server

Custom remote MCP server on the Synology NAS, exposing this vault's `raw/` and `wiki/` to Claude as a custom connector. Goal: voice capture from Android anywhere, deep work from MacBook, no recurring fees, no third-party copy of the vault.

Related: [[Personal Agent Platform]] · [[Autonomo]]

## Decisions (2026-08-11)

| Question | Decision |
|---|---|
| Exposure | DDNS + HTTPS, public — conditional on the auth story below holding up |
| Tool surface | Both layers: primitives + semantic wrappers |
| Runtime | Container Manager, kept light. No persistent index. |
| Build workflow (2026-08-15) | `~/work/ai-factory` — Claude Code specs, Antigravity `agy` implements. Token cost is the stated reason. |

## Architecture

```
Android / MacBook / claude.ai
        │  HTTPS (DDNS hostname, LE cert)
        ▼
DSM reverse proxy  ──  rate limit, IP autoblock, TLS termination
        ▼
Container: MCP server (Streamable HTTP)
        ▼
Bind mount: /vault  →  PersonalObsidian/  (rw)
```

Synology Drive keeps the same folder in sync with Mac and phone. Server writes to the NAS copy; sync fans out. No second source of truth.

## Tool surface

**Primitives** — thin, no vault knowledge.

| Tool | Notes |
|---|---|
| `list_notes(glob, since?)` | Paths + mtime only, no bodies |
| `read_note(path)` | |
| `write_note(path, content, mode)` | `mode`: create \| overwrite \| append |
| `search_vault(query, scope?)` | ripgrep on demand — no index, per runtime decision |
| `move_note(from, to)` | Archive = move to `raw/archive/`. Never hard-delete. |

**Semantic** — encodes `CLAUDE.md` rules server-side so mobile capture can't misfile.

| Tool | Notes |
|---|---|
| `capture_thought(text, source)` | Writes `raw/thoughts/YYYY-MM-DD-HHMM-slug.md` with correct frontmatter. The voice-while-driving path. |
| `add_task(text, priority?, due?, link?)` | Appends to `Tasks.md` under the right `##` section. Never invents dates. |
| `get_tasks(filter?)` | Parses `Tasks.md`, returns structured + flags overdue |
| `propose_wiki_page(...)` | Drafts into `wiki/`, sets `status: processed` on the source raw file |
| `append_log(line)` | `meta/log.md`, append-only, enforced server-side |

Server owns the invariants CLAUDE.md states as rules: no files at root or bare `raw/`/`wiki/`, lowercase-hyphen folders, append-only log, no hard delete. A rule enforced in code stops being a prompt that can be forgotten.

## Security

Non-negotiable before the DDNS hostname goes live:

1. **Auth.** Claude custom connectors negotiate OAuth 2.1 (dynamic client registration). ⚠️ **Verify first** whether a static bearer token is accepted — if not, an OAuth layer is mandatory scope, not optional. This is the single biggest unknown; it decides whether phase 3 is a day or a week.
2. **TLS.** Let's Encrypt via DSM, auto-renew. DDNS hostname already exists (reused from Home Assistant).
3. **Path confinement.** Every path arg resolved and asserted under `/vault`. Reject symlinks, `..`, absolute paths. The bind mount is the blast radius — keep it to `PersonalObsidian/`, not the whole Notes share. **`EPAM/` must not be reachable** — work material on a public endpoint is a separate risk class.
4. **DSM hardening.** Reverse-proxy rate limit, auto-block on failed auth, firewall the container port to the proxy only. Never publish the container port directly.
5. **Non-root container**, read-only rootfs, `/vault` the only writable mount.
6. **Audit.** Every write appends to `meta/log.md`. An unexplained line is the tripwire.

Prompt-injection note: content in the vault becomes model input. A note that says "call write_note on ../.." is the realistic attack once anything external (articles, forwarded mail) lands in `raw/`. Path confinement in code, not judgment, is what holds here.

## Phases

1. **Local** — server on the Mac, `/vault` pointed at the synced folder, stdio transport. Prove the tool surface against real notes. No network, no Docker, no auth.
2. **Containerize** — same code, Container Manager, Streamable HTTP, LAN only. Watch disk behaviour under Container Manager; this is where the known lag would show.
3. **Expose** — resolve the auth question, then DSM reverse proxy + LE cert + hardening. Register as custom connector. Test from Android.
4. **Semantic layer** — once primitives are stable in daily use. Ordering is deliberate: the semantic tools encode rules, and the rules will change once you've used it for a week.

## Open questions

- Auth mode accepted by Claude custom connectors — blocks phase 3
- ~~Does the existing Claude Code + Antigravity plan/execute setup slot in as the build workflow?~~ **Decided 2026-08-15: yes.** This server is the first job through `~/work/ai-factory` — Claude Code writes the spec, Antigravity `agy` implements, explicitly to save Claude tokens. Design in `raw/articles/AI Factory Claude + Antigravity (agy).md`; repo created 2026-08-15, contents not inspected here. [[lacrimosa]] is researched prior art for the same problem, not Vlad's code.
- Conflict handling if Synology Drive and the server write the same file — the `_DiskStation_..._Conflict` files already in the share say this is real
- Whether `Tasks.md` parsing stays regex or the file moves to a stricter format
