# 05 — Stuck-application recovery

**What to build:** the reconcile pass closes any open build-attempt row whose application is not `building` (orphaned open attempts), so no application is abandoned in limbo. The two observed stuck rows (attempts for apps 2 and 5) resolve via the normal reconcile command, and app 2 commits as-is from its existing complete artifact set rather than being re-authored.

**Blocked by:** 04 (commit-path fix) — app 2 must commit through the fixed path.

**Status:** ready-for-agent

- [ ] Reconcile closes open attempt rows for applications not at `building`
- [ ] App 2's open attempt (id 13) resolves through reconcile, not manual DB edits
- [ ] App 5's open attempt (id 16) resolves through reconcile
- [ ] App 2 commits to `staged` using its existing artifacts with no re-authoring

**Agent brief:** Spec 1, Implementation Decisions — Stuck-application recovery (`.scratch/pipeline-execution-fixes/spec.md`).