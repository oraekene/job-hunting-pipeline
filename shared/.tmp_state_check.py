import sqlite3
db = "C:/Users/rotim/AppData/Local/hermes/skills/job-hunting/shared/applications.db"
con = sqlite3.connect(db)
con.row_factory = sqlite3.Row
tabs = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
print("TABLES:", tabs)
print()
for r in con.execute("SELECT status,COUNT(*) c FROM applications GROUP BY status"):
    print("APP status:", dict(r)['status'], dict(r)['c'])
print()
for r in con.execute("SELECT status,COUNT(*) c FROM social_outreach GROUP BY status"):
    print("SO status:", dict(r)['status'], dict(r)['c'])
print()
print("=== recent applications ===")
for r in con.execute("SELECT id,company,role_title,posting_url,status,source_board,posted_at,discovered_at FROM applications ORDER BY id DESC LIMIT 5"):
    print(dict(r))
print()
print("=== recent social_outreach ===")
for r in con.execute("SELECT id,trigger_type,source_platform,source_cta_type,contact_handle,status,created_at FROM social_outreach ORDER BY id DESC LIMIT 5"):
    print(dict(r))
print()
print("=== posting_sources table? ===")
ps = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE name='posting_sources'")]
print("posting_sources exists:", bool(ps))
