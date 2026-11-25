#!/bin/bash
echo "=== himalaya in PATH ==="
command -v himalaya 2>&1 || echo "not in PATH"
echo "=== himalaya anywhere under home ==="
find ~ -iname "himalaya*" -not -path "*/node_modules/*" 2>/dev/null | head
echo "=== email config dirs ==="
ls -la ~/.config/himalaya/ 2>&1 || echo "no himalaya config dir"
echo "=== mbsync/aerc/other mail tools ==="
command -v mbsync mblaze mu 2>&1 || echo "none"
echo "=== DB: any email-related rows or outcome_source values ==="
DB="C:/Users/rotim/AppData/Local/hermes/skills/job-hunting/shared/applications.db"
sqlite3 -header -column "$DB" "SELECT outcome_source, COUNT(*) FROM applications GROUP BY outcome_source; SELECT 'pending with sent_at' AS chk, COUNT(*) AS cnt FROM applications WHERE sent_at IS NOT NULL AND outcome='pending';" 2>&1
echo "DONE"
