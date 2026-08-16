# Project context

caveman: how this project works. every build agent reads this. keep it short,
keep it true. a stale line here is worse than no line.

## Stack

- language / runtime: Python 3.11+ (system python3 is 3.9.6 — do NOT use it; `uv` provides the interpreter)
- framework: MCP Python SDK (FastMCP)
- package manager: `uv` (at `/Users/vladislav/.local/bin/uv`)

## Commands

- install: `uv sync`
- test: `uv run --frozen pytest -q`
- lint / typecheck: `uv run ruff check .`
- run locally: `VAULT_PATH=/Users/vladislav/work/vault-sandbox/PersonalObsidian uv run python -m second_brain_mcp`
  (that path is a throwaway copy of the real vault, made 2026-08-16 — safe to write to and
  safe to delete. Re-make it with `rsync -a` from the real vault if it drifts.)

## Layout

- `src/second_brain_mcp/` — the package, `src`-layout. `config.py`, `errors.py`, `server.py`,
  `__main__.py`, plus `vault/` (paths, store, audit, conventions) and `tools/`.
- `tests/` — pytest. `conftest.py` holds the vault fixture and the safety guard.
- `tests/fixtures/vault/` — committed synthetic vault, mirrors the real structure. Must contain
  a symlink pointing outside itself; skip that test cleanly where symlinks cannot be created.
- `docs/initial_spec.md` — the original design record. Source of truth for intent, not for detail.
- `specs/` and `factory/adr/` — what to build and the rules that bind it. ADRs are not advisory.

## Conventions

- Every caller-supplied path goes through `vault/paths.py::resolve()`. Nothing else in the
  package calls `open()`, `Path()`, or `os.*` on a path that came from a tool argument.
- Confinement to the vault root is absolute and has no runtime opt-out. `resolve()` takes no
  bypass flag, no per-call root, no trusted-path list. Containment is checked by path
  ancestry against the resolved root — never `startswith`, since root `/vault` would
  otherwise admit the sibling `/vault-evil`. See ADR-0002.
- The vault root is resolved and frozen once at startup in `config.py` and read from the
  environment nowhere else.
- Writes are atomic: temp file in the same directory, then `os.replace`. Never open-truncate.
- No hard delete. There is no `unlink`/`os.remove`/`shutil.rmtree` anywhere in the package.
  Removal is `move_note` into `raw/archive/`.
- Config comes from environment variables only. `VAULT_PATH` has **no default** — the server
  refuses to start without it. A default is how a test run reaches the real vault.
- Transport and auth live in `__main__.py` only — never imported under `tools/` or `vault/`.
  See ADR-0003.
- Tools are thin adapters. They call `store`, never each other. `vault/conventions.py` is pure
  string functions with no I/O — no `os`, no `pathlib`, no `open`.
- Errors are explicit exception types, not bare `ValueError`. A rejected path must say why.
- A good test here is table-driven over the fixture vault copied into `tmp_path`. Tests never
  touch a real path on this machine.

## Gotchas

- `pytest -q` exits **5** on empty collection, which reads as a failed round. Always ship a test.
- `run_antigravity.sh:90` greps each brain file for the unfilled-template marker and silently
  drops any file containing it. Never let that marker string appear in this file or memory.md —
  not even inside a quoted example, since the grep does not care about context.
- The real vault is at `~/Library/CloudStorage/SynologyDrive-Mergoth/Notes/PersonalObsidian/`.
  It is **not** under git and has no verified restore path. Never point tests or a build run at it.
- That path is a macOS File Provider mount, not a plain directory — `realpath` and mtime behave
  differently there than on the NAS bind mount used later.
- `rg` (`/opt/homebrew/bin/rg`) exists on this Mac but will not exist in a slim container.
