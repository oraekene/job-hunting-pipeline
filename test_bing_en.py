#!/usr/bin/env python3
"""Bing search with English locale + r.bing.com redirect parsing."""
import urllib.request, re, os
from urllib.parse import quote, unquote

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}

# Try Bing with English locale
q = 'hiring product manager remote'
url = 'https://www.bing.com/search?q=' + quote(q) + '&count=50&mkt=en-US&setlang=en-US'
req = urllib.request.Request(url, headers=HEADERS)
resp = urllib.request.urlopen(req, timeout=15)
html = resp.read().decode('utf-8', errors='replace')
print(f"HTML: {len(html)} chars")

# Extract r.bing.com redirect URLs
bing_redirects = re.findall(r'href="(https://r\.bing\.com/[^"]+)"', html)
print(f"r.bing.com redirects: {len(bing_redirects)}")

# Follow redirects to get actual URLs
seen = set()
for r in bing_redirects[:10]:
    try:
        req2 = urllib.request.Request(r, headers=HEADERS)
        resp2 = urllib.request.urlopen(req2, timeout=10)
        final = resp2.geturl()
        if final not in seen:
            seen.add(final)
            print(f"  -> {final[:120]}")
    except Exception as e:
        print(f"  ERROR following redirect: {e}")

# Also extract cite tags
cites = re.findall(r'<cite[^>]*>(.*?)</cite>', html, re.DOTALL)
print(f"\nCite tags: {len(cites)}")
for c in cites[:10]:
    clean = re.sub(r'<[^>]+>', '', c).strip()
    print(f"  {clean[:120]}")

# Look for search result titles
titles = re.findall(r'<h2>(.*?)</h2>', html, re.DOTALL)
print(f"\nH2 tags: {len(titles)}")
for t in titles[:10]:
    clean = re.sub(r'<[^>]+>', '', t).strip()
    print(f"  {clean[:80]}")
