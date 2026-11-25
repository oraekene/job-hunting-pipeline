#!/usr/bin/env python3
"""Fetch job posting content for apps 91-93."""
import urllib.request, ssl, re, json

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def fetch(url):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    })
    try:
        with urllib.request.urlopen(req, timeout=25, context=ctx) as r:
            return r.read().decode('utf-8', errors='replace')
    except Exception as e:
        return f'ERROR: {e}'

urls = {
    'teleperformance_91': 'https://careersus-teleperformance.icims.com/jobs/85572/ai-product-manager%2C-internal-transformations/job',
    'mci_92': 'https://careers-mci2.icims.com/jobs/50183/ai-product-manager/job',
    'chime_93': 'https://boards.greenhouse.io/chime/jobs/8694087002',
}

for name, url in urls.items():
    html = fetch(url)
    print(f'=== {name} ===')
    print(f'Length: {len(html)}')
    if html.startswith('ERROR'):
        print(html[:500])
    else:
        # Extract JSON-LD
        ld_scripts = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE)
        print(f'JSON-LD scripts: {len(ld_scripts)}')
        for i, ld in enumerate(ld_scripts):
            try:
                data = json.loads(ld.strip())
                print(f'  LD[{i}] type: {data.get("@type", "unknown")}')
                for key in ['title', 'description', 'hiringOrganization', 'jobLocation', 'datePosted', 'employmentType', 'qualifications', 'responsibilities', 'skills']:
                    val = data.get(key, '')
                    if val:
                        if isinstance(val, str) and len(val) > 200:
                            print(f'  {key} (first 500): {val[:500]}')
                        else:
                            print(f'  {key}: {val}')
            except Exception as e:
                # Try to print raw and see what's in it
                print(f'  LD[{i}] parse error: {e}')
                print(f'  LD[{i}] raw (first 800): {ld[:800]}')
        # Extract body text
        body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
        if body_match:
            body = body_match.group(1)
            text = re.sub(r'<[^>]+>', ' ', body)
            text = re.sub(r'\s+', ' ', text).strip()
            print(f'Body text length: {len(text)}')
            if len(text) > 200:
                print(f'Body text (first 1000): {text[:1000]}')
        else:
            print(f'No body found. First 500 chars: {html[:500]}')
    print()
