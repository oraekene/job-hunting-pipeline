# 07 — Repair package integrity so dry-run.py is green

**What to build:** Fix the three failing `dry-run.py` checks caused by the
background curator's rogue skill created during the 2026-08-12 run:

1. `job-hunting-build-artifacts` ships without `metadata.hermes` frontmatter.
2. Its reference file (`references/missing-templates-fallback.md`) points to
   `shared/templates/{star-story-bank,domain-knowledge,career-timeline}.md`
   — paths that don't exist (the real files live at `templates/`), which is
   the exact wrong-path trap that degraded the app-3 build during the run.
3. Three files still state "25 skills" while the bundle now has 26.

The rogue skill is curator auto-created output, not Kenechukwu-authored
content — this ticket decides its fate and restores the package's own
integrity gate to green, permanently.

**Blocked by:** None — can start immediately

**Status:** done

- [ ] Decide and execute on `job-hunting-build-artifacts`: either delete it
  (if curator noise) or give it valid `metadata.hermes` frontmatter and
  corrected reference paths (if it documents a real recovery flow)
- [ ] Its reference file no longer cites non-existent `shared/templates/`
  paths; if the fallback knowledge is worth keeping, paths point at the real
  `templates/` locations
- [ ] Skill-count statements updated to the actual number (26) in
  `00-orchestrator/SKILL.md`, `11-analytics-and-learning/SKILL.md`, and
  `README.md`
- [ ] `python 00-orchestrator/scripts/dry-run.py --skill-dir .` exits with
  all 26 checks passing
- [ ] Root-cause note added to the skill (or a short ADR): background
  curators must not be able to create skills inside this bundle without
  passing `dry-run.py` — state the guard that enforces it
- [ ] No functional pipeline behavior changes in this ticket beyond package
  hygiene
