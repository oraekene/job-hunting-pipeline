#!/usr/bin/env python3
"""Test HN Who is Hiring + Remotive for PM jobs."""
import requests, re, json, time
from bs4 import BeautifulSoup

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
PM_TITLES = ['product manager', 'ai product manager', 'ai engineer', 'automation engineer',
             'associate product manager', 'junior product manager', 'workflow engineer',
             'product owner', 'technical product manager', 'growth product manager',
             'ai/ml product manager', 'head of product', 'product lead']

def title_matches(title):
    t = title.lower().strip()
    for v in PM_TITLES:
        if v in t:
            return v
    return None

# === 1. HN API: Find "Who is Hiring" posts from user 'whoishiring' ===
print("=== HN: Find Who is Hiring thread ===")
try:
    r = requests.get("https://hacker-news.firebaseio.com/v0/user/whoishiring/submitted.json", timeout=15)
    print(f"HN API: HTTP {r.status_code}")
    if r.status_code == 200:
        ids = r.json()
        print(f"Submitted item IDs: {len(ids)}")
        # Check the most recent items
        for item_id in ids[:10]:
            item_url = f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
            ir = requests.get(item_url, timeout=10)
            if ir.status_code == 200:
                item = ir.json()
                title = item.get('title', '')
                print(f"  id={item_id} title='{title}' score={item.get('score','?')} time={item.get('time','?')}")
                if not item.get('text') and not item.get('kids') and not item.get('url'):
                    print(f"    -> text length: {len(item.get('text',''))}, kids: {item.get('kids')}")
except Exception as e:
    print(f"HN API error: {e}")

# === 2. HNRSS search for "who is hiring" ===
print("\n=== HNRSS: search for hiring threads ===")
r = requests.get("https://hnrss.org/newest?q=who%27s+hiring+september", headers=HEADERS, timeout=15)
print(f"HTTP {r.status_code}, size={len(r.text)}")
if r.status_code == 200:
    soup = BeautifulSoup(r.text, 'xml')
    items = soup.find_all('item')
    print(f"Items: {len(items)}")
    for item in items[:5]:
        title = item.title.get_text() if item.title else ''
        link = item.link.get_text() if item.link else ''
        print(f"  {title[:75]} | {link}")

# === 3. Remotive: get ALL jobs, check for PM titles ===
print("\n=== Remotive: all jobs, filter for PM ===")
r = requests.get("https://remotive.com/api/remote-jobs", headers=HEADERS, timeout=15)
print(f"HTTP {r.status_code}, size={len(r.text)}")
if r.status_code == 200:
    data = json.loads(r.text)
    jobs = data.get('jobs', [])
    print(f"Total jobs: {len(jobs)}")
    pm_matches = []
    for j in jobs:
        title = j.get('title', '')
        m = title_matches(title)
        if m:
            pm_matches.append(j)
            print(f"  [{m}] {j.get('company_name','?')}: {title[:55]} | url={j.get('url','?')[:70]} | cat={j.get('category','?')}")
    print(f"PM matches: {len(pm_matches)} / {len(jobs)} total")

# === 4. Remotive by category: product-management ===
print("\n=== Remotive: product-management category ===")
r = requests.get("https://remotive.com/api/remote-jobs?category=product-management", headers=HEADERS, timeout=15)
if r.status_code == 200:
    data = json.loads(r.text)
    jobs = data.get('jobs', [])
    print(f"Total jobs in product-management: {len(jobs)}")
    for j in jobs:
        title = j.get('title', '')
        m = title_matches(title)
        marker = f"[{m}]" if m else "    "
        print(f"  {marker} {j.get('company_name','?')}: {title[:50]} | url={j.get('url','?')[:60]}")
        print(f"       sal={j.get('salary','?')[:40]} | loc={j.get('candidate_required_location','?')[:40]}")
        print(f"       pub={j.get('publication_date','?')}")

# === 5. Try HN "Who is Hiring" thread text directly ===
print("\n=== HN: Check recent Who is Hiring thread content ===")
# The September 2026 "Who is Hiring" thread is typically posted on the 1st weekday of the month
# Let's search for it via HNRSS with different terms
for query in ["hiring", "Ask HN", "who is hiring"]:
    encoded = requests.utils.quote(query)
    r = requests.get(f"https://hnrss.org/newest?q={encoded}", headers=HEADERS, timeout=15)
    if r.status_code == 200:
        soup = BeautifulSoup(r.text, 'xml')
        items = soup.find_all('item')
        hiring_items = [i for i in items if 'hire' in (i.title.get_text() if i.title else '').lower()]
        print(f"Query '{query}': {len(items)} items, {len(hiring_items)} hiring-related")
        for i in hiring_items[:3]:
            link = i.link.get_text() if i.link else ''
            print(f"  {i.title.get_text()[:70]} | {link}")
