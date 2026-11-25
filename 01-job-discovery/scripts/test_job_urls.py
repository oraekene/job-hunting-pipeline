#!/usr/bin/env python3
"""Test accessibility of job posting URLs found in HN thread + extract structured data."""
import requests, re, json
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
           'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}

# URLs from HN thread results (cleaned apply URLs)
test_urls = [
    ('Wikimedia Greenhouse', 'https://job-boards.greenhouse.io/wikimedia/jobs/8140060'),
    ('Axmed Teamtailor', 'https://axmed.teamtailor.com/jobs/8175859-ai-engineer'),
    ('Snowflake Workday', 'https://careers.snowflake.com/us/en/job/SNCOUSA253CD7A2'),
    ('SearchAtlas', 'https://careers.searchatlas.com/jobs/599248-product-eng'),
    ('ODK', 'https://getodk.org/about/jobs/senior-product-manager'),
    ('Pomelo Care Greenhouse', 'https://grnh.se/k4xos2c24us'),
    ('Baton Greenhouse', 'https://grnh.se/t1doekv97us'),
    ('Starbridge', 'https://starbridge.ai/'),
    ('Checkly', 'https://www.checklyhq.com'),
]

print("=== Testing job posting URL accessibility ===")
for label, url in test_urls:
    try:
        r = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        size = len(r.text)
        # Check for JSON-LD JobPosting
        has_jsonld = '"@type":"JobPosting"' in r.text or '"@type": "JobPosting"' in r.text or 'JobPosting' in r.text[:5000]
        # Check for anti-bot
        anti_bot = any(w in r.text.lower()[:2000] for w in ['captcha', 'cloudflare', 'checking your browser', 'access denied'])
        # Check for Greenhouse embed
        is_greenhouse = 'greenhouse' in r.text.lower()[:2000]
        print(f"  [{label}] HTTP {r.status_code} size={size} jsonld={has_jsonld} anti_bot={anti_bot} greenhouse={is_greenhouse} final_url={r.url[:80]}")
        
        # Try to extract JSON-LD
        if has_jsonld:
            for m in re.finditer(r'<script[^>]*type=["\']?application/ld\+json["\']?[^>]*>(.*?)</script>', r.text, re.DOTALL):
                try:
                    data = json.loads(m.group(1).strip())
                    if isinstance(data, dict) and data.get('@type') in ('JobPosting', ['JobPosting', 'Article'], 'Product'):
                        print(f"    JSON-LD: {json.dumps({k: data.get(k, '') for k in ['@type','title','datePosted','description'] if k in data}, indent=2)[:300]}")
                except:
                    pass
    except Exception as e:
        print(f"  [{label}] ERROR: {str(e)[:80]}")
