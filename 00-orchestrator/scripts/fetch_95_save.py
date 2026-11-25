#!/usr/bin/env python3
"""Fetch LawnStarter (Wellfound) app 95 and save raw HTML."""
import urllib.request, ssl, re, json, os

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
    outpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_ls_95_raw.txt')
    with open(outpath, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'Saved {len(html)} chars to {outpath}')
    # Extract and print JSON-LD
    ld_scripts = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE)
    for i, ld in enumerate(ld_scripts):
        try:
            data = json.loads(ld.strip())
            if data.get('@type') == 'JobPosting':
                desc = data.get('description', '')
                # Strip HTML tags
                desc_text = re.sub(r'<[^>]+>', ' ', desc)
                desc_text = re.sub(r'\s+', ' ', desc_text).strip()
                print(f'\n=== FULL DESCRIPTION (JSON-LD) ===')
                print(desc_text)
                print(f'\n=== LENGTH: {len(desc_text)} ===')
        except Exception as e:
            print(f'LD parse error: {e}')
except Exception as e:
    print(f'ERROR: {type(e).__name__}: {e}')
