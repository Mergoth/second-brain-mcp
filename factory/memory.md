# Factory memory

caveman: what past runs taught us. one line each. newest at top.

Rules for whoever writes here:
- one line, concrete, useful next time. no essays.
- write only what would have changed a decision. skip trivia.
- delete lines that stopped being true. a wrong memory costs more than none.
- keep under ~40 lines. when it grows past that, merge and cut.
- conventions and commands do NOT go here - those belong in `context.md`.

- `uv` lives in `~/.local/bin`; if it is not on agy's PATH the round fails at the test step looking like a code failure
- `pytest -q` exits 5 on empty collection, so a round with source but no tests reads as failed; always ship a test
- the real vault has no git and no verified restore path - never point VAULT_PATH at it from a build run
- `docs/initial_spec.md:80` claims Synology conflict files prove the conflict risk; there are zero under PersonalObsidian/ - do not build merge logic on that citation
