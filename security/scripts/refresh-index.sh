#!/usr/bin/env bash
# Nightly retrieval-index refresh — cron-jobs.md §17.
#
# Refreshes the journal projection (career_journal lives in SQLite; qmd only
# sees files) and re-embeds the qmd index so it never answers confidently
# with stale content. qmd is optional — no-op rather than fail if absent.
#
# Paths are HERMES_HOME-relative like backup.sh: on Windows installs
# ~/.hermes can be a stale ghost tree that shadows the real one, and
# `python3` may be a Store stub rather than the real interpreter.

set -euo pipefail

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
SKILL_DIR="${SKILL_DIR:-$HERMES_HOME/skills/job-hunting}"
PY="${PYTHON:-python}"

if [ ! -d "$SKILL_DIR" ]; then
  echo "job-hunting skill dir not found: $SKILL_DIR" >&2
  exit 1
fi

"$PY" "$SKILL_DIR/16-career-pulse/scripts/journal-export.py" \
  --db "$SKILL_DIR/shared/applications.db" \
  --out "$SKILL_DIR/shared/journal_export/" --quiet

if command -v qmd >/dev/null 2>&1; then
  (cd "$SKILL_DIR" && qmd embed)
else
  echo "[SILENT] qmd not installed — journal export refreshed, index skipped"
fi
