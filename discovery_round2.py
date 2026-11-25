#!/usr/bin/env python3
"""
Round 2: Fix HN Algolia API, find Who is Hiring thread, fetch job details.
"""
import urllib.request, json, re, sqlite3
from urllib.parse import quote
from datetime import datetime, timezone, timedelta

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

# ── 1. HN Algolia API — simple search ──
print("=" * 60)
print("1. HN ALGOLIA API (fixed query)")
print("=" * 60)

algolia_candidates = []
for q in ["product manager hiring", "ai product manager", "associate product manager"]:
    try:
        url = f'https://hn.algolia.com/api/v1/search?query={quote(q)}&hitsPerPage=20&matchRateMode=partialMatch'
        data = fetch_json(url)
        hits = data.get('hits', [])
        print(f"Query '{q}': {len(hits)} hits")
        for hit in hits[:5]:
            title = hit.get('title', '') or hit.get('story_text', '')
            url_val = hit.get('url', '')
            if title_matches(title) and url_val:
                print(f"  MATCH: {title[:80]} | {url_val[:80]}")
                algolia_candidates.append({
                    'company': '', 'role_title': title, 'posting_url': url_val,
                    'location': 'Remote', 'salary_range': '', 'source': 'hn-algolia',
                    'snippet': (hit.get('story_text','') or '')[:200],
                    'created_at': hit.get('created_at', ''),
                })
    except Exception as e:
        print(f"Query '{q}': ERROR: {e}")

# ── 2. Find "Who is Hiring" thread ──
print("\n" + "=" * 60)
print("2. HN WHO IS HIRING thread")
print("=" * 60)

hiring_candidates = []
try:
    url = f'https://hn.algolia.com/api/v1/search?query={quote("who is hiring")}&hitsPerPage=5&matchRateMode=partialMatch'
    data = fetch_json(url)
    hits = data.get('hits', [])
    print(f"Found {len(hits)} 'hiring' posts")
    for hit in hits:
        title = hit.get('title', '')
        story_id = hit.get('story_id', hit.get('id', 0))
        created = hit.get('created_at', '')
        print(f"  Post {story_id}: {title[:60]} ({created})")
        # Fetch this story's comments that mention product manager
        if story_id:
            try:
                search_url = f'https://hn.algolia.com/api/v1/search?query={quote("product manager")}&hitsPerPage=50&filters=story_id:{story_id}'
                comment_data = fetch_json(search_url)
                comment_hits = comment_data.get('hits', [])
                print(f"    PM comments in this thread: {len(comment_hits)}")
                for ch in comment_hits[:10]:
                    text = (ch.get('comment_text','') or '').strip()
                    # Strip HTML tags
                    text_clean = re.sub(r'<[^>]+>', ' ', text)
                    text_clean = html_mod.unescape(' '.join(text_clean.split()))
                    if text_clean:
                        # Extract company from comment text
                        first_line = text_clean.split('\n')[0][:100]
                        print(f"    - {first_line}")
                        # Try to extract URLs from comment
                        urls = re.findall(r'https?://[^\s<>"\)]+', text_clean)
                        if urls:
                            hiring_candidates.append({
                                'company': '', 'role_title': first_line,
                                'posting_url': urls[0],
                                'location': 'Remote', 'salary_range': '',
                                'source': f'hn-wih-{story_id}',
                                'snippet': text_clean[:300],
                                'created_at': ch.get('created_at', ''),
                            })
            except Exception as e:
                print(f"    Comment search error: {e}")
except Exception as e:
    print(f"ERROR: {e}")

# ── 3. Fetch bild.ai/jobs ──
print("\n" + "=" * 60)
print("3. FETCH bild.ai/jobs")
print("=" * 60)

try:
    req = urllib.request.Request('https://www.bild.ai/jobs', headers=HEADERS)
    resp = urllib.request.urlopen(req, timeout=15)
    html = resp.read().decode('utf-8', errors='replace')
    print(f"HTTP {resp.status}, {len(html)} chars")
    if 'captcha' in html.lower() or 'challenge' in html.lower() or len(html) < 1000:
        print("BLOCKED: anti-bot")
    else:
        # Extract job titles
        titles = re.findall(r'<h[1-4][^>]*>(.*?)</h[1-4]>', html, re.DOTALL)
        cleaned = [re.sub(r'<[^>]+>', '', t).strip() for t in titles]
        for t in cleaned:
            if t and len(t) > 5 and len(t) < 200:
                print(f"  Title: {t[:80]}")
        # Extract job links
        job_links = re.findall(r'href="([^"]*(?:job|career|position)[^"]*)"', html, re.IGNORECASE)
        for l in job_links[:10]:
            print(f"  Link: {l[:100]}")
except Exception as e:
    print(f"ERROR: {e}")

# ── 4. Try fetching remote job boards directly ──
print("\n" + "=" * 60)
print("4. DIRECT JOB BOARD FETCHES")
print("=" * 60)

direct_candidates = []
boards = {
    'remotive-dev': 'https://remotive.com/remote-jobs/software-development',
    'remotive-all': 'https://remotive.com/remote-jobs',
    'weworkremotely': 'https://weworkremotely.com/remote-full-time-jobs.json',
}

for name, url in boards.items():
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=15)
        content = resp.read().decode('utf-8', errors='replace')
        print(f"{name}: HTTP {resp.status}, {len(content)} chars")
        if 'json' in url:
            data = json.loads(content)
            if isinstance(data, list):
                print(f"  JSON array: {len(data)} items")
                for j in data:
                    title = j.get('title', '')
                    if title_matches(title):
                        print(f"  MATCH: {title}")
            elif isinstance(data, dict):
                print(f"  JSON keys: {list(data.keys())[:5]}")
        else:
            if 'captcha' in content.lower() or 'challenge' in content.lower():
                print("  BLOCKED: anti-bot")
            else:
                # Look for job links
                links = re.findall(r'href="([^"]*remote-jobs[^"]*)"', content)
                print(f"  Job links: {len(links)}")
                for l in links[:3]:
                    print(f"  -> {l[:80]}")
    except Exception as e:
        print(f"{name}: ERROR: {e}")

# ── 5. Collect all candidates ──
all_candidates = algolia_candidates + hiring_candidates
print(f"\n{'=' * 60}")
print(f"5. SUMMARY")
print(f"{'=' * 60}")
print(f"Total candidates from all sources: {len(all_candidates)}")
for c in all_candidates:
    print(f"  {c['source']} | {c['role_title'][:50]} | {c['posting_url'][:60]}")
