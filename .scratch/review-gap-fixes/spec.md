# Spec: Fix the compile-deploy review gaps

**Status:** ready-for-agent

## Problem Statement

The 2026-08-12 two-axis review of the compile-deploy effort surfaced gaps that were left open after the verification pass:

1. **Ticket conventions drift.** Three tickets are `Status: resolved` without an `## Answer` heading (the tracker's documented resolve protocol); status vocabulary is inconsistent (`partially complete` / `partly complete` / `in progress`) for the same "some done, rest blocked on user action" state; and two blocked items were briefly marked `[x]` (corrected to `[~]`) because no partial-checkbox notation was documented.
2. **Phantom script citation.** `PREFLIGHT.md` presents `extract_settings.py` as runnable, but the script was deliberately retired (map.md: "Not needed"). `check_build.py` therefore reports `documented scripts: 9/10 present` while printing `specifications and implementation agree` — a WARN-with-exit-0 that reads as a clean gate.
3. **Server plumbing in customer bundles.** The built bundle ships the `worker/` tree (`schema.sql`, `keygen.js`, `wrangler.toml`, `package.json`, `package-lock.json`) plus root-level duplicated worker files, because the build's exclusion set only drops `_merge-history`, `.git`, `__pycache__`, `.github`. A customer's bundle should never carry server-side schema, key-generation, or deployment plumbing.
4. **CI never ran and cannot run.** `.github/workflows/release.yml` exists only inside the build-infra folder, which is excluded from the git repo pushed to GitHub. `actions/checkout` produces a tree with no workflow, no checkers, no `build.py` — the Actions workflow is dead weight until the repo actually contains it and the infra it depends on.
5. **Two divergent signed bundles.** The repo-root bundle (179 files, manifest signed with rolled key `cb4bf49d…`) and the build-infra `dist` (94 files, signed `3c404a2a…`) are different artifacts with no documented relationship; the review could not tell which is the customer bundle.

## Solution

Make the repo the single source of truth for both the bundle and its build:

- **Codify ticket conventions** in the tracker doc (status vocabulary, `## Answer` on resolve, `[~]` for partial checkboxes) and conform the three resolved tickets.
- **Make the documented-scripts assertion honest**: drop the retired `extract_settings.py` citation from `PREFLIGHT.md` so the checker reports 10/10, and turn the WARN into a hard gate — every script a document presents as runnable must exist, and a missing one fails the gate.
- **Keep server plumbing out of bundles**: extend the build's exclusion set so `worker`, `node_modules`, `.wrangler`, `dist`, and the build-infra folder itself can never be packaged, and assert that coverage from the checker gate.
- **Wire CI into the repo**: commit the build-infra sources (with a nested ignore keeping `node_modules`/`.wrangler`/`dist`/caches out), place the release workflow where GitHub will see it, and make it validate → regenerate artefacts → audit → build → verify → upload, with the upload step conditional so CI goes green before R2 exists.
- **Declare the canonical bundle**: the repo root (the tracked, manifest-signed tree) is the customer bundle; the build-infra folder is tooling, and its `dist` is a build check, not a product.

## User Stories

1. As an agent maintaining this repo, I want `Status: resolved` to always come with an `## Answer` heading, so that resolution claims carry their evidence in a place the tracker conventions define.
2. As an agent maintaining this repo, I want exactly one documented status for "some items done, the rest blocked on the user", so that ticket statuses are greppable and consistent.
3. As an agent maintaining this repo, I want a documented `[~]` notation for partially fulfilled checkboxes, so that a done-marker never silently covers a blocked item.
4. As an agent reading the tracker conventions, I want the status vocabulary and heading rules codified in the tracker doc itself, so that future tickets follow them without re-derivation.
5. As an agent running the checker gate, I want every script a document claims is runnable to exist before the gate passes, so that a 9/10-with-exit-0 report cannot pass as clean.
6. As an agent maintaining the checker gate, I want a missing documented script to fail the gate loudly instead of warming, so that doc/script drift is caught at validation time.
7. As a developer reading `PREFLIGHT.md`, I want its runnable-script table to match what actually ships, so that the preflight runbook does not point at retired files.
8. As a customer, I want my downloaded bundle to contain only skills, configs, tooling and docs that belong to the package, so that server schema, key generation, and deployment files never reach my machine.
9. As a security reviewer, I want the build's exclusion set to cover worker/cloudflare/node_modules/dist/build-infra, so that server plumbing cannot accidentally leak into a shipped bundle.
10. As an agent, I want the exclusion coverage asserted by the existing checker gate, so that the same check that gates releases also guards bundle contents.
11. As a developer, I want the release workflow to exist in the pushed repo where `actions/checkout` will find it, so that a tag push actually runs it.
12. As a developer, I want the release workflow's validate step to run the full checker suite including the new content assertions, so that nothing unreviewable ships on a tag.
13. As a developer, I want the release workflow's upload step to be conditional on R2 secrets existing, so that the pipeline verifies green before Cloudflare setup completes.
14. As a maintainer, I want one documented canonical bundle (the repo root, signed and pushed), so that there is never ambiguity about which tree customers receive.
15. As a maintainer, I want the build-infra folder's role documented as tooling whose `dist` output is a build check only, so that its manifest/signature cannot be mistaken for the product bundle.
16. As a developer, I want a tagged test release to produce a signed, verified, R2-uploaded bundle end to end once the Cloudflare secrets land, so that the whole pipeline gets exercised before the first sale.

## Implementation Decisions

### Bundle canonicalisation

- **The repo root is the customer bundle.** It is the tree whose files are listed in the pushed `MANIFEST.json`, signed with the rolled key, and delivered through the installer. Nothing else is a product.
- **The build-infra folder is tooling.** Its sources are committed into the repo (see CI), its local `dist` output is a build-check artifact whose signature proves the pipeline ran — not a distributable. The review's "two divergent bundles" finding is resolved by documentation, not by merging the two trees.

### Bundle contents gate

- The build's exclusion set is extended so that any path segment matching `worker`, `node_modules`, `.wrangler`, `dist`, or `job-hunting-BUILD-FILES` is never packaged. The existing match-any-segment mechanism is reused; no new exclusion mechanics.
- The checker gate gains a **bundled-content assertion**: the exclusion set must cover each of those five names, and after a build the output tree must not contain any of them. A regression in either direction (exclusion set weakened, or packaging rule changed) fails `check_build.py`.
- The root-level duplicated worker files (flat `index.js`, `crypto.js`, `delivery.js`, `run.js`, `wrangler.toml`) are no longer packaged by construction once paths matching the five names are excluded only if they fall under those names — see note below on the two layouts; the worker directory tree is the authoritative copy.

### Documented-scripts gate

- The `extract_settings.py` citation is removed from `PREFLIGHT.md` (the script is retired by a prior recorded decision; fix 1's verification is a manual read, already documented in the map).
- `check_build.py`'s documented-scripts check flips from append-WARN to hard-fail: the set of scripts documents present as runnable must equal the set of scripts present. Missing → gate fails; extra present-but-undocumented is reported as a warning only (a script can exist without being documented).

### CI wiring

- The release workflow is placed at the repo-root workflows path so `actions/checkout` sees it, and the build-infra sources become part of the tracked repo. A nested ignore keeps `node_modules`, `.wrangler`, `dist`, and Python/Node caches out of the checkout.
- The workflow: checkout → validate (the five checkers plus the supplementary suites, run from the build-infra directory) → regenerate graph + manual into the repo root → audit → `build.py build` from the repo root (validation already passed; `--skip-validate` as today) → `verify` → conditional R2 upload (`if: R2 secrets present`), so the workflow itself goes green before Cloudflare exists.
- Signing uses the `${SIGNING_KEY}` secret already set on the repo. No new secrets for the fix; `R2_*` secrets remain a documented prerequisite for the upload step only.

### Ticket conventions

- The tracker doc codifies: the status vocabulary (open / `ready-for-agent` / `claimed` / `blocked` / `resolved` — one word for the mixed state: `blocked`, with the unblocked remainder described in the body), `## Answer` as the required resolve section, and `[~]` as the partial-checkbox notation (never `[x]` on anything blocked or partial).
- The three resolved tickets gain `## Answer` sections carrying the verification text already written, and their status lines are normalised to the documented vocabulary.

## Testing Decisions

- **Highest seam, kept single**: `check_build.py` is the one gate that covers bundle contents, documented scripts, stages, and test suites together. New assertions (exclusion coverage, documented-scripts equality, post-build absence of the five names) live there, so one command reviews everything a release depends on.
- **Good test = asserts external behaviour**: the gate checks what *can be shipped* (names that must never appear in the output tree; scripts documents promise), not the internals of any stage function.
- **Where tested**: the exclusion-coverage logic is exercised by (a) a fresh pipeline run from both the repo root and the build-infra tree, asserting the five names are absent from both outputs, and (b) a mutation check — temporarily weakening the exclusion set must flip the gate to fail (performed once, not committed).
- **Prior art**: the existing `check_build.py` stages/suites report; `test_installer.py`'s refusal-to-unpack cases and `test_install_check.py`'s exit-code matrix are the established pattern for gate-behaviour tests in this repo.
- **CI test**: after wiring, a tag push on a private branch (no R2 secrets) must produce a green run through the upload step's skip path; the documented-scripts regression flip is re-run locally to prove the gate catches doc drift.
- Conventions fixes are verified by grep/read against the tracker doc — no code seam exists for documentation discipline, by design.

## Out of Scope

- Cloudflare login, D1 database creation, R2 bucket creation, Worker deployment, `wrangler secret put`, and the live endpoint checks — require interactive account access (unchanged from the compile-deploy spec).
- Bachs product creation, webhooks, sandbox purchases — require live credentials.
- Resend domain verification / API key.
- Marketing site deployment and installer-hash publication.
- Nuitka upgrade (a known `py_compile` fallback note, not a gap).
- Any change to skill content, gates, flows, or the watermark scheme.
- Merging the two bundle trees into one (rejected in the bundle-canonicalisation decision).
- Re-verifying the already-passing checker suite results; this spec only adds the two new assertions to the gate.

## Further Notes

- The key-roll narrative (`7297df6` re-sign → `2ebbcda` rotate → review note) is historical record; the spec does not reopen it. The current canonical key is `cb4bf49d…` (rolled 2026-08-12), saved to the password manager and the `SIGNING_KEY` secret.
- The local build-infra mirror inside the repo is 1.6 MB and contains no `node_modules`; the authoritative worker copy lives in the older build folder, and only the tracked sources ship into the repo for CI.
- The two layouts (repo root vs build-infra folder) both produce `dist` outputs today; after this spec only the repo-root build is canonical, and the build-infra `dist` is re-created to prove the exclusion gate, not to ship.
- The upload-step condition means the first real tag can precede Cloudflare setup; the checklist item "verify bundle uploaded to R2" remains blocked until the bucket exists.

## Comments

> *This was generated by AI during triage.*

**Triage (2026-08-12):** Category `enhancement` (all five areas are improvements/fixes to existing behaviour, none are broken-at-runtime bugs). State `ready-for-agent` — the spec is fully specified and the seams are pre-agreed with the maintainer (single gate `check_build.py`; repo root as canonical bundle; workflow adapted into the existing repo). Redundancy check: no exclusion-coverage assertion exists in the gate, and the documented-scripts check is WARN-only — the work is not already implemented. Prior-rejection check: no `.out-of-scope/` KB entries resemble this work. Agent briefs below are the contracts; the spec body is context.

### Agent Brief — A1: Bundle canonicalisation

**Category:** enhancement
**Summary:** Declare the repo root the one customer bundle and document the build-infra folder as tooling whose `dist` is a build check

**Current behavior:**
Two signed trees exist — the repo-root bundle (manifest-signed, pushed with the rolled key) and a build-infra `dist` output (94 files, separately signed). Nothing documents which is the product; the review could not tell them apart.

**Desired behavior:**
The repo root is the canonical customer bundle; the build-infra folder is tooling only, and both roles are documented where a maintainer or agent will find them. Its `dist` output is re-created afterwards to prove the gate, never called a distributable.

**Key interfaces:**
- The bundle manifest and its signature — unchanged, but their role is stated unambiguously
- The build-infra tooling docs — should state the two-tree relationship

**Acceptance criteria:**
- [ ] A document states the repo root is the only customer bundle and the build-infra `dist` is a build-check artifact
- [ ] No doc or ticket presents the build-infra `dist` as shippable
- [ ] The compiled worker text references this ruling in its own notes

**Out of scope:**
- Merging the two trees
- Re-signing either tree
- Changing what ships

### Agent Brief — A2: Bundle contents gate

**Category:** enhancement
**Summary:** Server plumbing can never be packaged into a customer bundle, and the gate asserts it

**Current behavior:**
The built bundle carries the `worker/` tree (`schema.sql`, `keygen.js`, `wrangler.toml`, `package.json`, `package-lock.json`) and root-level duplicated worker files, because the build's exclusion set only drops `_merge-history`, `.git`, `__pycache__`, `.github`.

**Desired behavior:**
A build with the standard pipeline produces an output tree that contains no `worker`, `node_modules`, `.wrangler`, `dist`, or build-infra directory at any path level, from source or from the build-infra tree. The gate (`check_build.py`, or the module it delegates to) asserts (a) the exclusion set covers those five names and (b) a built output tree contains none of them. Weakening the exclusion set flips the gate to fail.

**Key interfaces:**
- The build's exclusion-set constant — extend to cover the five names, matching by any path segment like the existing entries
- `check_build.py` — add the two assertions (set coverage + post-build absence)

**Acceptance criteria:**
- [ ] Clean pipeline builds from both source trees produce outputs without any of the five names
- [ ] The gate fails when the exclusion set is weakened (demonstrated once, not committed)
- [ ] The gate passes on the normal run, reported as a single command output

**Out of scope:**
- Changing the watermark scheme or compile stage
- Touching worker behaviour or tests

### Agent Brief — A3: Documented-scripts gate honesty

**Category:** enhancement
**Summary:** Every script a document presents as runnable must exist, or the gate fails

**Current behavior:**
`PREFLIGHT.md` cites `extract_settings.py` as runnable though the script was retired. The gate reports `documented scripts: 9/10` with exit 0, reading as clean while one citation dangles.

**Desired behavior:**
The retired citation is removed from the preflight runbook (the task it described is verified by a manual read, already recorded). The gate's documented-scripts check hard-fails when a document cites a script that is absent from the bundle; extra present-but-undocumented scripts remain a warning only.

**Key interfaces:**
- The preflight runbook's runnable-script table — remove the retired entry
- `check_build.py`'s documented-scripts collection — flip missing-script handling from append-WARN to hard-fail

**Acceptance criteria:**
- [ ] The runbook's runnable-script table cites only scripts present in the bundle
- [ ] The gate reports 10/10 documented scripts on a normal run
- [ ] Temporarily adding a phantom citation (or removing a script) fails the gate with exit != 0
- [ ] A present-but-undocumented script still reports as WARN, not fail

**Out of scope:**
- Re-adding `extract_settings.py`
- Changing the other four checkers

### Agent Brief — A4: CI wiring into the repo

**Category:** enhancement
**Summary:** A tag push actually runs the release pipeline on GitHub, ending with a verified bundle and a conditional R2 upload

**Current behavior:**
The release workflow exists only inside the build-infra folder, which is excluded from the pushed repo. A checkout has no workflow, no checkers, no build script — Actions cannot run it. The workflow was dead weight from the moment the repo was pushed.

**Desired behavior:**
The repo contains the workflow at the location GitHub scans, plus the build-infra sources it needs (with nested ignores keeping `node_modules`, `.wrangler`, `dist`, and caches out of the checkout). The workflow: checkout → validate (five checkers + supplementary suites from the build-infra directory) → regenerate graph and manual into the repo root → audit → build from the repo root → verify → upload to R2 gated on R2 secrets existing, so the run goes green before Cloudflare setup. Signing uses the existing `SIGNING_KEY` secret.

**Key interfaces:**
- The release workflow file at the repo's workflows path
- The nested ignore rules so heavy/local-only directories never enter the checkout
- The build command's source root = repo root, validation from the build-infra directory (mirrors the existing `--skip-validate` usage after a prior validate step)

**Acceptance criteria:**
- [ ] The workflow is present in the pushed repo's workflows path and `git ls-files` shows the build-infra sources are tracked
- [ ] A local dry run of the workflow's steps (validate → regenerate → audit → build → verify) completes green on the repo root
- [ ] With no R2 secrets set, the R2 upload step is skipped and the run is green
- [ ] With R2 secrets set, the bundle lands in the bucket (may stay unexecuted until the bucket exists — documented, not blocking)
- [ ] The runner's checkout does not contain `node_modules`/caches

**Out of scope:**
- D1, Worker deployment, `wrangler secret put`, live endpoints
- Bachs, Resend, site deployment

### Agent Brief — A5: Ticket conventions codified and conformed

**Category:** enhancement
**Summary:** One documented status vocabulary, `## Answer` on resolve, `[~]` for partial checkboxes — and the three resolved tickets conform

**Current behavior:**
Tickets 01/02/06 are `Status: resolved` without the `## Answer` section the tracker's resolve protocol requires; status wording mixes `partially complete` / `partly complete` / `in progress`; a `[~]` partial-checkbox notation exists but is undocumented.

**Desired behavior:**
The tracker doc codifies exactly: the status vocabulary (open, `ready-for-agent`, `claimed`, `blocked`, `resolved` — `blocked` being the single word for "some done, rest needs the user"), `## Answer` as the required resolve section, and `[~]` as the partial-checkbox notation. The three resolved tickets carry answer sections with the verification already written, and status lines use only the documented words except where the codified vocabulary is `blocked`.

**Key interfaces:**
- The tracker conventions doc — the vocabulary and rules list
- The three tickets' status lines and answer sections

**Acceptance criteria:**
- [ ] The tracker doc defines the vocabulary, resolve section, and partial-checkbox notation
- [ ] Each of the three resolved tickets has an `## Answer` section
- [ ] Grep over the feature directory shows no status word outside the documented set
- [ ] No `[x]` appears on any blocked or partial item in the effort's issues

**Out of scope:**
- Reopening or re-litigating the tickets' decisions
- Touching tickets 03-05 (already conformant)