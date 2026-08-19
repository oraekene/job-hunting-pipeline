# Sweep-Run Operational Lessons — session-verified 2026-08-17 (apps 20/21/22)

Lessons from a full manual sweep: reconcile → build artifacts for 3 discovered
apps (parallel subagent dispatch) → claim → commit → Telegram approval handoff.
The pipeline's own skills (orchestrator, approval-submit) are user-owned and
cannot be patched by the curator; these notes keep the executable detail in the
one curator-managed skill of the family.

## 1. Live JD drift from the DB row — score the LIVE posting (app_21 Arize)

DB rows go stale between discovery and build. app_21's row said
`AI Product Manager / seniority mid / $150k–220k / Remote / title_matched`,
but the LIVE Wellfound page showed **Senior** AI Product Manager, Observability,
$200k–250k, Remote (United States) only, with a 3–5+ years PM/AI-ML gate and an
engineering/tech-lead requirement.

- Always re-extract the live posting at build time and score THAT. The live
  page wins on title/salary/remote scope; the discovery row is a hint, not
  evidence.
- A stale "AI Product Manager / mid" row would have skipped the 25% seniority
  penalty and granted transferable domain credit it must not get. Scoring the
  live Senior title changed app_21 from a plausible ~mid-70s pass to 59% raw /
  44% penalized Gate 1 FAILED — staging vs not staging.
- Record the drift explicitly in `resume_match.md`'s Gate 1 verdict line so the
  human approval gate sees the correction and can reproduce the score.
- Same discipline for remote scope ("Remote (US only)" vs "Remote") and salary
  band — both change the visa/location eligibility note and the Gate-2 comp
  analysis.

## 2. Dead stored URL ≠ gone posting (app_22 Guidewire)

A stored `posting_url` can be a placeholder or break while the role is still
live elsewhere. app_22's stored URL (`https://www.indeed.com/viewjob?jk=guidewire1`
— not a valid Indeed key) 404'd, but a web search for the exact role title +
company found the live posting on Guidewire's own careers page
(`guidewire.com/about/careers/jobs/outbound-product-manager--ai-and-workflow-automation-jr_14798`).

- Before rejecting as `gone`: web_search the exact role title (quoted) +
  company, fetch the company's careers site, build against the REAL posting URL.
- Note the URL correction in the approval ping so the human gate knows the JD
  came from the company site, not the dead stored link.

## 3. Subagent mid-build failure — parent completes in place (app_20)

Of three parallel `delegate_task` builds, one died mid-build with an upstream
connection error after writing only `keyword_analysis.json`; the other two
completed. The parent resumed the failed app's build itself.

- Check the delegation live transcripts (`~/.cache/delegation/live/<id>/task-*.log`)
  rather than assuming a dispatched batch is healthy; a child can die silently
  after its last visible tool call.
- **Do not restart a partial build from zero.** Preserve the surviving
  artifact(s) — the verified `keyword_analysis.json` is the canonical score
  source — and author the remaining 7 files against it in place, keeping every
  downstream number consistent with the surviving JSON.
- Re-run the canonical verifier on the completed dir before claiming/committing.
  Three independently-authored sets must each pass the same verifier before any
  of them is committed.

## 4. Approval ping mechanics (hermes send CLI)

The orchestrator/approval-submit skills say "a real Telegram send, confirmed
delivered" but do not carry the executable detail.

- Delivery channel: `hermes send --to telegram:<chat_id> --file <message.txt> --json`.
  Discover the target with `hermes send --list telegram` (prints e.g.
  `telegram:Nft Kene  [5229564924]` — the numeric id is the `<chat_id>`).
- **Delivered = `"message_id": N` AND `"mirrored": true` in the `--json`
  output.** Only then run `--mark-approval-pinged`. A `"error": "Telegram send
  failed: Timed out"` result means NOT delivered — leave `approval_sent_at`
  NULL, keep the row in the queue, retry ONCE (app_22's first send timed out;
  the immediate retry delivered with `message_id: 182`).
- Message body: temp file with a `MEDIA:<absolute-path>` line attaching the
  `risk_tactics_change_log.md` as a downloadable document, plus
  company/role/verdict summary and the single approve/edit/skip question.
  Include the ready-to-paste `/moa` prompt when the change-log has a
  `[BORDERLINE PASS]` entry (app_22 pattern — see
  `09-risk-tactics-gate/references/moa-cross-check.md` for the envelope format).
- **Windows path pitfall:** `hermes send` is a native Windows binary — `--file`
  needs a native `C:\Users\...` path with escaped backslashes in bash
  (`"C:\\...\\ping.txt"`). MSYS `/c/Users/...` paths fail with `cannot read ...
  No such file or directory` even though bash itself resolves them.
- **D10 before each ping:** `curl -s -o /dev/null -w "%{http_code}" -L -A
  "Mozilla/5.0..." <posting_url>` must return 200. A 404/redirect at ping time
  means the posting is gone — surface as information (set `posting_gone_at` /
  `posting_gone_signal`), don't ask for a decision on a dead role.
- **`--mark-approval-pinged` only writes `approval_sent_at`; it does NOT change
  status.** After the mark succeeds (row still `staged`), transition status
  separately in the same logical transaction:
  `UPDATE applications SET status='awaiting_approval' WHERE id IN (...) AND
  status='staged' AND approval_sent_at IS NOT NULL`. Skipping this leaves the
  row at `staged` with a timestamp — half-asked and invisible to the next
  `--approval-queue`.

## 5. Verifier state

The sibling verifier copy at `job-hunting-artifact-qa/scripts/verify_app_artifacts.py`
still carries the old 3-arg `check()` bug (crashes on its first check). Apply
`def check(cond, msg, fails=None)` with the append guarded by `fails is not
None` — same one-line fix applied to this skill's copy on 2026-08-17 (verified
ALL CHECKS PASSED on apps 20/21/22).