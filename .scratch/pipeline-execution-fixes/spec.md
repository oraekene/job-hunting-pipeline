# Spec: Pipeline Execution Fixes

**Status:** ready-for-agent

## Problem Statement

The 2026-08-12 full-pipeline run (session `20260812_175348_808428`) proved stages 2–9 can produce complete, honest artifact sets, but the run never completed end to end. The pipeline processor's commit step crashed with `too many values to unpack (expected 2)` for any application whose risk log contains `[FAIL]` entries, rolling the application back to `building` forever. Around that crash, the run surfaced five more defects: queries against columns the database does not have, a documented template path that does not exist, artifacts from a previously successful build silently disappearing, applications stuck in limbo with open build-attempt ledger rows, and file-search tooling failing on the skills directory.

The pipeline cannot be trusted to run unattended until every step from claim to staged is atomic, verifiable, and exercised by tests.

## Solution

Make the pipeline processor's unit-of-work contract (claim → process → reject → reconcile) reliable and verifiable:

- Fix and regression-test the commit path so any risk log — with or without `[FAIL]` entries — commits atomically.
- Reconcile the live database schema with every query the processor and its helpers issue, and add schema-drift detection to the gate suite.
- Resolve the template-path mismatch so the documented evidence sources resolve to real files, and make the evidence loader fail loudly instead of improvising.
- Recover the stuck applications (open attempt rows, `building` rows past staleness) through the reconcile path.
- Give the processor a real test suite at the highest seam: its own CLI.

## User Stories

1. As the pipeline operator, I want an application with `[FAIL]` risk entries to commit to `staged` exactly like one without, so that no valid application is blocked by its own honesty.
2. As the pipeline operator, I want the commit step to be all-or-nothing — fully `staged` with ledger and gaps written, or untouched at the previous status — so that a crash can never leave a half-written application.
3. As the pipeline operator, I want every query the processor issues to run against the database, so that a `no such column` error cannot occur during a live sweep.
4. As the pipeline operator, I want a schema-drift check in the validation gate so that processor code and database schema diverging is caught before a sweep, not during one.
5. As an agent authoring stage artifacts, I want the documented evidence sources (STAR story bank, domain knowledge, career timeline) to resolve to real files from a single canonical location, so that no subagent is forced to improvise its evidence base.
6. As an agent authoring stage artifacts, I want the evidence loader to fail loudly with the correct location when a source is missing, so that the defect surfaces at build time instead of silently degrading the artifacts.
7. As the pipeline operator, I want applications stuck at `building` past the staleness threshold to be reconciled — ledger closed with outcome `vanished`, retry budget honored — so that no application is abandoned in limbo.
8. As the pipeline operator, I want the stale open attempt rows (outcome `NULL` after hours) to be resolved by the reconcile pass, so that attempt-number bookkeeping stays truthful.
9. As the pipeline operator, I want the file-search tooling to work against the skills directory, so that agents can actually search the package during a run.
10. As a developer, I want a test suite that exercises the processor's claim/process/reject/reconcile against a scratch database, so that regressions are caught before a sweep.
11. As a developer, I want the tests to use the processor's own CLI and a temporary database, so that they test external behavior, not internals.

## Implementation Decisions

### Commit-path fix

- The risk-gap extraction must return a single, documented tuple shape (description, missing-evidence), and the commit loop must unpack exactly that shape. A shape mismatch must fail the gate, not the live sweep. (The live copy already carries a 2-tuple fix dated after the failed run; this decision pins the shape and adds the regression test so it cannot regress.)
- The commit path writes three things in one transaction: `open_gaps` rows from the risk log, the closing of the open build-attempt row (or its completion), and the application row's advance to `staged` with all gate columns. Any failure rolls the whole transaction back.

### Schema-drift gate

- The applications schema is the single source of truth (documented addenda are its changelog). A new gate assertion compares every column name the processor's SQL references against the live table's columns and fails on any mismatch.
- All ad-hoc diagnostic queries observed during the run that referenced nonexistent columns are corrected to the real schema (status lives on the applications row; source-board data lives in its own table).

### Evidence-source canonicalisation

- The three mandatory evidence sources (STAR story bank, domain knowledge, career timeline) are documented as living in a single canonical location; the sub-skills that reference them are updated to that location, and the previously-documented-but-nonexistent path is removed from all references.
- The evidence loader: resolve each source; if any is missing, raise a hard error naming the missing source and the canonical location. No improvisation fallback.

### Stuck-application recovery

- The reconcile pass, which already resolves `building` rows past staleness to `vanished` and returns retryable rows to `discovered`, is extended to also close any open build-attempt row whose application is not `building` (orphaned open attempts) — the two observed stuck rows (attempts for apps 2 and 5) are the acceptance targets.
- Recovery is executed once via the normal CLI paths (reconcile), never by editing the database by hand.

### File-search reliability

- The search tool's failures against the skills directory are diagnosed (the observed error is an OS-level IO error on a path that exists) and the tool is made to work on the package root, with a guard that reports the failing path explicitly when an IO error occurs.

## Testing Decisions

- **Highest seam, kept single**: the pipeline processor's own CLI against a scratch database. Tests run `claim`, `process` (with and without `[FAIL]` risk entries), `reject`, and `reconcile` as subprocesses against a temporary database seeded with the real schema, asserting only observable state transitions (row status, ledger outcome, gaps rows, exit codes).
- **Good test = external behavior**: a test asserts the database state after a command; it never imports or mocks processor internals.
- **Prior art**: the repo's established gate-behaviour tests (install-check exit-code matrix, installer refusal tests) are the model; the new suite follows their "run the command, assert the state" shape.
- **Schema-drift test**: a mutation check — rename one column the processor references — must flip the gate to fail (performed once, not committed).
- **Evidence-source test**: point the loader at a missing source and assert it exits non-zero with the source named.

## Out of Scope

- Changing the stage-artifact authoring skills (their content is not the defect; the evidence-source references are).
- The submission/approval flow (never reached in the run; its own concern).
- LLM-provider reliability issues observed during the run (separate spec).
- Agent-execution-discipline issues observed during the run (separate spec).
- Data migration of existing application rows beyond the reconcile-driven recovery described above.

## Further Notes

- The run produced complete artifact sets for apps 2, 3, and 4 (all files verified non-empty, match scores 52/53/47, visa blockers surfaced honestly). Those artifacts are valid; only the commit step failed. After this spec's fixes, the recovery path should commit app 2 as-is rather than re-authoring.
- App 1's artifact folder was observed empty while the database references it — its row predates the failing commit path; the recovery decision covers whether to re-run or retire it.
- The run also recorded a `grep`-style artifact check reporting "all 8 stage outputs present" in the same breath as the tuple crash — the artifact-presence check and the commit crash are independent; both are covered here (presence check already passes, tuple fix is the regression target).