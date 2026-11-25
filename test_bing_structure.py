#!/usr/bin/env python3
"""Examine Bing HTML structure and try alternative search."""
import urllib.request, re
from urllib.parse import quote

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}

# 1. Examine Bing HTML structure
print("=" * 60)
print("1. BING HTML STRUCTURE EXAMINATION")
print("=" * 60)

q = 'product manager remote hiring'
url = 'https://www.bing.com/search?q=' + quote(q) + '&count=50&mkt=en-US&setlang=en-US'
req = urllib.request.Request(url, headers=HEADERS)
resp = urllib.request.urlopen(req, timeout=15)
html = resp.read().decode('utf-8', errors='replace')
print(f"HTML: {len(html)} chars")

# Check for consent/cookie page
if 'consent' in html.lower() or 'cookie' in html.lower():
    print("Contains consent/cookie page")
if 'js(' in html.lower() or 'javascript' in html.lower():
    print("Contains JavaScript references")

# Look for ANY URLs in the HTML
all_hrefs = re.findall(r'href="(https?://[^"]+)"', html)
job_related = [h for h in all_hrefs if any(k in h.lower() for k in ['greenhouse', 'lever', 'ashby', 'icims', 'smartrecruiters', 'job', 'careers', 'hiring'])]
print(f"\nAll hrefs: {len(all_hrefs)}")
print(f"Job-related hrefs: {len(job_related)}")
for h in job_related[:15]:
    print(f"  -> {h[:120]}")

# Look for URLs in JavaScript
js_urls = re.findall(r'"(https?://[^"]*(?:greenhouse|lever|ashby|icims|smartrecruiters|job|career)[^"]*)"', html)
print(f"\nJS URLs (job-related): {len(js_urls)}")
for u in js_urls[:10]:
    print(f"  -> {u[:120]}")

# Print first 2000 chars to see structure
print("\n--- First 3000 chars of HTML ---")
print(html[:3000])

# 2. Try Google search
print("\n" + "=" * 60)
print("2. GOOGLE SEARCH")
print("=" * 60)
try:
    q2 = quote('"product manager" remote hiring')
    url2 = f'https://www.google.com/search?q={q2}&num=20'
    req2 = urllib.request.Request(url2, headers=HEADERS)
    resp2 = urllib.request.urlopen(req2, timeout=15)
    html2 = resp2.read().decode('utf-8', errors='replace')
    print(f"Google HTML: {len(html2)} chars")
    # Extract result URLs
    result_urls = re.findall(r'href="(https?://[^"]+)"', html2)
    job_urls = [u for u in result_urls if not any(x in u for x in ['google.com', 'gstatic.com', 'youtube.com'])]
    print(f"Job-related URLs: {len(job_urls)}")
    for u in job_urls[:10]:
        print(f"  -> {u[:120]}")
    # Print structure
    print(f"\n--- First 2000 chars ---")
    print(html2[:2000])
except Exception as e:
    print(f"Google ERROR: {e}")

# 3. Try alternative search engines
print("\n" + "=" * 60)
print("3. ALTERNATIVE SEARCH ENGINES")
print("=" * 60)

for engine_name, engine_url in [
    ('SearXNG', 'https://search.bus-hit.me/search?q=product+manager+remote+jobs&format=json'),
    ('SearXNG2', 'https://searx.tiekoetter.at/search?q=product+manager+remote+jobs&format=json'),
]:
    try:
        req3 = urllib.request.Request(engine_url, headers=HEADERS)
        resp3 = urllib.request.urlopen(req3, timeout=10)
        data = resp3.read().decode('utf-8', errors='replace')
        print(f"{engine_name}: HTTP {resp3.status}, {len(data)} chars")
        print(data[:200])
    except Exception as e:
        print(f"{engine_name}: ERROR: {e}")
