#!/usr/bin/env python3
"""Diagnostic: test all 5 social scan queries against Bing, report b_algo blocks."""
import urllib.request, urllib.parse, re, html, json

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

queries = {
    "reddit-pm-hiring-dm": 'site:reddit.com "hiring" "product manager" OR "AI product manager" OR "AI engineer" OR "automation engineer" "DM me" OR "message me" remote 2026',
    "reddit-forhire-techjobs-hiring": "site:reddit.com r/forhire r/jobbit r/techjobs r/remotework \"we're hiring\" OR \"looking for\" \"product manager\" OR \"AI engineer\" OR \"automation\" remote 2026",
    "n8n-community-hiring": 'site:community.n8n.io "hiring" "AI automation" OR "n8n" OR "AI agent" remote',
    "x-twitter-hiring-pm-ai": 'site:x.com OR site:twitter.com "hiring" "product manager" OR "AI product manager" OR "AI engineer" OR "automation engineer" "DM" remote 2026',
    "reddit-aiproductmanagers-hiring": 'site:reddit.com r/AIProductManagers r/AIJobs "hiring" "product manager" OR "AI product manager" remote 2026',
}

for qid, q in queries.items():
    url = f"https://www.bing.com/search?q={urllib.parse.quote(q)}&count=10"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html", "Accept-Language": "en-US,en;q=0.9"})
    html_content = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
    all_links = re.findall(r'href="(https?://[^"]+)"', html_content)
    reddit_links = [l for l in all_links if "reddit.com" in l]
    ext_links = [l for l in all_links if not l.startswith("https://www.bing.") and not l.startswith("https://r.bing.") and not l.startswith("https://go.microsoft") and "microsoft.com" not in l]
    blocks = re.findall(r'<li[^>]*class="[^"]*b_algo[^"]*"[^>]*>(.*?)</li>', html_content, re.DOTALL)
    titles = []
    for b in blocks:
        t = re.search(r'<a[^>]*>(.*?)</a>', b, re.DOTALL)
        if t:
            t = re.sub(r'<[^>]+>', '', t.group(1)).strip()
            t = html.unescape(t)
            titles.append(t[:80])
    nores = "000 results" in html_content
    print(f"\n=== {qid} ===")
    print(f"  html_len: {len(html_content)}")
    print(f"  reddit_links: {len(reddit_links)}")
    print(f"  ext_links (non-bing/microsoft): {len(ext_links)}")
    print(f"  b_algo blocks: {len(blocks)}")
    print(f"  b_algo titles: {titles[:6]}")
    print(f"  no-results-indicator (000 results): {nores}")
    if ext_links:
        print(f"  sample ext_links: {ext_links[:5]}")
    if reddit_links:
        print(f"  reddit_links sample: {reddit_links[:5]}")
