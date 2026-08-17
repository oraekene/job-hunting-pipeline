# 02 — Status-query docs + outbox cleanup

**What to build:** An agent asked "what's pending?" follows the orchestrator skill to the two working state commands instead of inventing a nonexistent `--status` flag; and the outbox confusion is dead — the stray root debug file is gone and the real ingest outbox is documented.

**Blocked by:** None — can start immediately.

**Status:** done (2026-08-17)

- [x] The orchestrator skill's status-queries section names `_inspect_state.py` (counts + recent row) and `_query_discovered.py` (discovered/building queue)
- [x] The stray root-level `.outbox/_inspect_db.py` debug file is removed
- [x] The processor's docs state the real ingest outbox is `shared/.outbox` (JSON only, `consumed/`/`rejected/` semantics)
- [x] `python 00-orchestrator/scripts/dry-run.py --skill-dir .` stays 29/29
- [x] `.scratch/orchestrator-status-query/issues/01-document-state-query-commands.md` is marked `done` (it is satisfied by this ticket)
