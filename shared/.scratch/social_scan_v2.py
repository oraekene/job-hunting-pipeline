#!/usr/bin/env python3
"""Social listening scan v2 - fetch and parse Reddit/X/n8n directly."""
import urllib.request, re, json
from html import unescape
from pathlib import Path

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
BASE = Path(r'C:\Users\rotim\AppData\Local\hermes\skills\job-hunting')

def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={
        'User-Agent': UA,
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9',
    })
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        return None, f"ERROR: {type(e).__name__}: {e}"

def fetch_ret(url, timeout=20):
    """Fetch and return (content, status)"""
    req = urllib.request.Request(url, headers={
        'User-Agent': UA,
        'Accept-Language': 'en-US,en;q=0.9',
    })
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.read().decode('utf-8', errors='replace'), 'ok'
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode('utf-8', errors='replace')
            return body, f'HTTP {e.code}'
        except:
            return None, f'HTTP {e.code}'
    except Exception as e:
        return None, f'ERROR: {type(e).__name__}: {e}'

all_posts = []

# === Reddit: Try searching via www.reddit.com/search ===
# Reddit's search page returns JSON-like content in HTML
print("=== Searching Reddit for hiring posts ===")

# Search 1: r/forhire - hiring posts
sr_urls = [
    ('forhire', 'https://www.reddit.com/r/forhire/new/'),
    ('remotework', 'https://www.reddit.com/r/remotework/new/'),
    ('jobbit', 'https://www.reddit.com/r/jobbit/new/'),
    ('techjobs', 'https://www.reddit.com/r/techjobs/new/'),
    ('ProductManagementJobs', 'https://www.reddit.com/r/ProductManagementJobs/new/'),
    ('AIJobs', 'https://www.reddit.com/r/AIJobs/new/'),
]

for sr_name, sr_url in sr_urls:
    content, status = fetch_ret(sr_url, timeout=15)
    if status != 'ok' or content is None:
        print(f'  r/{sr_name}: FAILED ({status})')
        continue
    
    # Reddit uses <a> tags with href containing /r/sr_name/comments/
    # Find post links
    pattern = r'href="(https://www\.reddit\.com/r/[a-zA-Z0-9_]+/comments/[a-zA-Z0-9]+/[a-zA-Z0-9_]+)"'
    matches = re.findall(pattern, content)
    
    # Also try finding titles near these links
    posts = []
    for m in matches[:20]:
        posts.append({'url': m, 'sr': sr_name})
    
    # Extract titles from the page
    # Reddit titles are in <h3> or in data-testid attributes
    titles = re.findall(r'"title":"([^"]{10,200})"', content)
    
    if posts or titles:
        print(f'  r/{sr_name}: status={status}, found {len(posts)} links, {len(titles)} titles')
        for t in titles[:5]:
            print(f'    title: {t[:100]}')
    else:
        # Let's look at the raw HTML for clues
        print(f'  r/{sr_name}: status={status}, content_len={len(content) if content else 0}')
        if content and len(content) > 0:
            # Check if it's a redirect/blocked
            lower = content.lower()
            if 'blocked' in lower or 'captcha' in lower or 'robot' in lower:
                print(f'    BLOCKED/CAPTCHA detected in response')
            # Show a snippet of the HTML for debugging
            snippet = content[:500]
            print(f'    snippet: {snippet[:200]}')

# === Try Reddit search JSON via www.reddit.com/search ===
print("\n=== Reddit search via search page ===")
search_url = 'https://www.reddit.com/search/?q=' + urllib.parse.quote('hiring product manager remote 2026') + '&sort=new'
content, status = fetch_ret(search_url, timeout=15)
if content and status == 'ok':
    titles = re.findall(r'"title":"([^"]{10,200})"', content)
    print(f'  Search results: {len(titles)} titles')
    for t in titles[:10]:
        print(f'    {t[:120]}')
    if not titles:
        print(f'  No titles found in content (len={len(content)})')
        # Check for redirect/blocks
        lower = content.lower()
        if 'blocked' in lower or 'captcha' in lower:
            print('  BLOCKED/captcha detected')
        # Try finding any post links
        links = re.findall(r'href="(https://www\.reddit\.com/[^\"]+comments/[^\"]+)"', content)
        print(f'  Post links found: {len(links)}')
        for l in links[:5]:
            print(f'    {l[:100]}')
else:
    print(f'  Search FAILED: {status}')

# === Try X/Twitter search ===
print("\n=== X/Twitter search ===")
x_url = 'https://x.com/search?q=' + urllib.parse.quote('hiring product manager DM remote 2026')
content, status = fetch_ret(x_url, timeout=15)
if content and status == 'ok':
    print(f'  X search: status={status}, content_len={len(content)}')
    # Look for tweets with hiring
    tweets = re.findall(r'"full_text":"([^"]{20,400})"', content)
    if not tweets:
        tweets = re.findall(r'"text":"([^"]{20,400})"', content)
    print(f'  Tweets found: {len(tweets)}')
    for t in tweets[:5]:
        print(f'    {t[:120]}')
else:
    print(f'  X search FAILED: {status}')

# === Try n8n community ===
print("\n=== n8n community search ===")
n8n_url = 'https://community.n8n.io/search?q=hiring'
content, status = fetch_ret(n8n_url, timeout=15)
if content and status == 'ok':
    print(f'  n8n search: status={status}, content_len={len(content)}')
    topics = re.findall(r'href="(/t/[a-zA-Z0-9\-]+/[0-9]+)"', content)
    print(f'  Topics found: {len(topics)}')
    for t in topics[:5]:
        print(f'    {t}')
else:
    print(f'  n8n search FAILED: {status}')

# Save results
all_results = all_posts
with open(str(BASE / 'shared' / '.scratch' / 'social_scan_v2.json'), 'w') as f:
    json.dump({'posts': all_posts, 'status': 'scan complete'}, f, indent=2)
print(f'\n=== Saved to social_scan_v2.json ===')
