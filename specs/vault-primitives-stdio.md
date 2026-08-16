# Vault primitives over stdio

Slug: `vault-primitives-stdio`
Written: 2026-08-16
Brief: `factory/briefs/vault-mcp-server.md`

Increment 1 of 4. Later: `vault-containerize`, `vault-expose-auth`, `vault-semantic-tools`.

## Problem

There is no code in this repo — `git log` fatals with "does not have any commits yet".
`docs/initial_spec.md` describes a five-primitive, five-semantic-tool MCP server across
four phases, but nothing exists to run, and the filing rules the server is meant to
enforce live as prose in the vault's `CLAUDE.md`.

## Solution

A Python MCP server exposing the five primitives from `docs/initial_spec.md:36-42` over
stdio, built around a single path-resolution chokepoint that every filesystem access
passes through. Layout is chosen so that later phases change the entrypoint, not the
tools: transport and auth live in `__main__.py` alone, because the MCP Python SDK cannot
consult a token verifier over stdio at all.

Modules:

- `config.py` — reads `VAULT_PATH` from the environment **once at startup**, resolves it to
  a real path, and freezes it. **No default.** Server refuses to start if unset, missing, or
  not a directory. The root is never re-read and is not settable after startup.
- `vault/paths.py` — `resolve(user_path) -> Path`. The only place a caller-supplied path
  becomes a real path. Fully resolves symlinks, then asserts the result is inside the frozen
  root by **path ancestry, not string prefix** (root `/vault` must not admit `/vault-evil`).
  Rejects `..`, absolute paths, null bytes, and empty paths. Takes **no options** — no
  bypass flag, no trusted-path list, no follow-symlinks toggle, no per-call root. A symlink
  inside the vault pointing outside it is rejected. Both ends of `move_note` are resolved
  independently.
- `vault/store.py` — list, read, write, move, search over already-resolved paths. Writes
  are atomic (temp file in the same directory, then `os.replace`). Every mutation appends
  one line to the machine audit file.
- `vault/audit.py` — append-only machine audit in a strict parseable format, to its own
  file. `meta/log.md` is human-curated and is **not** written by this increment.
- `vault/conventions.py` — pure string functions, no I/O: slug from text, timestamped
  filename, frontmatter rendering. Not wired to any tool yet; it exists and is unit-tested
  now so `vault-semantic-tools` is registration over proven code.
- `tools/primitives.py` — thin MCP tool adapters. They call `store`, never each other.
- `server.py` — builds the FastMCP object, registers tools.
- `__main__.py` — chooses transport. stdio only in this increment.

## Scope

In:
- `list_notes(glob, since?)` — paths + mtime only, no bodies. Excludes dotfiles/dotdirs.
- `read_note(path)`
- `write_note(path, content, mode)` — `create` | `overwrite` | `append`
- `search_vault(query, scope?)` — ripgrep subprocess, with a timeout and a clean error
  when `rg` is absent
- `move_note(from, to)` — the only removal verb. No `unlink` anywhere in the package.
- The `resolve()` chokepoint and its adversarial test table
- A plain local-filesystem backend. No storage abstraction, no network or cloud backend.
- `vault/conventions.py` as tested pure functions
- A committed fixture vault under `tests/fixtures/vault/`

Out:
- HTTP transport, Docker, auth, TLS, reverse proxy (increments 2 and 3)
- All five semantic tools (increment 4)
- `meta/log.md` writes — the human file stays untouched
- Any conflict-resolution logic for Synology Drive — the evidence for that risk is
  misattributed in the source spec; see the brief's Persona notes. Atomic writes only.
- A validator built literally from the vault's `CLAUDE.md` — the real vault violates its
  own "root holds two files only" rule today (`.DS_Store`, `.obsidian/`, `.claude/`).

## Assumptions

- `VAULT_PATH` points at a **throwaway copy** for the first hand-run. Tests never touch it.
- Python 3.11+, `uv`, pytest. Forced by `factory.env` and the MCP SDK's 3.10 floor.
- The fixture vault is hand-written but mirrors the real structure: the real emoji `##`
  headers in `Tasks.md`, obsidian-tasks-plugin syntax (`⏫` `🔼` `📅` `✅`), both existing
  `meta/log.md` line shapes, `.obsidian/` and `.DS_Store` present so exclusion is tested.
- `list_notes(since)` uses filesystem mtime and is documented as sync-time, not edit-time,
  on a Synology-synced folder.
- Confinement rejects everything outside the vault root, absolutely and with no runtime
  opt-out (Vlad, 2026-08-16). Sibling trees (`EPAM/`, `copilot-conversations/`) are archive
  and not the driving threat, but one regression test keeps the boundary honest.
- "Pre-configured root" is read as: `VAULT_PATH` from the environment, resolved and frozen
  at startup, with no default and no way to change it afterwards. Not a literal path
  constant in source — a constant would have to be edited between the test vault, the
  throwaway copy, and the container's `/vault` bind mount, and would make the tmp_path test
  fixture impossible. The confinement is what is hardcoded; the root is what is configured.

## Notes

- **`factory/context.md` and `factory.env` were fixed as part of this spec.** `context.md`
  previously carried the `factory:template` marker, and `run_antigravity.sh:90-92` silently
  drops template files — the build agent would have received no stack, no commands, no
  conventions.
- `TEST_CMD` is `uv run --frozen pytest -q`. Plain `pytest` is not on PATH and system
  python3 is 3.9.6, below the SDK floor. `uv` is at `/Users/vladislav/.local/bin/uv`; if it
  is not on the build agent's PATH the round fails looking like a code error.
- **pytest exits 5 on empty collection.** A round that writes source but no test file reads
  as a failed round. At least one real test must exist.
- The fixture vault must include a symlink pointing outside itself. Git stores symlinks
  fine, but the test must skip cleanly on a filesystem that cannot create one.
- `rg` is at `/opt/homebrew/bin/rg` here and will not exist in a slim container later.
  Keep the subprocess call behind `store` so it stays swappable.
