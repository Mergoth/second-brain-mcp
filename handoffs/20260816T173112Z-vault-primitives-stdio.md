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
