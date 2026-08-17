# CONTEXT.md

Single-context map of the job-hunting pipeline. Read this before exploring.

## What this repo is

`github.com/oraekene/job-hunting-pipeline` — a Hermes skill package that turns
Kenechukwu's job-hunting prompts and tactics into a pipeline: discovers
postings, tailors every application, stops for a one-tap Telegram approval
before anything is ever sent, and improves over time. **This is the single
base repository and the only tree Hermes runs the pipeline from.**

## Repo roles (ADR-0001)

- **This repo (single base):** the installed skill bundle Hermes executes.
  All docs, tickets, ADRs, and fixes land here.
- **Documents repo (`github.com/oraekene/job-hunting.git`):** frozen as an
  archive/planning mirror. Session files and planning history stay there; no
  new code work.

## Domain glossary

- **Application** — one job posting discovered and tracked in
  `shared/applications.db`.
- **Status** — an application's lifecycle state: `discovered`, `building`,
  `staged`, `awaiting_approval`, `approved_sent`, `rejected_by_kene`.
- **Sweep** — a scheduled pass of the pipeline: reconcile, then claim at
  most 3 applications to build.
- **Stage / staging** — a completed build ready for approval. Nothing is
  ever sent without Kenechukwu's approval (Rule 1, `shared/pipeline-rules.md`).
- **Submit gate** — the one-tap Telegram approval step; enforced by the
  `pre_tool_call` submit-gate hook as the third enforcement layer of Rule 1.
- **Outbox** — `shared/.outbox/` — JSON records agents write for the
  processor to ingest (`consumed/`, `rejected/`). Not the root-level debug
  folders.
- **Build artifact** — per-application stage output under
  `shared/build_artifacts/app_N/` (jd_analysis, resume_match, keyword
  analysis, cover letter, QA, change logs).
- **Blueprint** — a Hermes automation declaration in a skill's frontmatter;
  a skill can carry exactly one. Four jobs ship as blueprints; the rest are
  registered by the idempotent cron-registration process.

## Where things live

| Concern | Location |
|---|---|
| Pipeline rules (Rule 1) | `shared/pipeline-rules.md` |
| Orchestrator + processor CLI | `00-orchestrator/` |
| Cron jobs + registration | `cron/` |
| DB schema + addenda | `shared/` |
| Security hooks + setup | `security/` |
| Issue tracker (local markdown) | `.scratch/<feature>/` |
| Triage labels | `docs/agents/triage-labels.md` |
| Diagnostics / post-mortems | `diagnostics/` |

## Verification seams

- Package invariants: `python 00-orchestrator/scripts/dry-run.py --skill-dir .`
- Processor regression: `python 00-orchestrator/scripts/regression-harness.py --skill-dir .`
- State inspection: `python 00-orchestrator/scripts/_inspect_state.py`
- Discovery queue: `python 00-orchestrator/scripts/_query_discovered.py`
