---
name: job-hunting-build-artifacts
description: Use to author offline job-hunting app artifacts and resume.
metadata:
  hermes:
    tags: [job-hunting, artifacts, subagent]
    category: job-hunting
    related_skills:
      - job-hunting-orchestrator
---

# Job-Hunting — Build Application Artifacts (Offline / Subagent)

## When to use
- A delegating agent / user asks to "author the full 8-file stage artifact set (stages 2-9) plus a tailored .docx resume for job application id=N."
- Explicit constraints present: Do NOT touch the database, do NOT run pipeline_processor.py, do NOT send/submit anything.
- This is the **offline, manual authoring** path — distinct from running the live pipeline (covered by the `00-orchestrator` skill).

## Canonical output (all in `shared/build_artifacts/app_N/`)
1. `jd_analysis.md`
2. `resume_match.md` (Overall % + Gate1 + Gate2 verdict + per-req table + gaps + red flags + visa/eligibility note)
3. `keyword_analysis.json` (schema-exact; gaps as `found_in_resume:false`)
4. `resume_change_log.md` (Stage 5; Tactics 1-4 with `[PASS]`/`[FAIL]`/`[BORDERLINE PASS]`; Tactic 3 all from STAR bank)
5. `risk_tactics_change_log.md` (Stage 9; overclaims marked `[FAIL]` with missing evidence)
6. `cover_letter.txt` (<400 words, human, address the hiring team generically — e.g. "Apera team" / "Sproxil team" — no fabricated recruiter name; one STAR example, briefly explain the genuine gap)
7. `application_qa.md` (ATS form, free-text questions, CAPTCHA, list questions, note answers need Kenechukwu's input)
8. `generate_resume.py` (python-docx → `tailored_resume.docx`; RUN it to verify)
+ `tailored_resume.docx` (produced by running `generate_resume.py`)

## Evidence sources (READ FIRST)
Per pipeline convention: `templates/{star-story-bank.md, domain-knowledge.md, career-timeline.md}`, `shared/target-profile.yaml`, an existing `app_M` `build_artifacts/` set (as FORMAT template), and `04-keyword-analysis/references/keyword-json-schema.md`.

### CRITICAL FALLBACK — missing templates
The three `templates/*.md` files live at the package root (`templates/`, NOT `shared/templates/` — a delegation using the wrong path reported them ABSENT during one run and fell back to `app_M` artifacts for evidence). When they are genuinely missing, use an existing `app_M` `build_artifacts/` set as BOTH:
- the **FORMAT template** (mirror its 8 files' structure/sections), AND
- the **EVIDENCE source** (its files embed/cite every STAR story and every number).
Full discovery + fallback recipe: `references/missing-templates-fallback.md`.

## Strict-fidelity honesty rules (target-profile `fidelity_mode: strict`)
- Every quantitative claim MUST trace to the STAR bank. **Never invent numbers.**
- Do NOT mark domain gaps as matched. For this candidate there is **NO** [insert candidate's actual gap domain here — per application] experience. Mark those `found_in_resume:false`.
- Per `keyword-json-schema` seniority logic: if the JD title contains `Senior`/`Lead`/`Principal`, do NOT grant transferable credit for domain keywords; if the industry is mismatched, penalize the final score by 25% (raw × 0.75). Compute raw score, then apply penalty; report **both**. Encoding (from app_15 Camunda / app_19 PandaDoc): keyword JSON keeps the RAW in `analysis.match_score_percentage` and the penalized value in `analysis.penalized_score_percentage` (plus a `penalty_applied` note); resume_match.md header is "N% raw / M% with seniority penalty applied" (raw FIRST — the processor reads the first % in the file); **Gate 1 is evaluated on the PENALIZED score** (≥65 PASSED / 50–65 [STRETCH] / <50 FAILED — a Principal/Senior mismatch usually lands <50 and is not staged). Gate 2 stays independent and typically PASSES on overqualification for these cases (role band above candidate, comp above floor). Full recipe + forbidden-grep set: `references/seniority-penalty-encoding.md`.
- **"Manager" inside "Product Manager" is NOT a seniority qualifier.** Established precedent (app_11 Figma PM, app_13 Peek PM, app_16 Cluster Protocol): plain "Product Manager" titles are mid-level, get NO penalty, and domain keywords DO get transferable credit. The penalty only fires on Senior/Lead/Principal-qualified titles (e.g. app_15 Camunda Senior PM).
- **EXCEPTION (app_17 Meta): seniority is judged by the JD's substance, not just the title string.** A JD titled plainly "Product Manager" but carrying an explicit **10+ years minimum**, **executive-audience presenting**, and **large-product-area ownership** is senior-IC in substance → the 25% penalty DOES apply and no transferable credit for domain keywords (raw 62% → penalized 46%, Gate 1 FAILED <65). Deciding signals to check in every JD: explicit year gate (10+), exec presenting, large-area ownership. When those are present, apply the penalty even though the title is unqualified; when absent (app_11/13/16 style), no penalty.
- Keep the displayed resume title honest (e.g., "Product Manager"); do NOT inflate to "Principal".
- `generate_resume.py` must mirror ONLY grounded JD terminology for this posting (e.g. Product Strategy, Roadmap, AI/LLM portfolio, Discovery, Stakeholder Management, GTM, Success Metrics, Post-launch Optimization — the exact set depends on the role). It must NOT claim the candidate's genuine gap domains (per `found_in_resume:false` in the keyword analysis).

## VISA / ELIGIBILITY (surface, never hide)
- If the posting is Remote US/CA and the candidate (Kenechukwu, Asaba Nigeria) requires visa sponsorship (`target-profile.visa_sponsorship_required: true`), add an **honest eligibility/visa note in `resume_match.md` flagged for the human approval gate**. Do NOT pretend it's fine.
- **Location-screening questions on the form** (e.g. Greenhouse "Are you currently based in Europe?"): the honest answer (NO for Nigeria) is recorded in `application_qa.md` and flagged for human decision — per pipeline memory, location-only blockers do **not** auto-reject. Never claim residence in the resume or cover letter; the answer lives in the form field only. But a location flag does not rescue a failed Gate 1: if the penalized score is already below threshold, the recommendation stays do-not-stage with an explicit human override.

## Workflow
1. Read `target-profile.yaml`, the `keyword-json-schema`, and an existing `app_M` set (format + evidence). If `templates/*.md` is missing, follow the explicit fallback below.
2. **Missing-templates fallback (explicit step):** when `templates/{star-story-bank.md, domain-knowledge.md, career-timeline.md}` are absent, use the highest-numbered existing `app_M` set (`shared/build_artifacts/app_N/`) as BOTH format template (mirror its 8 files' structure/sections) AND evidence source (its files embed/cite every STAR story and number). File discovery on this host: use `terminal` with `find`/`grep -ril` — the Hermes `search_files` tool resolves paths in a separate sandbox and fails on Windows paths. See `references/missing-templates-fallback.md` for the full recipe.
3. Build `keyword_analysis.json` (count points, raw %, penalty %, rating). **Self-consistency check (mandatory):** after writing, recompute `total_possible_points` and `earned_points` from the file's OWN keyword list (sum `priority_weight` per category; sum only entries with `found_in_resume:true`) and assert they match the `analysis` block, plus `match_score_percentage == round(earned/total*100)` and the rating band. The `analysis` block has drifted from its own keyword list before (claimed 22/34=65% while the list actually yields 25/34=74% — app_16; and app_17 hand-wrote 63/47 where Python computes 62/46) — an ad-hoc verification script caught both; a hand-eye read did not. **Rounding convention (app_17): `round()` is Python banker's rounding — round(62.5)=62, NOT the half-up 63 you'll naturally hand-write; the 25% penalty truncates with `int(raw*0.75)` — 62×0.75=46.5→46 (app_15: 34.5→34).** Write 62/46 first-time, or let the script correct you. See `references/keyword-analysis-verification.md` and `scripts/verify_app_artifacts.py`.
4. Write `jd_analysis.md`, `resume_match.md`, `resume_change_log.md`, `risk_tactics_change_log.md`, `cover_letter.txt`, `application_qa.md` — all non-empty.
5. Adapt `generate_resume.py` from `app_M` (python-docx; grounded terms only; no forbidden-claim violations).
6. **RUN** `generate_resume.py`; verify `tailored_resume.docx` exists + non-empty.
7. Grep the docx text for **this application's** forbidden claims — derive the grep pattern from the genuine gaps in `keyword_analysis.json`/`resume_match.md` (`found_in_resume:false`), NOT from a fixed string. For example, a DevSecOps posting greps `DevSecOps|infrastructure|self-hosted|Principal|Kubernetes|Docker`; a robotics/hardware posting (like this one) greps `robotics|hardware|manufacturing|physical product|supply chain|manufacturability`. Expect zero hits under strict mode. **Use word-boundary regexes, never substring `in` checks**: `\bdefi\b` matches only "DeFi", but a naive `'defi' in text` also fires on "defin**ed**" (real false positive this session). The generator script's own grep (`re.search(pat, text, re.I)`) is the authoritative check; an independent re-check with the same word-boundary patterns is a good second opinion.
8. Report a one-paragraph summary + honest match score. **Do NOT submit.**

## Verification checklist
- [ ] All 8 `.md`/`.txt`/`.py` files + `tailored_resume.docx` present and non-empty
- [ ] `keyword_analysis.json` valid JSON, schema-exact, gaps `found_in_resume:false`
- [ ] `keyword_analysis.json` math self-consistent: recomputed earned/total from its own keyword list equals the `analysis` block (`round(earned/total*100)` == `match_score_percentage`, rating band correct)
- [ ] `tailored_resume.docx` non-empty (script was actually run)
- [ ] grep docx text for **this application's** forbidden claims (derive from `found_in_resume:false` gaps in `keyword_analysis.json`, e.g. `robotics|hardware|manufacturing|physical product|supply chain|manufacturability` for a robotics role; `DevSecOps|infrastructure|self-hosted|Principal|Kubernetes|Docker` for a DevSecOps role) → expect NONE
- [ ] visa/eligibility note present in `resume_match.md` when role is US/CA remote
- [ ] `cover_letter.txt` < 400 words

## Overlaps / notes
- This is a **META/orchestration wrapper** over the per-stage skills (`03-resume-match`, `04-keyword-analysis`, `05-resume-customizer`, `06-cover-letter`, `08-application-qa`, `09-risk-tactics-gate`). Those govern each individual stage's substance; this skill governs the *offline batch authoring of all of them together* with the honesty/visa guardrails and the missing-templates fallback.
- `00-orchestrator` governs running the **live** pipeline (which this task explicitly avoids).
- See `references/missing-templates-fallback.md` for the missing-evidence fallback and the working file-discovery method on the Windows host.
- See `references/keyword-analysis-verification.md` for the JSON score self-consistency check, word-boundary forbidden-grep pitfalls, the "Product Manager" title seniority precedent (incl. the app_17 substance-over-title exception), the Python banker's-rounding/truncation convention, and the Indeed-blocked → careers-page fallback.
- See `scripts/verify_app_artifacts.py` for the ready-made package verifier (JSON math recompute, resume_match.md header cross-check, generator run, docx forbidden grep, stale-reference grep): `python scripts/verify_app_artifacts.py shared/build_artifacts/app_N/ --forbidden "pat1|pat2" --stale "63|47"`.
- See `references/seniority-penalty-encoding.md` for the Senior/Principal-title penalty encoding (raw vs penalized placement, Gate 1 on penalized, location-screening questions) from the app_15 Camunda and app_19 PandaDoc builds.
