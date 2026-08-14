# 16 — Tighten scoring: apply the seniority penalty, cap overalls

**What to build:** The 2026-08-13 scores were liberal in two measurable
ways:

1. **Seniority penalty not applied.** The keyword schema's seniority rule
   ("title contains Senior/Lead/Manager → no transferable credit for
   domain keywords; industry mismatch → −25%") should have fired for the
   Figma and Camunda builds (all titles contain "Manager", candidate
   lacks design-tools / enterprise-process-automation industry history).
   Raw = final everywhere (77=77, 92→68 "adjusted", 75=75) — the −25%
   penalty never landed in `match_score_percentage`.
2. **Overall scores outrun their own evidence.** Stated overalls (77/68/75
   for apps 11/12/14) sit well above the mean of their own per-requirement
   tables (65/61/60 respectively). A score that the artifact's own
   arithmetic can't reproduce is an inflated score.

Tighten both, enforce with dry-run checks, and correct the affected
artifacts/rows.

**Blocked by:** None — can start immediately

**Status:** done

- [x] `04-keyword-analysis/references/keyword-json-schema.md`: seniority
  penalty is mandatory — `match_score_percentage` must equal
  `round(raw_match_score_percentage * 0.75)` when the title contains
  Senior/Lead/Manager/Principal and the industry is not a strict match;
  both raw and final recorded in `analysis` (`raw_match_score_percentage`,
  `match_score_percentage`, `seniority_penalty_applied: true|false`)
- [x] `03-resume-match/SKILL.md`: overall score must be reproducible from
  the per-requirement table (overall ≤ round(mean of per-req × 10), with
  a stated margin only when justified); hard-gate rule added — an unmet
  mandatory requirement (e.g. "N+ years PM") caps the overall below the
  auto-stage minimum regardless of other credits
- [x] dry-run static check: for every `build_artifacts/app_N/
  keyword_analysis.json` with `analysis.raw_match_score_percentage`
  present, the recorded `match_score_percentage` must reflect the
  penalty (or a justified absence) — no silent raw=final for
  Manager-titled JDs. Title taken from the applications DB
  (role_title). Legacy files without raw are not flagged
- [x] Apps 11/12/14 re-scored: keyword JSONs now carry
  raw=77→58 / 92→69 / 75→56 with `seniority_penalty_applied: true`;
  resume_match overalls recomputed to be reproducible from their own
  per-req tables (app_11 58, app_12 61, app_14 60); app_11 & app_12
  state the hard gate (5+/7+ years PM not met), app_14 states the
  table-mean cap; Gate 1 verdicts rewritten to NOT PASSED
- [x] DB rows 11/12/14 corrected (documented one-off):
  overall 77→58 / 68→61 / 75→60, keyword 77→58 / 92→69 / 75→56
- [x] Staging question surfaced and answered by Kenechukwu: all three
  rows unstaged (status `discovered`) — they were below
  `match_score.minimum` (65) and he chose not to override
- [x] Harness unaffected: 17/17 green; dry-run scoring/currency checks
  green (suite 27/29 — the 2 remaining failures are the in-flight
  `job-hunting-artifact-qa` skill refs + stale skill count, out of this
  ticket's scope)
