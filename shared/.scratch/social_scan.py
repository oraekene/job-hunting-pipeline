#!/usr/bin/env python3
"""Social listening scan - searches Reddit, X/Twitter, n8n community for hiring posts."""
import urllib.request, re, json, time
from html import unescape
from pathlib import Path

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
BASE = Path(r'C:\Users\rotim\AppData\Local\hermes\skills\job-hunting')
OUT = BASE / 'shared' / '.scratch' / 'social_scan_results.json'

def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={
        'User-Agent': UA,
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml',
    })
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"

def bing_search(query):
    """Search Bing and extract result URLs."""
    url = 'https://www.bing.com/search?q=' + urllib.parse.quote(query)
    html = fetch(url)
    if html.startswith('ERROR'):
        return [], html
    # Extract all links from Bing results
    links = re.findall(r'<a[^>]*href="(https?://[^"]+)"[^>]*>', html)
    # Filter out bing.com itself and common nav links
    result_links = [l for l in links if 'bing.com' not in l and 'microsoft.com' not in l
                    and len(l) > 20]
    return result_links[:30], html

def extract_bing_titles(html):
    """Extract titles and URLs from Bing search results."""
    results = []
    # Bing result blocks: <li class="b_algo">
    blocks = re.findall(r'<li class="b_algo">(.*?)</li>', html, re.DOTALL)
    if not blocks:
        blocks = re.findall(r'<li[^>]*class="b_algo"(.*?)</li>', html, re.DOTALL)
    for block in blocks:
        href_match = re.search(r'href="(https?://[^"]+)"', block)
        title_match = re.search(r'<h2[^>]*>(.*?)</h2>', block, re.DOTALL)
        if href_match and title_match:
            href = href_match.group(1)
            title = re.sub(r'<[^>]+>', '', title_match.group(1))
            title = unescape(title.strip())
            results.append({'title': title, 'url': href})
    return results

# Query 1: Reddit hiring posts with DM/message CTA
q1 = 'site:reddit.com "hiring" "product manager" OR "AI engineer" OR "automation engineer" "DM me" OR "message me" remote 2026'
links1, html1 = bing_search(q1)
titles1 = extract_bing_titles(html1)
print(f'=== Query 1: Reddit hiring + DM/message ===')
print(f'  Links found: {len(links1)}, Titles extracted: {len(titles1)}')
for t in titles1[:10]:
    print(f'  {t["title"][:80]} -> {t["url"][:80]}')

# Query 2: Reddit hiring subreddits
q2 = 'site:reddit.com r/forhire r/jobbit r/techjobs r/remotework "we are hiring" OR "looking for" "product manager" OR "AI engineer" remote 2026'
links2, html2 = bing_search(q2)
titles2 = extract_bing_titles(html2)
print(f'\n=== Query 2: Reddit subreddits hiring ===')
print(f'  Links found: {len(links2)}, Titles extracted: {len(titles2)}')
for t in titles2[:10]:
    print(f'  {t["title"][:80]} -> {t["url"][:80]}')

# Query 3: Reddit AI hiring
q3 = 'site:reddit.com r/AIProductManagers r/AIJobs "hiring" "product manager" OR "AI product manager" remote 2026'
links3, html3 = bing_search(q3)
titles3 = extract_bing_titles(html3)
print(f'\n=== Query 3: Reddit AI subreddits hiring ===')
print(f'  Links found: {len(links3)}, Titles extracted: {len(titles3)}')
for t in titles3[:10]:
    print(f'  {t["title"][:80]} -> {t["url"][:80]}')

# Query 4: X/Twitter hiring
q4 = 'site:x.com OR site:twitter.com "hiring" "product manager" "DM" remote 2026'
links4, html4 = bing_search(q4)
titles4 = extract_bing_titles(html4)
print(f'\n=== Query 4: X/Twitter hiring ===')
print(f'  Links found: {len(links4)}, Titles extracted: {len(titles4)}')
for t in titles4[:10]:
    print(f'  {t["title"][:80]} -> {t["url"][:80]}')

# Query 5: n8n community
q5 = 'site:community.n8n.io "hiring" "AI automation" OR "n8n" OR "AI agent" remote'
links5, html5 = bing_search(q5)
titles5 = extract_bing_titles(html5)
print(f'\n=== Query 5: n8n community hiring ===')
print(f'  Links found: {len(links5)}, Titles extracted: {len(titles5)}')
for t in titles5[:10]:
    print(f'  {t["title"][:80]} -> {t["url"][:80]}')

# Collect all unique results
all_results = titles1 + titles2 + titles3 + titles4 + titles5
unique = {}
for r in all_results:
    if r['url'] not in unique and 'reddit.com' in r['url'].lower() or 'x.com' in r['url'].lower() or 'twitter.com' in r['url'].lower() or 'n8n' in r['url'].lower():
        unique[r['url']] = r
print(f'\n=== TOTAL unique social results: {len(unique)} ===')
with open(str(OUT), 'w') as f:
    json.dump(list(unique.values()), f, indent=2)
print(f'Saved to {OUT}')
