# 05 — CI wiring into the repo

**What to build:** a tag push actually runs the release pipeline on GitHub. The workflow lives at the repo's workflows path, the build-infra sources it needs are tracked (nested ignores keep `node_modules`, `.wrangler`, `dist`, and caches out of the checkout), and the run does checkout → validate (five checkers + suites from the build-infra directory) → regenerate graph and manual into the repo root → audit → build from the repo root → verify → R2 upload gated on R2 secrets existing, so the run goes green before Cloudflare setup. Signing uses the existing `SIGNING_KEY` secret.

**Blocked by:** 02 (bundle contents gate), 03 (documented-scripts gate) — the hardened gate must exist and pass before CI validates with it; A1 (bundle canonicalisation) conceptually grounds the repo-root build.

**Status:** ready-for-agent

- [ ] The workflow is present in the pushed repo's workflows path and `git ls-files` shows the build-infra sources are tracked
- [ ] A local dry run of the workflow's steps (validate → regenerate → audit → build → verify) completes green on the repo root
- [ ] With no R2 secrets set, the R2 upload step is skipped and the run is green
- [ ] With R2 secrets set, the bundle lands in the bucket (may stay unexecuted until the bucket exists — documented, not blocking)
- [ ] The runner's checkout does not contain `node_modules`/caches

**Agent brief:** A4 in `.scratch/review-gap-fixes/spec.md` (## Comments — CI wiring into the repo)