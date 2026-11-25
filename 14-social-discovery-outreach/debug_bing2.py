#!/usr/bin/env python3
"""Debug: examine Bing HTML structure to find result links."""
import urllib.request, urllib.parse, re

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 (Hermes-JobHunt/1.0)"

q = '"hiring" "product manager" remote "DM me" site:reddit.com'
url = f"https://www.bing.com/search?q={urllib.parse.quote(q)}&count=10"
req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html", "Accept-Language": "en-US,en;q=0.9"})
resp = urllib.request.urlopen(req, timeout=20)
html = resp.read().decode('utf-8', errors='replace')

# Find all cite tags with their surrounding context
cites = re.findall(r'<cite[^>]*>(.*?)</cite>', html, re.DOTALL)
print(f"Cite tags found: {len(cites)}")
for c in cites[:10]:
    clean = re.sub(r'<[^>]+>', '', c).strip()
    clean = re.sub(r'\s+', ' ', clean)
    print(f"  cite: {clean[:150]}")

# Look for href attributes that point to external sites (not bing)
all_hrefs = re.findall(r'href="(https?://[^"]+)"', html)
external = [h for h in all_hrefs if 'bing.com' not in h and 'microsoft.com' not in h and 'go.microsoft' not in h]
print(f"\nExternal hrefs found: {len(external)}")
for h in external[:10]:
    print(f"  {h[:150]}")

# Try to find the results in the HTML - look for common patterns
# Bing may use <li class="b_algo"> or <div class="b_algo"> or different structure
patterns_to_try = [
    r'class="b_algo"',
    r'class="b_algo"',
    r'<li[^>]*class="[^"]*algo[^"]*"',
    r'data-testid="result"',
    r'class="b_attribution"',
    r'<a[^>]*href="https?://(?!www\.bing)',
]
for pat in patterns_to_try:
    matches = re.findall(pat, html)
    print(f"\nPattern '{pat}': {len(matches)} matches")

# Let's look at the cite context - what's around them
cite_contexts = re.findall(r'.{0,200}<cite[^>]*>.*?</cite>.{0,200}', html, re.DOTALL)
for ctx in cite_contexts[:3]:
    clean = re.sub(r'<[^>]+>', ' ', ctx)
    clean = re.sub(r'\s+', ' ', clean).strip()
    print(f"\nCite context: {clean[:300]}")
