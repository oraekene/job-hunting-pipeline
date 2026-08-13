# Missing Templates Fallback (job-hunting build artifacts)

## What happened
The evidence templates live at the package root `templates/` (`templates/star-story-bank.md`,
`templates/domain-knowledge.md`, `templates/career-timeline.md`). During one run, a
delegation passed the wrong path `shared/templates/…` — that directory does not exist, so
`read_file` returned "File not found" and the subagent fell back to `app_M` artifacts for
evidence. The pipeline still produced grounded output because every STAR story and every
number is **embedded/cited inside the existing `build_artifacts/app_M/*` files** (e.g.,
`resume_match.md`, `resume_change_log.md`, `risk_tactics_change_log.md`,
`generate_resume.py`).

**Always try the real path first:** `templates/{star-story-bank.md, domain-knowledge.md,
career-timeline.md}` at the package root. The fallback below is for environments where
those files genuinely do not exist.

## Fallback recipe (verified working)
1. Locate a completed app set: `shared/build_artifacts/app_1/` (or the highest-numbered `app_N` that exists). It contains all 8 artifact files AND the candidate's real evidence.
2. Use `app_1/*` as:
   - **FORMAT template** — copy each file's structure/sections (headings, tables, tagging conventions like `[PASS]`/`[FAIL]`/`[BORDERLINE PASS]`).
   - **EVIDENCE source** — STAR story names + numbers are cited there; reuse verbatim. Do NOT invent evidence.
3. Map every quantitative claim to a STAR story already cited in `app_1`, e.g.:
   `150 active users`, `₦2.3M`, `40% cycle time`, `40% loan processing`, `15% fewer defaults`, `92% disbursement`, `150+ farmers`, `25% churn`, `30% quality`, `180% follower growth`, `80% engagement`, `50,000+ images`, `95% time reduction`.

## File discovery on the Windows host
- The Hermes `search_files` tool resolves paths in a **separate sandbox** and FAILS on Windows paths (`C:\...` and `/c/...`) with "IO error ... The system cannot find the file specified (os error 2)." Do not rely on it here.
- **Reliable method:** use the `terminal` tool with `find` / `grep -ril` for discovery, then `read_file` for reading. This is the working approach on this host.
  - Example: `cd "C:/Users/rotim/AppData/Local/hermes/skills/job-hunting" && grep -ril "Kenechukwu" .`
  - `find` with `-maxdepth` is also fine for listing the tree.

## Other environment notes
- `python-docx` 1.2.0 and `pyyaml` are available; `python` = 3.11.15. `generate_resume.py` runs cleanly via `python generate_resume.py`.
- In `generate_resume.py`: `ARTIFACTS = script dir`, `SHARED = app_N/../../` (resolves to `shared/`). `keyword_analysis.json` is read from the `app_N` dir; `target-profile.yaml` from `shared/`.
- After generation, verify `tailored_resume.docx` is non-empty (run the script) AND grep its extracted text for forbidden claims (`DevSecOps|infrastructure|self-hosted|Principal|Kubernetes|Docker`) — expect ZERO hits under strict mode.
