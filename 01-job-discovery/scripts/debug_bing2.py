#!/usr/bin/env python3
"""
Debug: test better Bing queries and URL decoding.
"""
import re, json, base64
from urllib.parse import quote, unquote
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def bing_search_raw(query, count=15):
    url = "https://www.bing.com/search?q=" + quote(query) + f"&count={count}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    resp = urllib.request.urlopen(req, timeout=20)
    return resp.read().decode("utf-8", errors="replace")

def decode_bing_redirect(href):
    """Decode Bing's redirect URL to get the actual destination."""
    # Bing redirects look like: https://www.bing.com/ck/a?!&...&u=a1aHR0cHM6Ly9...
    # The 'u=' parameter contains a base64-encoded URL with 'a1' prefix
    m = re.search(r'[?&]u=a1([A-Za-z0-9+/=]+)', href)
    if m:
        encoded = m.group(1)
        # Pad if needed
        padding = 4 - len(encoded) % 4
        if padding != 4:
            encoded += '=' * padding
        try:
            decoded = base64.b64decode(encoded).decode('utf-8', errors='replace')
            return decoded
        except Exception:
            pass
    return href

# Test with more specific queries
test_queries = [
    '"Product Manager" remote job hiring site:boards.greenhouse.io',
    '"Product Manager" remote job site:greenhouse.io',
    '"Product Manager" "remote" "job" "hiring"',
    'job "Product Manager" remote',
]

for q in test_queries:
    print(f"\n=== Query: {q} ===")
    html = bing_search_raw(q, count=10)
    print(f"  HTML length: {len(html)}")
    b_algo_count = len(re.findall(r'class="b_algo"', html))
    print(f"  b_algo blocks: {b_algo_count}")
    
    # Extract h2 titles
    h2_blocks = re.findall(r'<h2[^>]*>(.*?)</h2>', html, re.DOTALL)
    for h in h2_blocks[:5]:
        text = re.sub(r'<[^>]+>', '', h).strip()
        print(f"  Title: {text[:100]}")
    
    # Extract cite tags (actual destination URLs)
    cite_tags = re.findall(r'<cite[^>]*>(.*?)</cite>', html, re.DOTALL)
    for c in cite_tags[:5]:
        text = re.sub(r'<[^>]+>', '', c).strip()
        print(f"  URL: {text[:120]}")
