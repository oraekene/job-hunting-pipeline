import sqlite3, os, json
DB = "C:/Users/rotim/AppData/Local/hermes/skills/job-hunting/shared/applications.db"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

print("=== applications columns ===")
for r in con.execute("PRAGMA table_info(applications)"):
    print(f"  {r['name']}  {r['type']}  default={r['dflt_value']}")

print("\n=== social_outreach columns ===")
for r in con.execute("PRAGMA table_info(social_outreach)"):
    print(f"  {r['name']}  {r['type']}  default={r['dflt_value']}")

print("\n=== posting_sources columns ===")
for r in con.execute("PRAGMA table_info(posting_sources)"):
    print(f"  {r['name']}  {r['type']}")

print("\n=== daily_cap / gate state ===")
gs = json.load(open("shared/.discovery_gate_state.json"))
print(json.dumps(gs, indent=2))

print("\n=== existing social_outreach count ===")
print(con.execute("SELECT COUNT(*) FROM social_outreach").fetchone()[0])

print("\n=== recent application IDs ===")
for r in con.execute("SELECT id,company,role_title,status,source_board,posting_fingerprint FROM applications ORDER BY id DESC LIMIT 5"):
    print(f"  {dict(r)}")
