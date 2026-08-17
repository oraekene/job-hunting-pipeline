# Verification record — single-base remediation, 2026-08-17

Seam results per ticket. All five seams green as of 2026-08-17.

| Ticket | What | Seam result |
|---|---|---|
| 01 | Single-base documentation | `CONTEXT.md` + `docs/adr/0001-single-base-repository.md` exist; dry-run 33/33 |
| 02 | Status-query docs + outbox cleanup | SKILL.md status-queries section names `_inspect_state.py`/`_query_discovered.py`; stray root `.outbox/_inspect_db.py` deleted; `shared/.outbox/README.md` documents JSON-only + consumed/rejected; absorbed ticket `orchestrator-status-query/01` marked done |
| 03 | Provider config fix | Kenechukwu override: `opencode-go/glm-5.2` default + two `glm-5.2` fallback entries preserved exactly as set; no OpenRouter |
| 04 | Hook hardening | Both hooks installed at `C:\Users\rotim\.hermes\agent-hooks\` and registered in `config.yaml` with absolute paths (no `~`); standalone invocation exits 0 for both; install-check `submit-hook`/`ownership-hook` OK; install-check now also reads `cli-config.yaml` for `hooks_auto_accept` (warning cleared) |
| 05 | Cron registration process | `cron/register-jobs.py` created (idempotent, manifest of 23 non-blueprint jobs); 18 jobs registered on the live install; duplicate old #16 removed; `hermes cron list` = 27 (4 blueprints + 23 manual); `--check` re-run = 0 missing (idempotency proven); install-check `cron-registration` OK; README step 6 names the process |
| 06 | Schema-drift gate | dry-run gains an EXPLAIN-based SQL validation check + 3 mutation cases (33/33); found and fixed real drift: `run_discovery.py` `priority`/`salary_info` → `salary_range`; `title_taxonomy_builder.py` excluded (own DB); ported ticket `pipeline-execution-fixes/02` marked done; harness still 17/17 |
| 07 | Platform issues checklist | `diagnostics/platform-issues-checklist.md` written (8 items, owners, monitoring steps, no repo changes) |

## Seam summary

| Seam | Result |
|---|---|
| `dry-run.py --skill-dir .` | 33/33 PASS |
| `regression-harness.py --skill-dir .` | 17/17 GREEN |
| `install-check.py` | passed, no warnings |
| `hermes cron list` | 27 jobs (4 blueprints + 23 manual; 0 missing on `--check`) |
| `_inspect_state.py` + config read | readable; counts: awaiting_approval 9, discovered 32, rejected_by_kene 7, staged 3 (pipeline progressing) |

## Residual operational items

- Provider 429s were still observed on the cron runs of 2026-08-17 (before/around the glm-5.2 switch settled); watch `hermes cron runs <id>` — owner: Kenechukwu (account limits).
- The fallback chain repeats the same backend (glm-5.2 twice) and Hermes skips same-backend entries — accepted by Kenechukwu 2026-08-17.
- Platform-level items (Telegram DNS, gateway exits, desktop boot, execute_code policy, browser URL quoting, `shell` tool, cron PATH) — tracked in `diagnostics/platform-issues-checklist.md`, out of repo scope.
- A live end-to-end pipeline run was not executed (not required — the five seams verify the fixes without provider spend).
