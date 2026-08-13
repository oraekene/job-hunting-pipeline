# 02 — Sweep must not claim artifact-less rows and must fail loudly

**What to build:** Change sweep mode so it never converts a `discovered`
row into `building` unless the 8 required artifacts already exist in
`shared/build_artifacts/app_<id>/`. A tick that claims nothing and stages
nothing exits non-zero with a visible reason. This stops the
claim → 7h-stale → `vanished` → attempt-burn death spiral that killed
app 2 and is currently chewing through app 5's attempts.

**Blocked by:** 01 — Commit the processor regression harness

**Status:** done

- [ ] Sweep mode verifies artifacts BEFORE claiming; rows without a complete
  artifact set are reported as "artifacts not ready" and left `discovered`
  (never `building`), with no `build_attempts` increment
- [ ] Sweep mode exits non-zero when it failed to stage any claimed row
  (currently it prints "FAILED to stage" and exits 0, hiding failures from
  cron)
- [ ] `--claim <id>` single-row mode refuses to claim when artifacts are
  absent (or documents why it is exempt), keeping the manual path honest
- [ ] The sweep still stops at the configured `--limit` even when skipping
  unready rows; skipped rows are retried by a later tick, not forgotten
- [ ] Harness case "sweep-mode" from ticket 01 is green: 3 discovered rows,
  1 with artifacts, 2 without → exactly 1 staged, 2 still `discovered`,
  exit code reflects success
- [ ] Live-DB dry check: no row transitions discovered → building without
  artifacts (verified with `--dry-run` before any real sweep)
