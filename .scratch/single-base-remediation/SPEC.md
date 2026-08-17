# SPEC — Single-base remediation: consolidate, reconfirm, fix every issue from the 2026-08-15 diagnosis

**Status:** ready-for-agent

**Source:** `diagnostics/2026-08-15/diagnosis.md`, `diagnostics/2026-08-15/diagnosing-bugs-findings.md`, `.scratch/orchestrator-status-query/issues/01-document-state-query-commands.md`, snapshot comparison vs `job-hunting-as-at-14082026-15_58_30pm-before-using-deepseek-free`.

---

## Problem Statement

The job-hunting pipeline exists as two git repos that both look like "the project" — the Documents repo (`job-hunting.git`, planning/session files) and the AppData repo (`job-hunting-pipeline.git`, the installed Hermes skill package the pipeline actually runs from). The 2026-08-15 full-pipeline run failed on: provider 429s, an agent inventing a nonexistent `--status` flag, missing setup docs in the running repo, a broken Windows hook path, and 16 of 26 documented cron jobs never installed. A byte-level comparison against the 2026-08-14 snapshot proved the code has **zero regressions** — the failures are operational, documentation, and installation gaps, and the issue tracker itself is split across two repos.

## Solution

Make `github.com/oraekene/job-hunting-pipeline` the single base repository. Complete the skill setup docs there, port the 11 open tickets, fix the provider/hook configuration, make cron registration a repeatable install-time process built into the bundle, document the status-query commands, build the schema-drift gate, and clean the stray outbox file. Every fix is verified through the five seams (dry-run, regression harness, install-check, cron list, state inspection) without needing a live pipeline run.

## User Stories

1. As Kenechukwu, I want one canonical repository for the pipeline, so that agents and cron jobs never again confuse two trees.
2. As Kenechukwu, I want the AppData repo to be the only tree Hermes reads from, so that docs, tickets, and fixes land where the pipeline actually runs.
3. As Kenechukwu, I want the Documents repo's role explicitly declared (archive/planning mirror), so that its remaining files are never mistaken for the live pipeline.
4. As an agent, I want `AGENTS.md` in the running repo to name the issue tracker and triage labels, so that I file issues in the right place without being told.
5. As an agent, I want `CONTEXT.md` and an `docs/adr/` directory to exist in the running repo, so that domain context and architectural decisions are discoverable in one place.
6. As an agent, I want the orchestrator skill's status-query section to name the exact state commands, so that I never invent a nonexistent `--status` flag again.
7. As an agent, I want a schema-drift gate that fails loudly when SQL references a column the live schema does not have, so that wrong-column queries die at validation time instead of mid-run.
8. As Kenechukwu, I want the paid `opencode-go / deepseek-v4-flash` as the default model and `opencode-zen / deepseek-v4-flash-free` as a genuinely different fallback, so that the fallback chain is not skipped as same-backend dead weight.
9. As Kenechukwu, I want the submit-gate hook command to use a Windows-safe absolute path, so that the Rule-1 third enforcement layer actually fires.
10. As Kenechukwu, I want the db-ownership hook installed and registered too, so that both documented security hooks exist, not just one.
11. As someone installing the skills bundle fresh, I want cron registration to be an idempotent, repeatable install step, so that every job is registered automatically instead of by hand-typed commands.
12. As an installer, I want re-running registration to be a no-op for jobs already present, so that the process is safe to run repeatedly.
13. As an installer, I want the four blueprint jobs to keep surfacing as one-tap suggestions, so that the core loop stays effortless.
14. As an agent, I want the real outbox directory to contain only ingestible JSON records, so that reconcile never chokes on stray debug files.
15. As Kenechukwu, I want the 11 ready-for-agent tickets from the Documents repo visible in the single tracker, so that no open work is stranded in the old repo.
16. As an agent, I want `dry-run.py` to stay green after every doc or schema edit, so that package invariants remain the cheap first gate.
17. As an agent, I want the regression harness to keep pinning reconcile-silent-when-idle as by-design, so that nobody "fixes" it back into spam.
18. As Kenechukwu, I want a written verification checklist proving each diagnosed issue is gone, so that closure is evidence-based, not asserted.
19. As Kenechukwu, I want platform-level failures (Telegram DNS, gateway exits, desktop boot, execute_code policy) explicitly declared out of repo scope, so that effort is not spent patching what the repo cannot patch.
20. As an agent running cron jobs, I want cron prompts to avoid `execute_code` and unquoted browser URLs, so that blocked tools and shell-interpreted URLs stop burning run time.

## Implementation Decisions

1. **Single base repository.** `github.com/oraekene/job-hunting-pipeline` (AppData tree) is the single base. The Documents repo is frozen as a planning/archive mirror — no new code work there; its commit history and session files stay put. Record this as ADR-0001.
2. **Ticket porting.** Copy the 11 ready-for-agent tickets plus their two specs verbatim from the Documents repo into the AppData tracker, preserving feature folders: `pipeline-execution-fixes/` (spec + issues 01–06) and `review-gap-fixes/` (spec + issues 01–05). Statuses stay `ready-for-agent`. Porting is copy-only; no ticket content is rewritten.
3. **Setup completion.** Create `CONTEXT.md` (single-context domain pointer per the domain docs convention) and `docs/adr/0001-single-base-repository.md`. `AGENTS.md` and `docs/agents/*` already exist and are committed.
4. **Provider configuration (operational, file outside repo).** `config.yaml`: set default to `opencode-go / deepseek-v4-flash`; replace the duplicated `fallback_providers` entries with a single `opencode-zen / deepseek-v4-flash-free` entry. Do not configure OpenRouter. Leave MoA disabled. This fixes the "Fallback skip: same backend" dead chain and the free-tier weekly limit on the primary lane.
5. **Hook configuration (operational, file outside repo).** In `config.yaml` replace the hook command `python ~/.hermes/agent-hooks/job-hunting-verify-submit-approval.py` with the Windows absolute path `python C:\Users\rotim\.hermes\agent-hooks\job-hunting-verify-submit-approval.py` (the file already exists there). Install `security/hooks/verify-db-ownership.py` to the same agent-hooks directory and register its `pre_tool_call` block per `security/security-setup.md` section 3, with the same absolute-path form.
6. **Cron registration as a built-in process.** Add an idempotent registration script under `cron/` that treats the 23 non-blueprint jobs (name, schedule, script, skills, `--no-agent` flag, deliver target) as data sourced from the documented `cron-jobs.md` commands and runs `hermes cron create` only for jobs not already registered (matched by name/script). Wire it into the README install steps and `install-check.py` so a fresh install triggers the process; the four blueprint jobs stay one-tap via suggestions. Re-running registers zero new jobs. One-time action for the live install: run the process to register the missing jobs (18 registered on the 2026-08-17 live install).
7. **Status-query documentation.** Implement ticket `orchestrator-status-query/01`: add the two helper-command citations to the orchestrator SKILL.md status-queries section (`_inspect_state.py` for counts + recent row, `_query_discovered.py` for the discovered/building queue).
8. **Schema-drift gate.** Implement ported ticket `pipeline-execution-fixes/02`: a validation assertion that every SQL column reference in the processor's queries resolves against the live table schema, failing on any mismatch; wire it into the existing validation flow (dry-run/harness family); correct the observed wrong-column queries (`source` vs `source_name`, and the other wrong-column references listed in the ticket) where they appear in repo code. Note: the `WHERE source = 'wellfound_search'` query that failed in the 2026-08-15 cron run was agent-authored ad-hoc SQL, not repo code — the gate exists to make that class of failure impossible to miss.
9. **Outbox cleanup.** Remove the stray root `.outbox/_inspect_db.py` debug file. The processor's real ingest outbox is `shared/.outbox/` (JSON only, with `consumed/` and `rejected/`); document this in the processor's outbox doc section so agents stop pointing at the wrong directory.
10. **Reconcile silence.** No code change — silence when idle is by-design and pinned by the regression harness case. Ticket 11 already documents this as done.
11. **Platform-level failures.** Telegram DNS, unclean gateway exit, desktop boot timeouts, `execute_code` blocked in cron, browser URL shell-interpretation, unknown `shell` tool, and cron PATH ("Python was not found") are Hermes platform/environment issues outside this repo. The spec records them as an operational checklist for monitoring — no repo code changes.
12. **Verification artifact.** Implementation results are recorded in the same feature folder (per-issue check results against the five seams) so closure is auditable.

## Testing Decisions

- **What makes a good test:** external behavior only — run the CLI, assert exit code and output shape; never assert internal implementation.
- **Seams (as agreed):**
  1. Package seam — `python 00-orchestrator/scripts/dry-run.py --skill-dir .` (29 checks, throwaway DB, no network). Must stay green after doc/schema/skill edits.
  2. Processor seam — `python 00-orchestrator/scripts/regression-harness.py --skill-dir .` (17 cases). Run after any script change.
  3. Install seam — `python 00-orchestrator/scripts/install-check.py` plus the new registration script; second registration run must register zero jobs.
  4. Cron seam — `hermes cron list` must show all 26 documented jobs after registration.
  5. Config/state seam — config file read confirms default model and fallback chain; `python 00-orchestrator/scripts/_inspect_state.py` confirms DB state claims.
- **Prior art:** the harness's `reconcile_silent_when_idle` case; dry-run's static package-integrity and honesty checks (currency, seniority penalty, mojibake).
- **New tests:** one harness (or dry-run) case for the schema-drift gate — a mutation check that a wrong-column reference fails; one idempotency check for the cron registration script (second run = zero new registrations).

## Out of Scope

- Hermes platform bugs: Telegram DNS, gateway unclean exit, desktop boot timeouts, `execute_code` cron policy, browser tool URL quoting, `shell` tool alias, Python-not-found PATH.
- OpenRouter configuration (explicitly ignored as a fallback by Kenechukwu).
- The Documents repo's compile-deploy feature (interactive Cloudflare/credentials items stay there).
- Changing Hermes itself to allow multiple blueprints per skill.
- A live end-to-end pipeline run — the five seams verify the fixes without spending provider budget.

## Further Notes

- Evidence base lives in `diagnostics/2026-08-15/` (diagnosis + diagnosing-bugs findings) and the 2026-08-14 snapshot comparison concluded zero regressions.
- The `--status` session failure was an agent guessing a flag; the fix is documentation (ticket 01), not a new flag.
- After implementation, each issue closes by recording its seam result in this folder, not by assertion.
