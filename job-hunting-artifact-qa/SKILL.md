---
name: job-hunting-artifact-qa
description: "Verify job-hunting artifacts against processor contracts."
metadata:
  hermes:
    tags: [job-hunting, artifacts, qa, verification, pipeline-processor]
    category: job-hunting
---

# Job-Hunting Artifact QA

## When this skill applies

Use this when authoring or QA-ing an offline job-application artifact set in
`job-hunting/shared/build_artifacts/app_N/` (cron subagent builds, stages 2–9),
or whenever a downstream processor will parse those artifacts. It encodes the
**exact parsing contracts** of `00-orchestrator/scripts/pipeline_processor.py`
(empirically verified against app_15/app_16/app_18 output), the Senior-title
scoring conventions, and a re-runnable verification harness. The goal: artifacts
that parse correctly at commit time so the processor never mis-stages or
mis-records an application.

Do NOT use this to author the artifacts themselves (that is the user's
`job-hunting-build-artifacts` / stage skills) — this is the QA layer on top.

## Key contracts (summary — full detail in references/)

1. **`overall_match_score` = the FIRST `(\d+)%` in `resume_match.md`.** Follow
   the app_15/app_18 convention: `## Overall Match Score: 73% raw / 55% with
   seniority penalty` — raw score first. The processor stores the raw number,
   even when the artifact's own Gate 1 verdict is evaluated on the penalized
   score. Divergence trap: for Senior titles the raw score can clear
   `match_score.minimum` (65) while the penalized score fails — the markdown
   verdict must state the penalized basis explicitly.
2. **`keyword_match_score` = nested `analysis.match_score_percentage`** in
   `keyword_analysis.json` (top-level key is only a legacy fallback). Always
   nest it under `analysis`.
3. **Gate 2 verdict** is parsed from a line matching
   `Gate\s*2[^\n]*?verdict[^\n]*?:` — write `**Gate 2 verdict**: [PASSED] —
   not overqualified. ...` so "passed" normalizes to DB enum `clean`.
4. **Displayed title** comes from the `## Tactic 2` table: header row MUST be
   `| Original Title | Displayed Title | Evidence | Status |`; the first data
   row's `cells[1]` is the recorded title (never inflate — no Senior variants).
5. **Risk-gate counts** match `[PASS]`, `[FAIL]`, `[BORDERLINE PASS]`,
   `[CORRECTED]`, `[UNVERIFIED]` over the WHOLE file — including the "Final
   counts" summary lines, so each declared count in the summary adds a phantom
   +1 to the processor's raw count. `[PASS]` does NOT match inside
   `[BORDERLINE PASS]` (space before PASS). Keep the bracket format anyway;
   this is the established convention.
6. **open_gaps rows** are extracted from `[FAIL]` entries in
   `risk_tactics_change_log.md`: one-line form `[FAIL] <claim> — <missing
   evidence>` (em-dash separator; the claim must not contain an em-dash), or
   `### [FAIL] <claim>` followed by a `Missing evidence:` line within 3 lines.
   Never write `[FAIL]: N` summary lines in a form the extractor could mistake
   for gaps (the `(?!:)` guard handles this — but keep claims em-dash-free).

## Scoring conventions for Senior-titled roles

- Per `04-keyword-analysis/references/keyword-json-schema.md`: when the JD
  title contains "Senior"/"Lead"/"Manager" and the candidate lacks the specific
  industry experience, do NOT grant transferable credit for domain keywords and
  apply a **25% penalty** to the final score. Example (app_18 Toggl): raw
  `round(24/33*100) = 73` → penalized `round(73*0.75) = 55`.
- Gate 1 verdict compares the **penalized** score against
  `shared/dynamic-target-calibration.yaml` `match_score.minimum` (65; stretch
  floor 50, enabled). Penalized in 50–65 → the candidacy sits in the `[STRETCH]`
  band (human review), NOT a silent drop (app_15's 34 was below the floor —
  clean no-stage; app_18's 55 is stretch territory). State this explicitly in
  the verdict.
- Strict fidelity: every claim must trace to an exact line in
  `templates/star-story-bank.md` / `domain-knowledge.md` / `career-timeline.md`.
  The forbidden-claim grep list for the resume derives from the
  `found_in_resume: false` gaps in `keyword_analysis.json` plus JD-specific
  claims (title inflation, domain tenure, team-scale practices).

## Workflow

1. Read the processor's parsers first: `00-orchestrator/scripts/pipeline_processor.py`
   (functions `count_resume_match_score`, `count_keyword_score`,
   `read_overqualification_gate`, `read_displayed_title`, `count_risk_gate`,
   `extract_gaps_from_risk_log`, `verify_artifacts`).
2. Author the 8 artifacts (jd_analysis, resume_match, keyword_analysis.json,
   resume_change_log, risk_tactics_change_log, cover_letter.txt,
   application_qa.md, generate_resume.py) per the app_16 format template.
3. Run `generate_resume.py` (writes `tailored_resume.docx`); it should include
   an in-script forbidden-claim grep that fails the build on any hit.
4. Independently verify: run `scripts/verify_app_artifacts.py <app_dir>` — it
   simulates every processor parser against the artifacts (no DB writes) and
   reads the generated docx back with python-docx for a second forbidden-grep
   pass (headline + STAR-bank numbers + forbidden patterns).
5. Confirm cover-letter body words < 400 (processor excludes lines starting
   with the signature name).

## Pitfalls

- **`search_files` (rg) fails on this Windows host** for paths under the
  job-hunting tree ("IO error ... The system cannot find the file specified"),
  with backslashes or forward slashes. Fall back to `grep -rn` in the terminal
  tool — it works reliably. Don't retry rg more than once.
- First-`%` trap: never put a lower/higher number before the intended
  `overall_match_score` in resume_match.md — the header line should be the
  first line containing a percentage.
- Keyword JSON must be parseable by `json.load` and the score MUST be nested
  under `analysis` — free-text deviation breaks the processor.
- Risk-log FAIL claims containing em-dashes break the one-line gap-extraction
  regex (non-greedy match stops at the first em-dash). Use en-dashes or commas
  inside claims.
- Declared "Final counts" in the risk log will be +1 per category in the
  processor's raw counts (summary lines match the regexes). This is expected —
  keep the bracket format for consistency with prior builds.

## Files

- `references/processor-parsing-contracts.md` — exact regexes, function names,
  and behaviors verified against pipeline_processor.py, plus the app_15/app_18
  score math worked examples.
- `scripts/verify_app_artifacts.py` — re-runnable verification harness:
  artifact presence, JSON schema + score math, first-% score, Gate verdicts,
  displayed title, risk-gap parsing, cover-letter word count, docx read-back
  forbidden grep. Usage: `python verify_app_artifacts.py <app_dir>
  [--forbidden "pat1,pat2"]`.
