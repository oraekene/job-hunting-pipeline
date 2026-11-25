#!/usr/bin/env python3
"""Extract job postings from the HN 'Who is Hiring' September 2026 thread.
Uses concurrent requests for speed."""
import requests, re, json, time, datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from pathlib import Path

SKILL_ROOT = Path("C:/Users/rotim/AppData/Local/hermes/skills/job-hunting")
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
HN_API = "https://hacker-news.firebaseio.com/v0"

PM_TITLES = [
    'product manager', 'ai product manager', 'ai engineer', 'automation engineer',
    'associate product manager', 'junior product manager', 'workflow engineer',
    'product owner', 'technical product manager', 'growth product manager',
    'ai/ml product manager', 'head of product', 'product lead', 'head of growth',
]

def title_matches(title):
    t = title.lower().strip()
    for v in PM_TITLES:
        if v in t:
            return v
    return None

def fetch_item(item_id):
    try:
        r = requests.get(f"{HN_API}/item/{item_id}.json", timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None

now = datetime.datetime.now(datetime.timezone.utc)

# Step 1: Fetch the "Who is Hiring" September thread
post_id = 49522897
print(f"=== Fetching HN item {post_id} ===")
post = fetch_item(post_id)
print(f"Title: {post.get('title')}")
kids = post.get('kids', [])
print(f"Top-level comments: {len(kids)}")

# Step 2: Fetch all comments concurrently
print(f"\nFetching {len(kids)} comments (concurrent, max 20 workers)...")
all_items = []
with ThreadPoolExecutor(max_workers=20) as executor:
    future_to_id = {executor.submit(fetch_item, kid_id): kid_id for kid_id in kids}
    for i, future in enumerate(as_completed(future_to_id)):
        result = future.result()
        if result:
            all_items.append(result)
        if (i + 1) % 50 == 0:
            print(f"  ... fetched {i+1}/{len(kids)}")

print(f"Fetched {len(all_items)} comments successfully")

# Step 3: Parse comments for PM jobs
pm_jobs = []

for item in all_items:
    text = item.get('text', '')
    if not text:
        continue
    
    soup = BeautifulSoup(text, 'lxml')
    links = soup.find_all('a', href=True)
    full_text = soup.get_text(separator=' ', strip=True)
    
    if not title_matches(full_text):
        continue
    
    matched = title_matches(full_text)
    
    # Parse pipe-delimited format: Company | Role | Location | Salary | link
    cleaned = full_text.replace('\n', ' ').strip()
    parts = [p.strip() for p in cleaned.split('|')]
    
    company = ''
    role_title = ''
    location = ''
    salary = ''
    apply_url = ''
    
    if len(parts) >= 2:
        company = parts[0]
        for part in parts:
            m = title_matches(part)
            if m:
                role_title = part
                break
        if len(parts) >= 3:
            for part in parts[1:]:
                if not title_matches(part) and '$' not in part and not re.search(r'\d+k', part, re.I) and len(part) < 50:
                    location = part
                    break
        for part in parts:
            if '$' in part or re.search(r'\d\s*k\b|\d\s*k/annum|\dkusd', part.lower()):
                salary = part
                break
    
    for a in links:
        href = a['href']
        if 'hackernews' in href or 'ycombinator' in href or href.startswith('#') or href.startswith('item?id='):
            continue
        apply_url = href
        break
    
    pm_jobs.append({
        'company': company or 'unknown',
        'role_title': role_title or full_text[:120],
        'location': location,
        'salary': salary,
        'apply_url': apply_url,
        'comment_id': item.get('id'),
        'matched_variant': matched,
        'text_snippet': full_text[:250],
        'posted_at_raw': None,
        'posted_at': None,
    })

print(f"\n=== PM Jobs found in HN thread: {len(pm_jobs)} ===")
for j in pm_jobs:
    print(f"  [{j['matched_variant']}] {j['company'][:25]:25s} | {j['role_title'][:45]} | loc={j['location'][:20]} | url={j['apply_url'][:55]}")

outpath = SKILL_ROOT / "01-job-discovery" / "scripts" / "hn_hiring_jobs.json"
with open(outpath, 'w') as f:
    json.dump({'scan_time': now.isoformat(), 'thread_id': post_id, 'jobs': pm_jobs}, f, indent=2)
print(f"\nSaved to {outpath}")
