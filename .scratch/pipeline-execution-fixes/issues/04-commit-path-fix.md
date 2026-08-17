# 04 — Commit-path fix

**What to build:** an application whose risk log contains `[FAIL]` entries commits to `staged` exactly like one without. The risk-gap extraction returns one documented tuple shape and the commit loop unpacks exactly that shape; the commit writes gaps, ledger, and application row in one all-or-nothing transaction. A regression test in the harness pins the shape.

**Blocked by:** 01 (test harness) — the regression test lives in the suite.

**Status:** ready-for-agent

- [ ] `process` with a risk log containing `[FAIL]` entries commits the row to `staged`
- [ ] `open_gaps` rows are written for the `[FAIL]` entries in the same transaction
- [ ] The commit is all-or-nothing — a failure leaves the row at `building` with no partial writes
- [ ] A regression test with `[FAIL]` entries passes in the harness

**Agent brief:** Spec 1, Implementation Decisions — Commit-path fix (`.scratch/pipeline-execution-fixes/spec.md`).