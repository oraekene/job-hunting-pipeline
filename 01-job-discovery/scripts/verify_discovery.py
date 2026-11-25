#!/usr/bin/env python3
"""Verify the discovery scan results in the database."""
import sqlite3
from datetime import datetime

DB_PATH = "C:/Users/rotim/AppData/Local/hermes/skills/job-hunting/shared/applications.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Check total count
cur.execute("SELECT COUNT(*) FROM applications")
total = cur.fetchone()[0]
print(f"Total applications: {total}")

# Check today's discovered count
today = datetime.now().strftime("%Y-%m-%d")
cur.execute("SELECT COUNT(*) FROM applications WHERE date(discovered_at) = ?", (today,))
discovered_today = cur.fetchone()[0]
print(f"Discovered today: {discovered_today}")

# Check staged count today
cur.execute("SELECT COUNT(*) FROM applications WHERE date(staged_at) = ? AND staged_at IS NOT NULL", (today,))
staged_today = cur.fetchone()[0]
print(f"Staged today: {staged_today}")

# List all discovered-status applications from today
cur.execute("""
    SELECT id, company, role_title, posting_url, status, posting_fingerprint, 
           priority, discovered_at, posted_at
    FROM applications 
    WHERE date(discovered_at) = ? 
    ORDER BY discovered_at DESC
""", (today,))
rows = cur.fetchall()
print(f"\nApplications discovered today ({len(rows)} total):")
for r in rows:
    print(f"  id={r[0]} | {r[1]} | {r[2]}")
    print(f"    url={r[3]}")
    print(f"    status={r[4]} | priority={r[6]}")
    print(f"    fingerprint={r[5]}")
    print(f"    discovered_at={r[7]} | posted_at={r[8]}")
    print()

# Check posting_sources for today's discoveries
cur.execute("""
    SELECT ps.id, ps.application_id, ps.posting_url, ps.source_name, ps.discovered_by
    FROM posting_sources ps
    JOIN applications a ON ps.application_id = a.id
    WHERE date(a.discovered_at) = ?
    ORDER BY ps.id DESC
    LIMIT 20
""")
ps_rows = cur.fetchall()
print(f"\nPosting sources entries for today's discoveries ({len(ps_rows)} total):")
for r in ps_rows:
    print(f"  ps_id={r[0]} | app_id={r[1]} | source={r[3]} | url={r[2]}")

# Check for any integrity issues
cur.execute("SELECT COUNT(*) FROM applications WHERE posting_fingerprint IS NULL")
null_fp = cur.fetchone()[0]
print(f"\nApplications with NULL fingerprint: {null_fp}")

conn.close()
