# Seniority-Penalty Encoding — Senior/Principal-title JDs (app_15, app_19)

Companion to `keyword-analysis-verification.md`. The "Product Manager" title gets NO
penalty (app_11/app_13/app_16 precedents). This file covers the OTHER case: the JD
title is `Senior`/`Lead`/`Principal` — penalty fires.

## The two precedent builds

| App | Title / gate | Raw | Penalized (×0.75) | Gate 1 verdict | Gate 2 |
|---|---|---|---|---|---|
| app_15 Camunda | Senior PM, 5+ yrs, distributed-systems domain | 46% | 34% | **[FAILED]** (34 < stretch floor 50) | FAILED-as-underqualified (not overqualified) |
| app_19 PandaDoc | Principal PM, 7+ yrs B2B SaaS, document domain | 51% | 38% | **[FAILED]** (38 < stretch floor 50) | **[PASSED]** (role band above candidate; comp far above $36k floor) |

Both were **not staged**. Mid-level candidates targeting Principal/Senior roles with a
domain mismatch will essentially always land below the 50% stretch floor after the
penalty — expect FAILED, don't fight it.

## Where each number goes (processor contract)

- `keyword_analysis.json`: `analysis.match_score_percentage` = **RAW** (nested key is the
  canonical processor source; keep raw there — same as app_15). `analysis.penalized_score_percentage`
  = penalized. `analysis.penalty_applied` = one-line note naming the 25% penalty, the title
  qualifier, and the precedent.
- `resume_match.md`: header `## Overall Match Score: N% raw / M% with seniority penalty applied`
  — **raw first** (the processor reads the first % in the file; app_15/app_19 both put raw
  first). The Gate 1 verdict paragraph then evaluates the **penalized** number explicitly:
  "Score (M%) < match_score.minimum (65%) and below stretch.floor (50%) — [FAILED]".
- Gate 1 bands on the penalized score: ≥65 PASSED / 50–65 [STRETCH] / <50 FAILED (not staged).
- Gate 2 (overqualification) is independent and usually PASSES on these: title_delta is
  negative (Principal band above mid-level candidate) and comp_delta is negative (posting
  comp clears the $36k/yr floor) → not overqualified. Do not conflate the two verdicts.

## Score math (recompute from the file's own keyword list)

possible = Σ priority_weight over all keywords; earned = Σ weight of `found_in_resume:true`;
raw = round(earned/possible×100); penalized = round(raw × 0.75). Example app_19:
37 possible / 19 earned = 51% raw; 51 × 0.75 = 38.25 → 38%.

For these postings, mark the seniority/tenure/domain items `found_in_resume:false`
(7+ years B2B SaaS tenure, Principal-level scope, leading multiple squads, the domain
itself, structured-content/cross-format skills, EU-based residence) and the genuinely
held craft (Product Strategy & Roadmap, End-to-End Ownership, AI Fluency, Cross-Functional
Collaboration, Experimentation/Feedback Iteration) true — with honest "partial" context
notes where the evidence is adjacency, not direct.

## Forbidden-grep set for seniority+domain-gap postings (app_19 example)

Word-boundary regexes only. Zero hits required under strict fidelity:

```
principal|senior\s*product|7\+?\s*years|seven\s*years|b2b\s*saas|
document\s*(platform|domain|experience|systems|workflow)|cross-?format|
\bpdf\b|\bdocx\b|\bmarkdown\b|structured\s*content|multi-?squad|\bsquads?\b|
telemetry|eu-?based|\beurope\b|shipped\s*ai|ai-?powered\s*features|
platform\s*constraints|greenhouse|\bpln\b|zlot
```

Note `\bpdf\b` — "PDF" as a claimed skill is forbidden, but the honest denial "I haven't
shipped AI features at enterprise product scale" is fine in the cover letter (a denial is
not a claim; grep the resume docx, and keep denials out of the resume entirely).

## Location-screening questions (e.g. "Are you currently based in Europe?")

- Honest answer (NO — candidate in Asaba, Nigeria, UTC+1) goes in `application_qa.md`,
  flagged for Kenechukwu's decision. Per pipeline memory, location-only blockers stay for
  human decision — they do not auto-reject. A false answer is never offered.
- The time zone is NOT the blocker for EU-aligned roles (UTC+1 aligns with EU hours); the
  residence requirement is. Say so in the eligibility note.
- Residence is never claimed in resume or cover letter — the answer lives in the form field.
- The location flag does not rescue a failed Gate 1: recommendation stays do-not-stage with
  an explicit human override noted in the eligibility section.
- Also flag in the same note: salary disclosed only for one region (Poland range here) →
  Nigeria-route comp unverified; "contract type varies by location" → EOR/sponsorship
  vehicle unverified.
