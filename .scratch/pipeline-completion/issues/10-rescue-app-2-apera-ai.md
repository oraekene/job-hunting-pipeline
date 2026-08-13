# 10 — Rescue app 2: restore and stage the Apera AI build

**What to build:** The end-to-end proof of the whole fix chain: take app 2
(Apera AI, Senior Product Manager) — currently terminal `failed` at 3
attempts with a complete 8-artifact build parked at
`build_artifacts/app_2.failed-3` — and get it to `staged` with correct gate
columns, then into the approval handoff. This is the demo that the pipeline
now completes end-to-end for a real, previously-destroyed application.

**Blocked by:** 04 — Restore command; 07 — Package integrity repair

**Status:** done

- [x] Verify the parked build at `app_2.failed-3` is complete (8 artifacts,
  non-empty, docx present) and free of ticket-09 mojibake before touching
  state
- [x] Move/point the artifacts back to `shared/build_artifacts/app_2/` using
  the restore flow, not a manual DB edit
- [x] `--restore 2` + `--claim 2` + `--app-id 2` lands the row at `staged`;
  overall_match_score=52 (the artifact's honest score — the ticket's
  "62" was a stale discovery-time estimate; gate columns are read from
  artifacts, never fabricated), keyword_match_score=52 from the nested
  key, overqualification_gate='flagged' (visa), title_displayed='Product
  Manager' (honest, no "Senior" inflation)
- [x] Attempt ledger shows the `restored` marker from ticket 04 and no
  further `vanished` burn
- [x] The staged row sits in `--approval-queue` per ticket 06; the actual
  Telegram ping fires on the next sweep tick (approval_sent_at NULL until
  then, by design)
- [x] Dry-run (27/27) and the regression harness (15/15) both green after
  the rescue; the Tactic 2 section of app_2's resume_change_log.md was
  corrected from app_1's copied "Credit Officer" framing to the honest
  "Product Manager" before re-commit
