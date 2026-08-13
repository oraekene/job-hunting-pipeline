# 06 — Approval handoff for every staged application

**What to build:** Make "staged → approval ping" automatic and verifiable.
Today `approval_sent_at` is NULL for every staged row (apps 1, 3, 4 have sat
unreviewed for days) because the orchestrator's instruction to hand staged
rows to `10-approval-and-submit` is executed by nobody. The sweep — after
committing — must hand every row with `status='staged' AND approval_sent_at IS
NULL` to the approval-submit stage, and the ping must record its own
timestamp so the state is provable.

**Blocked by:** 02 — Sweep must not claim artifact-less rows; 05 — Align
gate-column parsing

**Status:** done

- [ ] The sweep prompt/flow includes the handoff step after commit: for each
  row staged this tick (plus any pre-existing `staged` rows still lacking
  `approval_sent_at`), invoke `10-approval-and-submit`
- [ ] Approval-submit sets `approval_sent_at` at ping time (not before), so
  `approval_sent_at IS NULL` remains a truthful "never pinged" marker
- [ ] If Telegram is unreachable, the handoff leaves `approval_sent_at` NULL
  and reports the failure in the sweep digest; it never silently drops the
  handoff
- [ ] Duplicate pings prevented: two concurrent sweeps cannot both ping the
  same row (the timestamp is written in the same transaction as the ping
  claim)
- [ ] Harness or dry-run case asserts a staged row with NULL
  `approval_sent_at` is selected by the handoff query
- [ ] Sweep digest now includes "N staged, M awaiting approval, K pings sent"
  so Kenechukwu sees the pipeline actually reach him
