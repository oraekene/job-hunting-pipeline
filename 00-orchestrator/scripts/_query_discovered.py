#!/usr/bin/env python3
import sqlite3, os, json, sys

# The applications DB always lives two directories up from this script,
# next to the package's own shared/. That path is the one thing that
# cannot be wrong on any install, so it is checked FIRST. Everything
# else is a fallback for exotic layouts.
#
# A candidate is only accepted if it PASSES A SCHEMA CHECK, not merely
# exists: an old install at ~/.hermes can leave a 0-byte
# applications.db that os.path.exists() happily reports (the sweep spent
# runs querying "no such table: applications" because of exactly that
# ghost). A file without the applications table is not this database.
HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT_RELATIVE = os.path.normpath(os.path.join(HERE, "..", "..", "shared", "applications.db"))


def candidate_paths():
    out = [SCRIPT_RELATIVE]
    hermes_home = os.environ.get("HERMES_HOME", "").strip()
    if hermes_home:
        out.append(os.path.join(hermes_home, "skills", "job-hunting", "shared", "applications.db"))
    localappdata = os.environ.get("LOCALAPPDATA", "").strip()
    if localappdata:
        out.append(os.path.join(localappdata, "hermes", "skills", "job-hunting", "shared", "applications.db"))
    appdata = os.environ.get("APPDATA", "").strip()
    if appdata:
        out.append(os.path.join(appdata, "..", "Local", "hermes", "skills", "job-hunting", "shared", "applications.db"))
    # Last resort fallback for git-bash-style layouts. NEVER first: on a
    # Windows install ~/.hermes can be a ghost tree holding only a 0-byte
    # DB, and a ghost that shadows the real database stalls the sweep.
    out.append(os.path.expanduser("~/.hermes/skills/job-hunting/shared/applications.db"))
    return out


def has_applications_table(db):
    try:
        con = sqlite3.connect("file:{}?mode=ro".format(db.replace("\\", "/")), uri=True)
        ok = any(
            r[0] == "applications"
            for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
        )
        con.close()
        return ok
    except Exception:
        return False


DB = None
for candidate in candidate_paths():
    if candidate and os.path.exists(candidate) and has_applications_table(candidate):
        DB = candidate
        break

if not DB:
    # Try all candidates for error reporting
    print("DB PATHS CHECKED:")
    for c in candidates:
        if c:
            print(f"  {c}: exists={os.path.exists(c)}")
    print("ERROR: No applications.db found")
    sys.exit(1)

print("DB PATH:", DB)
print("DB EXISTS:", os.path.exists(DB))

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in c.fetchall()]
print("TABLES:", tables)

# Query both 'discovered' and 'building' statuses, since build attempts may leave apps at 'building'
c.execute("SELECT id, company, role_title, posting_url, source_board, status, discovered_at, overall_match_score, keyword_match_score, staged_at, posted_at, remote_type, salary_range, industry, seniority, build_attempts, building_started_at FROM applications WHERE status IN ('discovered', 'building') ORDER BY discovered_at DESC")
rows = c.fetchall()
print("PENDING COUNT:", len(rows))
for r in rows:
    d = dict(r)
    print(json.dumps(d, indent=2, default=str))
