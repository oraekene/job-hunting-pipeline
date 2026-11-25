#!/usr/bin/env python3
"""Test Bing HTML search for product manager jobs."""
import urllib.request, re
from urllib.parse import quote

queries = [
    "product manager remote site:boards.greenhouse.io",
    "product manager remote site:jobs.lever.co",
    "AI product manager remote site:jobs.ashbyhq.com",
    "product manager remote site:careers.smartrecruiters.com",
    "associate product manager site:boards.greenhouse.io",
]

for q in queries:
    url = "https://www.bing.com/search?q=" + quote(q) + "&count=50"
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
    })
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        html = resp.read().decode('utf-8', errors='replace')
        print(f"Query: {q}")
        print(f"  HTML length: {len(html)}")
        # Extract links from search result snippets
        links = re.findall(r'href="(https?://[^"]+)"', html)
        job_links = [l for l in links if not any(x in l for x in ['bing.com', 'microsoft.com', 'msn.com', 'w3.org', 'schema.org'])]
        print(f"  Total links: {len(links)}, job_links: {len(job_links)}")
        for l in job_links[:10]:
            print(f"  -> {l[:120]}")
        print()
    except Exception as e:
        print(f"Query: {q} -> ERROR: {e}")
        print()
