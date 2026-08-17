# 06 — Schema-drift gate

**What to build:** SQL that references a nonexistent column fails validation loudly instead of dying mid-run; the observed wrong-column queries are corrected; the gate is part of the existing validation flow with a red/green case.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] A validation assertion compares the processor's SQL column references against the live table schema and fails on any mismatch
- [ ] The observed wrong-column references (e.g. `source` vs `source_name`, and the list in ported ticket `pipeline-execution-fixes/02`) are corrected where they appear in repo code
- [ ] The gate runs inside the existing dry-run/harness validation family
- [ ] Mutation case proven: a wrong-column reference fails the gate; correct references pass
- [ ] `python 00-orchestrator/scripts/dry-run.py --skill-dir .` stays 29/29 and `python 00-orchestrator/scripts/regression-harness.py --skill-dir .` stays 17/17 (plus the new gate case)
- [ ] Ported ticket `.scratch/pipeline-execution-fixes/issues/02-schema-drift-gate.md` is marked `done`
