# 02 — Schema-drift gate

**What to build:** a gate assertion that compares every column name the pipeline processor's SQL references against the live table schema and fails on any mismatch. The ad-hoc diagnostic queries observed during the 2026-08-12 run that referenced nonexistent columns (`company` on the wrong table, `application_id`, `ats_pipeline_stage`) are corrected to the real schema.

**Blocked by:** None — can start immediately.

**Status:** done (implemented 2026-08-17 by ticket single-base-remediation/06)

- [x] Every SQL column reference in the processor's queries resolves against the live schema
- [x] The gate fails when a referenced column does not exist (mutation check, not committed)
- [x] The gate passes on the normal run as part of the existing validation flow
- [x] The observed wrong-column queries are corrected to the real schema

**Agent brief:** Spec 1, Implementation Decisions — Schema-drift gate (`.scratch/pipeline-execution-fixes/spec.md`).