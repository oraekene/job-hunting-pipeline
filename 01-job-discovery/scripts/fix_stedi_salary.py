#!/usr/bin/env python3
"""Correction: Stedi row has an unverifiable salary range - null it out."""
import sqlite3, os, json

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(SKILL_ROOT, "shared", "applications.db")

conn = sqlite3.connect(DB)
cur = conn.cursor()
url = "https://jobs.ashbyhq.com/stedi/65b38320-75df-4386-b5e5-25b411e7a6a4"
cur.execute("UPDATE applications SET salary_disclosed = 0, salary_range = NULL WHERE posting_url = ?", (url,))
print("rows updated:", cur.rowcount)
cur.execute("SELECT id, company, role_title, overall_match_score, keyword_match_score, salary_disclosed, salary_range FROM applications WHERE posting_url = ?", (url,))
print(cur.fetchone())
conn.commit()
conn.close()

# Fix results file
RESULTS = os.path.join(SKILL_ROOT, "shared", ".discovery_results.json")
with open(RESULTS) as f:
    res = json.load(f)
for q in res["queued"]:
    if q["company"] == "Stedi":
        q["salary_range"] = None
        q["note"] = "salary not disclosed on posting (initially mis-staged, corrected same run)"
with open(RESULTS, "w") as f:
    json.dump(res, f, indent=2)
print("results file fixed")
