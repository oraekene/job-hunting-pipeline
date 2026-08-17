# diagnosing-bugs findings — 2026-08-15

Applies the `/diagnosing-bugs` discipline to the failed `deciding-what-to-work-on`
session. Companion to `diagnosis.md` in this folder.

## Feedback loop built

| Command | Verdict | Meaning |
|---|---|---|
| `python 00-orchestrator/scripts/dry-run.py` | **29/29 GREEN** | Package integrity + fixture pipeline invariants hold |
| `python 00-orchestrator/scripts/regression-harness.py --skill-dir .` | **17/17 GREEN** | Processor CLI end-to-end on throwaway DB |
| `python 00-orchestrator/scripts/pipeline_processor.py --reconcile` | exit 0, **empty stdout** | **By design** — GREEN case `reconcile_silent_when_idle` pins it |
| `python 00-orchestrator/scripts/_inspect_state.py` | prints counts + row | Works |
| `python 00-orchestrator/scripts/_query_discovered.py` | prints 35 pending | Works |

Live DB state (explains the silent reconcile): 35 `discovered`, 9
`awaiting_approval`, 7 `rejected_by_kene`; **no `building` rows, no retryable
`failed` rows**; `.outbox/` holds one stray helper script (`_inspect_db.py`), not
a JSON record. Nothing for reconcile to do → correctly silent.

## Conclusion

**The pipeline processor and package are not broken.** The session failed for
two reasons, neither a code bug in this repo:

1. **Operational: provider 429s.** `opencode-go` weekly limit hit, `opencode-zen`
   `FreeUsageLimitError`, `nous` key rate-limited, fallback chain points at the
   same backend (`config.yaml` lines 5–9), credential pool exhausted, OpenRouter
   unhealthy, `auxiliary.free_only` not set. Fix is configuration, not code.
2. **Agent didn't know the status command.** It called
   `pipeline_processor.py --status`, which does **not exist** (valid flags are
   `--app-id --claim --reconcile --reject --restore --approval-queue
   --mark-approval-pinged --limit --dry-run`). The correct helpers
   (`_inspect_state.py`, `_query_discovered.py`) exist and work but are **not
   named** in the orchestrator SKILL.md "Status queries" section (lines 123–130),
   which only says "query the DB".

## The one code-adjacent defect (ready-for-agent)

**Finding:** the orchestrator skill's "Status queries" section does not tell an
agent which command answers "what's pending?", so an agent reaching for state
invents `--status` and fails.

- **Tight loop (red-capable):**
  - RED: `python 00-orchestrator/scripts/pipeline_processor.py --status` →
    `error: unrecognized arguments: --status`
  - GREEN: `python 00-orchestrator/scripts/_inspect_state.py` → prints status counts
- **Fix:** add one line to `00-orchestrator/SKILL.md` under "Status queries":
  point at `python 00-orchestrator/scripts/_inspect_state.py` (counts + recent
  row) and `_query_discovered.py` (the discovered/building queue).
- **No regression seam needed** — this is documentation, verified by the
  red/green loop above.

## Not code bugs (operational, do by hand)

- Install the Rule-1 submit hook (`security/hooks/verify-submit-approval.py` →
  `~/.hermes/agent-hooks/`) — `~` never expanded on Windows; README step 5
  incomplete.
- Fix `config.yaml` fallback chain (same-backend entries are skipped).
- Set `auxiliary.free_only: true` to avoid PAID-lane spend.
- Wait out / top up the opencode weekly limit before any pipeline run.
- PATH for cron (Microsoft Store python alias), Telegram DNS/fallback, unclean
  gateway exit, desktop backend-port timeouts.

## Hand-off

Not architecture — nothing for `/improve-codebase-architecture`. The actionable
fix is the one-line SKILL.md status-query citation; operational items are in
`diagnosis.md` §4–§6.