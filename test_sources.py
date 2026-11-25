#!/usr/bin/env python3
"""Test fetching other job boards via urllib."""
import urllib.request, json, re, html as html_mod

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}

# Test WorkingNomads
print("=== WorkingNomads ===")
try:
    req = urllib.request.Request('https://workingnomads.com/jobs?category=product-management', headers=HEADERS)
    resp = urllib.request.urlopen(req, timeout=15)
    html = resp.read().decode('utf-8', errors='replace')
    print(f"HTTP {resp.status}, {len(html)} chars")
    if 'captcha' in html.lower() or 'challenge' in html.lower():
        print("BLOCKED: anti-bot")
    else:
        links = re.findall(r'href="(/jobs/[0-9a-f-]+)"', html)
        print(f"Job links: {len(links)}")
        for l in links[:5]:
            print(f"  -> {l}")
except Exception as e:
    print(f"ERROR: {e}")

# Test WeWorkRemotely
print("\n=== WeWorkRemotely ===")
try:
    req = urllib.request.Request('https://weworkremotely.com/categories/remote-product-manager-jobs', headers=HEADERS)
    resp = urllib.request.urlopen(req, timeout=15)
    html = resp.read().decode('utf-8', errors='replace')
    print(f"HTTP {resp.status}, {len(html)} chars")
    if 'captcha' in html.lower() or 'challenge' in html.lower():
        print("BLOCKED: anti-bot")
    else:
        links = re.findall(r'href="(/remote-jobs/[0-9]+)"', html)
        print(f"Job links: {len(links)}")
        for l in links[:5]:
            print(f"  -> {l}")
except Exception as e:
    print(f"ERROR: {e}")

# Test Greenhouse job search (specific company boards)
print("\n=== Greenhouse (direct) ===")
for company in ['chime', 'ezcater', 'check-technologies']:
    try:
        url = f'https://boards.greenhouse.io/{company}/jobs'
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=15)
        html = resp.read().decode('utf-8', errors='replace')
        print(f"  {company}: HTTP {resp.status}, {len(html)} chars")
        if len(html) > 1000 and 'captcha' not in html.lower():
            links = re.findall(r'href="(https?://boards\.greenhouse\.io/\S+)"', html)
            print(f"    Job links: {len(links)}")
    except Exception as e:
        print(f"  {company}: ERROR: {e}")

# Test Lever job search
print("\n=== Lever (direct) ===")
for company_path in ['kpler/c7103421-ccbe-43b4-b23d-752e8c8a3a9c']:
    try:
        url = f'https://jobs.lever.co/{company_path.split("/")[0]}'
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=15)
        html = resp.read().decode('utf-8', errors='replace')
        print(f"  Lever {url}: HTTP {resp.status}, {len(html)} chars")
        if len(html) > 1000 and 'captcha' not in html.lower():
            links = re.findall(r'href="(https?://jobs\.lever\.co/\S+)"', html)
            print(f"    Job links: {len(links)}")
    except Exception as e:
        print(f"  Lever ERROR: {e}")

# Test Bing HTML search for specific companies
print("\n=== Bing HTML search: product manager company pages ===")
from urllib.parse import quote
queries = [
    'site:boards.greenhouse.io "product manager" remote hiring',
]
for q in queries[:1]:
    url = 'https://www.bing.com/search?q=' + quote(q) + '&count=20'
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=15)
        html = resp.read().decode('utf-8', errors='replace')
        print(f"  HTML: {len(html)} chars")
        # Look for job links in the search results
        all_links = re.findall(r'href="(https?://[^"]+)"', html)
        job_links = [l for l in all_links if not any(x in l for x in ['bing.com', 'microsoft.com', 'w3.org'])]
        print(f"  Links: {len(all_links)} total, {len(job_links)} non-bing")
        for l in job_links[:10]:
            print(f"  -> {l[:100]}")
    except Exception as e:
        print(f"  ERROR: {e}")
