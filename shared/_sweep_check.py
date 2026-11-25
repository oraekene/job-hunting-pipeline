import sqlite3, os, json

con = sqlite3.connect('shared/applications.db')
con.row_factory = sqlite3.Row

print('=== STATUS COUNTS ===')
for r in con.execute('SELECT status, COUNT(*) as n FROM applications GROUP BY status'):
    print(f"  {r['status']}: {r['n']}")

print()
print('=== DISCOVERED APPS ===')
rows = con.execute(
    'SELECT id, company, role_title, source_board, posting_url, '
    'salary_range, remote_type, build_attempts, discovered_at '
    'FROM applications WHERE status="discovered" ORDER BY id'
).fetchall()
for r in rows:
    print(f"  app {r['id']}: {r['company']} | {r['role_title']} | {r['source_board']} | "
          f"attempts={r['build_attempts']} | {r['discovered_at']}")
    print(f"    url: {r['posting_url']}")
    print(f"    salary: {r['salary_range']} | remote: {r['remote_type']}")

print()
print('=== STAGED (awaiting approval) ===')
rows = con.execute(
    'SELECT id, company, role_title, staged_at, approval_sent_at '
    'FROM applications WHERE status="staged" ORDER BY id'
).fetchall()
for r in rows:
    print(f"  app {r['id']}: {r['company']} | {r['role_title']} | "
          f"staged={r['staged_at']} | approval_pinged={r['approval_sent_at']}")
if not rows:
    print('  (none)')

print()
print('=== BUILDING ROWS ===')
rows = con.execute(
    'SELECT id, company, role_title, building_started_at, build_attempts '
    'FROM applications WHERE status="building"'
).fetchall()
for r in rows:
    print(f"  app {r['id']}: {r['company']} | {r['role_title']} | "
          f"started={r['building_started_at']} | attempts={r['build_attempts']}")
if not rows:
    print('  (none)')

print()
print('=== OUTBOX ===')
ob = 'shared/.outbox'
if os.path.isdir(ob):
    files = [f for f in sorted(os.listdir(ob)) if f.endswith('.json')]
    for f in files:
        print(f'  {f}')
    if not files:
        print('  (empty)')
else:
    print('  (no .outbox dir)')

con.close()
