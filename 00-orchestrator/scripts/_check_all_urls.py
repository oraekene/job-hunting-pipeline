#!/usr/bin/env python3
"""Check URL accessibility for discovered apps."""
import urllib.request, ssl, sqlite3, json

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

con = sqlite3.connect('shared/applications.db')
con.row_factory = sqlite3.Row
rows = con.execute(
    "SELECT id, company, role_title, posting_url, remote_type, salary_range "
    "FROM applications WHERE status='discovered' ORDER BY id"
).fetchall()

for r in rows:
    url = r['posting_url']
    if not url:
        print(f"  app {r['id']}: {r['company']} | {r['role_title'][:40]} | NO URL")
        continue
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            length = len(resp.read())
            print(f"  app {r['id']}: {r['company']} | {r['role_title'][:40]} | HTTP {resp.status} | {length} bytes")
    except urllib.error.HTTPError as e:
        print(f"  app {r['id']}: {r['company']} | {r['role_title'][:40]} | HTTP {e.code} {e.reason}")
    except Exception as e:
        print(f"  app {r['id']}: {r['company']} | {r['role_title'][:40]} | ERROR: {e}")
con.close()
