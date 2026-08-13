# 01 — Commit the processor regression harness

**What to build:** A durable, repo-committed regression loop for
`pipeline_processor.py` that exercises the state machine end-to-end against a
throwaway copy of the applications DB — claim, commit, sweep, and reconcile —
and asserts the resulting row statuses, gate columns, and exit codes. It must
be runnable by any agent in one command, in seconds, with no network and no
touch of the live DB. The harness that diagnosed this spec's bugs (a
PowerShell driver + seed script + sandbox dir layout) is the starting point;
this ticket makes it permanent, deterministic, and self-resetting.

**Blocked by:** None — can start immediately

**Status:** done

- [ ] A single script (PowerShell or Python) sets up a sandbox dir with the
  processor at `00-orchestrator/scripts/`, a copied `shared/applications.db`,
  and a seeded fixture row, then runs `--claim <id>` + `--app-id <id>` and
  fails unless the row lands at `staged` with gate columns matching the
  seeded artifacts
- [ ] A sweep-mode case seeds 3 discovered rows (some with artifacts, some
  without) and asserts the exit code and per-row outcomes exactly match the
  claim-after-artifacts rule (red until ticket 02 lands, then green)
- [ ] A reconcile case seeds a stale `building` row with a complete
  8-artifact build and asserts the artifacts are NOT moved or burned (red
  until ticket 03 lands, then green)
- [ ] The harness resets the sandbox on every run (fresh DB copy each time);
  live `shared/applications.db` is never opened for write
- [ ] Output ends with a single GREEN/RED verdict line per case; total
  runtime under 30 seconds
- [ ] Documented in the orchestrator's README or SKILL.md: the one command
  to run, what it proves, and where the sandbox lives
