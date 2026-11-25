#!/usr/bin/env python3
"""Test additional discovery sources for the open-web sweep."""
import requests, re, json, urllib.parse
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

PM_TITLES = [
    'product manager', 'ai product manager', 'ai engineer', 'automation engineer',
    'associate product manager', 'junior product manager', 'workflow engineer',
    'product owner', 'technical product manager', 'growth product manager',
    'ai/ml product manager', 'head of product', 'product lead'
]

def title_matches(title):
    t = title.lower().strip()
    for v in PM_TITLES:
        if v in t:
            return v
    return None

# 1. HNRSS "Who is Hiring"
print("=== 1. HNRSS: Who is Hiring ===")
r = requests.get("https://hnrss.org/newest?q=who%27s+hiring", headers=HEADERS, timeout=15)
print(f"HTTP {r.status_code}, size={len(r.text)}")
if r.status_code == 200:
    soup = BeautifulSoup(r.text, 'xml')
    items = soup.find_all('item')
    print(f"Items: {len(items)}")
    for item in items[:5]:
        title = item.title.get_text() if item.title else ''
        link = item.link.get_text() if item.link else ''
        print(f"  {title[:70]} | {link[:80]}")

# 2. Working Nomads API
print("\n=== 2. Working Nomads API ===")
r = requests.get("https://www.workingnomads.com/api/jobs?category=product-management&location=worldwide", headers=HEADERS, timeout=15)
print(f"HTTP {r.status_code}, size={len(r.text)}")
if r.status_code == 200:
    try:
        data = json.loads(r.text)
        print(f"Jobs: {len(data) if isinstance(data, list) else 'not a list'}")
        if isinstance(data, list):
            for j in data[:5]:
                print(f"  {j.get('company','?')}: {j.get('title','?')[:55]} | url={j.get('url','?')[:70]}")
    except:
        print(f"  Raw: {r.text[:200]}")

# 3. Working Nomads website scrape
print("\n=== 3. Working Nomads website scrape ===")
r = requests.get("https://www.workingnomads.com/jobs?category=product", headers=HEADERS, timeout=15)
print(f"HTTP {r.status_code}, size={len(r.text)}")
if r.status_code == 200:
    soup = BeautifulSoup(r.text, 'lxml')
    # Working Nomads job cards have class 'card' or links to /jobs/
    job_links = soup.find_all('a', href=re.compile(r'/jobs/'))
    print(f"Job links: {len(job_links)}")
    for a in job_links[:8]:
        text = a.get_text(strip=True)[:60]
        href = a['href']
        if text:
            print(f"  {text} | https://www.workingnomads.com{href}")

# 4. Lever company pages (known companies)
print("\n=== 4. Lever company pages ===")
lever_companies = ['linear', 'latona-labs', 'syntego', 'replit', 'retool', 'ashby', 'figma', 'notion']
for co in lever_companies:
    url = f"https://jobs.lever.co/{co}"
    r = requests.get(url, headers=HEADERS, timeout=10)
    if r.status_code == 200 and len(r.text) > 1000:
        soup = BeautifulSoup(r.text, 'lxml')
        pm_jobs = []
        for a in soup.find_all('a', href=True):
            t = a.get_text(strip=True)
            href = a['href']
            if href.startswith('/{co}/') or href.startswith(f'/{co}/'):
                continue
            m = title_matches(t)
            if m and ('jobs' in href or '/{co}' in href or re.match(r'^[A-Za-z]', href)):
                pm_jobs.append((t, href))
        # Better: look for job posting links
        job_links = soup.find_all('a', href=re.compile(r'/[^\s]*product[-_]manager'))
        print(f"  {co}: HTTP 200, size={len(r.text)}, PM job links={len(job_links)}")
        for a in job_links[:3]:
            print(f"    {a.get_text(strip=True)[:50]} | https://jobs.lever.co{a['href'][:80]}")
    else:
        print(f"  {co}: HTTP {r.status_code}")

# 5. Ashby company pages
print("\n=== 5. Ashby company pages ===")
ashby_companies = ['linear', 'retool', 'figma', 'notion', 'webflow', 'passbase']
for co in ashby_companies:
    url = f"https://jobs.ashbyhq.com/{co}"
    r = requests.get(url, headers=HEADERS, timeout=10)
    print(f"  {co}: HTTP {r.status_code}, size={len(r.text)}")
    if r.status_code == 200 and len(r.text) > 2000:
        soup = BeautifulSoup(r.text, 'lxml')
        job_links = soup.find_all('a', href=re.compile(r'/[^\s]*product'))
        print(f"    PM-related links: {len(job_links)}")
        for a in job_links[:3]:
            print(f"    {a.get_text(strip=True)[:50]} | {a['href'][:80]}")

# 6. Greenhouse company pages
print("\n=== 6. Greenhouse company pages ===")
gh_companies = ['gitlab', 'docker', 'notion', 'figma', 'retool', 'zapier']
for co in gh_companies:
    url = f"https://www.{co}.com/jobs" if co != 'gitlab' else "https://about.gitlab.com/jobs/"
    r = requests.get(url, headers=HEADERS, timeout=10)
    print(f"  {co}: HTTP {r.status_code}, size={len(r.text)}")
