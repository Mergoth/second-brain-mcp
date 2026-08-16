# Semantic tools

Slug: `vault-semantic-tools`
Written: 2026-08-16
Brief: `factory/briefs/vault-mcp-server.md`

Increment 3 of 4. Done: `vault-primitives-stdio`, `vault-http-transport`.

## Problem

`docs/initial_spec.md:4` names voice capture from Android as the goal, and `capture_thought` is the
tool that serves it — but nothing built so far files a note correctly. The filing rules live as
prose in the vault's `CLAUDE.md`, which is a prompt that can be forgotten rather than code
(`docs/initial_spec.md:54`).

## Solution

Semantic tools that compose `vault/store` and `vault/conventions`, never each other (ADR-0004
territory). `conventions.py` already exists and is unit-tested from increment 1, so this is largely
registration over proven code.

- `capture_thought(text, source)` — the voice-while-driving path. Writes
  `raw/thoughts/YYYY-MM-DD-HHMM-<slug>.md`.
- `list_task_sections()` — returns the `##` headers currently in `Tasks.md`, read live.
- `add_task(text, section, priority=None, due=None, link=None)` — appends one line under an
  existing section.
- `get_tasks(filter=None)` — parses `Tasks.md`, returns structured tasks, flags overdue.
- `append_log(line)` — appends to `meta/log.md`.

## The rules these tools encode

Transcribed from the vault's `CLAUDE.md` on 2026-08-16. **That file is upstream and will drift —
re-sync this section rather than assuming it is current.**

**Placement.** Never create files at root or directly inside `raw/`, `wiki/`, `meta/` — always a
subfolder. Never hard-delete; move to `raw/archive/`. Never write outside the vault.

**Raw file naming.** `YYYY-MM-DD-HHMM-short-slug.md`, with frontmatter:

```yaml
created: YYYY-MM-DDTHH:MM   # the recency anchor, NOT mtime — Synology rewrites mtimes in bulk
source: voice | text
status: raw
tags: [type/note, domain/x]
```

`type/` derives from the folder — `raw/thoughts/` is always `type/note`. `domain/` is a **closed
list**: `work` `finance` `legal` `health` `trips` `home` `plants` `smart-home` `projects`
`learning`. Never invent one mid-capture; free topic tags may follow but are never load-bearing.

**Tasks.md.** One line per task, the action and nothing else — "reads at a glance while driving".
Format `- [ ] Task ⏫ 📅 YYYY-MM-DD [[Note]]`. Priorities `⏫` urgent, `🔼` high, `⏬` low.

- **Never invent a date or priority.** Only set what the owner stated.
- **Every marker the tool adds that the owner did not state must be reported back in the result.**
  `CLAUDE.md` calls this out explicitly: the failure was silence, not ignorance.
- Owner's language is preserved — Russian stays Russian.
- Split run-on dictation into one `- [ ]` per action.
- Flag overdue proactively.

**Sections are unstable by design.** `CLAUDE.md:73`: *"Sections are a view, not a taxonomy. Re-sort
when reality moves."* `CLAUDE.md:71`'s prose list already disagrees with the live headers, and
`meta/log.md` records a restructure on 2026-08-15. Therefore:

> **Never hardcode the section list.** `list_task_sections()` reads the live `##` headers.
> `add_task` requires a `section` argument, matched case-insensitively against those live headers,
> and **raises listing the available sections when there is no match**. It never guesses, and never
> falls back to a default section.

A hardcoded table is a test that passes today and silently misfiles the next time Vlad re-sorts.

**meta/log.md is append-only.** Never rewrite, never prune — "a tidied log can't show a trend".

## Scope

In: the five tools above, over both transports, with tests.

Out:
- `propose_wiki_page` — its arguments are unspecified in the source spec and it serves deep work at
  the MacBook, where nothing is blocked. Rejected in the brief.
- Any validator built literally from `CLAUDE.md`'s "root holds two files only" rule — the real vault
  violates it today (`.DS_Store`, `.obsidian/`, `.claude/`).
- Re-sorting, re-prioritizing, or moving existing tasks. These tools append and read.
- Automatic per-write audit lines — those already go to `meta/audit.log` from `store`.

## Assumptions

- `append_log` writes the **human** `meta/log.md`. That does not contradict the machine/human split
  decided in the brief: the split was about automatic per-write noise, and this tool is a
  deliberate, explicitly-invoked write.
- `capture_thought` defaults `tags` to `[type/note]` plus any caller-supplied `domain/` value that
  is in the closed list; an out-of-list domain is rejected rather than invented.
- Timestamps come from local time, matching `created:` semantics.

## Notes

- Tools compose `store` + `conventions`, never each other. Every path still goes through
  `vault/paths.resolve()` — ADR-0002 applies unchanged, and `capture_thought` builds its filename
  from `conventions`, then resolves it like any other path.
- Slug generation already exists and is tested in `conventions.py`; do not write a second one.
- Appending under a section means inserting after that header's existing lines, not at end of file.
- The fixture vault already carries the real emoji headers and obsidian-tasks syntax.
