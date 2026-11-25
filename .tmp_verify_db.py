import sqlite3, datetime
conn = sqlite3.connect('shared/applications.db')
c = conn.cursor()
now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d')
print('today UTC:', now)
print('rows discovered today:', c.execute("SELECT COUNT(*) FROM applications WHERE date(discovered_at)=date('now')").fetchone()[0])
print('--- discovered today rows (if any) ---')
for r in c.execute("SELECT id, posting_url, company, role_title, status, source_board, priority, discovered_at FROM applications WHERE date(discovered_at)=date('now') ORDER BY id DESC LIMIT 20"):
    print(r)
print('total applications:', c.execute("SELECT COUNT(*) FROM applications").fetchone()[0])
conn.close()
