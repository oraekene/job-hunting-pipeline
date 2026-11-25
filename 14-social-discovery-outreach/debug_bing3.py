#!/usr/bin/env python3
"""Debug: examine Bing result block structure to extract actual URLs."""
import urllib.request, urllib.parse, re
from datetime import datetime, timezone

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 (Hermes-JobHunt/1.0)"

def fetch(url, accept="text/html"):
    headers = {"User-Agent": UA, "Accept": accept, "Accept-Language": "en-US,en;q=0.9"}
    req = urllib.request.Request(url, headers=headers)
    resp = urllib.request.urlopen(req, timeout=20)
    return resp.read().decode('utf-8', errors='replace')

now = datetime.now(timezone.utc)

# Query 1: Broader query without site: filter
q1 = '"hiring" "product manager" remote "DM me"'
url1 = f"https://www.bing.com/search?q={urllib.parse.quote(q1)}&count=20"
print(f"Query: {q1}")
html1 = fetch(url1)
print(f"Response: {len(html1)} chars")

# Find b_algo blocks
blocks = re.findall(r'<li class="b_algo">(.*?)</li>', html1, re.DOTALL)
print(f"b_algo blocks: {len(blocks)}")

for i, block in enumerate(blocks[:5]):
    # Look for all href attributes
    hrefs = re.findall(r'href="(.*?)"', block)
    # Look for title in h2
    h2 = re.search(r'<h2>(.*?)</h2>', block, re.DOTALL)
    title = re.sub(r'<[^>]+>', '', h2.group(1)).strip() if h2 else "(no h2)"
    title = re.sub(r'&amp;', '&', title)
    
    # Look for cite
    cite = re.search(r'<cite[^>]*>(.*?)</cite>', block, re.DOTALL)
    cite_text = re.sub(r'<[^>]+>', '', cite.group(1)).strip() if cite else ""
    
    # Find the actual destination URL - Bing wraps in ck/a links
    # The real URL might be in a different attribute or need decoding
    actual_urls = [h for h in hrefs if not h.startswith('https://www.bing.com') and 'javascript' not in h]
    
    print(f"\n  Block {i+1}:")
    print(f"  Title: {title[:100]}")
    print(f"  Cite: {cite_text[:100]}")
    print(f"  All hrefs ({len(hrefs)}):")
    for h in hrefs[:5]:
        print(f"    {h[:150]}")
    print(f"  Non-bing URLs: {actual_urls[:3]}")

# Query 2: Broader query about hiring on Reddit
print("\n" + "=" * 70)
q2 = 'reddit hiring product manager remote "need someone"'
url2 = f"https://www.bing.com/search?q={urllib.parse.quote(q2)}&count=20"
print(f"Query: {q2}")
html2 = fetch(url2)
print(f"Response: {len(html2)} chars")
blocks2 = re.findall(r'<li class="b_algo">(.*?)</li>', html2, re.DOTALL)
print(f"b_algo blocks: {len(blocks2)}")
for i, block in enumerate(blocks2[:5]):
    h2 = re.search(r'<h2>(.*?)</h2>', block, re.DOTALL)
    title = re.sub(r'<[^>]+>', '', h2.group(1)).strip() if h2 else "(no h2)"
    title = re.sub(r'&amp;', '&', title)
    hrefs = re.findall(r'href="(.*?)"', block)
    actual = [h for h in hrefs if not h.startswith('https://www.bing.com')]
    print(f"  [{i+1}] {title[:100]} | URLs: {actual[:2]}")

# Query 3: Try Reddit directly via JSON search
print("\n" + "=" * 70)
print("Reddit JSON search:")
rd_url = "https://www.reddit.com/search.json?q=hiring+product+manager+remote&sort=new&limit=10&restrict_sr=0"
try:
    rd_html = fetch(rd_url, accept="application/json")
    import json
    data = json.loads(rd_html)
    posts = data.get("data", {}).get("children", [])
    print(f"  Posts found: {len(posts)}")
    for c in posts[:5]:
        p = c["data"]
        print(f"  [{p.get('subreddit','?')}] {p['title'][:100]}")
        print(f"    https://reddit.com{p['permalink']}")
except Exception as e:
    print(f"  ERROR: {e}")

# Query 4: Try Reddit RSS
print("\n" + "=" * 70)
print("Reddit RSS - r/forhire:")
rss_url = "https://www.reddit.com/r/forhire/.rss"
try:
    rss_xml = fetch(rss_url, accept="application/rss+xml")
    import xml.etree.ElementTree as ET
    root = ET.fromstring(rss_xml)
    items = root.findall('.//item')
    print(f"  RSS items: {len(items)}")
    for item in items[:5]:
        title = item.findtext('title', '').strip()
        link = item.findtext('link', '').strip()
        print(f"  {title[:100]}")
        print(f"    {link[:120]}")
except Exception as e:
    print(f"  ERROR: {e}")
