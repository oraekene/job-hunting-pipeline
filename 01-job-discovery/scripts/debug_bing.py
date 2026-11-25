#!/usr/bin/env python3
"""Debug Bing search result HTML structure."""
import re, json
from urllib.parse import quote
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

url = "https://www.bing.com/search?q=" + quote("Product Manager remote jobs hiring") + "&count=10"
req = urllib.request.Request(url, headers={"User-Agent": UA})
resp = urllib.request.urlopen(req, timeout=20)
html = resp.read().decode("utf-8", errors="replace")

# Save raw HTML for inspection
with open("01-job-discovery/scripts/bing_debug.html", "w", encoding="utf-8") as f:
    f.write(html)

print(f"HTML length: {len(html)}")

# Look for b_algo
b_algo_count = len(re.findall(r'class="b_algo"', html))
print(f"b_algo blocks: {b_algo_count}")

# Look for all <a href="https://..."> patterns
all_links = re.findall(r'<a[^>]+href="(https?://[^"]+)"', html)
print(f"\nAll external links ({len(all_links)} total):")
for link in all_links:
    if "bing.com" not in link and "microsoft.com" not in link and "msn.com" not in link:
        print(f"  {link[:120]}")

# Try to find h2 tags (Bing uses h2 for result titles)
h2_blocks = re.findall(r'<h2[^>]*>(.*?)</h2>', html, re.DOTALL)
print(f"\nh2 blocks: {len(h2_blocks)}")
for h in h2_blocks[:10]:
    text = re.sub(r'<[^>]+>', '', h).strip()
    print(f"  {text[:100]}")

# Look for cite tags (shows the URL below the title in Bing)
cite_tags = re.findall(r'<cite[^>]*>(.*?)</cite>', html, re.DOTALL)
print(f"\ncite tags: {len(cite_tags)}")
for c in cite_tags[:10]:
    text = re.sub(r'<[^>]+>', '', c).strip()
    print(f"  {text[:120]}")

# Dump a section around the first h2
h2_idx = html.find("<h2")
if h2_idx >= 0:
    print(f"\n=== Context around first <h2> (at index {h2_idx}) ===")
    print(html[h2_idx:h2_idx+1000])
