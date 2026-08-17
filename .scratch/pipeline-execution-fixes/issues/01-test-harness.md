# 01 — Test harness: pipeline processor CLI suite

**What to build:** a test suite that exercises the pipeline processor's `claim`, `process`, `reject`, and `reconcile` commands as subprocesses against a scratch database seeded with the real schema. The suite asserts only observable state transitions (row status, build-attempt ledger outcome, gaps rows, exit codes). Every later pipeline fix lands its regression test in this suite.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] A temporary database with the real schema is created for each test run
- [ ] `claim` moves a discovered row to `building` and opens a build-attempt row
- [ ] `process` with a complete artifact set advances a row to `staged` and closes the attempt
- [ ] `reject` marks an unavailable posting `rejected_by_kene` with the reason
- [ ] `reconcile` resolves a stale `building` row to `vanished` and returns retryable rows to `discovered`
- [ ] Tests run the CLI as subprocesses; no processor internals are imported

**Agent brief:** Spec 1, Testing Decisions — "the pipeline processor's own CLI against a scratch database" (`.scratch/pipeline-execution-fixes/spec.md`).