#!/usr/bin/env python3
import sqlite3, json, os
HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.normpath(os.path.join(HERE, "..", "..", "shared", "applications.db"))
print("DB:", DB)
print("EXISTS:", os.path.exists(DB))
con = sqlite3.connect(DB, timeout=10)
con.row_factory = sqlite3.Row
cur = con.cursor()
print()
print("=== TABLES ===")
for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
    print(" ", r[0])
print()
print("=== SCHEMA applications ===")
for r in cur.execute("PRAGMA table_info(applications)"):
    print(f"  {r[1]} {r[2]}")
print()
print("=== STATUS COUNTS ===")
for r in cur.execute("SELECT status, COUNT(*) c FROM applications GROUP BY status"):
    print(f"  {r['status']}: {r['c']}")
print()
print("=== applications (all, key fields) ===")
cols = "id, company, role_title, status, build_attempts, build_artifacts_path, staged_at, discovered_at, overall_match_score, last_failure_stage, last_failure_reason"
for r in cur.execute(f"SELECT {cols} FROM applications ORDER BY id"):
    print(json.dumps(dict(r), default=str, indent=2))
con.close()
