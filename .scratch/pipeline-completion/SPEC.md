# Spec: Make the job-hunting pipeline complete end-to-end

**Slug:** pipeline-completion
**Status:** ready-for-agent
**Tracker:** local (`.scratch/pipeline-completion/issues/`)

## Problem Statement

Kenechukwu cannot get a single job application through the full pipeline. The
pipeline currently stalls or destroys work at three distinct choke points:

1. **Apps die before staging.** The sweep claims `discovered` rows even when no
   stage artifacts exist, leaves them at `building`, then — after the 7-hour
   staleness window — the reconcile marks them `vanished` and burns a build
   attempt. Three such burns make an application terminal `failed`, even when a
   complete 8-artifact build sits on disk. This has already happened: app 2
   (Apera AI) is terminal `failed` with its full build parked in
   `build_artifacts/app_2.failed-3`, and app 5 (EvolutionIQ) is on its second
   burned attempt.
2. **Gate data is silently wrong or missing.** `keyword_match_score` lands as
   0.0 for apps 3 and 4 because the processor reads a top-level JSON key that
   stage 4 nests inside `analysis`. The overqualification gate is recorded as
   NULL even when `resume_match.md` states a verdict, because the parser's
   vocabulary does not match the artifacts' vocabulary. The honest displayed
   resume title ("Product Manager") never makes it into the DB, which keeps the
   JD title ("Principal …").
3. **Staged applications never reach approval.** No application has ever been
   pinged for approval (`approval_sent_at` is NULL for all staged rows). The
   orchestrator's instruction to hand staged rows to approval-submit is
   executed by nobody.

Compounding this, the package's own integrity gate (`dry-run.py`) is red: a
rogue auto-created skill (`job-hunting-build-artifacts`) ships without
`metadata.hermes` and references template paths that do not exist — the exact
wrong paths that degraded the app-3 build during the 2026-08-12 run. The
bundle also states stale skill counts (25 vs actual 26).

The environment the pipeline runs in is hostile: the free-tier LLM API
rate-limits (HTTP 429) kill cron sweeps mid-run, timeouts (HTTP 524) kill
long turns, and Telegram connectivity is intermittent. These are external
challenges, but today the pipeline converts each infrastructure hiccup into a
permanent application loss (attempt burning). That coupling is a pipeline
bug, not an environment fact.

## Solution

From Kenechukwu's perspective:

- Every application that has a complete build reaches `staged`, and every
  staged application is offered for approval (Telegram ping) exactly once,
  with no silent losses.
- Infrastructure interruptions no longer consume build attempts; a killed run
  resumes on the next tick from wherever it left off, and finished work is
  never discarded.
- Gate values in the DB (keyword score, overqualification verdict, displayed
  title) always match what the stage artifacts actually recorded.
- `dry-run.py` is green: the package is self-consistent, and it stays green
  because the checks that catch this class of bug exist.

## User Stories

1. As Kenechukwu, I want queued postings to be staged rather than silently
   failed, so that applications I'm actually interested in don't die from
   infrastructure hiccups.
2. As Kenechukwu, I want a build attempt to be consumed only when real
   building work happened, so that rate-limit deaths don't permanently kill
   an application.
3. As Kenechukwu, I want complete build artifacts preserved when the commit
   step fails, so that a fixable processor bug doesn't destroy hours of
   tailoring work.
4. As Kenechukwu, I want terminal-failed applications with complete artifacts
   recoverable, so that app 2 (Apera AI) can be salvaged without rebuilding.
5. As Kenechukwu, I want the sweep to exit with a non-zero code when it fails
   to stage anything, so that cron can detect and surface pipeline failures.
6. As Kenechukwu, I want `keyword_match_score` in the DB to equal the score
   the keyword-analysis stage actually computed, so that analytics and
   approval decisions see real numbers.
7. As Kenechukwu, I want the overqualification verdict recorded whenever the
   resume-match stage stated one, so that no gate is silently NULL.
8. As Kenechukwu, I want the displayed resume title stored in the DB to be
   the honest title the customizer chose, so that the pipeline doesn't claim
   I inflated "Principal" when I didn't.
9. As Kenechukwu, I want every staged application to trigger an approval
   request to me, so that applications stop piling up un-reviewed.
10. As Kenechukwu, I want the outbox to reject malformed files with a clear,
    actionable error instead of silently quarantining them forever, so that
    the stuck Sproxil file gets resolved.
11. As Kenechukwu, I want artifact and DB content free of mojibake (naira
    symbol, em-dashes), so that my documents don't ship with `?` characters.
12. As Kenechukwu, I want `dry-run.py` to pass, so that I can trust the
    package before pointing it at real employers.
13. As Kenechukwu, I want the rogue skill that the background curator created
    removed or made legitimate, so that package integrity checks can't be
    accidentally satisfied by deleting the check.
14. As an agent picking up a ticket, I want a red-capable, deterministic,
    fast regression loop for the processor state machine, so that I can
    prove fixes without touching the live applications DB.
15. As Kenechukwu, I want the pipeline to tolerate the free-tier model's rate
    limiting, so that a 429 doesn't silently fail a cron job.

## Implementation Decisions

- **Claim-after-artifacts rule.** The sweep only claims a `discovered` row
  when its 8 required artifacts already exist (or it performs the build in
  the same bounded run before claiming). Claiming an artifact-less row and
  leaving it at `building` is forbidden. `build_attempts` therefore measures
  real build work.
- **Failure exits.** Sweep mode returns a non-zero exit code when it claimed
  zero rows or failed to stage a claimed row; cron can key on the exit code.
- **Reconcile preservation.** Reconcile distinguishes a complete 8-artifact
  build from a partial one. Complete builds are never moved to `.failed-N`
  and never burned as `vanished`; they are left in place for a retryable
  commit. Only genuinely partial builds get the stale treatment.
- **Recovery path for terminal-failed rows.** A new processor sub-command
  (e.g. `--restore <id>`) resets a terminal `failed` row with a complete
  build back to `discovered` (or straight to a claimable state) so a fixed
  pipeline can stage it. Restore does not fabricate gate data — it re-reads
  everything from artifacts at commit time, exactly as normal commits do.
- **Artifact contract alignment.** The processor reads
  `analysis.match_score_percentage` (nested) as the canonical keyword score,
  falling back to the top-level key only when the nested key is absent. The
  04-keyword-analysis SKILL.md output contract is updated to state the
  canonical location explicitly, and to require UTF-8 output.
- **Gate vocabulary alignment.** The overqualification parser accepts the
  vocabulary stage artifacts actually use (PASSED / CLEAN / FLAGGED /
  DROPPED / SKIPPED, with and without markdown bold), normalizes to the DB
  enum, and never silently records NULL when a verdict text exists.
- **Honest title persistence.** At commit, the processor persists the
  displayed title parsed from the resume change-log into `title_displayed`
  when present; the JD title stays in `title_original`.
- **Approval handoff automation.** The sweep prompt/script is amended so
  that, after committing, it hands every row with `status='staged' AND
  approval_sent_at IS NULL` to `10-approval-and-submit`. The handoff sets
  `approval_sent_at` only after the ping actually fires.
- **Outbox strictness.** Outbox ingestion keeps rejecting non-conforming
  files, but rejection now records the reason into the file and the sweep
  report surfaces it; the stuck Sproxil file is classified and re-processed
  or deleted by hand through a documented decision, not left in limbo.
- **Encoding discipline.** All processor writes use explicit UTF-8; artifact
  authors are instructed to emit the currency symbol as `NGN` or `₦` (never
  a replacement character); a dry-run static check asserts no replacement
  characters in shared artifacts.
- **Package repair.** The rogue `job-hunting-build-artifacts` skill is either
  deleted or given valid `metadata.hermes` frontmatter plus corrected
  reference paths; skill-count statements are updated to the real number and
  a dry-run check keeps them honest.

## Testing Decisions

- **What makes a good test here:** tests assert the processor's external
  behavior through its CLI and the resulting DB rows / artifact files — never
  internal function shapes. A test is good if it can catch this class of bug
  (state machine destroying data, parser silently returning defaults) without
  needing the live DB.
- **The regression seam (highest, single):** a sandboxed processor harness
  that copies the real `applications.db` into a throwaway dir, seeds a row,
  runs `pipeline_processor.py --claim` / `--app-id` / sweep / `--reconcile`
  against it, and asserts the resulting status, gate columns, and exit codes.
  This is the same loop used to diagnose the bugs in this spec (a
  PowerShell/Python harness already exists in a temp dir; the ticket commits
  it to the repo in durable form).
- **Modules tested:** the orchestrator processor (claim/commit/reconcile/
  sweep/restore), gate-column parsing (keyword score, overqualification,
  title), outbox ingestion, plus the existing `dry-run.py` static checks
  (extended with the encoding check and kept green).
- **Prior art:** `00-orchestrator/scripts/dry-run.py` — the package's own
  fixture pipeline with a throwaway database — is the pattern to extend and
  the bar for "the check exists and is enforced".

## Out of Scope

- Fixing the free-tier API rate limits, Copilot 403s, Cloudflare 524s, or
  Telegram DNS failures themselves (Hermes-level infrastructure).
- Making the sweep's LLM stage-building faster or cheaper.
- Parallel-mode sweep verification.
- Interview-prep, analytics, or any stage not on the staging/approval path.
- Auto-submission of applications (never on the table, by Rule 1).

## Further Notes

- The 2026-08-12 run log and session export that motivated this spec live in
  `C:\Users\rotim\Documents\RANDOM QUESTIONS\` ("hermes agent log file …" and
  "run-full-job-pipeline-with-templates-…json").
- Yesterday's `too many values to unpack` bug is already fixed in the working
  copy; this spec is about locking the whole class down, not re-fixing it.
- Tickets in `.scratch/pipeline-completion/issues/` are numbered in
  dependency order; the numbering is the blocking-edge reference.
