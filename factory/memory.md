# Factory memory

caveman: what past runs taught us. one line each. newest at top.

Rules for whoever writes here:
- one line, concrete, useful next time. no essays.
- write only what would have changed a decision. skip trivia.
- delete lines that stopped being true. a wrong memory costs more than none.
- keep under ~40 lines. when it grows past that, merge and cut.
- conventions and commands do NOT go here - those belong in `context.md`.

- claude.ai custom connectors on personal plans = OAuth (DCR/CIMD) or authless only; static bearer headers are an org-Owner beta. Read claude.com/docs/connectors/building/authentication before betting on an auth mode again
- MCP SDK 2.0.0 RevocationRequest makes client_secret required, so public clients (Claude) get 400 on /revoke; the SDK's own suite misses it. Revocation is left unadvertised
- Synology: files under /volume1 inherit ACLs that override umask (a "600" .env came out 777+); chmod after creating secrets and check with ls. Bare `rsync` over SSH is intercepted by DSM and fails auth; wrap it via --rsync-path="sh-cmd && rsync"
- the container never ran until a real `docker run --read-only`: `uv run` needs a writable cache and the app bound 127.0.0.1; neither shows up in tests
- agy truncated mid-run and still exited 0, writing source but zero tests; the tell was the test count staying flat, not the report
- a green suite proved nothing about output FORMAT twice (append_log bullet prefix); read the resulting file, not just the assertions
- green tests + every done criterion met still shipped an RCE (round 1, vault-primitives-stdio); grep-shaped criteria check spelling, so verify security claims by running the exploit
- MCP SDK 2.0 removed `mcp.server.fastmcp`; the class is `MCPServer` from `mcp.server.mcpserver`
- `uv` lives in `~/.local/bin`; if it is not on agy's PATH the round fails at the test step looking like a code failure
- `pytest -q` exits 5 on empty collection, so a round with source but no tests reads as failed; always ship a test
- the real vault has no git and no verified restore path - never point VAULT_PATH at it from a build run
- `docs/initial_spec.md:80` claims Synology conflict files prove the conflict risk; there are zero under PersonalObsidian/ - do not build merge logic on that citation
