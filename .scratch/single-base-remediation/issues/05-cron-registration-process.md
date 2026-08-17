# 05 — Cron registration process

**What to build:** Fresh installs register all documented jobs automatically instead of by hand-typed commands; the live install reaches 26/26 registered jobs; re-running the process registers zero new jobs.

**Blocked by:** None — can start immediately.

**Status:** done (2026-08-17)

- [x] An idempotent registration script exists in the bundle that registers the 23 non-blueprint jobs from the documented schedules (name, schedule, script, skills, `--no-agent`, deliver) and skips jobs already registered
- [x] The install-check flow invokes it, and the README install steps name it as the cron step
- [x] The four blueprint jobs remain suggestion-based (no change to them)
- [x] On the live install: running the process registers the missing jobs; `hermes cron list` shows all 27 jobs (4 blueprints + 23 manual)
- [x] A second run registers 0 new jobs (idempotency proven)
