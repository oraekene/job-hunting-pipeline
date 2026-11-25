#!/usr/bin/env python3
"""
Round 3: Fix Algolia API, parse Remotive HTML, try GitHub jobs API,
parse HN top stories for hiring posts.
"""
import urllib.request, json, re, html as html_mod
from urllib.parse import quote

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
}

TITLE_VARIANTS = [
    "product manager", "ai product manager", "ai engineer",
    "automation engineer", "associate product manager", "junior product manager",
    "workflow engineer", "product owner", "technical product manager",
    "growth product manager", "ai/ml product manager",
]

def title_matches(title):
    tl = title.lower().strip()
    return any(v in tl for v in TITLE_VARIANTS)

def fetch_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    resp = urllib.request.urlopen(req, timeout=15)
    return json.loads(resp.read().decode())

def fetch_html(url):
    req = urllib.request.Request(url, headers=HEADERS)
    resp = urllib.request.urlopen(req, timeout=15)
    return resp.read().decode('utf-8', errors='replace')

all_candidates = []

# ── 1. HN Algolia API — simplest possible query ──
print("=" * 60)
print("1. HACKER NEWS ALGOLIA API")
print("=" * 60)

for test_url in [
    'https://hn.algolia.com/api/v1/search?query=hello&hitsPerPage=1',
    'https://hn.algolia.com/api/v1/search?query=product+manager&hitsPerPage=10',
    'https://hn.algolia.com/api/v1/search_by_date?query=product+manager&hitsPerPage=10',
]:
    try:
        data = fetch_json(test_url)
        hits = data.get('hits', [])
        print(f"  OK: {test_url} -> {len(hits)} hits")
        for h in hits[:3]:
            t = h.get('title', '')
            u = h.get('url', '')
            print(f"    - {t[:70]} | {u[:60]}")
            if u and title_matches(t):
                all_candidates.append({
                    'company': '', 'role_title': t, 'posting_url': u,
                    'location': 'Remote', 'salary_range': '', 'source': 'hn-algolia',
                    'snippet': (h.get('story_text','') or '')[:200],
                })
    except Exception as e:
        print(f"  FAIL: {test_url} -> {e}")

# ── 2. Remotive HTML parse ──
print("\n" + "=" * 60)
print("2. REMOTIVE HTML")
print("=" * 60)

try:
    html = fetch_html('https://remotive.com/remote-jobs')
    print(f"HTML: {len(html)} chars")
    job_links = re.findall(r'href="(/remote-jobs/[a-z0-9-]+)"', html)
    job_links = list(dict.fromkeys(job_links))
    print(f"Unique job link paths: {len(job_links)}")
    for path in job_links[:30]:
        title_guess = path.replace('/remote-jobs/', '').replace('-', ' ').title()
        full_url = f'https://remotive.com{path}'
        if title_matches(title_guess):
            print(f"  PM MATCH: {title_guess} -> {full_url}")
            all_candidates.append({
                'company': '', 'role_title': title_guess, 'posting_url': full_url,
                'location': 'Remote', 'salary_range': '', 'source': 'remotive-html',
                'snippet': '',
            })
    if job_links:
        print("First 15 job paths:")
        for p in job_links[:15]:
            print(f"  {p}")
except Exception as e:
    print(f"ERROR: {e}")

# ── 3. HN Firebase top stories ──
print("\n" + "=" * 60)
print("3. HN FIREBASE TOP STORIES (hiring posts)")
print("=" * 60)

try:
    stories = fetch_json('https://hacker-news.firebaseio.com/v0/topstories.json')
    print(f"Top stories: {len(stories)}")
    for sid in stories[:300]:
        try:
            item = fetch_json(f'https://hacker-news.firebaseio.com/v0/item/{sid}.json')
            title = item.get('title', '')
            url_val = item.get('url', '')
            if 'hiring' in title.lower() or 'careers' in title.lower() or 'jobs' in title.lower():
                print(f"  Hiring post: {title[:80]} | {url_val[:80] if url_val else '(text-only)'}")
            elif title_matches(title) and url_val and 'reddit' not in url_val.lower():
                print(f"  PM MATCH: {title[:80]} | {url_val[:80]}")
                all_candidates.append({
                    'company': '', 'role_title': title, 'posting_url': url_val,
                    'location': 'Remote', 'salary_range': '', 'source': 'hn-top',
                    'snippet': item.get('text', '')[:200] if item.get('text') else '',
                })
        except Exception:
            pass
except Exception as e:
    print(f"ERROR: {e}")

# ── 4. GitHub issues search ──
print("\n" + "=" * 60)
print("4. GITHUB ISSUES SEARCH")
print("=" * 60)

for q in ['hiring product manager remote', 'product manager remote', 'AI engineer remote']:
    try:
        url = f'https://api.github.com/search/issues?q={quote(q)}&sort=created&order=desc&per_page=10'
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/vnd.github.v3+json',
        })
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read().decode())
        items = data.get('items', [])
        print(f"Query '{q}': {len(items)} results")
        for item in items[:5]:
            title = item.get('title', '')
            url_val = item.get('html_url', '')
            repo_full = item.get('repository_url', '')
            created = item.get('created_at', '')
            print(f"  {title[:60]} | {url_val[:60]} | {created}")
            if title_matches(title):
                all_candidates.append({
                    'company': repo_full.split('/')[-1] if repo_full else '',
                    'role_title': title, 'posting_url': url_val,
                    'location': 'Remote', 'salary_range': '', 'source': 'github',
                    'snippet': (item.get('body','') or '')[:200],
                    'created_at': created,
                })
    except Exception as e:
        print(f"Query '{q}': ERROR: {e}")

# ── 5. HN Firebase job stories (already found Bild AI, check for more) ──
print("\n" + "=" * 60)
print("5. HN FIREBASE JOB STORIES (full sweep)")
print("=" * 60)

try:
    job_ids = fetch_json('https://hacker-news.firebaseio.com/v0/jobstories.json')
    print(f"Total job story IDs: {len(job_ids)}")
    for jid in job_ids:
        try:
            item = fetch_json(f'https://hacker-news.firebaseio.com/v0/item/{jid}.json')
            title = item.get('title', '')
            url_val = item.get('url', '')
            if title_matches(title):
                print(f"  PM MATCH: {title[:80]} | {url_val[:80]}")
                all_candidates.append({
                    'company': '', 'role_title': title, 'posting_url': url_val,
                    'location': 'Remote', 'salary_range': '', 'source': 'hn-jobs',
                    'snippet': item.get('text', '')[:200] if item.get('text') else '',
                })
        except Exception:
            pass
except Exception as e:
    print(f"ERROR: {e}")

# ── Summary ──
print(f"\n{'=' * 60}")
print(f"TOTAL CANDIDATES (incl. dups): {len(all_candidates)}")
print(f"{'=' * 60}")
for c in all_candidates:
    print(f"  [{c['source']}] {c['role_title'][:50]} | {c['posting_url'][:60]}")
