# 14 — open_gaps parser: accept the multi-line [FAIL] format

**What to build:** App 11's risk-tactics log wrote FAIL entries as
`### [FAIL] Title` followed by `- Missing evidence: …` on the next line.
The processor's `extract_gaps_from_risk_log` regex only matches
`[FAIL] claim — evidence` on one line (em-dash), so app 11 committed with
`risk_gate_fail_count=5` but **0 open_gaps rows**. The parser must accept
both shapes, and the 09-risk-tactics-gate skill must pin one canonical
format so both forms stay parseable.

**Blocked by:** None — can start immediately

**Status:** done

- [x] Parser accepts one-line form: `[FAIL] claim — evidence` (existing)
- [x] Parser accepts multi-line form: `### [FAIL] Title` followed within a
  few lines by `- Missing evidence: …` (or `- evidence: …`), extracting
  title + evidence
- [x] Summary lines like `[FAIL]: 4` are never extracted as gaps
  (`(?!:)` guard; verified against app_11's own summary line)
- [x] Harness case `open_gaps_multiline_fail`: fixture risk log in the
  multi-line format commits `open_gaps` rows equal to the FAIL count (red
  before fix, green after)
- [x] Backfill (documented one-off): app 11's FAIL entries are inserted
  into `open_gaps` from the existing artifact — 4 rows (Generative
  Search/SEO, Logged-out funnel, Growth Marketing partnership, 5+ years
  PM tenure); `risk_gate_fail_count` corrected 5→4 so count == gaps (the
  old count included the `[FAIL]: 4` summary line)
- [x] `09-risk-tactics-gate/SKILL.md` change-log reference pins the
  canonical formats: both the one-line em-dash form and the multi-line
  `### [FAIL]` + `- Missing evidence:` form are contract, with a warning
  that anything else is invisible to the parser
