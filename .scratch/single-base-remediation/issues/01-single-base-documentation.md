# 01 — Single-base documentation

**What to build:** The running repo carries its domain context and the single-base decision. An agent opening the repo finds `CONTEXT.md` pointing at the single-context domain docs, and an ADR recording that `github.com/oraekene/job-hunting-pipeline` is the single base while the Documents repo is frozen as an archive/planning mirror.

**Blocked by:** None — can start immediately.

**Status:** done (2026-08-17)

- [x] `CONTEXT.md` exists at the repo root and follows the domain-docs single-context convention
- [x] `docs/adr/0001-single-base-repository.md` records the decision (both repos named, their roles declared, date stamped)
- [x] `python 00-orchestrator/scripts/dry-run.py --skill-dir .` stays 29/29 after the edits
