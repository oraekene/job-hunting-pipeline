# 11 — Reconcile-only cron must be silent when idle

**What to build:** The 30-minute reconcile safety net was spamming Telegram
every tick with "Outbox: empty." because `pipeline_processor.py --reconcile`
always printed a header even when it did nothing. The no-agent cron script
treats empty stdout as silent, so the processor must print NOTHING on a
no-op reconcile while still printing every real action (outbox ingested,
build preserved, partial burned, retry returned).

**Blocked by:** None — can start immediately

**Status:** done

- [x] Regression case `reconcile_silent_when_idle` in the harness: all rows
  discovered, outbox empty, `--reconcile` exits 0 with empty stdout (red
  before the fix, green after)
- [x] `reconcile()` prints nothing when idle; action lines unchanged
- [x] `ingest_outbox` no longer prints "Outbox: empty." when empty; consumed/
  rejected lines still print
- [x] Harness 16/16 green including the new case
