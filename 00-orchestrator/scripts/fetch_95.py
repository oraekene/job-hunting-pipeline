#!/usr/bin/env python3
"""Fetch LawnStarter (Wellfound) job posting for app 95."""
import urllib.request, ssl, re, json

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

url = 'https://wellfound.com/jobs/4677997-principal-product-manager'
req = urllib.request.Request(url, headers=HEADERS)
try:
    with urllib.request.urlopen(req, timeout=25, context=ctx) as r:
        html = r.read().decode('utf-8', errors='replace')
    print(f'App 95: Length: {len(html)}')
    # Extract JSON-LD
    ld_scripts = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE)
    print(f'JSON-LD scripts: {len(ld_scripts)}')
    for i, ld in enumerate(ld_scripts):
        try:
            data = json.loads(ld.strip())
            ld_type = data.get('@type', 'unknown')
            print(f'  LD[{i}] type: {ld_type}')
            for key in ['title', 'description', 'hiringOrganization', 'jobLocation', 'datePosted', 'baseSalary']:
                val = data.get(key, '')
                if val:
                    print(f'  {key}: {str(val)[:500]}')
        except Exception as e:
            print(f'  LD[{i}] parse error: {e}')
    # Extract body text
    body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
    if body_match:
        body = body_match.group(1)
        text = re.sub(r'<[^>]+>', ' ', body)
        text = re.sub(r'\s+', ' ', text).strip()
        print(f'Body text length: {len(text)}')
        if len(text) > 200:
            print(f'Body text (first 2500):')
            print(text[:2500])
    else:
        print(f'No body found. First 500: {html[:500]}')
except Exception as e:
    print(f'ERROR: {type(e).__name__}: {e}')
