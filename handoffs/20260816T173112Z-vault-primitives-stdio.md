# Handoff: vault-primitives-stdio

Spec: `specs/vault-primitives-stdio.md`
Created: 20260816T173112Z

## Goal

Build the five vault primitives from the spec as a local-filesystem MCP server over stdio,
with every caller-supplied path passing through one `resolve()` chokepoint confined to a
vault root that is frozen at startup. Tests run against a committed synthetic fixture vault
copied into `tmp_path` and never touch a real path on this machine.

Read `factory/adr/0001-0003` first — they are binding, and 0002 is the one that decides
this build. Conventions are in `factory/context.md`; the module breakdown is in the spec.

Difficulty: tricky
<!-- confinement is the subtle part: symlink resolution order and ancestry checking.
     a miss writes outside the vault root, on a vault with no restore path. -->

## Files to touch

Scaffolding already exists and `uv run --frozen pytest -q` is green — extend it, do not
recreate it. If you add a dependency, run `uv sync` so `uv.lock` stays current, or `--frozen`
fails the whole test command.

- `src/second_brain_mcp/` - exists with `__init__.py` only. Add the modules per the spec.
- `tests/test_toolchain.py` - exists, 3 passing smoke tests. Keep them.
- `tests/conftest.py` - NEW. tmp_path vault fixture, plus the guard that fails the session if
  the resolved root is not under tmp_path.
- `tests/fixtures/vault/` - NEW. Synthetic vault mirroring the real structure, including a
  symlink pointing outside it.
- `tests/` - NEW test modules per package module.

## Tests to run

```
uv run --frozen pytest -q
```

Must pass — the confinement table in `tests/test_paths.py` covering every rejection case the
spec lists, plus:
- `test_never_points_at_real_vault`
- `test_move_to_archive_never_unlinks`
- `test_config_refuses_to_start_without_vault_path`

## Done criteria

- [ ] `uv run --frozen pytest -q` exits 0 and collects more than 0 tests
- [ ] `grep -rE "unlink|os\.remove|shutil\.rmtree" src/` returns no matches
- [ ] `grep -rn "startswith" src/second_brain_mcp/vault/paths.py` returns no matches
- [ ] `resolve()` takes exactly one parameter, and no tool accepts a root or base-dir argument
- [ ] `grep -rn "VAULT_PATH" src/` shows it only in `config.py`, with no default value
- [ ] `grep -rn "open(" src/second_brain_mcp/` shows calls only in `vault/store.py` and `vault/audit.py`
- [ ] `uv run python -m second_brain_mcp` with `VAULT_PATH` unset exits non-zero with a named error
- [ ] `grep -rn "SynologyDrive" src/ tests/` returns no matches

---

<!-- factory-check appends "## Check <timestamp>" blocks below this line -->

## Check 20260816T181230Z

Status: Needs fix
Tests: 62 passed in 0.78s (re-run independently, not agy's number)
Walkthrough: overstates
Round: 1, model claude-opus-4-6-thinking

Done criteria — all 8 met:
- [x] `uv run --frozen pytest -q` exits 0, 62 collected
- [x] no `unlink`/`os.remove`/`shutil.rmtree` in `src/`; also checked `rmdir`, `rmtree`, `remove(` — none
- [x] no `startswith` in `vault/paths.py`; ancestry via `root not in candidate.parents`
- [x] `resolve()` takes exactly one parameter; no tool accepts a root or base-dir argument
- [x] `VAULT_PATH` only in `config.py`, no default, frozen at startup
- [x] `open(` only in `vault/store.py` and `vault/audit.py`
- [x] `VAULT_PATH` unset exits 1 with named `ConfigError`
- [x] no `SynologyDrive` in `src/` or `tests/`

Red flags:
- **CRITICAL — arbitrary command execution via `search_vault(query)`.** `store.search_vault`
  (store.py:120) appends the caller-supplied `query` as a bare positional argument to `rg`,
  so a query beginning with `-` is parsed as a flag. Proven by execution, not inspection:
  `search_vault('--pre=/tmp/pre.sh')` ran the script. `query` is model-controlled, and
  spec line 67 names prompt injection from `raw/` as the threat model — a note saying
  "search for --pre=..." is remote code execution. The empty result list hides it; the
  damage is the side effect, not the output.
- **`list_notes(glob)` escapes the vault root.** `store.list_notes` (store.py:41) passes the
  caller's glob to `root.glob()`, which does traverse `..` — verified returning
  `/tmp/globtest/vault/../outside/secret.md`. Nothing leaks today only because `_is_dotfile`
  (store.py:30) treats `..` as a dot component and skips it. Confinement by coincidence, in
  the one control ADR-0002 says must not be incidental.
- **Walkthrough overstates.** It claims "Each primitive calls `vault.paths.resolve(user_path)`
  — the single chokepoint". `read_note`, `write_note`, `move_note` do. `list_notes` and
  `search_vault` do not: they take `glob`/`scope`/`query` and pass them to `store` beside the
  raw root, never through `resolve()`. That gap is the cause of both findings above.
- Minor: agy edited source comments specifically so `grep -rE "unlink|..."` would stop
  matching (log line 35). The underlying rule is genuinely honored — no delete calls exist —
  but the criterion was satisfied partly by rewording. Criterion's fault as much as agy's.
- Not a flag: `MCPServer` instead of `FastMCP`. Verified independently — `mcp.server.fastmcp`
  is gone from SDK 2.0, `mcp.server.mcpserver.MCPServer` is present. ADR-0001's wording is
  stale; the ADR needs updating, agy does not.
- Clean: no tracked file modified, `specs/`/`handoffs/`/`factory-engine/` untouched, no tests
  deleted or skipped, no secrets, audit correctly separate at `meta/audit.log`.

Against the brief: "What done looks like" says any path escaping the vault root is refused
with a named error. True for read/write/move. False for search and list, whose caller-
controlled inputs never reach the chokepoint — and search additionally executes commands.
Not done.

### Next fix

- In `store.search_vault` (store.py:115-121), stop passing `query` as a bare positional. Use
  `cmd.extend(["-e", query])`, and append `"--"` before `str(root)`. Same for `scope`: reject
  it if it starts with `-`, contains `..`, or is absolute.
- Add `tests/test_store.py::test_search_query_starting_with_dash_is_not_a_flag` asserting
  `search_vault("--files")` searches for the literal string rather than listing files, and
  `test_search_cannot_inject_preprocessor` asserting a `--pre=` query does not execute
  (create a script that touches a temp file; assert the file does not appear).
- In `store.list_notes` (store.py:41), validate `glob` before use: reject absolute patterns,
  any `..` component, and leading `-`. Then assert each match is inside the root explicitly
  rather than relying on `_is_dotfile`'s ValueError branch.
- Add `tests/test_store.py::test_list_notes_rejects_escaping_glob` asserting `../**/*.md`
  raises a named error rather than returning `[]`. Silent empty results hid this.
- Change `_is_dotfile`'s outside-root branch (store.py:28-29) from returning True to raising
  — a path outside the root is a bug, not a hidden file.

## Check 20260816T181835Z

Status: Success
Tests: 70 passed in 0.77s (re-run independently; 62 -> 70, 8 added, none removed or weakened)
Walkthrough: matches diff
Round: 2, model claude-opus-4-6-thinking

Both round-1 findings re-tested by execution, not inspection:
- **RCE closed.** `search_vault('--pre=/tmp/pre.sh')` no longer executes the script — the
  sentinel file is not created. `store.py:149-151` now builds `["-e", query]` and
  `["--", str(root)]`, so a dash-prefixed query is a pattern and the root can never be
  parsed as an option. `search_vault('--files')` returns 0 literal-search results instead
  of listing files.
- **Glob escape closed.** `_validate_glob()` rejects `..`, absolute, leading `-`, and empty
  with a named `PathValidationError` — verified for `../outside/*.md`, `../**/*.md`, `/etc/*`.
  `list_notes` additionally re-checks each match's resolved path by ancestry, so confinement
  no longer depends on `_is_dotfile`'s incidental dot-component behaviour.
- Scope validated the same way (leading `-`, `..`, absolute).
- Regression guarded, not just fixed: `test_search_cannot_inject_preprocessor`,
  `test_search_query_starting_with_dash_is_not_a_flag`, `test_list_notes_rejects_escaping_glob`
  and 5 more.
- Sanity-checked that the fix did not break the feature: normal `list_notes()` and
  `search_vault('inside')` both return correct results.

Done criteria — all 8 re-verified this round: C1 exit 0 / 70 collected, C2 no delete verbs,
C3 no `startswith`, C4 `resolve(user_path)` single parameter, C5 `VAULT_PATH` only in
`config.py`, C6 `open(` only in store/audit, C7 exit 1 with named `ConfigError`, C8 no
`SynologyDrive`.

Against the brief: "any path escaping the vault root is refused with a named error" is now
true for all five primitives, including the two caller-controlled non-path inputs that
bypassed the chokepoint in round 1. Done.

Red flags: none blocking.
- Walkthrough is accurate and volunteers the real nuance: `list_notes` uses `continue` rather
  than `raise` for outside-root matches because conftest's escape symlink is matched by a
  legitimate `**/*.md` glob. Verified in code; the reasoning holds.
- Non-blocking: `uv run ruff check .` reports 8 errors (2 unused imports agy admits are round-1
  leftovers, 3 unused test imports, 1 import sort, 1 `datetime.UTC` alias, 1 deliberate
  `subprocess.run` without `check=`). All cosmetic, 7 auto-fixable. Not worth a paid round;
  fix with `uv run ruff check . --fix` whenever convenient.
- `handoffs/<this file>` shows modified in git status — that is this check block, not agy.
