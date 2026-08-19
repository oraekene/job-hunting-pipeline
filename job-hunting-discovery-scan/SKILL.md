---
name: job-hunting-discovery-scan
description: "Run discovery scan scripts without hitting known bugs."
metadata:
  hermes:
    tags: [job-hunting, discovery, scripts, blueprint]
    category: job-hunting
    related_skills:
      - job-hunting-discovery
      - job-hunting-orchestrator
---

# Discovery Scan Scripts — Pitfalls & Fixes

Companion to `job-hunting-discovery`. Covers the **scripts** that execute the discovery pipeline in practice — `shared/01-job-discovery/scripts/discovery_scan_new.py`, `insert_discovered.py`, and related helpers. Read this before modifying or running those scripts.

## When this skill applies

Use when:
- Running the discovery scan scripts outside the main `job-hunting-discovery` pipeline (e.g., ad-hoc re-scans, debugging, testing filter logic).
- Modifying the scan scripts — new bugs can re-emerge in these three areas.
- Writing a new scan script — start from `references/scan-script-pitfalls.md`.

## Key pitfalls

### 1. Salary extraction: `[kK]` suffix must be inside the regex capture group
`r'\$(\d+[,.]?\d*)'` captures `215` from `$215K`, not `215000`. Fix: move `[kK]?` **inside** group 1, then multiply by 1000 in Python. The original code also double-multiplied (replacing `k`→`000` *and* `*1000`).

See `references/scan-script-pitfalls.md` §1 for full fix and test cases.

### 2. Sort by priority + recency *before* applying the daily cap
Web search returns results in arbitrary order. Without sorting, a 28-minutes-ago job can land in overflow while a 3-day-old job fills the last queue slot. Fix: sort `new_to_queue` by `(0 if high else 1, posted_hours_ago)` before slicing `[:remaining_slots]`.

See `references/scan-script-pitfalls.md` §2 for the verified sort key.

### 3. Overflow must be captured even when `remaining_slots == 0`
Old logic `if remaining_slots > 0 and len > remaining_slots else []` returns `[]` when the cap is full, silently dropping overflow. Fix: drop the `remaining_slots > 0` guard.

See `references/scan-script-pitfalls.md` §3 for the one-line fix.

## Verification pattern
After inserting queued postings into the DB, re-run the scan. Newly inserted postings should appear as "Skipped as duplicates" with 0 queued on the second pass (same day, same data).

## Gate state file
Write `shared/.discovery_gate_state.json` after each run with `last_run_at`, `mode`, `sources_checked`, `queued`, `today_queued`, `cap_reached`, `remaining_slots`.

## Fingerprint null-handling
Older rows may have `NULL` in `posting_fingerprint`. This is **correct** — NULL means "unknown, re-examine rather than skip." Do not `.fillna()` and risk false-merge duplicates.

## Related files
- `references/scan-script-pitfalls.md` — detailed bug descriptions, fix diffs, and test cases.
