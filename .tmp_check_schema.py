import sqlite3
conn = sqlite3.connect('shared/applications.db')
c = conn.cursor()
print('=== applications columns ===')
for r in c.execute('PRAGMA table_info(applications)'):
    print(r[1], r[2])
print('=== posting_sources columns ===')
for r in c.execute('PRAGMA table_info(posting_sources)'):
    print(r[1], r[2])
print('=== today_count (discovered|building|staged|awaiting_approval) ===')
today = c.execute("SELECT COUNT(*) FROM applications WHERE date(discovered_at)=date('now') AND status IN ('discovered','building','staged','awaiting_approval')").fetchone()[0]
print(today)
print('=== distinct statuses ===')
for r in c.execute("SELECT status, COUNT(*) FROM applications GROUP BY status"):
    print(r)
conn.close()
