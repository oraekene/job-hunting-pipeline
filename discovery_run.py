#!/usr/bin/env python3
"""
Comprehensive discovery using accessible APIs and sources.
Primary: HN Firebase API (reliable), HN Algolia search, Bing RSS with locale.
"""
import urllib.request, json, re, html as html_mod, sqlite3
from urllib.parse import quote
from datetime import datetime, timezone

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'application/json, text/plain, */*',
}

# ── Load DB state ──
DB_PATH = r'C:\Users\rotim\AppData\Local\hermes\skills\job-hunting\shared\applications.db'
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute("SELECT DISTINCT posting_url FROM applications WHERE posting_url IS NOT NULL")
existing_urls = set(r[0].lower() for r in c.fetchall())
c.execute("SELECT DISTINCT posting_url FROM posting_sources WHERE posting_url IS NOT NULL")
for r in c.fetchall():
    existing_urls.add(r[0].lower())
c.execute("SELECT COUNT(*) FROM applications WHERE date(discovered_at) = date('now') AND status IN ('discovered','building','staged','awaiting_approval')")
today_count = c.fetchone()[0]
conn.close()

daily_cap = 15
remaining = daily_cap - today_count
print(f"DB: {len(existing_urls)} known URLs | Today: {today_count} | Cap: {daily_cap} | Remaining: {remaining}")

TITLE_VARIANTS = [
    "product manager", "ai product manager", "ai engineer",
    "automation engineer", "associate product manager", "junior product manager",
    "workflow engineer", "product owner", "technical product manager",
    "growth product manager", "ai/ml product manager",
]

def title_matches(title):
    tl = title.lower().strip()
    return any(v in tl for v in TITLE_VARIANTS)

def normalize_title(title):
    t = title.lower().strip()
    for pat in [r'\s*\(.*?\)', r'\s*-\s*contract\s*$', r'\s*-\s*req\s*#?\d+\s*$',
                r'\s*\[\d+\]\s*$', r'^senior\s+', r'^lead\s+', r'^staff\s+',
                r'^principal\s+', r'\s+(ii|iii|iv|v|vi)\s*$', r'[^\w\s]']:
        import re as remod
        t = remod.sub(pat, '', t, flags=remod.I)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def compute_fingerprint(company, title, location):
    company = (company or 'unknown').lower().strip()
    loc = (location or 'remote').lower().strip()
    if any(w in loc for w in ['remote', 'worldwide', 'global', 'anywhere', 'us only', 'united states']):
        loc = 'remote' if any(w in loc for w in ['remote','worldwide','global','anywhere']) else 'united states'
    loc = re.sub(r'[^\w\s]', '', loc).strip()
    nt = normalize_title(title)
    return f"{company}|{nt}|{loc}"

all_candidates = []
source_results = {}

# ── 1. HN Algolia Search API ──
print("\n" + "=" * 60)
print("1. HN ALGOLIA SEARCH API")
print("=" * 60)

hn_queries = [
    'product manager remote hiring',
    'AI product manager hiring',
    'associate product manager remote',
    'technical product manager remote',
]

for q in hn_queries:
    url = 'https://hn.algolia.com/api/v1/search?query=' + quote(q) + '&hitsPerPage=15&restrictSearchableAttributes=title,text'
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read().decode())
        hits = data.get('hits', [])
        print(f"\nQuery: '{q}' -> {len(hits)} hits")
        for hit in hits:
            title = hit.get('title', hit.get('story_text', ''))[:80]
            url_val = hit.get('url', '')
            if url_val and 'http' in url_val:
                if title_matches(title) or 'product manager' in title.lower() or 'hiring' in title.lower():
                    print(f"  -> {title} | {url_val[:80]}")
                    all_candidates.append({
                        'company': '', 'role_title': title, 'posting_url': url_val,
                        'location': 'Remote', 'salary_range': '', 'source': 'hn-algolia',
                        'snippet': hit.get('story_text', '')[:200],
                    })
    except Exception as e:
        print(f"\nQuery: '{q}' -> ERROR: {e}")
        source_results['hn-algolia'] = str(e)

source_results['hn-algolia'] = f"processed"

# ── 2. HN Firebase API — job stories ──
print("\n" + "=" * 60)
print("2. HN FIREBASE API — Job Stories")
print("=" * 60)

try:
    req = urllib.request.Request('https://hacker-news.firebaseio.com/v0/jobstories.json', headers=HEADERS)
    resp = urllib.request.urlopen(req, timeout=15)
    job_ids = json.loads(resp.read().decode())
    print(f"Total job story IDs: {len(job_ids)}")

    pm_jobs = []
    for jid in job_ids[:100]:
        try:
            req2 = urllib.request.Request(f'https://hacker-news.firebaseio.com/v0/item/{jid}.json', headers=HEADERS)
            resp2 = urllib.request.urlopen(req2, timeout=5)
            item = json.loads(resp2.read().decode())
            title = item.get('title', '')
            url_val = item.get('url', '')
            if title_matches(title) and url_val:
                company = re.match(r'^([^\s-]+)', title)
                company_name = company.group(1) if company else ''
                print(f"  -> {title} | {url_val[:80]}")
                all_candidates.append({
                    'company': company_name, 'role_title': title, 'posting_url': url_val,
                    'location': 'Remote', 'salary_range': '', 'source': 'hn-jobs',
                    'snippet': item.get('text', '')[:200] if item.get('text') else '',
                })
                pm_jobs.append(item)
        except Exception:
            pass
    source_results['hn-firebase-jobs'] = f"{len(pm_jobs)} PM matches from {len(job_ids[:100])} stories"
    print(f"PM matches: {len(pm_jobs)}")
except Exception as e:
    print(f"ERROR: {e}")
    source_results['hn-firebase-jobs'] = str(e)

# ── 3. Bing RSS with locale ──
print("\n" + "=" * 60)
print("3. BING RSS (with en-US locale)")
print("=" * 60)

bing_queries = [
    'product manager remote',
    'AI engineer remote hiring',
    'associate product manager remote',
]
for q in bing_queries:
    rss_url = 'https://www.bing.com/search?q=' + quote(q) + '&format=rss&count=50&mkt=en-US&setlang=en-US'
    try:
        import xml.etree.ElementTree as ET
        req = urllib.request.Request(rss_url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=15)
        xml = resp.read().decode('utf-8', errors='replace')
        root = ET.fromstring(xml)
        items = root.findall('.//item')
        print(f"\nQuery: '{q}' -> {len(items)} RSS items")
        for item in items[:5]:
            title = (item.find('title').text or '')[:80] if item.find('title') is not None else ''
            link = (item.find('link').text or '')[:100] if item.find('link') is not None else ''
            print(f"  - {title}")
            print(f"    {link}")
            # Check if this is a job posting
            if title_matches(title):
                all_candidates.append({
                    'company': '', 'role_title': title, 'posting_url': link,
                    'location': 'Remote', 'salary_range': '', 'source': 'bing-rss',
                    'snippet': '',
                })
    except Exception as e:
        print(f"\nQuery: '{q}' -> ERROR: {e}")
source_results['bing-rss'] = "done"

# ── 4. Reddit JSON API ──
print("\n" + "=" * 60)
print("4. REDDIT JSON API")
print("=" * 60)

for subreddit in ['remotejs', 'digitalnomad', 'workonline', 'remotework']:
    for t in ['new', 'hot']:
        url = f'https://www.reddit.com/r/{subreddit}/{t}.json?limit=50'
        try:
            req = urllib.request.Request(url, headers={**HEADERS, 'User-Agent': 'Mozilla/5.0 (compatible; DiscoveryBot/1.0)'})
            resp = urllib.request.urlopen(req, timeout=15)
            data = json.loads(resp.read().decode())
            posts = data.get('data', {}).get('children', [])
            pm_posts = [p for p in posts if title_matches(p['data'].get('title', ''))]
            print(f"r/{subreddit}/{t}: {len(posts)} posts, {len(pm_posts)} PM matches")
            for p in pm_posts[:3]:
                title = p['data']['title'][:80]
                url_val = 'https://reddit.com' + p['data']['permalink']
                print(f"  -> {title} | {url_val}")
                all_candidates.append({
                    'company': '', 'role_title': title, 'posting_url': url_val,
                    'location': 'Remote', 'salary_range': '', 'source': f'reddit-{subreddit}',
                    'snippet': p['data'].get('selftext', '')[:200],
                })
            if pm_posts:
                source_results[f'reddit-{subreddit}'] = f"{len(pm_posts)} matches"
        except Exception as e:
            print(f"r/{subreddit}/{t}: ERROR: {e}")

# ── 5. Dedup + Filter ──
print("\n" + "=" * 60)
print("5. DEDUP + FILTER")
print("=" * 60)

included = []
duplicates = []
non_matches = []

for p in all_candidates:
    url_lower = p.get('posting_url', '').lower()
    if url_lower in existing_urls:
        duplicates.append((p, 'existing URL'))
        continue
    fp = compute_fingerprint(p.get('company',''), p.get('role_title',''), p.get('location',''))
    if fp in existing_urls:
        duplicates.append((p, 'fingerprint'))
        continue
    if not title_matches(p.get('role_title','')):
        non_matches.append((p, 'title mismatch'))
        continue
    included.append(p)

print(f"\nTotal candidates found: {len(all_candidates)}")
print(f"New (not dup): {len(included)}")
print(f"Duplicates: {len(duplicates)}")
print(f"Non-matches: {len(non_matches)}")

# Apply daily cap
to_queue = included[:max(0, remaining)] if remaining > 0 else []
print(f"\nRemaining slots: {remaining}")
print(f"To queue: {len(to_queue)}")

# Print queue candidates
for p in to_queue:
    print(f"\n  QUEUE: {p.get('company','?')} | {p.get('role_title','')[:50]} | {p.get('posting_url','')[:60]}")
    print(f"    Source: {p.get('source','')} | Location: {p.get('location','')}")

print("\n=== SOURCE RESULTS ===")
for src, status in source_results.items():
    print(f"  {src}: {status}")
print(f"\nTotal found: {len(all_candidates)}, New: {len(included)}, Queued: {len(to_queue)}, Dups: {len(duplicates)}, Non-matches: {len(non_matches)}")
