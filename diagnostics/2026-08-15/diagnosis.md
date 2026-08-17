# Diagnosis — 2026-08-15 job-hunting session post-mortem

**Date:** 2026-08-15
**Sources:** `deciding-what-to-work-on-20260815.json`, `deciding-what-to-work-on-20260815-logs-0818am.txt`
**Status:** diagnosis only — no fixes applied

---

## 1. The project-directory split (root confusion)

There are two separate git repos that both look like "the job-hunting project":

| | Documents repo | AppData repo (running pipeline) |
|---|---|---|
| Path | `C:\Users\rotim\Documents\job hunting port 0 (base)\job-hunting` | `C:\Users\rotim\AppData\Local\hermes\skills\job-hunting` |
| Remote | `github.com/oraekene/job-hunting.git` | `github.com/oraekene/job-hunting-pipeline.git` |
| Branch | `master` | `main` |
| `AGENTS.md` / `docs/agents/` | present (partial setup) | **absent** |
| Session files (`deciding-what-to-work-on-*.{json,txt}`) | present | **absent** |
| Role | planning / engineering-skills repo | the installed Hermes skill package the pipeline actually runs from |

Consequences:

- Every terminal call in the failed session used `C:\Users\rotim\AppData\Local\hermes\skills\job-hunting` as cwd — that is the repo the pipeline executes against.
- The `/setup-matt-pocock-skills` output (`AGENTS.md`, `docs/agents/issue-tracker.md`, `docs/agents/domain.md`) exists **only in the Documents repo**. The AppData repo has none of it.
- The session files the user referenced are in the Documents repo, not the repo they named as the project directory.
- **Fix direction:** run skill setup in the AppData repo (the running pipeline), and decide how the two repos are meant to relate (documents repo as an upstream mirror? a separate planning view?).

## 2. Skill-setup gaps (AppData repo)

- No `AGENTS.md`, no `CLAUDE.md`, no `docs/`, no `CONTEXT.md`, no `docs/adr/`.
- The `triage` skill IS installed, but there is no `docs/agents/triage-labels.md` anywhere and no `### Triage labels` block in any `AGENTS.md`.
- The `.scratch/<feature>/` local-markdown convention IS already in use (`.scratch/pipeline-completion/SPEC.md` + `issues/01–16`), but no `docs/agents/issue-tracker.md` documents it.
- Domain docs are declared single-context but no `CONTEXT.md` / `docs/adr/` exists (acceptable per domain.md "proceed silently" rule, but recorded here).

## 3. The session itself (`deciding-what-to-work-on-20260815.json`)

- Session `20260815_081325_ba9344`, titled "Deciding What to Work On", but the user asked to **run the full Job Hunt pipeline**.
- The run **never completed**:
  1. Agent loaded `job-hunting-orchestrator` skill and read `shared/pipeline-rules.md`.
  2. Called `pipeline_processor.py --status` — **flag does not exist** (valid flags: `--app-id --claim --reconcile --reject --restore --approval-queue --mark-approval-pinged --limit --dry-run`). Should have used `_inspect_state.py` / `_query_discovered.py`.
  3. Ran `pipeline_processor.py --reconcile` → **empty output, exit 0**. Matches known issue `11-reconcile-silent-when-idle` in `.scratch/pipeline-completion/issues/`.
  4. Session killed by HTTP 429 (`FreeUsageLimitError`) on `opencode-zen` / `deepseek-v4-flash-free` — 3 retries, then abort. No stage work done.

## 4. Provider / credential layer (the hard blocker)

- `opencode-go` / `deepseek-v4-flash`: **weekly usage limit reached** (GoUsageLimitError), resets ~1 day.
- `opencode-zen` / `deepseek-v4-flash-free`: 429 `FreeUsageLimitError` ("Rate limit exceeded. Please try again later.").
- `nous` / `poolside/laguna-xs-2.1:free` and `poolside/laguna-s-2.1:free`: 429 on the shared API key.
- **Fallback chain is dead weight:** `config.yaml` lines 5–9 list `opencode-zen / deepseek-v4-flash-free` twice. Log: *"Fallback skip: chain entry opencode-zen/deepseek-v4-flash-free resolves to the same backend as the current one"*. Same-backend entries are skipped, so there is effectively **no fallback** when the primary is saturated.
- Credential pool fully exhausted (`no available entries (all exhausted or empty)`); `OPENCODE_ZEN_API_KEY` marked exhausted/rotating.
- OpenRouter marked unhealthy (payment / credit error); `auxiliary.free_only` not set → **PAID lane may incur real spend** (`google/gemini-3.6-flash` is not a `:free` SKU).
- Copilot token exchange degraded to RAW token (may 400 for enterprise-only models).

## 5. Cron infrastructure failures

- **Both** production cron jobs failed outright on 429 this morning:
  - `Scan configured sources in shared/sources.yaml for …` (weekly usage limit, 3 retries over ~50 min).
  - `Pipeline sweep (reconcile + claim at most 3)` (weekly usage limit, 3 retries).
  - A third job (`b1bc74c7b1f5`, no_agent) returned `[SILENT]` / empty stdout — delivery skipped.
- `execute_code` is **BLOCKED in cron**: "execute_code runs arbitrary local Python … Cron jobs run without a user present to approve i…" — the discovery job tried it.
- Browser `open` stderr: URL query params interpreted as shell commands on Windows — `'f_TPR' is not recognized…`, `'f_WT'…`, `'sortBy'…`, `=dateThe system cannot find the file specified.` (URL not quoted → `&` splits into commands).
- **Rule-1 submit hook not installed:** `python ~/.hermes/agent-hooks/job-hunting-verify-submit-approval.py` fails — `~` is never expanded on Windows, resolving to `C:\Users\rotim\AppData\Local\hermes\~\.hermes\agent-hooks\...` (No such file). README install step 5 (`cp security/hooks/verify-submit-approval.py ~/.hermes/agent-hooks/`) was not completed. Security-relevant: Rule 1's third enforcement layer is absent.
- **Schema drift live in cron:** `SELECT * FROM posting_sources WHERE source = 'wellfound_search'` → `no such column: source`. The column is `source_name` (see `applications_db_schema_addendum_8.sql`). Exactly the class of bug ticket `02-schema-drift-gate` targets.
- One cron job hit **"Python was not found; run without arguments to install from the Microsoft Store"** — PATH/alias problem in the cron environment.
- Agent repeatedly called unknown tool **`shell`** instead of `terminal` ("Unknown tool 'shell' — sending error to model for agent-correction"). Matches the `agent-execution-discipline` spec.

## 6. Platform / network

- Telegram: `api.telegram.org` DNS resolution failed (`[Errno 11001] getaddrinfo failed`) for long stretches; fallback IPs also failed; gateway ran **with no connected platforms**; reconnect loop eventually succeeded via sticky fallback IP (~23:14). Delivery and command handling were degraded for ~an hour.
- Gateway life exited **UNCLEANLY** (SIGKILL / OOM / VM death) — no exit path ran.
- Desktop boot repeatedly failed: "Timed out waiting for Hermes backend port announcement (90000ms)", renderer "Timed out connecting to Hermes backend after 60000ms".
- A message-alternation violation was auto-repaired in another restored session (`20260813_213054_681ec1`).

## 7. Verified live facts (AppData repo)

- `python -c "...applications.db..."` → status counts: `awaiting_approval 9`, `discovered 35`, `rejected_by_kene 7`.
- `pipeline_processor.py` valid flags confirmed from `--help` (no `--status`).
- `.outbox/` non-empty (1 file pending ingest).
- `posting_sources` schema (addendum_8): columns `application_id, posting_url, source_name, discovered_by, first_seen_at, is_canonical` — **no `source` column**.
- `config.yaml` fallback_providers: two identical `opencode-zen / deepseek-v4-flash-free` entries.

## 8. Recommended next flow

- **`/diagnosing-bugs`** on the pipeline execution path. Tight feedback loop first:
  - `python 00-orchestrator/scripts/pipeline_processor.py --reconcile` (silent exit-0 — the live bug; matches ticket 11)
  - `python 00-orchestrator/scripts/dry-run.py` (19 invariants, no network, throwaway DB)
  - Begin with **schema-drift gate** (`no such column: source`) and **reconcile-silent** behaviour.
- Agent-ready tickets already exist and skip `/triage`:
  - `.scratch/pipeline-completion/issues/01–16` (AppData repo)
  - `.scratch/pipeline-execution-fixes/issues/01–06` (Documents repo)
  - `.scratch/review-gap-fixes/issues/01–05` (Documents repo)
  - `.scratch/compile-deploy/issues/01–11` (Documents repo)
- Operational (non-code) fixes to do by hand: provider config/fallback chain, `auxiliary.free_only`, install the submit hook, PATH for cron, Telegram DNS/fallback, clean the weekly-limit wait.

---
Generated by the diagnosis session on 2026-08-15. No repo changes made by this document.