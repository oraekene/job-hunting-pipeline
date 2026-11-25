#!/usr/bin/env python3
"""Consistency: recompute Stedi match score without the salary bonus; final verification of all 4 inserts."""
import sqlite3, os, json

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(SKILL_ROOT, "shared", "applications.db")

conn = sqlite3.connect(DB)
cur = conn.cursor()
# Stedi: no salary bonus now -> base 70 + exact-variant title 15 = 85
cur.execute("UPDATE applications SET overall_match_score = 85, keyword_match_score = 85 WHERE posting_url = ?",
            ("https://jobs.ashbyhq.com/stedi/65b38320-75df-4386-b5e5-25b411e7a6a4",))
print("stedi score updated:", cur.rowcount)

cur.execute("""SELECT id, company, role_title, status, source_board, seniority, remote_type,
               posted_at, posted_at_raw, salary_disclosed, salary_range,
               overall_match_score, priority, posting_fingerprint
               FROM applications WHERE date(discovered_at) = date('now') ORDER BY id""")
rows = cur.fetchall()
print(f"\n{len(rows)} rows discovered today:")
for r in rows:
    print(" ", r)

cur.execute("SELECT COUNT(*) FROM applications WHERE date(discovered_at) = date('now')")
n_disc = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM applications WHERE date(staged_at) = date('now') AND staged_at IS NOT NULL")
n_staged = cur.fetchone()[0]
conn.close()

print(f"\ncap check: staged_today={n_staged} discovered_today={n_disc} used={n_staged+n_disc}/15 remaining={15-n_staged-n_disc}")
assert len(rows) == 4 and all(r[3] == "discovered" for r in rows), "unexpected row state"
print("VERIFIED OK")
