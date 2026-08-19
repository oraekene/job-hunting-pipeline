#!/usr/bin/env bash
# =============================================================================
# setup-enable-guardrails.sh — job-hunting-pipeline prerequisite bootstrap
#
# A fresh Hermes install ships with tool-loop guardrails DISABLED and a short
# browser command timeout. Heavy autonomous pipelines (this one runs discovery
# 6x/day and fills application forms) are exactly the workload that burns
# millions of tokens when a blocked source becomes a retry loop. This script
# checks the install, warns if the protective settings are off, and (on
# consent) enables them — with a backup of config.yaml before any change.
#
# SCOPE (deliberately narrow):
#   + tool_loop_guardrails.*  (hard-stop + warn thresholds)
#   + browser.command_timeout / inactivity_timeout
#   + verifies the marker-gated submit-approval hook is installed
# DELIBERATELY DOES NOT TOUCH:
#   - fallback_providers (user/subscription-specific) — no model is pinned here
#   - .env / credentials / provider keys
#   - anything else in config.yaml
#
# Idempotent + re-runnable. Flags: run `bash setup-enable-guardrails.sh --yes`
# to apply without interactive prompts (for scripts/CI).
# =============================================================================
set -uo pipefail

HERMES_DIR="${HERMES_DIR:-$HOME/AppData/Local/hermes}"
CONFIG="${HERMES_DIR}/config.yaml"
HOOK_DIR="${HOOKS_DIR:-$HOME/.hermes/agent-hooks}"
HOOK="${HOOK_DIR}/job-hunting-verify-submit-approval.py"
ASYNC="${1:-}"
STAMP="$(date +%Y%m%d-%H%M%S)"

say() { printf '\n==> %s\n' "$*"; }
ok()  { printf '    [ok]   %s\n' "$*"; }
warn(){ printf '    [warn] %s\n' "$*"; }

command -v hermes >/dev/null 2>&1 || { echo "[FATAL] hermes CLI not on PATH — install Hermes first."; exit 1; }
[ -f "$CONFIG" ] || { echo "[FATAL] no config at $CONFIG"; exit 1; }

ask() { # prompt -> 0 (yes) / 1 (no)
  [ "$ASYNC" = "--yes" ] && return 0
  printf '    %s [y/N] ' "$1"; read -r a
  case "$a" in y|Y|yes|YES) return 0;; *) return 1;; esac
}

changed=0

# --- guardrails -----------------------------------------------------------------
say "Checking tool-loop guardrails"
if grep -qE '^\s{2}hard_stop_enabled:\s*true' "$CONFIG" \
   || hermes config get tool_loop_guardrails.hard_stop_enabled 2>/dev/null | grep -qi 'true'; then
  ok "guardrails already enabled"
else
  warn "hard-stop guardrails are OFF — repeated failures on blocked/unreachable"
  warn "sources become unbounded retry loops (a known multi-million-token burn)."
  if ask "Enable loop guardrails + sane thresholds now?"; then
    hermes config set tool_loop_guardrails.hard_stop_enabled true
    hermes config set tool_loop_guardrails.warn_after.exact_failure 2
    hermes config set tool_loop_guardrails.warn_after.same_tool_failure 3
    hermes config set tool_loop_guardrails.warn_after.idempotent_no_progress 3
    hermes config set tool_loop_guardrails.hard_stop_after.exact_failure 4
    hermes config set tool_loop_guardrails.hard_stop_after.same_tool_failure 6
    hermes config set tool_loop_guardrails.hard_stop_after.idempotent_no_progress 4
    cp "$CONFIG" "${CONFIG}.bak-guardrails-${STAMP}"
    ok "enabled (backup -> ${CONFIG}.bak-guardrails-${STAMP})"; changed=1
  else
    warn "skipped — pipeline runs WITHOUT loop guardrails (not recommended)"
  fi
fi

# --- browser timeouts -----------------------------------------------------------
say "Checking browser command timeouts"
if grep -qE '^\s{2}command_timeout:\s*4[0-9]|^\s{2}command_timeout:\s*5[0-9]' "$CONFIG" 2>/dev/null; then
  ok "browser.command_timeout already >= 40"
else
  warn "browser.command_timeout is short for slow pages (spurious tool failures)."
  if ask "Set browser.command_timeout=45 (and inactivity_timeout=120)?"; then
    hermes config set browser.command_timeout 45
    hermes config set browser.inactivity_timeout 120
    ok "browser timeouts set"; changed=1
  else
    warn "browser timeouts left as-is"
  fi
fi

# --- hook present? --------------------------------------------------------------
say "Checking submit-approval hook"
if [ -f "$HOOK" ] && grep -q "ACTIVE_APP_DIR" "$HOOK" && grep -q "_allow" "$HOOK"; then
  ok "marker-gated submit-approval hook installed ($HOOK)"
else
  warn "marker-gated hook NOT installed here. Install the pipeline hooks from"
  warn "security/hooks/ (copy both verify-*.py into $HOOK_DIR and chmod +x),"
  warn "then re-run this script. Plain-session submit clicks would otherwise"
  warn "be blocked (the bug this whole package fixes)."
fi

say "Done. $([ "$changed" -ge 1 ] && echo 'Changes applied (backups written, re-runnable).' || echo 'No changes needed — install is already hardened.')"
exit 0
