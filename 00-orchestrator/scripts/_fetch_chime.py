#!/usr/bin/env python3
"""Fetch full Chime posting text and save to file for analysis."""
import urllib.request, ssl, re

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

url = 'https://boards.greenhouse.io/chime/jobs/8694087002'
req = urllib.request.Request(url, headers={
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
})
with urllib.request.urlopen(req, timeout=25, context=ctx) as r:
    html = r.read().decode('utf-8', errors='replace')

body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
body = body_match.group(1) if body_match else html
text = re.sub(r'<[^>]+>', '\n', body)
text = re.sub(r'\n\s*\n', '\n', text)
text = re.sub(r'[ \t]+', ' ', text)
# Only keep lines with content
lines = [l.strip() for l in text.split('\n') if l.strip()]
clean = '\n'.join(lines)

with open('00-orchestrator/scripts/_chime_93_raw.txt', 'w', encoding='utf-8') as f:
    f.write(clean)

print(f"Saved {len(clean)} chars to _chime_93_raw.txt")
print(f"First 3000 chars:")
print(clean[:3000])
