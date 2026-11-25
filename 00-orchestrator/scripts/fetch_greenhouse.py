#!/usr/bin/env python
"""Fetch Greenhouse job posting."""
import json, re, sys, urllib.request, ssl

url = sys.argv[1]
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

req = urllib.request.Request(url, headers=headers)
resp = urllib.request.urlopen(req, timeout=25, context=ctx)
html = resp.read().decode('utf-8', errors='replace')

print(f"HTML length: {len(html)}")

# Greenhouse uses a JSON blob in a script tag
# Look for various patterns
patterns = [
    (r'window\.ghOpportunities\s*=\s*(\{.*?\});', 'ghOpportunities'),
    (r'window\.Greenhouse\.[^=]*=\s*(\{.*?\});', 'greenhouse'),
    (r'job_posting\s*=\s*(\{.*?\});', 'job_posting'),
]

# Also look for JSON-LD
ld_match = re.search(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.DOTALL)
if ld_match:
    ld_raw = ld_match.group(1).strip()
    if ld_raw.endswith(';'):
        ld_raw = ld_raw[:-1]
    try:
        ld = json.loads(ld_raw)
        print("\n=== JSON-LD ===")
        print(json.dumps(ld, indent=2)[:8000])
    except json.JSONDecodeError as e:
        print(f"JSON-LD parse error: {e}")

# Find all large script tags
scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
for i, s in enumerate(scripts):
    s_stripped = s.strip()
    if len(s_stripped) > 200:
        # Check if it looks like JSON with job data
        if 'job' in s_stripped.lower() or 'opportunity' in s_stripped.lower() or 'title' in s_stripped.lower():
            print(f"\n--- Script {i} (len={len(s_stripped)}) ---")
            print(s_stripped[:5000])

# Extract readable text
html_clean = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.DOTALL)
text = re.sub(r'<[^>]+>', '\n', html_clean)
text = re.sub(r'\n\s*\n', '\n', text)
text = re.sub(r'&amp;', '&', text)
text = re.sub(r'&lt;', '<', text)
text = re.sub(r'&gt;', '>', text)
text = re.sub(r'&quot;', '"', text)
text = re.sub(r'&#39;', "'", text)
lines = [l.strip() for l in text.split('\n') if l.strip() and len(l.strip()) > 1]
print(f"\n=== TEXT (first 8000 chars) ===")
print('\n'.join(lines[:200]))
