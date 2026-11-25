#!/usr/bin/env python3
"""Debug: check what Bing actually returns for a social search query."""
import urllib.request, urllib.parse, re
from datetime import datetime, timezone

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 (Hermes-JobHunt/1.0)"

def fetch(url, accept="text/html"):
    headers = {"User-Agent": UA, "Accept": accept, "Accept-Language": "en-US,en;q=0.9"}
    req = urllib.request.Request(url, headers=headers)
    resp = urllib.request.urlopen(req, timeout=20)
    return resp.read().decode('utf-8', errors='replace')

now = datetime.now(timezone.utc)
print(f"Debug scan at {now.strftime('%Y-%m-%dT%H:%M:%SZ')}")
print("=" * 70)

# Test 1: Bing search for a known query
q = '"hiring" "product manager" remote "DM me" site:reddit.com'
url = f"https://www.bing.com/search?q={urllib.parse.quote(q)}&count=10"
print(f"\nQuery: {q}")
print(f"URL: {url}")

try:
    html_content = fetch(url)
    print(f"Response length: {len(html_content)} chars")
    
    # Check for common Bing result patterns
    algo_blocks = re.findall(r'<li class="b_algo">(.*?)</li>', html_content, re.DOTALL)
    print(f"b_algo blocks found: {len(algo_blocks)}")
    
    # Try alternative patterns
    h2_links = re.findall(r'<h2><a href="(https?://[^"]+)"', html_content)
    print(f"h2 > a href links found: {len(h2_links)}")
    
    cite_tags = re.findall(r'<cite[^>]*>(.*?)</cite>', html_content, re.DOTALL)
    print(f"cite tags found: {len(cite_tags)}")
    
    # Look for any reddit links
    reddit_links = re.findall(r'https?://(?:www\.)?reddit\.com[^\s"<>]*)', html_content)
    print(f"Reddit links in HTML: {len(reddit_links)}")
    for rl in reddit_links[:5]:
        print(f"  {rl[:120]}")
    
    # Look for "no results" message
    if 'no results' in html_content.lower() or 'no matching' in html_content.lower():
        print("Bing returned 'no results' message")
    
    # Check if we got redirected or blocked
    if 'captcha' in html_content.lower() or 'blocked' in html_content.lower():
        print("WARNING: Bing may be blocking the request (captcha/blocked)")
    
    # Print a small slice of the HTML to see what we got
    print(f"\nHTML head (first 500 chars):")
    print(html_content[:500])
    
except Exception as e:
    print(f"ERROR: {e}")

# Test 2: Try a simpler query
print("\n" + "=" * 70)
q2 = "reddit hiring product manager remote"
url2 = f"https://www.bing.com/search?q={urllib.parse.quote(q2)}&count=10"
print(f"\nQuery: {q2}")
try:
    html2 = fetch(url2)
    print(f"Response length: {len(html2)} chars")
    algo2 = re.findall(r'<li class="b_algo">(.*?)</li>', html2, re.DOTALL)
    print(f"b_algo blocks found: {len(algo2)}")
    for a in algo2[:3]:
        link = re.search(r'<a[^>]*href="(https?://[^"]+)"', a)
        title = re.search(r'<a[^>]*>(.*?)</a>', a, re.DOTALL)
        if link and title:
            t = re.sub(r'<[^>]+>', '', title.group(1)).strip()[:80]
            print(f"  {t}")
            print(f"  {link.group(1)[:120]}")
except Exception as e:
    print(f"ERROR: {e}")

# Test 3: Try web_search tool approach - DuckDuckGo
print("\n" + "=" * 70)
print("\nTest 3: DuckDuckGo lite search")
ddg_url = f"https://lite.duckduckgo.com/lite/?q={urllib.parse.quote(q)}"
try:
    ddg_html = fetch(ddg_url)
    print(f"DDG response length: {len(ddg_html)} chars")
    # DDG lite results are in <a class="result-link" href="...">
    ddg_links = re.findall(r'<a[^>]*class="result-link"[^>]*href="(.*?)"', ddg_html)
    print(f"DDG result links: {len(ddg_links)}")
    for l in ddg_links[:5]:
        print(f"  {l[:120]}")
    if not ddg_links:
        # Try alternative DDG pattern
        ddg_links2 = re.findall(r'href="(https?://[^"]+)"', ddg_html)
        reddit_in_ddg = [u for u in ddg_links2 if 'reddit' in u.lower()]
        print(f"Any reddit links in DDG HTML: {len(reddit_in_ddg)}")
        for r in reddit_in_ddg[:5]:
            print(f"  {r[:120]}")
except Exception as e:
    print(f"DDG ERROR: {e}")
