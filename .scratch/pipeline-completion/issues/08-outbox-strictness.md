# 08 — Outbox strictness: surface rejections, resolve the stuck file

**What to build:** Outbox ingestion already rejects non-conforming files
safely, but the rejection is silent and permanent — the stuck
`jd_sprofil_product_manager.json` (a stage-2-shaped JD payload, not an
outbox record) has sat in `shared/.outbox/rejected/` unexamined. This ticket
makes rejections visible and actionable, then resolves the stuck file through
a documented decision rather than leaving it in limbo.

**Blocked by:** 01 — Commit the processor regression harness

**Status:** done

- [ ] Rejection path records WHY a file was rejected (unparseable JSON /
  missing `application_id` / missing `outcome`) into the sweep report or a
  sidecar note next to the rejected file
- [ ] Sweep digest surfaces "outbox: N rejected" with the reason summary so
  it is no longer invisible
- [ ] The stuck Sproxil file is classified: if its JD content is already
  covered by app 1 (Sproxil Product Manager, staged Aug 9), document that
  and delete the file; if it holds unique data, convert it to a valid
  outbox payload or re-route it through discovery — the decision is written
  down in the rejection sidecar
- [ ] Harness case: a malformed outbox file (missing `application_id`) is
  moved to `rejected/` AND the reason is recorded; a valid outbox file
  ingests cleanly with no regression
- [ ] `ingest_outbox` behavior otherwise unchanged (one transaction per
  file, consumed/rejected movement preserved)
