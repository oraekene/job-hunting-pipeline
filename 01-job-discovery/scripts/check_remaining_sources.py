#!/usr/bin/env python3
"""Check Remotive API, Working Nomads, and Wellfound API for PM jobs."""
import urllib.request, urllib.parse, re, json
from bs4 import BeautifulSoup
from datetime import datetime, timezone

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def fetch(url, timeout=15):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=timeout)
        ctype = resp.headers.get('Content-Type', '')
        data = resp.read().decode('utf-8', errors='replace')
        return data, resp.status, ctype
    except urllib.error.HTTPError as e:
        return '', e.code, ''
    except Exception as e:
        return str(e), 0, ''

TITLE_VARIANTS = [
    "Product Manager", "AI Product Manager", "AI Engineer", "Automation Engineer",
    "Associate Product Manager", "Junior Product Manager", "Workflow Engineer",
    "Product Owner", "Technical Product Manager", "Growth Product Manager",
    "AI/ML Product Manager",
]

def title_matches(title):
    t = title.lower().strip()
    for v in TITLE_VARIANTS:
        vl = v.lower().strip()
        if vl in t or t in vl:
            return v
    return None

# 1. Remotive API
print("=== Remotive API: category=product-management ===")
content, status, ctype = fetch("https://remotive.com/api/remote-jobs?category=product-management")
print(f"HTTP {status}, size={len(content)}")
if status == 200 and len(content) > 10:
    try:
        data = json.loads(content)
        jobs = data.get('jobs', []) if isinstance(data, dict) else []
        print(f"Jobs: {len(jobs)}")
        for j in jobs[:10]:
            title = j.get('title', '')
            company = j.get('company_name', '')
            url = j.get('url', '')
            pub = j.get('publication_date', '')
            m = title_matches(title)
            print(f"  {'[PM]' if m else '  '} {title[:60]} | {company[:30]} | {pub} | {url[:80]}")
    except Exception as e:
        print(f"JSON parse error: {e}")
        print(f"Content: {content[:300]}")

# 2. Remotive API keyword search
print("\n=== Remotive API: search=product manager ===")
content, status, ctype = fetch("https://remotive.com/api/remote-jobs?search=product%20manager")
print(f"HTTP {status}, size={len(content)}")
if status == 200 and len(content) > 10:
    try:
        data = json.loads(content)
        jobs = data.get('jobs', []) if isinstance(data, dict) else []
        print(f"Jobs: {len(jobs)}")
        for j in jobs[:10]:
            title = j.get('title', '')
            company = j.get('company_name', '')
            url = j.get('url', '')
            pub = j.get('publication_date', '')
            m = title_matches(title)
            print(f"  {'[PM]' if m else '  '} {title[:60]} | {company[:30]} | {pub} | {url[:80]}")
    except Exception as e:
        print(f"JSON error: {e}")

# 3. Working Nomads
print("\n=== Working Nomads: /jobs?category=product ===")
content, status, ctype = fetch("https://www.workingnomads.com/jobs?category=product")
print(f"HTTP {status}, size={len(content)}")
if status == 200:
    soup = BeautifulSoup(content, 'lxml')
    pm_links = []
    for a in soup.find_all('a', href=True):
        text = a.get_text(strip=True)
        href = a.get('href')
        if text and href and ('product' in text.lower() and 'manager' in text.lower()):
            pm_links.append((text[:80], href[:120]))
    print(f"PM links: {len(pm_links)}")
    for t, u in pm_links[:10]:
        print(f"  - {t} | {u}")

# 4. Wellfound sitemap
print("\n=== Wellfound sitemap ===")
content, status, ctype = fetch("https://wellfound.com/sitemap.xml")
print(f"HTTP {status}, size={len(content)}")
if status == 200 and len(content) > 100:
    job_urls = re.findall(r'<loc>([^<]*jobs[^<]*)</loc>', content)
    print(f"Job URLs in sitemap: {len(job_urls)}")
    for u in job_urls[:10]:
        print(f"  {u[:120]}")

# 5. Check for "today" or "yesterday" on Wellfound page
print("\n=== Wellfound: check for recent PM jobs ===")
wf_html = "C:/Users/rotim/AppData/Local/hermes/cache/web/wellfound-jobs-today.html"
try:
    with open(wf_html, 'r', errors='replace') as f:
        content = f.read()
    # Find all job title + company + date combinations
    # Look for pattern: job ID with title
    job_pattern = r'/jobs/(\d+)-([^"\']+)'
    jobs = re.findall(job_pattern, content)
    print(f"Total job URLs in HTML: {len(jobs)}")
    # Check which ones are PM-related
    for jid, slug in jobs:
        title = slug.replace('-', ' ').title()
        m = title_matches(title)
        if m:
            # Find the company and date nearby
            idx = content.find(f'/jobs/{jid}-{slug}')
            context = content[max(0, idx-200):idx+300]
            # Look for date info (today, yesterday, days ago)
            date_match = re.search(r'(today|yesterday|just now|\d+\s*days?\s*ago|\d+\s*hours?\s*ago)', context, re.I)
            company_match = re.search(r'>([^<]+)<!-- --> • </', context)
            date_raw = date_match.group(1) if date_match else 'unknown'
            company_raw = company_match.group(1) if company_match else 'unknown'
            in_db = jid in ['4678061', '4677997', '4664710']  # known DB entries
            print(f"  PM: {title[:50]} | comp={company_raw[:20]} | date={date_raw} | in_db={in_db}")
except FileNotFoundError:
    print("Wellfound HTML cache not found")

print("\n=== DONE ===")
