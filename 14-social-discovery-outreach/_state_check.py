import sqlite3, os
DB = os.path.join(r'C:\Users\rotim\AppData\Local\hermes\skills\job-hunting', 'shared', 'applications.db')
conn = sqlite3.connect(DB)
cur = conn.cursor()
tabs = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print('has social_outreach:', 'social_outreach' in tabs)
if 'social_outreach' in tabs:
    cols = [d[1] for d in cur.execute('PRAGMA table_info(social_outreach)').fetchall()]
    print('COLS:', cols)
    print('ROWS:', cur.execute('SELECT COUNT(*) FROM social_outreach').fetchone()[0])
print('--- schema_version ---')
for r in cur.execute('SELECT filename FROM schema_version ORDER BY filename').fetchall():
    print('  ', r[0])
print('--- applications count + statuses ---')
try:
    print('total apps:', cur.execute('SELECT COUNT(*) FROM applications').fetchone()[0])
    for r in cur.execute("SELECT status, COUNT(*) FROM applications GROUP BY status").fetchall():
        print('  ', r[0], r[1])
    print('--- applications with source_board social ---')
    rows = cur.execute("SELECT id, posting_url, source_board, status FROM applications WHERE source_board LIKE '%social%' OR source_board LIKE '%reddit%' OR source_board LIKE '%n8n%' OR source_board LIKE '%x.com%' OR source_board LIKE '%twitter%' LIMIT 20").fetchall()
    for r in rows:
        print('  app', r)
except Exception as e:
    print('apps error', e)
conn.close()
