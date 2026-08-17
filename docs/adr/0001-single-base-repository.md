# ADR-0001: Single base repository — job-hunting-pipeline

**Date:** 2026-08-17
**Status:** Accepted

## Context

The job-hunting project existed as two git repos that both looked like "the
project":

- `C:\Users\rotim\Documents\job hunting port 0 (base)\job-hunting` —
  `github.com/oraekene/job-hunting.git`, branch `master`. Held session files,
  planning tickets, and a partial engineering-skills setup.
- `C:\Users\rotim\AppData\Local\hermes\skills\job-hunting` —
  `github.com/oraekene/job-hunting-pipeline.git`, branch `main`. The installed
  Hermes skill package the pipeline actually runs from (cron `Workdir` points
  here; scripts resolve their skill root here).

Every terminal call in pipeline sessions used the AppData tree as cwd, but
setup output and tickets landed in the Documents repo. The 2026-08-15
diagnosis identified the split as root confusion: agents could not tell which
tree was live.

## Decision

`github.com/oraekene/job-hunting-pipeline` is the **single base repository**:

- All skill-setup docs, tickets, ADRs, diagnostics, and fixes land here.
- The Documents repo is frozen as an **archive/planning mirror**: its commit
  history and session files stay put; no new code work happens there.
- Ready-for-agent tickets that still live in the Documents repo were ported
  verbatim into this repo's tracker (`.scratch/pipeline-execution-fixes/`,
  `.scratch/review-gap-fixes/`).

## Consequences

- Agents and cron jobs read from exactly one tree.
- Planning-history lookups still work via the Documents repo (read-only).
- The Documents repo may fall out of sync with the live tree; it must never
  be treated as authoritative again.
