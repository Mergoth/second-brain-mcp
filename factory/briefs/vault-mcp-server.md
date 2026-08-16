# Brief: vault-mcp-server

Request: take docs/initial_spec.md and start working on it from scratch
Written: 2026-08-16
Personas: product, architect, skeptic, operator

## Problem

Vlad has an Obsidian vault at `Library/CloudStorage/SynologyDrive-Mergoth/Notes/PersonalObsidian/`
(78 `.md` files) synced to Mac and phone. From the phone, away from a keyboard, there is
no way to get a thought into it correctly filed — `docs/initial_spec.md:4` names
"voice capture from Android anywhere" as the goal. The filing rules live in the vault's
`CLAUDE.md` as prose, so they are a prompt that can be forgotten rather than code.

The repo is empty: `git log` fatals with "does not have any commits yet", `git ls-files`
returns nothing. Only `docs/initial_spec.md` plus the vendored harness exist. "From
scratch" is literal.

## Why now

The build harness is wired but misconfigured, and every hour it stays that way costs a
paid `agy` round to discover. `factory/context.md` and `memory.md` still carry the
`factory:template` marker, and `run_antigravity.sh:90-92` **silently drops** template
files — agy would receive spec + handoff and nothing else, re-deciding the stack on
every round against `MAX_ROUNDS="3"`.

## What done looks like

Round 1, observable from outside: `uv run --frozen pytest -q` exits 0 against a synthetic
fixture vault; the five primitives work over stdio against a throwaway copy of the real
vault; and any path escaping the vault root — `..`, absolute, symlink, null byte — is
refused with a named error rather than served.

## Constraints

- `factory.env:6` sets `TEST_CMD` — Python + pytest is de-facto decided (ADR-0001).
- `docs/initial_spec.md:14` forbids a persistent index. Ripgrep on demand.
- `docs/initial_spec.md:42` forbids hard delete. Archive is a move.
- `PRINCIPLES.md` #9/#10: never edit `factory-engine/`; the diff stays in the working tree.
- Confinement is bounded by the vault root. Siblings of the root (`EPAM/`, `copilot-conversations/`)
  are one `..` away, so the resolver must reject traversal — but per Vlad 2026-08-16 those trees
  are archive and are not the driving threat. The driving threat is prompt injection from
  anything landing in `raw/` (spec line 67).

## Approach

Land a `src/second_brain_mcp/` package whose seams are what keep phases 1→4 from becoming
a rewrite: `config.py` (VAULT_PATH from env, **no default**), `vault/paths.py` (the single
`resolve()` chokepoint — nothing else in the codebase opens a caller-supplied path),
`vault/store.py` (atomic write via temp-file + `os.replace`, audit emitted here so no tool
can forget it), `vault/conventions.py` (pure string functions — slugs, frontmatter,
`Tasks.md` grammar), and thin `tools/` adapters. `server.py` builds the FastMCP object;
`__main__.py` alone picks stdio vs streamable-http and wires auth, because the SDK cannot
consult a token verifier over stdio at all. Phase 1→2 becomes an entrypoint flag, phase 3
an entrypoint module. Before the first `agy` run: baseline commit, `TEST_CMD` →
`uv run --frozen pytest -q`, fill `context.md`, extend `.gitignore`, delete the dead
`.factory` stanza from `.gitmodules`.

## Rejected

- **Invert phases to chase the Android capture path first** — product argued phase 1 is not
  a user-visible win. Skeptic stress-tested the spec order and endorsed it; architect's
  `conventions.py`-in-phase-1 absorbs the concern without paying day-one auth cost.
- **Path confinement per-tool or as transport middleware** — phase 4 semantic tools call
  storage in-process and bypass a tool-boundary guard entirely.
- **Throwaway phase 1 prototype rewritten for phase 2** — spec line 72 says "same code";
  one server object serves both transports.
- **Persistent index for search** — banned by spec line 14, and a second source of truth.
- **Conflict-resolution logic for Synology Drive** — the spec's own evidence for it is
  misattributed (see Persona notes). Atomic writes yes; merge logic no.
- **Property-based fuzzing of `resolve()`** — the attack set is small and enumerable; an
  explicit case table is readable in a diff where a Hypothesis failure is not.

## Risks

- A confinement bug writes outside the vault root. The vault is **not** under git and has
  no verified restore path. Mitigated by round 1 running against a copy.
- Phase 1 runs on a macOS File Provider mount, phase 2 on a NAS bind mount — `realpath`
  behaves differently, so phase 1 does not fully exercise the phase 2 confinement path.
- Phase 2 non-root container vs. `Tasks.md` and `meta/log.md` at mode 600 → EACCES on
  exactly the two highest-value writes, looking like a tool bug. UID mapping is unspecified.
- `add_task`'s section taxonomy is unstable — `meta/log.md` records it was restructured
  2026-08-15. Hardcoding it misfiles silently on the next reorganisation.

## Assumptions

- Round 1 hand-run points at a **throwaway copy**; writes are in scope. (asked)
- **Spec phase order stands.** (asked)
- Machine audit gets its own append-only file; `meta/log.md` stays human-curated. (asked)
- Fixture vault is hand-written but derived from the real structure — real emoji section
  headers, real obsidian-tasks-plugin syntax (`⏫` `🔼` `📅` `✅`), both `meta/log.md` line
  shapes. Minimal-and-invented would be provably diverged; a raw snapshot would drift.
- The vault's `CLAUDE.md` gets copied into this repo — the semantic layer is currently
  specified against a file no implementer can reach.
- A literal CLAUDE.md validator is **not** built: the real vault violates its own
  "root holds two files only" rule today (`.DS_Store`, `.obsidian/`, `.claude/`).
- `add_task`/`get_tasks` target the obsidian-tasks-plugin grammar rather than invent one.
- Auth stays deferred, but an `auth/` seam exists from phase 1 — deferring the answer is
  fine, deferring the seam is not.

## Persona notes

- **product vs. skeptic — phase order.** Product: phase 1 ships nothing the user lacks,
  since Claude already reaches the synced folder on the Mac, and the justifying feature
  (`capture_thought`) sits in phase 4 behind everything. Skeptic independently checked the
  same ordering and called it "genuinely defensive… I would not touch it". Resolved by
  architect's structural answer — conventions land and are tested in phase 1, so phase 4
  is registration over proven code. Kept spec order; product's concern is real but is
  answered by module placement, not by resequencing.
- **operator vs. skeptic — sync conflict evidence.** Operator cited
  `EPAM_DiskStation_..._RemoveLocalConflict` as proof spec line 80's conflict risk is live.
  Skeptic checked and found **zero** conflict files under `PersonalObsidian/`, and that the
  one artifact is a whole-folder remove inside the tree line 62 declares out of scope.
  Skeptic wins on evidence. The risk stays plausible but unproven, so we pay only for
  atomic writes — cheap now, impossible to retrofit safely once five callers exist.
- **skeptic alone — `meta/log.md` dual role.** No other persona noticed the file cannot be
  both machine audit and human tripwire, or that it already carries two incompatible
  formats. Became a decision rather than a note.
