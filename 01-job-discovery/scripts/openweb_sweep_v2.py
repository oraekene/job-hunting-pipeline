#!/usr/bin/env python3
"""Diagnose accessible sources for open-web sweep."""
import urllib.request, urllib.parse, re
from bs4 import BeautifulSoup
from pathlib import Path
import sqlite3
from datetime import datetime, timezone

PYEXE = "C:/Users/rotim/AppData/Local/hermes/hermes-agent/venv/Scripts/python"
SKILL_ROOT = Path("C:/Users/rotim/AppData/Local/hermes/skills/job-hunting")
DB_PATH = SKILL_ROOT / "shared" / "applications.db"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def fetch(url, timeout=15):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.read().decode('utf-8', errors='replace'), resp.status
    except urllib.error.HTTPError as e:
        return '', e.code
    except Exception as e:
        return str(e), 0

TITLE_VARIANTS = [
    "Product Manager", "AI Product Manager", "AI Engineer", "Automation Engineer",
    "Associate Product Manager", "Junior Product Manager", "Workflow Engineer",
    "Product Owner", "Technical Product Manager", "Growth Product Manager",
    "AI/ML Product Manager",
]

def title_matches(title):
    title_lower = title.lower().strip()
    for variant in TITLE_VARIANTS:
        v = variant.lower().strip()
        if v in title_lower or title_lower in v:
            return variant
    return None

# Load existing DB data
conn = sqlite3.connect(str(DB_PATH))
c = conn.cursor()
c.execute("SELECT posting_url FROM applications WHERE posting_url IS NOT NULL")
existing_urls = set(r[0] for r in c.fetchall())
c.execute("SELECT posting_url FROM posting_sources WHERE posting_url IS NOT NULL")
existing_source_urls = set(r[0] for r in c.fetchall())
all_existing = existing_urls | existing_source_urls
conn.close()

NEW_FOUND = []

# 1. Bing simple search (no site: operator)
print("=== Bing: product manager remote hiring 2026 ===")
content, status = fetch("https://www.bing.com/search?q=product+manager+hiring+remote+job+2026&count=15")
print(f"  HTTP {status}, size={len(content)}")
if status == 200:
    soup = BeautifulSoup(content, 'lxml')
    results = soup.find_all('li', class_='b_algo')
    print(f"  b_algo results: {len(results)}")
    for r in results:
        link = r.find('a', href=True)
        if link:
            href = link.get('href', '')
            title = link.get_text(strip=True)
            # Check if it's a job listing (not a dictionary/encyclopedia page)
            is_dict = any(d in href for d in ['merriam-webster', 'cambridge.org', 'wikipedia', 'producthunt', 'thembains', 'simplicable', 'marketingtutor', 'aha.io'])
            if not is_dict and 'bing.com/ck' in href:
                # Bing redirect - try to extract real URL
                m = re.search(r'uddg=([^&]+)', href)
                if m:
                    real_url = urllib.parse.unquote(m.group(1))
                    matched = title_matches(title)
                    if matched:
                        print(f"  *** PM MATCH: {title[:70]} | {real_url[:120]}")
                        NEW_FOUND.append({'url': real_url, 'title': title, 'source': 'bing'})
                    else:
                        print(f"  - {title[:70]} | {real_url[:120]}")
            elif not is_dict:
                matched = title_matches(title)
                if matched:
                    print(f"  *** PM MATCH: {title[:70]} | {href[:120]}")
                    NEW_FOUND.append({'url': href, 'title': title, 'source': 'bing'})

# 2. Working Nomads
print("\n=== Working Nomads: product manager ===")
content, status = fetch("https://www.workingnomads.com/jobs?term=product+manager")
print(f"  HTTP {status}, size={len(content)}")
if status == 200:
    soup = BeautifulSoup(content, 'lxml')
    job_links = soup.find_all('a', href=re.compile(r'/jobs/'))
    print(f"  Job links: {len(job_links)}")
    for link in job_links:
        text = link.get_text(strip=True)
        href = link.get('href', '')
        if text and 'product' in text.lower():
            matched = title_matches(text)
            if matched:
                print(f"  *** PM MATCH: {text[:70]} | https://www.workingnomads.com{href}")
                NEW_FOUND.append({'url': f'https://www.workingnomads.com{href}', 'title': text, 'source': 'workingnomads'})

# 3. HN Who's Hiring via HNRSS
print("\n=== HN via HNRSS: who is hiring september ===")
content, status = fetch("https://hnrss.org/newest?q=who%27s+hiring+september", timeout=15)
print(f"  HTTP {status}, size={len(content)}")
if status == 200:
    # Parse RSS feed
    soup = BeautifulSoup(content, 'xml')
    items = soup.find_all('item')
    print(f"  Feed items: {len(items)}")
    for item in items[:10]:
        title = item.title.get_text() if item.title else ''
        link = item.link.get_text() if item.link else ''
        if 'hiring' in title.lower():
            print(f"  - {title[:70]} | {link[:100]}")

# 4. Direct Lever company pages (from DB)
print("\n=== Direct Lever company pages ===")
lever_companies = ['kindred', 'kpler', 'lendbuzz', 'synack']
for co in lever_companies:
    content, status = fetch(f"https://jobs.lever.co/{co}", timeout=10)
    print(f"  {co}: HTTP {status}, size={len(content)}")
    if status == 200:
        soup = BeautifulSoup(content, 'lxml')
        pm_jobs = []
        for link in soup.find_all('a', href=True):
            txt = link.get_text(strip=True)
            href = link.get('href', '')
            if href.startswith('/') and not href.startswith('//'):
                matched = title_matches(txt)
                if matched:
                    pm_jobs.append((txt, href))
        if pm_jobs:
            print(f"    PM jobs found: {len(pm_jobs)}")
            for t, h in pm_jobs[:3]:
                print(f"    - {t} | https://jobs.lever.co{h}")

# 5. Direct Ashby company pages
print("\n=== Direct Ashby company pages ===")
ashby_cos = ['kindred', 'stedi', 'kraken']
for co in ashby_cos:
    content, status = fetch(f"https://jobs.ashbyhq.com/{co}", timeout=10)
    print(f"  {co}: HTTP {status}, size={len(content)}")
    if status == 200:
        soup = BeautifulSoup(content, 'lxml')
        pm_jobs = []
        for link in soup.find_all('a', href=True):
            txt = link.get_text(strip=True)
            href = link.get('href', '')
            if 'product' in txt.lower() and 'manager' in txt.lower():
                pm_jobs.append((txt, href))
        if pm_jobs:
            print(f"    PM jobs found: {len(pm_jobs)}")
            for t, h in pm_jobs[:3]:
                full = f"https://jobs.ashbyhq.com{href}" if href.startswith('/') else href
                print(f"    - {t} | {full[:120]}")

# 6. Try searching for new Lever companies
print("\n=== Bing: lever.co product manager remote ===")
content, status = fetch("https://www.bing.com/search?q=lever.co+product+manager+remote+hiring+2026&count=10")
if status == 200:
    soup = BeautifulSoup(content, 'lxml')
    for r in soup.find_all('li', class_='b_algo')[:5]:
        link = r.find('a', href=True)
        if link:
            href = link.get('href', '')
            m = re.search(r'uddg=([^&]+)', href)
            if m:
                real_url = urllib.parse.unquote(m.group(1))
                if 'lever.co' in real_url and not any(u in real_url for u in ['merriam', 'wiki', 'producthunt']):
                    print(f"  {link.get_text(strip=True)[:60]} | {real_url[:120]}")

# Summary
print(f"\n{'='*60}")
print(f"NEW CANDIDATES FOUND: {len(NEW_FOUND)}")
for c in NEW_FOUND:
    dup = c['url'] in all_existing
    print(f"  {'DUP' if dup else 'NEW'}: {c['title'][:60]} | {c['url'][:100]} | {c['source']}")

# Save results
results = {
    'scan_time': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    'new_candidates': NEW_FOUND,
    'all_existing_urls': len(all_existing),
}
outpath = SKILL_ROOT / "01-job-discovery" / "scripts" / "openweb_sweep_results.json"
import json
with open(outpath, 'w') as f:
    json.dump(results, f, indent=2, default=str)
print(f"\nResults saved to: {outpath}")
