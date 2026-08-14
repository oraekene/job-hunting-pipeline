# Keyword-Analysis Self-Consistency + Forbidden-Grep Verification

Session-tested during app_16 (Cluster Protocol | Product Manager). These checks
caught a real bug: `keyword_analysis.json`'s `analysis` block claimed
`earned_points: 22 / 34 = 65%` while the file's OWN keyword list summed to
`25 / 34 = 74%`. The downstream `resume_match.md` and `risk_tactics_change_log.md`
had been written to the wrong score; all three needed correction. A scripted
recomputation found it; reading the file did not.

## 1. Recompute the score from the file's own keyword list

```python
import json
d = json.load(open("keyword_analysis.json"))
a, kws = d["analysis"], d["keywords"]
hp = [k for k in kws if k["priority_weight"] == 3]
mp = [k for k in kws if k["priority_weight"] == 2]
lp = [k for k in kws if k["priority_weight"] == 1]
poss = len(hp)*3 + len(mp)*2 + len(lp)*1
earn = (sum(3 for k in hp if k["found_in_resume"]) +
        sum(2 for k in mp if k["found_in_resume"]) +
        sum(1 for k in lp if k["found_in_resume"]))
assert poss == a["total_possible_points"], (poss, a["total_possible_points"])
assert earn == a["earned_points"], (earn, a["earned_points"])
assert a["match_score_percentage"] == round(earn/poss*100)
# rating bands: Excellent >80, Good 60-79, Needs Work <60
assert a["penalized_score_percentage"] == a["match_score_percentage"] or a["penalty_applied"]
```

Per-keyword sanity: `category` in {Hard Skill, Domain Concept, Soft Skill},
`priority_weight` in {1,2,3}, `found_in_resume` is bool, `context_note` non-empty.

### Rounding/truncation convention (app_17 — hand-math drift caught by script)

- `round()` in the check above is Python's banker's rounding: `round(62.5) == 62`,
  NOT the half-up 63 you will naturally hand-write. app_17 first pass wrote
  `match_score_percentage: 63` from 25/40 = 62.5%; the scripted recompute said 62.
- The 25% seniority penalty **truncates**: `int(raw * 0.75)` — 62×0.75=46.5 → 46
  (app_15: 46×0.75=34.5 → 34). Do not `round()` the penalized value.
- When the penalty applies, `penalized_score_percentage == int(match_score_percentage * 0.75)`;
  when no penalty applies (app_16 style "NO seniority penalty"), `penalized == raw`.
- After a correction, the new numbers must land in ALL of: `keyword_analysis.json`
  (analysis block + recommendation text), `resume_match.md` header + verdict line,
  `resume_change_log.md`, `risk_tactics_change_log.md`, `application_qa.md`. Grep
  the whole `app_N/` dir for the OLD numbers before declaring done (app_17 left
  zero stale `63`/`47` references after the fix).
- Ready-made runner: `../scripts/verify_app_artifacts.py <app_dir>` — recomputes the
  math, cross-checks the resume_match.md header, runs the generator, greps the
  docx, and flags stale references. The tempfile-based ad-hoc script pattern
  (hermes-verify-* prefix, delete after run) also works when a full script isn't
  available.

## 2. Forbidden-claim grep: word boundaries, never substrings

- Use `re.search(r"\bdefi\b", text, re.I)` — NOT `"defi" in text`.
  `"defi" in text` false-positives on "defin**ed** the roadmap" (happened this
  session). Same class of trap: `\btoken\b` vs "tokenization", `\baws\b` vs
  "lawsuits".
- The generator script's own grep (derived from `found_in_resume:false` gaps,
  run at script end) is authoritative; it exits non-zero on hits.
- Independent re-check should use the SAME word-boundary patterns, and a
  `re.I` flag — the generator's patterns do.
- If a portfolio project is honestly crypto-adjacent (e.g. "memecoin strategy
  builder"), describe it without the gap-domain vocabulary ("trading
  strategies", not "crypto-market strategies") so the gap grep stays clean.

## 3. Seniority-rule interpretation (plain "Product Manager" titles)

The schema's literal rule lists `Senior`/`Lead`/`Manager`/`Principal` as
seniority qualifiers, but pipeline precedent (app_11 Figma, app_13 Peek,
app_16 Cluster Protocol) treats "Manager" inside the title "Product Manager"
as part of the PM title, NOT a seniority qualifier:

- Title "Product Manager" → NO penalty, domain keywords get transferable
  credit (when genuine evidence exists — gaps still `found_in_resume:false`).
- Title "Senior Product Manager" / "Principal …" (e.g. app_15 Camunda) →
  25% industry-mismatch penalty, no transferable credit for domain keywords.
- **Substance over title string (app_17 Meta, plain "Product Manager"):** an
  unqualified title still gets the 25% penalty when the JD carries senior-IC
  signals — explicit year gate (10+ years PM/Product Design), executive-audience
  presenting, large-product-area ownership, org-wide consensus duties. Raw 62%
  → penalized 46%, Gate 1 FAILED (<65), same treatment as app_15. Check the
  year gate and exec-presenting lines before deciding "no penalty" on title alone.

When in doubt, cite the precedent set (app_11's recommendation text states the
reasoning verbatim) rather than re-deriving it — but weigh the app_17 exception
first: a 10+-years-gated "Product Manager" JD is senior in substance.

## 4. Indeed fetch blocked → company careers page

`web_extract` on `https://www.indeed.com/viewjob?jk=...` returned
`Blocked: URL targets a private or internal network address` (Indeed anti-bot;
the app_16 stage-2 analysis had documented the same). Working fallback: fetch
the company careers page (e.g. `https://www.clusterprotocol.ai/careers`) —
it carried the full JD text including the terse Product Manager description
and culture sections. The canonical `jd_analysis.md` remains authoritative;
use the careers page to confirm, not to overwrite.

## 5. When a score changes after the fact

A corrected score must be propagated to every artifact that cites it:
`resume_match.md` (Overall % + Gate 1 verdict wording — "exactly at threshold"
vs "comfortably above" are materially different), `risk_tactics_change_log.md`
recommendation line, and the JSON's own `recommendation` text. Grep the whole
`app_N/` dir for the old number before declaring done.
