#!/usr/bin/env python3
"""Debug HN Algolia API - try various URL formats."""
import urllib.request, json

# Try different URL formats
urls = [
    'https://hn.algolia.com/api/v1/search?query=hello&hitsPerPage=1',
    'https://hn.algolia.com/api/v1/search?query=product%20manager&hitsPerPage=5',
    'https://hn.algolia.com/api/v1/search?query=product+manager&hitsPerPage=5',
    'https://hn.algolia.com/api/v1/search?query=hello&hitsPerPage=1&page=0',
    'https://hn.algolia.com/api/v1/search?query=jobs+hiring&hitsPerPage=10',
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json',
}

for url in urls:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode())
        hits = data.get('hits', [])
        print(f"OK: {url}")
        print(f"  Hits: {len(hits)}, Page: {data.get('page')}, NbPages: {data.get('nbPages')}")
        for h in hits[:2]:
            print(f"  - {h.get('title','')[:60]} | {h.get('url','')[:60]}")
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {url}")
        body = e.read().decode('utf-8', errors='replace')[:300]
        print(f"  Body: {body}")
    except Exception as e:
        print(f"FAIL: {url} -> {e}")

# Also try with curl via subprocess
print("\n--- curl test ---")
import subprocess
result = subprocess.run(['curl', '-s', '-L', '-w', '\\nHTTP_CODE:%{http_code}\\n',
    '-H', 'User-Agent: Mozilla/5.0',
    'https://hn.algolia.com/api/v1/search?query=hello&hitsPerPage=1'],
    capture_output=True, text=True, timeout=10)
print(f"curl stdout (last 500 chars): ...{result.stdout[-500:]}")
print(f"curl stderr: {result.stderr[:200]}")
