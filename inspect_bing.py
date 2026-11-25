#!/usr/bin/env python3
"""Inspect Bing search result link structure."""
import urllib.request, re
from urllib.parse import quote, unquote

q = 'product manager remote site:boards.greenhouse.io'
url = 'https://www.bing.com/search?q=' + quote(q) + '&count=50'
req = urllib.request.Request(url, headers={
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
})
resp = urllib.request.urlopen(req, timeout=15)
html = resp.read().decode('utf-8', errors='replace')

# Show what kinds of links exist
all_links = re.findall(r'href="(https?://[^"]+)"', html)
from collections import Counter
domains = Counter()
for l in all_links:
    domain = l.split('/')[2] if len(l.split('/')) > 2 else 'unknown'
    domains[domain] += 1
print("Link domains:")
for d, c in domains.most_common(20):
    print(f"  {d}: {c}")

# Look for Bing redirect URLs (bing.com/ck/a?...u=...)
bing_redirects = re.findall(r'href="(https://www\.bing\.com/ck/a\?[^"]+)"', html)
print(f"\nBing redirect links: {len(bing_redirects)}")
for r in bing_redirects[:5]:
    print(f"  {r[:200]}")

# Look for cite tags
cites = re.findall(r'<cite[^>]*>(.*?)</cite>', html, re.DOTALL)
print(f"\nCite tags: {len(cites)}")
for c in cites[:10]:
    print(f"  {re.sub(r'<[^>]+>', '', c).strip()[:100]}")

# Look for data-urls or other attributes
data_urls = re.findall(r'data-url="([^"]+)"', html)
print(f"\nData-url attrs: {len(data_urls)}")
for d in data_urls[:5]:
    print(f"  {d[:120]}")

# Try to find search result snippets with surrounding context
result_blocks = re.findall(r'<h2><a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL)
print(f"\nH2 result links: {len(result_blocks)}")
for url_val, text in result_blocks[:10]:
    clean_text = re.sub(r'<[^>]+>', '', text).strip()
    print(f"  {clean_text[:60]} -> {url[:80]}")
