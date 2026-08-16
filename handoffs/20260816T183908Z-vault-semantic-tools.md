# Handoff: vault-semantic-tools

Spec: `specs/vault-semantic-tools.md`
Created: 20260816T183908Z

## Goal

Five semantic tools — `capture_thought`, `list_task_sections`, `add_task`, `get_tasks`,
`append_log` — that encode the vault's filing rules in code instead of prose. They compose
`vault/store` and `vault/conventions`, never each other, and every path still goes through
`vault/paths.resolve()`. All 81 existing tests keep passing.

**Read the spec's "The rules these tools encode" section in full — it is the contract.** The
single most important rule: task sections are read live from `Tasks.md` and never hardcoded.

Difficulty: normal

## Files to touch

- `src/second_brain_mcp/tools/semantic.py` - NEW. The five adapters.
- `src/second_brain_mcp/vault/tasks.py` - NEW. Parse/serialize `Tasks.md`: live `##` headers,
  obsidian-tasks syntax (`⏫` `🔼` `⏬` `📅 YYYY-MM-DD` `✅ YYYY-MM-DD` `[[link]]`), overdue flagging.
- `src/second_brain_mcp/vault/conventions.py` - extend only if a needed pure function is missing.
  A slug generator already exists — do not write a second one.
- `src/second_brain_mcp/server.py` - register the new tools.
- `tests/test_semantic.py`, `tests/test_tasks.py` - NEW.

## Tests to run

```
uv run --frozen pytest -q
```

Must pass — all 81 existing, plus:
- `test_capture_thought_writes_correct_filename_and_frontmatter`
- `test_capture_thought_rejects_domain_outside_closed_list`
- `test_capture_thought_never_writes_to_root_or_bare_raw`
- `test_list_task_sections_reads_live_headers`
- `test_add_task_rejects_unknown_section_and_lists_available`
- `test_add_task_never_invents_date_or_priority`
- `test_add_task_reports_markers_it_added`
- `test_add_task_inserts_under_section_not_end_of_file`
- `test_add_task_preserves_non_ascii_text`
- `test_get_tasks_flags_overdue`
- `test_get_tasks_parses_priority_due_and_link`
- `test_append_log_is_append_only`

## Done criteria

- [ ] `uv run --frozen pytest -q` exits 0 and collects more than 81 tests
- [ ] `grep -rnE "🔴|⏳|💶|👵|📅 Dated|🔄|🏠|⏸|✅ Done" src/` returns no matches — section names
      must never appear as literals in source; they are read from the file
- [ ] `add_task` has a required `section` parameter, and raises listing available sections on a miss
- [ ] `grep -rn "unlink\|os\.remove\|shutil\.rmtree" src/` still returns no matches
- [ ] `grep -rniE "auth|bearer|token|http|transport" src/second_brain_mcp/tools/ src/second_brain_mcp/vault/`
      still returns no matches (ADR-0003)
- [ ] `semantic.py` imports from `store` and `conventions` only — not from `primitives.py`
- [ ] Every filesystem path in `semantic.py` reaches `vault/paths.resolve()`; `grep -n "open(" src/second_brain_mcp/tools/semantic.py` returns nothing
- [ ] `append_log` only ever appends — no `w` mode anywhere near `meta/log.md`

Do not add dependencies. If you think one is required, stop and say so.

---

<!-- factory-check appends "## Check <timestamp>" blocks below this line -->

## Check 20260816T184452Z

Status: Needs fix
Tests: 117 passed in 1.10s (81 -> 117, 36 added, none removed or weakened)
Round: 1, model claude-opus-4-6-thinking

Everything works except one format defect, found by driving the tools against a throwaway vault
rather than by reading the tests.

Verified by execution:
- `list_task_sections()` returns the live headers from the file
- `capture_thought` wrote `raw/thoughts/2026-08-16-2044-call-the-gestor-about-the-autonomo-registration.md`
  with `created: 2026-08-16T20:44`, `source: voice`, `status: raw`, `tags: [type/note]` — correct
  shape, correct folder, nothing at vault root or bare `raw/`
- `add_task` with an unknown section **refused**: `TaskSectionNotFoundError` listing the available
  sections. It does not guess and does not fall back
- `add_task` invented no markers — `priority: None`, `due: None` when none were given
- Non-ASCII preserved: `- [ ] Позвонить маме` round-trips intact (CLAUDE.md: "Russian stays Russian")
- Tasks inserted **under their section**, not appended at end of file
- `get_tasks` parses priority, due, link, completion, and flags overdue

Done criteria: all met except the log format issue below.
- No section emoji appears as a literal in `src/` — sections are genuinely read from the file
- No delete verbs; ADR-0003 clean; no `open(` in `semantic.py`; imports are
  `conventions, paths, store, tasks` only — no tool-to-tool import

### The defect

`semantic.py:89-90` prefixes every log line with `- ` when it does not already start with one:

```python
if not entry.startswith("- "):
    entry = f"- {entry}"
```

The real `meta/log.md` uses `YYYY-MM-DD HH:MM | kind | text` with **no bullet**. Appending through
this tool produces:

```
2026-08-15 19:09 | daily | ran
- 2026-08-16 20:45 | test | second line
```

That is a **third** line shape in a file that already carries two incompatible ones, and
`docs/initial_spec.md:65` makes this file the audit tripwire — "an unexplained line is the
tripwire" only works while the lines are mechanically comparable. It is also cheap now and
annoying later, once real entries are interleaved.

Red flags: none besides the above. No tests skipped or weakened, `specs/` and `factory-engine/`
untouched, no dependencies added, no secrets or absolute local paths.

### Next fix

- Delete the bullet-prefixing branch at `semantic.py:89-90`. `append_log` writes the caller's line
  verbatim plus a trailing newline, and nothing else. It must not reformat, prefix, or normalize.
- Add `tests/test_semantic.py::test_append_log_does_not_add_a_bullet_prefix` — append
  `"2026-08-16 20:45 | test | x"` to a fixture `meta/log.md` and assert the file's last line equals
  that string exactly, with no leading `- `.
- Add `test_append_log_preserves_existing_line_format` — assert the pre-existing lines in the
  fixture are byte-identical after the append.
- Change nothing else. Every other tool verified correct by hand this round.

## Check 20260816T184727Z

Status: Success
Tests: 119 passed in 0.86s (117 -> 119, 2 added, none removed or weakened)
Round: 2, model claude-opus-4-6-thinking

The bullet-prefix branch is gone from `semantic.py`, and both requested format tests exist.
Re-verified by execution against a log seeded with **both** of the real file's incompatible line
shapes:

```
2026-08-15 19:09 | daily | ran
2026-08-15 — Tasks.md restructured: sections re-ordered
2026-08-16 20:50 | test | verbatim line          <- appended verbatim, no bullet
```

Pre-existing lines byte-identical; the new line matches the dominant format. `meta/log.md` stays
mechanically comparable, so the audit tripwire at `docs/initial_spec.md:65` still works.

Regression sweep — nothing else moved:
- `capture_thought` still writes `raw/thoughts/YYYY-MM-DD-HHMM-slug.md`
- `add_task` still refuses an unknown section (`TaskSectionNotFoundError`)
- Non-ASCII still round-trips
- `get_tasks` still flags overdue
- ADR-0002 (no `startswith` in `paths.py`), ADR-0003 (no transport/auth in `tools/`+`vault/`),
  no-delete, and no-hardcoded-sections all still clean

Done criteria: all met.

Red flags: none. No tests skipped or weakened, no dependencies added, `specs/` and
`factory-engine/` untouched.

Not covered:
- Docker image still unbuilt (daemon down on this machine) — carried over from increment 2.
- No end-to-end JSON-RPC test driving a semantic tool over HTTP; they are exercised via direct
  Python calls and over stdio.
- `propose_wiki_page` deliberately not built (rejected in the brief).
