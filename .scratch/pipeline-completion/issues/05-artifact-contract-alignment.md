# 05 — Align gate-column parsing with the artifact contracts

**What to build:** Fix the three silent-data-loss parser mismatches between
what the stage skills write and what the processor reads, so committed rows
carry exactly what the artifacts recorded:

1. Keyword score: stage 4 nests the score at `analysis.match_score_percentage`;
   the processor reads only the top level, so apps 3 and 4 landed
   `keyword_match_score = 0.0` despite a recorded 53.
2. Overqualification verdict: artifacts write `Gate 2 verdict
   (overqualification): **PASSED (not overqualified)**`; the parser's
   vocabulary (clean/flagged/dropped/skipped) and its strict regex (verdict
   word immediately after `:`, no markdown bold) match nothing, so the gate
   is NULL even when a verdict exists.
3. Honest displayed title: the customizer keeps "Product Manager" while the
   DB `title_displayed` keeps the JD's "Principal …" — the honest title
   never reaches the DB.

**Blocked by:** 01 — Commit the processor regression harness

**Status:** done

- [ ] Keyword score is read from `analysis.match_score_percentage`, with
  top-level fallback for older artifacts; a non-zero recorded score can no
  longer commit as 0.0
- [ ] 04-keyword-analysis SKILL.md states the canonical JSON location
  explicitly (single source of truth for both the stage and the processor)
- [ ] Overqualification parser accepts PASSED/CLEAN/FLAGGED/DROPPED/SKIPPED
  (case-insensitive, with or without `**`), normalizes to the DB enum, and
  only yields NULL when the artifact truly states no verdict — never when
  one exists
- [ ] Processor persists the customizer's displayed title into
  `title_displayed` at commit when the resume change-log records one; JD
  title remains in `title_original`
- [ ] Harness cases assert: a fixture with nested score 53 commits
  `keyword_match_score=53`; a fixture with "PASSED (not overqualified)"
  commits a non-NULL normalized gate; a fixture with honest title commits
  the honest title
- [ ] Live DB check: apps 3 and 4's committed rows are corrected (or a
  documented re-commit plan is produced) so analytics stop seeing 0.0
  keyword scores and NULL gates
