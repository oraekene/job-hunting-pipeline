# 02 — Bundle contents gate

**What to build:** server plumbing can never be packaged into a customer bundle. The build's exclusion set covers `worker`, `node_modules`, `.wrangler`, `dist`, and the build-infra directory at any path level, and the checker gate asserts both that the set covers those names and that a built output tree contains none of them. Weakening the set flips the gate to fail.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] Clean pipeline builds from both source trees produce outputs without any of the five names
- [ ] The gate fails when the exclusion set is weakened (demonstrated once, not committed)
- [ ] The gate passes on the normal run, reported as a single command output

**Agent brief:** A2 in `.scratch/review-gap-fixes/spec.md` (## Comments — Bundle contents gate)