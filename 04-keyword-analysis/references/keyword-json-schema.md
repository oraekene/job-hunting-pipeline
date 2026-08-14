# Keyword Extraction & Scoring — Reference

## Phase 1: Extraction

**Segmentation.** Divide the JD into up to three zones if present: Core
Domain (Title, Company Summary, About the Role), Hard Requirements
(Qualifications, Requirements, "Who You Are"), Soft/Bonus (Preferred
Qualifications, Benefits, Cultural values).

Extract 10–15 terms total, only what is explicitly written or a standard
variant (e.g. "Product Manager" → "Product Management"). Never fabricate
a term that isn't in the text.

**Category A — Hard Skills & Success Metrics (highest priority).**
Operational hard skills (e.g. "Inbound/Outbound calls," "Pipeline
Management"). Any KPI or quantitative goal stated in the JD (revenue
targets, quotas, retention rates). **Explode tech stacks into individual
tools** — never group as "Cloud Platforms (AWS/Azure)"; list "AWS",
"Azure", "Docker", "Kubernetes", "Terraform" separately, since ATS
systems rank on total tool-match count, not category coverage. Extract
protocols/standards/acronyms exactly as written (OAuth, SAML, RBAC, GAAP,
HIPAA). Extract specialized hard skills (Financial Analysis, Market
Research, Negotiation).

**Category B — Domain & Market Context (high priority).** 2–3 high-value
nouns defining the company's core product, even if low-frequency. Terms
defining target audience/customer base.

**Category C — Role-Specific Soft Skills (low priority).** Only if they
appear in "Requirements"/"Qualifications" (e.g. "Stakeholder management").
Ignore generic About-Us fluff ("passionate," "energetic," "dynamic").

**Negative constraints.** No hallucinated terms. No bare unigrams unless
a specific named methodology (Agile, Scrum) — use full phrases otherwise
("Product Strategy," not "Strategy"). No generic soft skills
("Communication," "Teamwork," "Passion," "Drive," "Motivation," "Time
Management") unless part of a specific technical methodology — these are
junk keywords that inflate the score without proving anything.

## Phase 2: Matching

Search the resume/memory profile for each extracted keyword.
Semantic matching allowed (JD "AI" matches resume "Artificial
Intelligence" or "LLM" — record the mapping in `context_note`).
Case- and pluralization-insensitive. Scan Experience, Skills, and
Projects sections.

**Seniority logic (mandatory, not advisory).** If the job title contains
"Senior," "Lead," "Manager," "Principal," or "Staff," do not accept
transferable-skill credit for domain keywords — require a strict industry
match. If Kenechukwu lacks the specific industry experience, the final
score is penalized by 25%: `match_score_percentage` MUST equal
`round(raw_match_score_percentage * 0.75)`. Record BOTH numbers in
`analysis`:

```json
"analysis": {
  "raw_match_score_percentage": 0,
  "match_score_percentage": 0,
  "seniority_penalty_applied": true
}
```

`raw_match_score_percentage` is the Phase-3 arithmetic before the
penalty; `match_score_percentage` is what downstream stages (resume
match, staging gate) actually consume. A silent raw=final on a
Manager-titled JD is a Rule 2 violation — the 2026-08-13 sweep shipped
77=77/68=68/75=75 exactly this way. If the title has no seniority
qualifier and no industry mismatch, `seniority_penalty_applied` is
`false` and the two numbers are equal.

## Phase 3: Scoring

```
TotalPossiblePoints = (CountHigh * 3) + (CountMed * 2) + (CountLow * 1)
EarnedPoints        = (MatchesHigh * 3) + (MatchesMed * 2) + (MatchesLow * 1)
FinalScore           = round((EarnedPoints / TotalPossiblePoints) * 100)
```

Rating: `Excellent` (>80%), `Good` (60–79%), `Needs Work` (<60%).

## Output format (JSON only, no prose wrapper)

```json
{
  "analysis": {
    "total_keywords_found": 0,
    "total_possible_points": 0,
    "earned_points": 0,
    "raw_match_score_percentage": 0,
    "match_score_percentage": 0,
    "seniority_penalty_applied": false,
    "match_rating": "Excellent | Good | Needs Work"
  },
  "keywords": [
    {
      "term": "extracted_keyword",
      "category": "Hard Skill | Domain Concept | Soft Skill",
      "priority_weight": 3,
      "found_in_resume": true,
      "context_note": "Matched 'LLM' to 'Large Language Model'"
    }
  ],
  "recommendation": "One-sentence tip based on the missing high-priority keywords."
}
```

`found_in_resume: false` entries are exactly what `05-resume-customizer`
and `09-risk-tactics-gate` work from next — every one of them needs
either a genuine evidence match in memory (apply it) or an honest gap
(leave it flagged, don't paper over it).
