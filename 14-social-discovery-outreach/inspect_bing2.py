#!/usr/bin/env python3
"""Inspect actual Bing result block HTML."""
import urllib.request, urllib.parse, re, html

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 (Hermes-JobHunt/1.0)"

for query in [
    'site:reddit.com "hiring" "product manager" remote 2026',
    'site:reddit.com r/forhire "looking for" remote product manager',
    'site:x.com OR site:twitter.com "hiring" "product manager" remote',
]:
    print(f"\n{'='*60}")
    print(f"Query: {query}")
    url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}&count=15"
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        content = resp.read().decode('utf-8', errors='replace')
        print(f"  Status: {resp.status}, Length: {len(content)}")
    except Exception as e:
        print(f"  ERROR: {e}")
        continue

    # Find b_algo blocks
    blocks = re.findall(r'class="b_algo">(.*?)</li>', content, re.DOTALL)
    print(f"  b_algo blocks: {len(blocks)}")
    for i, b in enumerate(blocks[:5]):
        # Extract href from the block
        hrefs = re.findall(r'href="([^"]+)"', b)
        title_match = re.search(r'<a[^>]*>(.*?)</a>', b, re.DOTALL)
        title = html.unescape(re.sub(r'<[^>]+>', '', title_match.group(1))).strip() if title_match else ""
        # Find any URL in the block text
        urls = re.findall(r'https?://[^\s"<>]+', b)
        print(f"  [{i+1}] title: {title[:80]}")
        print(f"      hrefs: {hrefs[:3]}")
        print(f"      urls: {[u[:80] for u in urls if 'bing' not in u][:3]}")
        # Check if it's a redirect URL
        if hrefs:
            h = hrefs[0]
            if 'bing.com' in h or 'microsoft' in h:
                # Look deeper in the HTML for the actual URL
                all_hrefs = re.findall(r'href="(https?://(?!www\.bing|go\.microsoft|bing\.com|microsoft\.com)[^"]+)"', b)
                if all_hrefs:
                    print(f"      actual external hrefs: {all_hrefs[:3]}")
                else:
                    # Check for url= parameter
                    url_match = re.search(r'url=([^&"\s]+)', b)
                    if url_match:
                        print(f"      url= param: {html.unescape(url_match.group(1))[:80]}")
                    # Check cite tag
                    cite_match = re.search(r'<cite[^>]*>(.*?)</cite>', b, re.DOTALL)
                    if cite_match:
                        print(f"      cite: {html.unescape(re.sub(r'<[^>]+>', '', cite_match.group(1))).strip()[:80]}")
        print()
