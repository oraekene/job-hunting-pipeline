#!/bin/bash
# Ghost-check probe: DB state + himalaya availability
DB="C:/Users/rotim/AppData/Local/hermes/skills/job-hunting/shared/applications.db"

echo "===== HIMALAYA ====="
command -v himalaya && himalaya --version 2>&1 || echo "himalaya: NOT FOUND"
echo ""

echo "===== HIMALAYA CONFIG ====="
cat "$HOME/.config/himalaya/config.toml" 2>&1 || echo "(no config found)"
echo ""

echo "===== DB SUMMARY ====="
sqlite3 "$DB" "SELECT COUNT(*) AS total, SUM(CASE WHEN sent_at IS NOT NULL THEN 1 ELSE 0 END) AS sent, SUM(CASE WHEN sent_at IS NOT NULL AND outcome='pending' THEN 1 ELSE 0 END) AS pending_after_sent, SUM(CASE WHEN sent_at IS NOT NULL AND outcome!='pending' THEN 1 ELSE 0 END) AS resolved_after_sent FROM applications;" 2>&1
echo ""

echo "===== PENDING AFTER SENT (with age in days) ====="
sqlite3 -header -column "$DB" "SELECT id, company, role_title, posting_url, sent_at, julianday('now') - julianday(substr(sent_at,1,19)) AS days_since_sent, outcome, outcome_source FROM applications WHERE sent_at IS NOT NULL AND outcome='pending' ORDER BY sent_at;" 2>&1
echo ""

echo "===== OVER 21 DAYS PENDING ====="
sqlite3 -header -column "$DB" "SELECT id, company, role_title, posting_url, sent_at, julianday('now') - julianday(substr(sent_at,1,19)) AS days_since_sent FROM applications WHERE sent_at IS NOT NULL AND outcome='pending' AND julianday('now') - julianday(substr(sent_at,1,19)) > 21 ORDER BY sent_at;" 2>&1
echo ""

echo "===== RESOLVED OUTCOMES (for reference) ====="
sqlite3 -header -column "$DB" "SELECT outcome, COUNT(*) AS cnt FROM applications WHERE sent_at IS NOT NULL GROUP BY outcome;" 2>&1
echo ""

echo "===== TABLES ====="
sqlite3 "$DB" ".tables" 2>&1
echo "DONE"
