#!/usr/bin/env python3
import sqlite3, json, os
HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.normpath(os.path.join(HERE, "..", "..", "shared", "applications.db"))
ARTIFACTS = os.path.normpath(os.path.join(HERE, "..", "..", "shared", "build_artifacts"))
con = sqlite3.connect(DB, timeout=10)
con.row_factory = sqlite3.Row
cur = con.cursor()
# Discovered apps with posting URLs
cols = "id, company, role_title, posting_url, source_board, discovered_at, overall_match_score, build_attempts, build_artifacts_path, posting_fingerprint"
for r in cur.execute(f"SELECT {cols} FROM applications WHERE status='discovered' ORDER BY id LIMIT 5"):
    d = dict(r)
    print(json.dumps(d, default=str, indent=2))
print("=== approval_sent_at check for staged ===")
for r in cur.execute("SELECT id, status, approval_sent_at FROM applications WHERE status IN ('staged','awaiting_approval') ORDER BY id"):
    print(json.dumps(dict(r), default=str))
con.close()
print()
print("=== app_85 artifact dir ===")
d = os.path.join(ARTIFACTS, "app_85")
if os.path.isdir(d):
    for f in sorted(os.listdir(d)):
        p = os.path.join(d, f)
        print(f"  {f}: {os.path.getsize(p) if os.path.isfile(p) else 'DIR'} bytes")
else:
    print("  no app_85 dir")
