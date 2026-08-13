# 03 — Reconcile must preserve complete builds and stop burning attempts

**What to build:** Teach the reconcile step to distinguish a complete
8-artifact build from a partial one. Today a `building` row past the 7-hour
staleness window is marked `vanished`, its attempt burned, and its artifacts
directory moved to `app_<id>.failed-<n>` — even when the build finished and
only the commit step failed (exactly what happened to app 2 after the
`too many values to unpack` bug: a finished 39KB-docx build was treated as a
dead run). Complete builds must be left in place and made retryable; only
genuinely partial builds get the stale treatment.

**Blocked by:** 01 — Commit the processor regression harness

**Status:** done

- [ ] Reconcile checks whether all 8 required artifacts exist and are
  non-empty before declaring a stale row `vanished`
- [ ] Stale rows with complete builds: artifacts stay in
  `build_artifacts/app_<id>/` (never moved), attempt is NOT burned with a
  `vanished` outcome, row is reset to `discovered` (or a retryable commit
  state) with a distinct reason like "build complete, commit pending"
- [ ] Stale rows with partial/missing artifacts: existing behavior —
  move to `.failed-<n>`, burn attempt, `vanished` outcome
- [ ] Reconcile's retry pass honors `build_attempts < 3` without double
  counting the preserved-complete rows
- [ ] Harness case "reconcile" from ticket 01 is green: stale `building` +
  complete artifacts → artifacts untouched, row retryable; stale `building`
  + partial artifacts → moved and burned
- [ ] Log lines clearly name the two paths so a later tick's report can show
  "N complete builds awaiting commit"
