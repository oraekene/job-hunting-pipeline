# 01 - Document the status-query commands in the orchestrator skill

**Status:** done (implemented 2026-08-17 by ticket single-base-remediation/02)

**Blocked by:** None

## Symptom

In the 2026-08-15 session, the agent asked "what's the pipeline state?" and ran
`pipeline_processor.py --status`, which does not exist:

```
pipeline_processor.py: error: unrecognized arguments: --status
```

It should have used the helpers that already exist and work:

- `python 00-orchestrator/scripts/_inspect_state.py` — DB path check, column
  list, status counts, one recent row.
- `python 00-orchestrator/scripts/_query_discovered.py` — the
  `discovered`/`building` queue with row details.

Neither is named in `00-orchestrator/SKILL.md`'s "Status queries" section
(lines 123-130), which only says "query the DB".

## Fix

Add to `00-orchestrator/SKILL.md` under "Status queries" one line pointing at
the two helper scripts, e.g.:

```
State counts + recent row: python 00-orchestrator/scripts/_inspect_state.py
Discovered/building queue: python 00-orchestrator/scripts/_query_discovered.py
```

## Verification

- RED (current): `python 00-orchestrator/scripts/pipeline_processor.py --status`
  → `error: unrecognized arguments: --status`
- GREEN (after): the skill's Status queries section names the two helpers, so
  an agent asked "what's pending?" runs `_inspect_state.py` and gets counts.
- Regression harness still 17/17 and dry-run still 29/29 after the doc edit
  (doc-only change, but re-run to be safe).

## Notes

No regression-test seam needed — documentation defect, verified by the
red/green loop above. Full context: `diagnostics/2026-08-15/diagnosing-bugs-findings.md`.