#!/usr/bin/env python
import sqlite3, json, os

# The applications DB always lives two directories up from this script,
# next to the package's own shared/. That path is the one thing that
# cannot be wrong on any install, so it is checked FIRST. A candidate is
# only accepted if it passes a SCHEMA CHECK, not merely exists — an old
# install at ~/.hermes can leave a 0-byte applications.db behind, and a
# file without the applications table is not this database.
HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT_RELATIVE = os.path.normpath(os.path.join(HERE, "..", "..", "shared", "applications.db"))


def candidate_paths():
    out = [SCRIPT_RELATIVE]
    localappdata = os.environ.get("LOCALAPPDATA", "").strip()
    if localappdata:
        out.append(os.path.join(localappdata, "hermes", "skills", "job-hunting", "shared", "applications.db"))
    hermes_home = os.environ.get("HERMES_HOME", "").strip()
    if hermes_home:
        out.append(os.path.join(hermes_home, "skills", "job-hunting", "shared", "applications.db"))
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
for p in candidate_paths():
    if os.path.exists(p) and has_applications_table(p):
        DB = p
        break

print("DB:", DB)
print("DB EXISTS:", os.path.exists(DB))
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute('PRAGMA table_info(applications)')
cols = [r[1] for r in cur.fetchall()]
print("COLUMNS:", cols)
print()

cur.execute('SELECT * FROM applications ORDER BY id')
rows = cur.fetchall()
print(f'TOTAL applications: {len(rows)}')
print()
for r in rows:
    d = dict(r)
    print(json.dumps(d, indent=2, default=str))
    print('---')

cur.execute('SELECT status, COUNT(*) as cnt FROM applications GROUP BY status')
print('=== Status counts ===')
for r in cur.fetchall():
    print(f'  {r["status"]}: {r["cnt"]}')

conn.close()
