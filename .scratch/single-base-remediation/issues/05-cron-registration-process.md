# 05 — Cron registration process

**What to build:** Fresh installs register all documented jobs automatically instead of by hand-typed commands; the live install reaches 26/26 registered jobs; re-running the process registers zero new jobs.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] An idempotent registration script exists in the bundle that registers the 22 non-blueprint jobs from the documented schedules (name, schedule, script, skills, `--no-agent`, deliver) and skips jobs already registered
- [ ] The install-check flow invokes it, and the README install steps name it as the cron step
- [ ] The four blueprint jobs remain suggestion-based (no change to them)
- [ ] On the live install: running the process registers exactly the 16 missing jobs; `hermes cron list` shows all 26 documented jobs
- [ ] A second run registers 0 new jobs (idempotency proven)
