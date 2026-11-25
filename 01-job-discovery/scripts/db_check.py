#!/usr/bin/env python3
"""Check DB state for discovery run: daily cap, existing fingerprints, last run time."""
import sqlite3, json, os
from datetime import datetime, timezone

DB_PATH = "C:/Users/rotim/AppData/Local/hermes/skills/job-hunting/shared/applications.db"

def main():
    if not os.path.exists(DB_PATH):
        print("ERROR: DB not found at", DB_PATH)
        return
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 1. Check today's staged count (daily cap)
    today = datetime.now().strftime("%Y-%m-%d")
    cur.execute("SELECT COUNT(*) FROM applications WHERE date(staged_at) = ? AND staged_at IS NOT NULL", (today,))
    staged_today = cur.fetchone()[0]
    print(f"Today ({today}) staged count: {staged_today} / 15 (starter cap)")

    # 2. Check discovered count today
    cur.execute("SELECT COUNT(*) FROM applications WHERE date(discovered_at) = ? AND status IN ('discovered','building','staged')", (today,))
    discovered_today = cur.fetchone()[0]
    print(f"Today discovered+active count: {discovered_today}")

    # 3. Check total applications
    cur.execute("SELECT COUNT(*) FROM applications")
    total = cur.fetchone()[0]
    print(f"Total applications in DB: {total}")

    # 4. Check existing fingerprints
    cur.execute("SELECT posting_fingerprint FROM applications WHERE posting_fingerprint IS NOT NULL")
    fingerprints = set(r[0] for r in cur.fetchall())
    print(f"Existing fingerprints: {len(fingerprints)}")

    # 5. Check last 10 applications with fingerprints
    cur.execute("SELECT company, role_title, posting_url, status, posting_fingerprint, discovered_at FROM applications ORDER BY discovered_at DESC LIMIT 10")
    print("\nRecent 10 applications:")
    for row in cur.fetchall():
        print(f"  {row}")

    # 6. Check if posting_fingerprint column exists
    cur.execute("PRAGMA table_info(applications)")
    cols = [c[1] for c in cur.fetchall()]
    print(f"\nColumns: {cols}")
    print(f"Has posting_fingerprint: {'posting_fingerprint' in cols}")
    print(f"Has priority: {'priority' in cols}")

    # 7. Check schema versions
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    print(f"\nTables: {tables}")

    # 8. Check posting_sources table
    if 'posting_sources' in tables:
        cur.execute("SELECT COUNT(*) FROM posting_sources")
        print(f"posting_sources count: {cur.fetchone()[0]}")

    conn.close()
    print("\n--- DB check complete ---")

if __name__ == "__main__":
    main()
