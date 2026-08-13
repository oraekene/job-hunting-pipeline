# 04 — Restore command for terminal-failed rows with complete builds

**What to build:** A `--restore <id>` sub-command on the processor that
recovers a terminal `failed` row (build_attempts >= 3) whose 8 artifacts are
complete: it re-points the row at the artifacts, resets status to a claimable
state, and re-reads all gate columns from the artifacts at the next commit —
no fabricated data, no attempt-count inflation. This is the tool that makes
ticket 10 (rescuing Apera AI) possible.

**Blocked by:** 03 — Reconcile must preserve complete builds

**Status:** done

- [ ] `--restore <id>` verifies the 8 artifacts first; refuses with a clear
  message when the build is incomplete (and suggests deleting the row or
  re-running discovery instead)
- [ ] On success: row returns to `discovered` (or a documented claimable
  state), `building_started_at` cleared, prior `vanished` failure record kept
  for the ledger, artifacts path re-pointed at the existing dir
- [ ] Restore never writes gate values directly — they are re-parsed from
  artifacts at commit, same code path as a normal commit
- [ ] Attempt ledger records a distinct `restored` marker so analytics can
  distinguish a restored build from a fresh one
- [ ] Harness case: seed a terminal `failed` row + complete artifacts, run
  `--restore` then `--claim` + `--app-id`, assert `staged` and gate columns
  correct
- [ ] `--dry-run --restore <id>` shows exactly what would change without
  touching the DB
