# 03 — Provider config fix

**What to build:** The model lanes match Kenechukwu's chosen setting, and no unintended provider entries exist.

**Blocked by:** None — can start immediately.

**Status:** done — 2026-08-17, per Kenechukwu's override

- [x] `config.yaml` default model kept as `glm-5.2` with provider `opencode-go` (Kenechukwu's setting)
- [x] `fallback_providers` kept as Kenechukwu set it: two `opencode-go / glm-5.2` entries (reverted an earlier attempt to change it; the same-backend skip behavior is accepted by Kenechukwu)
- [x] No OpenRouter entries added
- [x] Verification: config read shows the preserved values
