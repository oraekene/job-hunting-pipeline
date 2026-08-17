# Platform / environment issues checklist — out of repo scope

These failures were observed in the 2026-08-15 session and are
Hermes-platform or environment-level, not fixable in this repo's code.
Track them here; do not patch repo code for them.

**Status:** monitoring — no repo code changes for any item below.

| # | Issue | Owner | Monitoring / verification |
|---|---|---|---|
| 1 | Telegram `api.telegram.org` DNS failures (`[Errno 11001] getaddrinfo failed`); gateway ran with no connected platforms ~1h | Hermes platform / network | Check gateway logs after any run for "no connected platforms"; confirm the sticky fallback IP reconnect works; report to Hermes if it recurs |
| 2 | Gateway exited UNCLEANLY (SIGKILL/OOM/VM death) — no exit path ran | Hermes platform | Watch for unexpected gateway restarts; `hermes gateway status` after a session; report with logs if it repeats |
| 3 | Desktop boot timeouts ("Timed out waiting for Hermes backend port announcement 90000ms"; renderer 60000ms) | Hermes platform (desktop) | On next desktop boot, note boot time; report if timeouts recur |
| 4 | `execute_code` BLOCKED in cron ("runs arbitrary local Python... no user present to approve") | Hermes platform policy | Cron prompts/scripts must avoid `execute_code`; run `.py` files via the terminal tool / `--script` jobs instead. This is expected behaviour, not a bug |
| 5 | Browser `open` shell-interprets unquoted URLs with `&` query params on Windows (`'f_TPR' is not recognized...`) | Hermes platform (browser tool) | In cron/agent runs, avoid passing raw query-param URLs to the browser tool; prefer quoted/encoded URLs or web fetch. Report to Hermes |
| 6 | Agent called unknown tool `shell` instead of `terminal` ("Unknown tool 'shell'") | Hermes platform (tool naming) | Correct in prompt/skill guidance where seen; matches the agent-execution-discipline spec (Documents repo archive) |
| 7 | Cron environment: "Python was not found; run without arguments to install from the Microsoft Store" | Environment (PATH) | Ensure the cron/scheduler environment PATH resolves a real Python (not the Store alias); scripts already prefer `$PYTHON`/`python` with fallback per refresh-index.sh |
| 8 | Provider 429s killed cron runs (weekly usage limit on opencode-go, free-lane limit on opencode-zen) | Account/provider (user-owned) | Kenechukwu switched the default model (glm-5.2). Watch `hermes cron runs <id>` for 429s after the change; note the fallback chain currently repeats the same backend and Hermes skips same-backend entries — accepted by Kenechukwu 2026-08-17 |

Updated 2026-08-17 (single-base-remediation ticket 07).
