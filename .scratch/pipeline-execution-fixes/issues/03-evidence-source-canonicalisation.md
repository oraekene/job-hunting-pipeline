# 03 — Evidence-source canonicalisation

**What to build:** the three mandatory evidence sources (STAR story bank, domain knowledge, career timeline) resolve from a single canonical location. All sub-skills referencing the old nonexistent path are updated to the real location, and the evidence loader raises a hard error naming the missing source and the canonical location instead of allowing agents to improvise.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] The three evidence sources resolve from one canonical location
- [ ] No reference to the old nonexistent path remains in the skills or docs
- [ ] A missing source makes the loader exit non-zero naming the source and location
- [ ] No improvisation fallback exists in the loader

**Agent brief:** Spec 1, Implementation Decisions — Evidence-source canonicalisation (`.scratch/pipeline-execution-fixes/spec.md`).