#!/usr/bin/env python3
"""Comprehensive discovery: Bing b_algo parsing + Remotive full dump + direct fetches."""
import urllib.request, re, json, html as html_mod
from urllib.parse import quote

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}

# ── 1. Bing HTML search with b_algo parsing ──
print("=" * 60)
print("1. BING HTML SEARCH (b_algo parsing)")
print("=" * 60)

queries = [
    '"product manager" remote site:boards.greenhouse.io',
    '"product manager" remote site:jobs.lever.co',
    '"product manager" remote site:jobs.ashbyhq.com',
    '"associate product manager" remote site:boards.greenhouse.io',
    '"AI product manager" remote site:jobs.ashbyhq.com',
]

for q in queries:
    url = 'https://www.bing.com/search?q=' + quote(q) + '&count=50&mkt=en-US&setlang=en-US'
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=15)
        html = resp.read().decode('utf-8', errors='replace')
        # Parse b_algo blocks
        blocks = re.findall(r'<li class="b_algo">(.*?)</li>', html, re.DOTALL)
        print(f"\nQuery: {q}")
        print(f"  HTML: {len(html)} chars, b_algo blocks: {len(blocks)}")
        for block in blocks[:5]:
            # Extract URL
            url_match = re.search(r'href="(https?://[^"]+)"', block)
            # Extract title
            title_match = re.search(r'<h2>(.*?)</h2>', block, re.DOTALL)
            # Extract snippet
            snippet_match = re.search(r'(<p[^>]*>.*?</p>)', block, re.DOTALL)
            url_val = url_match.group(1) if url_match else "NO URL"
            title_val = re.sub(r'<[^>]+>', '', title_match.group(1)).strip() if title_match else "NO TITLE"
            snippet_val = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip() if snippet_match else ""
            print(f"  - {title_val[:60]}")
            print(f"    URL: {url_val[:100]}")
            if snippet_val:
                print(f"    Snippet: {snippet_val[:100]}")
    except Exception as e:
        print(f"\nQuery: {q} -> ERROR: {e}")

# ── 2. Remotive API full dump ──
print("\n" + "=" * 60)
print("2. REMOTIVE API (full dump)")
print("=" * 60)

try:
    req = urllib.request.Request('https://remotive.com/api/remote-jobs', headers=HEADERS)
    resp = urllib.request.urlopen(req, timeout=15)
    data = json.loads(resp.read().decode())
    jobs = data.get('jobs', [])
    print(f"Total jobs: {len(jobs)}")

    # Categorize
    categories = {}
    for j in jobs:
        cat = j.get('category', 'unknown')
        categories[cat] = categories.get(cat, 0) + 1
    print("\nCategories:")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")

    # Print all jobs
    print("\nAll jobs:")
    for j in jobs:
        title = j.get('title', '')
        company = j.get('company_name', '')
        url = j.get('url', '')
        cat = j.get('category', '')
        print(f"  [{cat}] {title} | {company} | {url[:60]}")
except Exception as e:
    print(f"ERROR: {e}")

# ── 3. Try direct ATS pages ──
print("\n" + "=" * 60)
print("3. DIRECT ATS PAGE FETCHES")
print("=" * 60)

# Try Remotive category pages
for cat_path in ['product-management', 'ai-data-science', 'devops-sysadmin', 'project-management']:
    try:
        url = f'https://remotive.com/remote-jobs/category/{cat_path}'
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=15)
        html = resp.read().decode('utf-8', errors='replace')
        print(f"\nRemotive /{cat_path}: HTTP {resp.status}, {len(html)} chars")
        if len(html) > 1000 and 'captcha' not in html.lower():
            links = re.findall(r'href="(/remote-jobs/[^\"]+)"', html)
            print(f"  Job links: {len(links)}")
            for l in links[:5]:
                print(f"  -> {l}")
    except Exception as e:
        print(f"\nRemotive /{cat_path}: ERROR: {e}")

# Try Ashby company pages
for company in ['augment', 'benepass', 'check-technologies', 'sekai', 'stedi', 'turquoise-health', 'ready', 'openrouter', 'kindred']:
    try:
        url = f'https://jobs.ashbyhq.com/{company}'
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=10)
        html = resp.read().decode('utf-8', errors='replace')
        if len(html) > 2000 and 'captcha' not in html.lower():
            # Find job links
            links = re.findall(r'href="(https://jobs\.ashbyhq\.com/[^"]+)"', html)
            job_links = set(links)
            print(f"\nAshby/{company}: HTTP {resp.status}, {len(html)} chars, {len(job_links)} job links")
            for l in sorted(job_links)[:5]:
                print(f"  -> {l[:100]}")
        else:
            print(f"\nAshby/{company}: HTTP {resp.status}, {len(html)} chars - blocked/small")
    except Exception as e:
        print(f"\nAshby/{company}: ERROR: {e}")

# Try Greenhouse company pages (known companies)
for company in ['chime', 'ezcater', 'nura', 'ashleyfurniture', 'knotel']:
    try:
        url = f'https://boards.greenhouse.io/{company}/jobs'
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=10)
        html = resp.read().decode('utf-8', errors='replace')
        if len(html) > 2000 and 'captcha' not in html.lower():
            links = re.findall(r'href="(https?://boards\.greenhouse\.io/[^"]+)"', html)
            print(f"\nGreenhouse/{company}: HTTP {resp.status}, {len(html)} chars, {len(links)} job links")
            for l in links[:5]:
                print(f"  -> {l[:100]}")
        else:
            print(f"\nGreenhouse/{company}: HTTP {resp.status}, {len(html)} chars - blocked/small")
    except Exception as e:
        print(f"\nGreenhouse/{company}: ERROR: {e}")
