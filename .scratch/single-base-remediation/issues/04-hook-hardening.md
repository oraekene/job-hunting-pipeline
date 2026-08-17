# 04 — Hook hardening

**What to build:** Both security hooks are installed and registered with Windows-safe absolute paths; `pre_tool_call` hook invocations stop exiting 2 with "No such file or directory".

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] The registered submit-gate hook command uses the absolute path to the agent-hooks directory (no literal `~`)
- [ ] The db-ownership hook file is copied from the bundle into the agent-hooks directory
- [ ] The db-ownership `pre_tool_call` block is registered per the security setup docs, same absolute-path form
- [ ] Manual invocation of each hook via its registered path exits 0 (or the hook's documented success/no-op code)
