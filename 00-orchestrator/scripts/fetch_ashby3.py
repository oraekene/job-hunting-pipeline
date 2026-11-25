#!/usr/bin/env python
"""Extract structured job data from Ashby pages."""
import json, re, sys, urllib.request, ssl

def fetch(url, timeout=25):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    req = urllib.request.Request(url, headers=headers)
    resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
    return resp.status, resp.read().decode('utf-8', errors='replace')

url = sys.argv[1]
status, html = fetch(url)

# Extract JSON-LD JobPosting
ld_match = re.search(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.DOTALL)
if ld_match:
    ld_raw = ld_match.group(1).strip()
    if ld_raw.endswith(';'):
        ld_raw = ld_raw[:-1]
    try:
        ld = json.loads(ld_raw)
        print(json.dumps(ld, indent=2))
    except json.JSONDecodeError as e:
        print(f"JSON-LD parse error: {e}")

# Extract window.__appData
app_match = re.search(r'window\.__appData\s*=\s*(\{.*?\});', html, re.DOTALL)
if app_match:
    app_raw = app_match.group(1).strip()
    try:
        app_data = json.loads(app_raw)
        posting = app_data.get('posting', {})
        print("\n\n=== __appData.posting ===")
        print(json.dumps(posting, indent=2))
    except json.JSONDecodeError as e:
        print(f"\n\n=== __appData parse error: {e} ===")
        print(app_raw[:10000])
