#!/usr/bin/env python3
"""Re-extract HN jobs with raw comment text saved for better parsing."""
import requests, re, json, datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

SKILL_ROOT = Path("C:/Users/rotim/AppData/Local/hermes/skills/job-hunting")
HN_API = "https://hacker-news.firebaseio.com/v0"
PM_TITLES = [
    'product manager', 'ai product manager', 'ai engineer', 'automation engineer',
    'associate product manager', 'junior product manager', 'workflow engineer',
    'product owner', 'technical product manager', 'growth product manager',
    'ai/ml product manager', 'head of product', 'product lead', 'head of growth',
]

def title_matches(text):
    t = text.lower().strip()
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
post_id = 49522897
post = fetch_item(post_id)
kids = post.get('kids', [])
print(f"Hiring thread: {post.get('title')}, {len(kids)} comments")

# Fetch all comments
all_comments = []
with ThreadPoolExecutor(max_workers=20) as executor:
    results = list(executor.map(fetch_item, kids))
    for r in results:
        if r:
            all_comments.append(r)

print(f"Fetched {len(all_comments)} comments")

# Save raw PM-related comments
pm_comments = []
for item in all_comments:
    text = item.get('text', '')
    if not text:
        continue
    if title_matches(text):
        pm_comments.append({
            'id': item.get('id'),
            'time': item.get('time'),
            'text_raw': text,
            'text_clean': re.sub(r'<[^>]+>', ' ', text),  # strip HTML
        })

print(f"PM-related comments: {len(pm_comments)}")

# Print raw text of first 10 PM comments for format analysis
for c in pm_comments[:10]:
    print(f"\n--- Comment {c['id']} (time={c['time']}) ---")
    print(c['text_clean'][:500])

outpath = SKILL_ROOT / "01-job-discovery" / "scripts" / "hn_raw_pm_comments.json"
with open(outpath, 'w') as f:
    json.dump({'scan_time': now.isoformat(), 'comments': pm_comments}, f, indent=2)
print(f"\nSaved {len(pm_comments)} raw PM comments to {outpath}")
