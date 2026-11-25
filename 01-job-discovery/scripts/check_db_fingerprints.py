#!/usr/bin/env python3
"""Check existing DB state for dedup comparison."""
import sqlite3
conn = sqlite3.connect('shared/applications.db')
c = conn.cursor()
c.execute('PRAGMA table_info(applications)')
print('applications columns:')
for col in c.fetchall():
    print(f'  {col[1]} ({col[2]})')
c.execute('PRAGMA table_info(posting_sources)')
print('posting_sources columns:')
for col in c.fetchall():
    print(f'  {col[1]} ({col[2]})')
print()
c.execute('SELECT company, role_title, posting_url, status, posting_fingerprint FROM applications ORDER BY status, discovered_at DESC')
print('=== All applications ===')
for r in c.fetchall():
    fp = r[4] if r[4] else 'NULL'
    print(f'  {str(r[3]):20s} | {str(r[0])[:25]:25s} | {str(r[1])[:45]:45s} | {r[2][:60]}')
    print(f'  {"":26s} fp={fp}')
print()
c.execute('SELECT posting_url, source_name FROM posting_sources')
print('=== Posting sources ===')
for r in c.fetchall():
    print(f'  {str(r[1]):20s} | {r[0][:80]}')
conn.close()
