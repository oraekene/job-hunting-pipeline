#!/usr/bin/env python3
"""Extract apply URLs from raw HN PM comments + test more job pages."""
import requests, re, json
from bs4 import BeautifulSoup
from pathlib import Path

SKILL_ROOT = Path("C:/Users/rotim/AppData/Local/hermes/skills/job-hunting")
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
           'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}

# Load raw PM comments
with open(SKILL_ROOT / "01-job-discovery" / "scripts" / "hn_raw_pm_comments.json") as f:
    data = json.load(f)

print(f"Total PM comments: {len(data['comments'])}")

# Extract apply URLs from each comment
job_urls = []
for c in data['comments']:
    text = c['text_raw']
    soup = BeautifulSoup(text, 'lxml')
    links = soup.find_all('a', href=True)
    external_links = []
    for a in links:
        href = a['href']
        link_text = a.get_text(strip=True)
        # Decode HTML entities
        href = href.replace('&#x2F;', '/').replace('&#39;', "'").replace('&amp;', '&')
        # Skip HN links
        if 'hackernews' in href or 'ycombinator' in href or '#' in href or href.startswith('item?id='):
            continue
        external_links.append((href, link_text))
    
    company = c['text_clean'].split('|')[0].strip().split('https')[0].strip()[:40]
    if external_links:
        for url, lt in external_links:
            job_urls.append({'company': company, 'url': url, 'link_text': lt, 'comment_id': c['id']})
    elif external_links == []:
        job_urls.append({'company': company, 'url': '', 'link_text': '', 'comment_id': c['id']})

print(f"\n=== Extracted URLs ({len(job_urls)}) ===")
for j in job_urls:
    print(f"  [{j['company'][:25]:25s}] url={j['url'][:80]} | lt={j['link_text'][:30]}")

# Test accessibility of job-page URLs (not company homepages)
job_page_urls = []
for j in job_urls:
    url = j['url']
    if not url:
        continue
    # Skip company homepages and non-job URLs
    skip_patterns = ['planting.space', 'greatquestion.com', 'govstar.us', 'workhero.pro',
                     'quill.co', 'biobase.ai/careers', 'langfuse.com', 'tandemhealth.ai',
                     'coder.com', 'estuary.dev', 'matterhaul.com', 'balerion.ai',
                     'matcha.fm', 'sourcegraph.com', 'cora.ai', 'starbridge.ai/']
    if any(p in url for p in skip_patterns):
        continue
    job_page_urls.append(j)

print(f"\n=== Testing {len(job_page_urls)} job-page URLs ===")
for j in job_page_urls:
    url = j['url']
    try:
        r = requests.get(url, headers=HEADERS, timeout=12, allow_redirects=True)
        final = r.url[:90]
        has_ld = 'JobPosting' in r.text or 'jobPosting' in r.text.lower()[:5000]
        is_greenhouse = 'greenhouse' in r.text.lower()[:2000] or 'greenhouse' in final
        title_h1 = ''
        soup = BeautifulSoup(r.text, 'lxml')
        h1 = soup.find('h1')
        if h1:
            title_h1 = h1.get_text(strip=True)[:60]
        # Find location
        loc_el = soup.find(class_=re.compile(r'location|job-location|place', re.I))
        loc_text = loc_el.get_text(strip=True)[:40] if loc_el else ''
        print(f"  [{j['company'][:18]:18s}] HTTP {r.status_code} size={len(r.text)} ld={has_ld} gh={is_greenhouse} h1='{title_h1}' loc='{loc_text}' -> {final}")
    except Exception as e:
        print(f"  [{j['company'][:18]:18s}] ERROR: {str(e)[:50]} | {url[:70]}")
