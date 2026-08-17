# 03 — Documented-scripts gate honesty

**What to build:** every script a document presents as runnable must exist, or the gate fails. The retired `extract_settings.py` citation leaves the preflight runbook, and the checker's documented-scripts check hard-fails on a missing citation while extra present-but-undocumented scripts remain a warning only. The gate's normal run reports 10/10.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] The runbook's runnable-script table cites only scripts present in the bundle
- [ ] The gate reports 10/10 documented scripts on a normal run
- [ ] Temporarily adding a phantom citation (or removing a script) fails the gate with exit != 0
- [ ] A present-but-undocumented script still reports as WARN, not fail

**Agent brief:** A3 in `.scratch/review-gap-fixes/spec.md` (## Comments — Documented-scripts gate honesty)