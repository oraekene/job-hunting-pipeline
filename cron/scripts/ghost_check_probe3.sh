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

echo "===== apps with approval_sent_at set (10) ====="
sqlite3 -header -column "$DB" "SELECT id, company, role_title, status, approval_sent_at, sent_at, approval_decision, outcome FROM applications WHERE approval_sent_at IS NOT NULL ORDER BY approval_sent_at DESC;" 2>&1
echo ""

echo "===== all timestamp cols non-null counts ====="
sqlite3 -header -column "$DB" "SELECT SUM(sent_at IS NOT NULL) AS sent_at, SUM(approval_sent_at IS NOT NULL) AS approval_sent, SUM(first_response_at IS NOT NULL) AS first_resp, SUM(outcome_updated_at IS NOT NULL) AS outcome_updated FROM applications;" 2>&1
echo ""

echo "===== cron_executions columns ====="
sqlite3 "$DB" "PRAGMA table_info(cron_executions);" 2>&1
echo "DONE"
