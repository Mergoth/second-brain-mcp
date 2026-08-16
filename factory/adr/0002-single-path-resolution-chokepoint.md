# ADR-0002: All filesystem access goes through one resolve() chokepoint

Date: 2026-08-16
Status: proposed

## Context

The server is a plain local-filesystem server: it takes paths from model-generated tool
calls and turns them into filesystem operations on a vault that is not under version
control and has no verified restore path. `docs/initial_spec.md:67` names the realistic
attack — a note that reaches `raw/` from an external source and instructs a write outside
the vault.

The tempting shapes — a decorator on each `@mcp.tool()`, or transport middleware — both
fail for the same structural reason. The phase 4 semantic tools (`capture_thought`,
`add_task`, `propose_wiki_page`) call storage functions in-process, so a guard at the tool
boundary is bypassable from inside, and middleware never sees the call at all.

A softer version of this rule — "resolve paths against the vault root" — leaves room for a
later per-call root, a trusted-path list, or an escape flag added under deadline. Per Vlad
(2026-08-16), confinement is absolute and not negotiable at runtime, so the rule is stated
in a form that has no configurable surface to widen.

## Decision

The vault root is resolved to a real path **once at process startup** from `VAULT_PATH`,
frozen as immutable, and never re-read. It is not a tool argument, not a request field, and
not settable after startup. The server refuses to start if `VAULT_PATH` is unset, missing,
or not a directory. There is no default.

Every caller-supplied path becomes a real path in exactly one function,
`vault/paths.py::resolve()`, which fully resolves symlinks and asserts the result is inside
the frozen root, raising a named error otherwise. Containment is tested with a proper
path-ancestry check, never string prefix matching. `resolve()` takes no options: there is no
bypass flag, no trusted-path list, no follow-symlinks toggle, no allow-outside mode. Both
ends of a two-path operation are resolved independently. No module in the package calls
`open()`, `Path()`, or `os.*` on a value that originated in a tool argument.

## Consequences

- Makes easy: one adversarial test table covers the whole attack surface, and adding a tool
  adds no new confinement risk.
- Makes hard: any "just read this one file" shortcut in a tool module. That is the point.
- A build agent must never call `open()` or construct a `Path` from a tool argument outside
  `vault/store.py` and `vault/audit.py`, both of which accept already-resolved paths.
- A build agent must never add a parameter that widens reach — no `root=`, `allow_outside=`,
  `follow_symlinks=`, or trusted-prefix list. Adding one requires superseding this ADR.
- String prefix comparison is forbidden: with root `/vault`, the sibling `/vault-evil`
  prefix-matches and would pass. Use path ancestry against the resolved root.
- A symlink **inside** the vault pointing outside it resolves outside and is rejected, even
  though the link itself lives in the vault.
- A default value for `VAULT_PATH` is forbidden — a default is how a test run reaches the
  real vault.
- The server cannot serve two vaults in one process. If that is ever wanted, it is a second
  process with its own root, not a parameter.
