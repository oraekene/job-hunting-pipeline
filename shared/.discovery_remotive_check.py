#!/usr/bin/env python
"""Phase 4: Extract Remotive job listings from main page (293KB content)."""

import requests, json, re, datetime
from bs4 import BeautifulSoup

SKILL_ROOT = "C:/Users/rotim/AppData/Local/hermes/skills/job-hunting"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

# Fetch Remotive main page
r = requests.get('https://remotive.com/remote-jobs', headers=HEADERS, timeout=15)
print(f"Status: {r.status_code}, Length: {len(r.text)}")

soup = BeautifulSoup(r.text, 'html.parser')

# Check for JSON-LD
scripts = soup.find_all('script', type='application/ld+json')
print(f"\nJSON-LD scripts found: {len(scripts)}")
for i, script in enumerate(scripts[:5]):
    try:
        data = json.loads(script.string)
        if isinstance(data, dict):
            print(f"  Script {i}: @type={data.get('@type', '?')}, keys={list(data.keys())[:5]}")
        elif isinstance(data, list):
            print(f"  Script {i}: array of {len(data)} items")
            if data and isinstance(data[0], dict):
                print(f"    First item keys: {list(data[0].keys())[:5]}")
    except:
        print(f"  Script {i}: parse error")

# Check for Next.js data
nextjs = soup.find('script', id='__NEXT_DATA__')
if nextjs:
    print(f"\n__NEXT_DATA__ found (length: {len(nextjs.string or '')})")
    try:
        data = json.loads(nextjs.string)
        print(f"Next.js data keys: {list(data.keys())[:10]}")
        if 'props' in data:
            props = data['props']
            print(f"Props keys: {list(props.keys())[:10]}")
            if 'pageProps' in props:
                pp = props['pageProps']
                print(f"pageProps keys: {list(pp.keys())[:10]}")
    except Exception as e:
        print(f"Next.js parse error: {e}")
else:
    print("\nNo __NEXT_DATA__ found")
    
    # Try to find job listings via class names
    classes = set()
    for elem in soup.find_all(class_=True):
        for c in elem.get('class', []):
            classes.add(c)
    job_classes = [c for c in classes if 'job' in c.lower() or 'posting' in c.lower() or 'listing' in c.lower() or 'remote' in c.lower()]
    print(f"\nClasses with 'job'/'listing'/'remote': {job_classes[:20]}")

    # Try data attributes
    job_elems = soup.find_all(attrs={'data-testid': True})
    testids = set(e.get('data-testid') for e in job_elems)
    print(f"data-testid values: {testids}")

    # Try to find all links with 'remotive.com' and 'job'
    job_links = soup.find_all('a', href=re.compile(r'/remote-jobs/.*', re.I))
    pm_links = [a for a in job_links if any(kw in a.get_text(strip=True).lower() for kw in 
        ['product manager', 'ai product', 'technical product', 'ai engineer', 'automation engineer', 'workflow engineer', 
         'product owner', 'growth product', 'junior product', 'associate product'])]
    print(f"\nJob links found: {len(job_links)}")
    print(f"PM-related job links: {len(pm_links)}")
    for a in pm_links[:10]:
        print(f"  {a.get_text(strip=True)[:80]} -> {a.get('href', '')}")

# Also try to find jobs via structured data (JSON embedded in any script)
all_scripts = soup.find_all('script')
for s in all_scripts:
    content = s.string or s.get('src', '')
    if content and isinstance(content, str):
        if 'Product Manager' in content or 'product-manager' in content:
            print(f"\nScript mentioning Product Manager (length: {len(content)}):")
            print(f"  First 200 chars: {content[:200]}")

# Try to find inline JSON with job data
for s in all_scripts:
    if s.string:
        text = s.string
        # Look for JSON arrays with job objects
        matches = re.findall(r'"title"\s*:\s*"(.*?Product Manager.*?)"', text, re.I)
        if matches:
            print(f"\nFound Product Manager title in script: {matches[:3]}")
