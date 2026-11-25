import sqlite3, os, json
from datetime import datetime, timedelta

db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'shared', 'applications.db')
db = sqlite3.connect(db_path)
db.row_factory = sqlite3.Row

print("=== TABLES ===")
tables = [r[0] for r in db.execute('SELECT name FROM sqlite_master WHERE type="table"').fetchall()]
print(tables)

print("\n=== COUNT BY STATUS ===")
for r in db.execute('SELECT status, COUNT(*) c FROM applications GROUP BY status'):
    print(dict(r))

print("\n=== COUNT BY OUTCOME ===")
for r in db.execute('SELECT outcome, COUNT(*) c FROM applications GROUP BY outcome'):
    print(dict(r))

print("\n=== COLUMNS ===")
cols = [r[1] for r in db.execute('PRAGMA table_info(applications)').fetchall()]
print(cols)

print("\n=== ALL SENT APPS (recent 40) ===")
for r in db.execute("SELECT id, company, role_title, sent_at, outcome, outcome_source, response_type FROM applications WHERE sent_at IS NOT NULL ORDER BY sent_at DESC LIMIT 40"):
    print(dict(r))

# Check for sent > 21 days ago still pending
print("\n=== SENT > 21 DAYS AGO, OUTCOME pending ===")
rows = db.execute("""
    SELECT id, company, role_title, posting_url, sent_at, outcome, outcome_source,
           response_type, first_response_at, outcome_updated_at,
           approval_decision, approval_sent_at
    FROM applications
    WHERE sent_at IS NOT NULL AND outcome = 'pending'
    ORDER BY sent_at
""").fetchall()
print(f"Total pending-with-sent: {len(rows)}")
twenty_one_days_ago = datetime.now() - timedelta(days=21)
print(f"Cutoff (21d ago): {twenty_one_days_ago}")
for r in rows:
    sent = r['sent_at']
    if sent:
        try:
            sent_dt = datetime.fromisoformat(sent.replace('Z','+00:00').replace('+00:00',''))
        except:
            sent_dt = datetime.now()
        age_days = (datetime.now() - sent_dt).days
        if age_days > 21:
            print(f"  > {age_days}d OLD: {dict(r)}")

# email_insights check
print("\n=== EMAIL_INSIGHTS ===")
try:
    for r in db.execute("SELECT * FROM email_insights ORDER BY extracted_at DESC LIMIT 20"):
        print(dict(r))
except Exception as e:
    print(f"email_insights error: {e}")

# open_gaps check
print("\n=== OPEN_GAPS (unresolved) ===")
try:
    for r in db.execute("SELECT * FROM open_gaps WHERE resolved=0 ORDER BY flagged_at DESC LIMIT 20"):
        print(dict(r))
except Exception as e:
    print(f"open_gaps error: {e}")

db.close()
