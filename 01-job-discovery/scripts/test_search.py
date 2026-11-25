#!/usr/bin/env python3
"""Test search backends for the open-web sweep."""
import requests, re, urllib.parse
from bs4 import BeautifulSoup
from pathlib import Path

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/**;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}
BING = 'https://www.bing.com/search'

def bing_search(query, count=10):
    r = requests.get(BING, params={'q': query, 'count': count}, headers=HEADERS, timeout=20)
    if r.status_code != 200:
        return [], r.status_code
    soup = BeautifulSoup(r.text, 'lxml')
    results = soup.select('li.b_algo h2 a')
    out = []
    for a in results:
        href = a.get('href', '')
        title = a.get_text(strip=True)
        m = re.search(r'uddg=([^&]+)', href)
        real = urllib.parse.unquote(m.group(1)) if m else href
        out.append((title, real))
    return out, r.status_code

# Test 1: Lever platform dork
print("=== Test 1: Lever platform dork ===")
res, st = bing_search('site:jobs.lever.co "product manager" remote hiring')
print(f"HTTP {st}, results: {len(res)}")
for t, u in res[:5]:
    print(f"  {t[:65]} | {u[:100]}")

# Test 2: Ashby platform dork
print("\n=== Test 2: Ashby platform dork ===")
res, st = bing_search('site:jobs.ashbyhq.com "product manager" remote')
print(f"HTTP {st}, results: {len(res)}")
for t, u in res[:5]:
    print(f"  {t[:65]} | {u[:100]}")

# Test 3: Greenhouse platform dork
print("\n=== Test 3: Greenhouse platform dork ===")
res, st = bing_search('site:greenhouse.io "product manager" remote')
print(f"HTTP {st}, results: {len(res)}")
for t, u in res[:5]:
    print(f"  {t[:65]} | {u[:100]}")

# Test 4: Generic query
print("\n=== Test 4: Generic search ===")
res, st = bing_search('"product manager" remote job hiring')
print(f"HTTP {st}, results: {len(res)}")
for t, u in res[:5]:
    print(f"  {t[:65]} | {u[:100]}")

# Test 5: Direct Lever page access
print("\n=== Test 5: Direct Lever jobs page ===")
r = requests.get('https://jobs.lever.co/', headers=HEADERS, timeout=15)
print(f"HTTP {r.status_code}, size={len(r.text)}")

# Test 6: Direct Ashby page access
print("\n=== Test 6: Direct Ashby jobs page ===")
r = requests.get('https://jobs.ashbyhq.com/', headers=HEADERS, timeout=15)
print(f"HTTP {r.status_code}, size={len(r.text)}")

# Test 7: Remotive API
print("\n=== Test 7: Remotive API ===")
r = requests.get('https://remotive.com/api/remote-jobs?category=product-management', headers=HEADERS, timeout=15)
print(f"HTTP {r.status_code}, size={len(r.text)}")
if r.status_code == 200:
    import json
    data = json.loads(r.text)
    jobs = data.get('jobs', [])
    print(f"Jobs in product-management: {len(jobs)}")
    for j in jobs[:3]:
        print(f"  {j.get('company_name','?')}: {j.get('title','?')[:50]} | url={j.get('url','?')[:80]}")
