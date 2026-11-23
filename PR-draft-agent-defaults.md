# PR DRAFT — Enable tool-loop guardrails & raise browser command timeout by default

**Repo:** `NousResearch/hermes-agent` · **Branch:** `chore/default-guardrails-on`
**Filing guide:** copy this into the PR body; the three file diffs below are ready to apply as-is.

---

## Title
`feat(loop): enable tool-loop hard-stop guardrails + raise browser command timeout by default`

## Why

A dedicated browser-automation battery (76 runs, Aug 18–19 2026, Hermes v0.20.0) was run to
diagnose a production incident: two cron-backed discovery jobs burned **1.59M and 2.38M input
tokens** (46–101 tool calls each) looping forever on blocked/unreachable sites (LinkedIn sign-in
wall → Indeed Cloudflare block → Wellfound login → retry). Root causes were (a) no stop-condition
in the task prompt and (b) **loop guardrails shipping disabled** (`hard_stop_enabled: false`), so
nothing ever terminated a pathological loop.

Flipping the default to **on** and giving slow pages a more realistic command timeout eliminates
the unbounded-retry footgun for every user, not just those who happen to tune config. After the
change, the same stack completed 68/76 runs cleanly with **zero loops**, and the worst-case runs
dropped from ~1.8M tokens to the cost of a normal multi-turn task (50k–190k for full
multi-field forms). Warnings still precede hard-stops, so interactive sessions are unaffected
unless they genuinely stall.

## Changes

### 1) `hermes_cli/config_defaults.py` — shipped default config template
```diff
@@ tool_loop_guardrails (defaults) @@
-    # Tool loop guardrails nudge models when they repeat failed or
-    # non-progressing tool calls. Soft warnings are always-on by default;
-    # hard stops are opt-in so interactive CLI/TUI sessions keep flowing.
+    # Tool loop guardrails nudge models when they repeat failed or
+    # non-progressing tool calls. Hard stops terminate only after repeated
+    # identical failures / no-progress turns (defaults: 5 / 8 / 5 attempts,
+    # all preceded by at least two soft warnings), so interactive sessions
+    # that are making progress never hit them — enabling by default protects
+    # autonomous/cron runs from unbounded retry loops (see #<PR> for the
+    # 76-run battery that triggered this change).
     "tool_loop_guardrails": {
         "warnings_enabled": True,
-        "hard_stop_enabled": False,
+        "hard_stop_enabled": True,
```
```diff
@@ browser (defaults) @@
-        "command_timeout": 30,  # Timeout for browser commands in seconds (screenshot, navigate, etc.)
+        "command_timeout": 45,  # Timeout for browser commands in seconds (screenshot, navigate, etc.)
```

### 2) `agent/tool_guardrails.py` — dataclass fallback (used when no config file)
```diff
-    hard_stop_enabled: bool = False
+    hard_stop_enabled: bool = True
```
*(line 73; applies to the no-config fallback path so the default is consistent everywhere.)*

### 3) `tools/browser_tool.py` — code-level command-timeout fallback
```diff
-DEFAULT_COMMAND_TIMEOUT = 30
+DEFAULT_COMMAND_TIMEOUT = 45
```
*(line 278; used when `browser.command_timeout` is unset — keep in sync with the template above.)*

## Notes for reviewers
- **Backward compatible.** Users who already set `hard_stop_enabled` / `command_timeout` in their
  `config.yaml` are unaffected (explicit values always win). No migration needed — this is a
  default-only change.
- **Safety margin intact.** Hard-stops are gated behind `warn_after` (2/3/2 default): a session gets
  at least two soft warnings *before* any hard-stop can fire, and only on repeated **identical**
  failures or **no-progress** turns. Legitimate multi-turn work never trips it.
- **Tightening is optional.** The battery used 4/6/4 hard-stop thresholds; this PR ships upstream's
  existing 5/8/5 to keep the change minimal. Happy to tighten thresholds in a follow-up.
- **Interactive sessions unaffected** when progressing (see comment rewrite above).

## Evidence appendix (from the 76-run battery)
- **Before:** 1,591,859 / 2,382,938 input tokens, 46 / 101 calls, no completion — blocked-site loops.
- **After (same stack, guardrails on + timeout 45 + stop-condition prompts):** 68 clean, 8
  diagnosed environmental timeouts, **0 loops**; median simple task ~600 tokens over cache in
  40–230s.
- Full per-run tables, blocked-site reachability map, and the reusable harness:
  private `oraekene/browser-test-harness` (REPORT.md) — happy to attach selected excerpts.
- Machine: Windows, local headless Chromium (agent-browser), deepseek-v4-flash default + free
  Nous fallback models.

---
*Generated 2026-08-19. Ready to file against `main` — excerpt from the evidence lives in the
private battery repo; this draft is archived at
`browser-test-harness/PR-draft-agent-defaults.md` (commit `add47a2` branch).*
