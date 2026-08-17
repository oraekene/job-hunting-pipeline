# 01 — Bundle canonicalisation

**What to build:** the repo root becomes the one documented customer bundle, and the build-infra folder's role as tooling — whose `dist` is a build check, not a product — is stated where maintainers and agents will find it. Ends the review's "two divergent signed bundles" ambiguity without merging trees or re-signing.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] A document states the repo root is the only customer bundle and the build-infra `dist` is a build-check artifact
- [ ] No doc or ticket presents the build-infra `dist` as shippable
- [ ] The compiled worker text references this ruling in its own notes

**Agent brief:** A1 in `.scratch/review-gap-fixes/spec.md` (## Comments — Bundle canonicalisation)