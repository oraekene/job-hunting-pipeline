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
- Per `keyword-json-schema` seniority logic: if the JD title contains `Senior`/`Lead`/`Manager`/`Principal`, do NOT grant transferable credit for domain keywords; if the industry is mismatched, penalize the final score by 25%. Compute raw score, then apply penalty; report **both**.
- Keep the displayed resume title honest (e.g., "Product Manager"); do NOT inflate to "Principal".
- `generate_resume.py` must mirror ONLY grounded JD terminology for this posting (e.g. Product Strategy, Roadmap, AI/LLM portfolio, Discovery, Stakeholder Management, GTM, Success Metrics, Post-launch Optimization — the exact set depends on the role). It must NOT claim the candidate's genuine gap domains (per `found_in_resume:false` in the keyword analysis).

## VISA / ELIGIBILITY (surface, never hide)
- If the posting is Remote US/CA and the candidate (Kenechukwu, Asaba Nigeria) requires visa sponsorship (`target-profile.visa_sponsorship_required: true`), add an **honest eligibility/visa note in `resume_match.md` flagged for the human approval gate**. Do NOT pretend it's fine.

## Workflow
1. Read `target-profile.yaml`, the `keyword-json-schema`, and an existing `app_M` set (format + evidence). If `templates/*.md` is missing, follow the explicit fallback below.
2. **Missing-templates fallback (explicit step):** when `templates/{star-story-bank.md, domain-knowledge.md, career-timeline.md}` are absent, use the highest-numbered existing `app_M` set (`shared/build_artifacts/app_N/`) as BOTH format template (mirror its 8 files' structure/sections) AND evidence source (its files embed/cite every STAR story and number). File discovery on this host: use `terminal` with `find`/`grep -ril` — the Hermes `search_files` tool resolves paths in a separate sandbox and fails on Windows paths. See `references/missing-templates-fallback.md` for the full recipe.
3. Build `keyword_analysis.json` (count points, raw %, penalty %, rating).
4. Write `jd_analysis.md`, `resume_match.md`, `resume_change_log.md`, `risk_tactics_change_log.md`, `cover_letter.txt`, `application_qa.md` — all non-empty.
5. Adapt `generate_resume.py` from `app_M` (python-docx; grounded terms only; no forbidden-claim violations).
6. **RUN** `generate_resume.py`; verify `tailored_resume.docx` exists + non-empty.
7. Grep the docx text for **this application's** forbidden claims — derive the grep pattern from the genuine gaps in `keyword_analysis.json`/`resume_match.md` (`found_in_resume:false`), NOT from a fixed string. For example, a DevSecOps posting greps `DevSecOps|infrastructure|self-hosted|Principal|Kubernetes|Docker`; a robotics/hardware posting (like this one) greps `robotics|hardware|manufacturing|physical product|supply chain|manufacturability`. Expect zero hits under strict mode.
8. Report a one-paragraph summary + honest match score. **Do NOT submit.**

## Verification checklist
- [ ] All 8 `.md`/`.txt`/`.py` files + `tailored_resume.docx` present and non-empty
- [ ] `keyword_analysis.json` valid JSON, schema-exact, gaps `found_in_resume:false`
- [ ] `tailored_resume.docx` non-empty (script was actually run)
- [ ] grep docx text for **this application's** forbidden claims (derive from `found_in_resume:false` gaps in `keyword_analysis.json`, e.g. `robotics|hardware|manufacturing|physical product|supply chain|manufacturability` for a robotics role; `DevSecOps|infrastructure|self-hosted|Principal|Kubernetes|Docker` for a DevSecOps role) → expect NONE
- [ ] visa/eligibility note present in `resume_match.md` when role is US/CA remote
- [ ] `cover_letter.txt` < 400 words

## Overlaps / notes
- This is a **META/orchestration wrapper** over the per-stage skills (`03-resume-match`, `04-keyword-analysis`, `05-resume-customizer`, `06-cover-letter`, `08-application-qa`, `09-risk-tactics-gate`). Those govern each individual stage's substance; this skill governs the *offline batch authoring of all of them together* with the honesty/visa guardrails and the missing-templates fallback.
- `00-orchestrator` governs running the **live** pipeline (which this task explicitly avoids).
- See `references/missing-templates-fallback.md` for the missing-evidence fallback and the working file-discovery method on the Windows host.
