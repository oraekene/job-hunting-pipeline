# 06 — File-search reliability

**What to build:** the search tool works against the skills directory during a pipeline run. The OS-level IO error observed repeatedly is diagnosed and fixed, and the tool reports the failing path explicitly when an IO error occurs instead of returning an opaque failure.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] Search returns results for the skills directory during a live run
- [ ] The observed IO error class is diagnosed and fixed
- [ ] An IO failure reports the failing path explicitly
- [ ] Search completes without the repeated failure pattern seen on 2026-08-12

**Agent brief:** Spec 1, Implementation Decisions — File-search reliability (`.scratch/pipeline-execution-fixes/spec.md`).