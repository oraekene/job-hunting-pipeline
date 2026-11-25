#!/usr/bin/env python3
"""Inspect Bing HTML structure to understand why b_algo parsing fails."""
import urllib.request, urllib.parse, re, html

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 (Hermes-JobHunt/1.0)"

q = 'site:reddit.com "hiring" "product manager" remote 2026'
url = f"https://www.bing.com/search?q={urllib.parse.quote(q)}&count=20"
req = urllib.request.Request(url, headers={
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
})
resp = urllib.request.urlopen(req, timeout=15)
content = resp.read().decode('utf-8', errors='replace')
print(f"Status: {resp.status}, Length: {len(content)}")

# Look for any result container patterns
patterns_to_try = [
    r'class="b_algo"',
    r'class="b_algo ',
    r'id="b_results"',
    r'class="b_algo"',
    r'"algolog"|"b_result"',
    r'<li[^>]*class="[^"]*b_algo',
    r'class="b_algo"[^>]*>',
]
for pat in patterns_to_try:
    matches = re.findall(pat, content)
    if matches:
        print(f"  Pattern '{pat}': {len(matches)} matches")

# Find ALL href links on the page
all_hrefs = re.findall(r'href="(https?://[^"]+)"', content)
# Filter out bing/microsoft links
external = [h for h in all_hrefs if not any(d in h for d in
    ['bing.com', 'microsoft.com', 'msn.com', 'microsoftedge', 'go.microsoft',
     'r.bing.com', 'th.bing.com', 'bing.cn', 'w3.org'])]
print(f"\nExternal href links: {len(external)}")
for h in external[:20]:
    print(f"  {html.unescape(h)[:120]}")

# Extract reddit/x/n8n links specifically
social = [h for h in all_hrefs if any(d in h for d in
    ['reddit.com', 'x.com', 'twitter.com', 'community.n8n.io'])]
print(f"\nSocial platform links: {len(social)}")
for s in social[:10]:
    print(f"  {html.unescape(s)[:120]}")

# Check for bot detection
first_500 = content[:500].lower()
if any(w in first_500 for w in ['captcha', 'are you', 'robot', 'block', 'suspicious']):
    print("\n*** POSSIBLE BOT DETECTION ***")
    print(content[:500])
else:
    # Look for search result markers
    if 'b_results' in content:
        print("\nb_results container found")
    else:
        print("\nNo b_results container found")
    print("First 300 chars:", content[:300])
