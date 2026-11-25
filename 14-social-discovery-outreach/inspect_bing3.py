#!/usr/bin/env python3
"""Deep inspect Bing result HTML around b_algo markers."""
import urllib.request, urllib.parse, re, html

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 (Hermes-JobHunt/1.0)"

query = 'site:reddit.com "hiring" "product manager" remote 2026'
url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}&count=15"
req = urllib.request.Request(url, headers={
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
})
resp = urllib.request.urlopen(req, timeout=15)
content = resp.read().decode('utf-8', errors='replace')

# Find all occurrences of b_algo and show surrounding HTML
positions = [m.start() for m in re.finditer(r'b_algo', content)]
print(f"Found {len(positions)} 'b_algo' occurrences")
for pos in positions[:3]:
    start = max(0, pos - 10)
    end = min(len(content), pos + 300)
    snippet = content[start:end]
    print(f"\n--- At position {pos} ---")
    print(repr(snippet))
    print()

# Also check: maybe Bing uses <div class="b_algo"> now instead of <li>
div_matches = re.findall(r'<div[^>]*class="b_algo"[^>]*>(.*?)</div>', content, re.DOTALL)
print(f"div.b_algo blocks: {len(div_matches)}")

# Check for <li> with b_algo
li_matches = re.findall(r'<li[^>]*class="b_algo"[^>]*>(.*?)</li>', content, re.DOTALL)
print(f"li.b_algo blocks: {len(li_matches)}")

# Try a broader approach: find all <h2> tags (Bing usually wraps result titles in <h2>)
h2_tags = re.findall(r'<h2>(.*?)</h2>', content, re.DOTALL)
print(f"\nh2 tags found: {len(h2_tags)}")
for h in h2_tags[:5]:
    clean = html.unescape(re.sub(r'<[^>]+>', '', h)).strip()
    print(f"  {clean[:100]}")
