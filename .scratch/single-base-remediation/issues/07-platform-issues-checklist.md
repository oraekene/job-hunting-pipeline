# 07 — Platform issues checklist

**What to build:** A written checklist records the Hermes-platform/environment failures declared out of repo scope, with monitoring steps, so they are tracked but never patched in repo code.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] A checklist file exists (under `diagnostics/` or `docs/`) listing: Telegram DNS failures, unclean gateway exit, desktop boot timeouts, `execute_code` blocked in cron, browser URL shell-interpretation, unknown `shell` tool, cron PATH ("Python was not found")
- [ ] Each item has a monitoring/verification step and an owner note (Hermes platform vs environment)
- [ ] The checklist states explicitly: no repo code changes for these items
