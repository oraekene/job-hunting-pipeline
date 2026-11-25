#!/bin/bash
DB="C:/Users/rotim/AppData/Local/hermes/skills/job-hunting/shared/applications.db"

echo "===== COLUMNS in applications ====="
sqlite3 "$DB" "PRAGMA table_info(applications);" 2>&1
echo ""

echo "===== STATUS distribution ====="
sqlite3 -header -column "$DB" "SELECT status, COUNT(*) AS cnt FROM applications GROUP BY status ORDER BY cnt DESC;" 2>&1
echo ""

echo "===== OUTCOME distribution ====="
sqlite3 -header -column "$DB" "SELECT outcome, COUNT(*) AS cnt FROM applications GROUP BY outcome ORDER BY cnt DESC;" 2>&1
echo ""

echo "===== sent_at non-null count & sample values ====="
sqlite3 "$DB" "SELECT COUNT(*) AS sent_at_set FROM applications WHERE sent_at IS NOT NULL;" 2>&1
echo "--- sample rows (id, company, role_title, status, sent_at, outcome, outcome_source) ---"
sqlite3 -header -column "$DB" "SELECT id, company, role_title, status, sent_at, outcome, outcome_source FROM applications ORDER BY id DESC LIMIT 10;" 2>&1
echo ""

echo "===== approval_sent_at / sent_at non-null ====="
sqlite3 -header -column "$DB" "SELECT COUNT(*) AS approval_sent_at_set FROM applications WHERE approval_sent_at IS NOT NULL; SELECT COUNT(*) AS sent_at_set FROM applications WHERE sent_at IS NOT NULL;" 2>&1
echo ""

echo "===== recent cron executions ====="
sqlite3 -header -column "$DB" "SELECT job_name, started_at, completed_at, exit_code, result_summary FROM cron_executions ORDER BY started_at DESC LIMIT 10;" 2>&1
echo "DONE"
