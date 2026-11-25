#!/usr/bin/env python3
"""
Round 4: Efficient HN Algolia API + GitHub API search.
Single requests per query, no per-item fetching.
"""
import urllib.request, json, re, html as html_mod
from urllib.parse import quote

HEADERS = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json',
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

def algolia_search(query, **params):
    """Single-request Algolia HN search."""
    base = 'https://hn.algolia.com/api/v1/search'
    param_str = '&'.join(f'{k}={quote(str(v))}' for k, v in params.items())
    url = f'{base}?query={quote(query)}&{param_str}'
    req = urllib.request.Request(url, headers=HEADERS)
    resp = urllib.request.urlopen(req, timeout=15)
    data = json.loads(resp.read().decode())
    return data.get('hits', [])

def comment_clean(text):
    if not text:
        return ''
    t = re.sub(r'<[^>]+>', ' ', text)
    t = html_mod.unescape(' '.join(t.split()))
    return t[:300]

all_candidates = []

# ── 1. Find "Who is hiring?" threads ──
print("=" * 60)
print("1. HN Algolia: Who is hiring threads")
print("=" * 60)

wih_hits = algolia_search("who is hiring", hitsPerPage=5, tags="story")
print(f"Found {len(wih_hits)} 'who is hiring' posts")

for h in wih_hits:
    title = h.get('title', '')
    sid = h.get('story_id', h.get('id', 0))
    created = h.get('created_at', '')
    print(f"  [story_{sid}] {title[:70]} ({created})")

    # Search comments in this thread for PM roles
    for q in ["product manager", "AI engineer", "technical product manager",
              "associate product manager", "AI product manager", "automation engineer"]:
        try:
            comment_hits = algolia_search(q, hitsPerPage=30,
                                          filters=f"story_id:{sid}", tags="comment")
            for ch in comment_hits:
                text = comment_clean(ch.get('comment_text', ''))
                if text and title_matches(text):
                    # Extract URLs from comment
                    urls = re.findall(r'https?://[^\s<>"]+', text)
                    url_val = urls[0] if urls else f'https://news.ycombinator.com/item?id={ch.get("id", "")}'
                    # Extract company from first line
                    first_line = text.split('\n')[0].strip()[:100]
                    print(f"  PM COMMENT: {first_line[:70]}")
                    print(f"    URL: {url_val[:80]}")
                    all_candidates.append({
                        'company': '', 'role_title': first_line,
                        'posting_url': url_val,
                        'location': 'Remote', 'salary_range': '',
                        'source': f'hn-wih-{sid}',
                        'snippet': text,
                        'created_at': ch.get('created_at', ''),
                    })
        except Exception as e:
            print(f"  Comment search for '{q}' in story_{sid}: {e}")

# ── 2. Search job stories for PM roles ──
print("\n" + "=" * 60)
print("2. HN Algolia: Job stories with PM titles")
print("=" * 60)

for q in ["product manager remote", "AI engineer remote",
          "associate product manager", "technical product manager remote"]:
    try:
        hits = algolia_search(q, hitsPerPage=20, tags="job")
        pm_hits = [h for h in hits if title_matches(h.get('title', ''))]
        print(f"Query '{q}' (tags=job): {len(hits)} total, {len(pm_hits)} PM matches")
        for h in pm_hits:
            title = h.get('title', '')
            url_val = h.get('url', '')
            print(f"  MATCH: {title[:70]} | {url_val[:70]}")
            if url_val:
                all_candidates.append({
                    'company': '', 'role_title': title, 'posting_url': url_val,
                    'location': 'Remote', 'salary_range': '',
                    'source': 'hn-algolia-job',
                    'snippet': comment_clean(h.get('story_text', '')),
                    'created_at': h.get('created_at', ''),
                })
    except Exception as e:
        print(f"Query '{q}' (tags=job): ERROR: {e}")

# ── 3. Search story titles for "hiring" + PM ──
print("\n" + "=" * 60)
print("3. HN Algolia: Stories mentioning hiring + PM")
print("=" * 60)

for q in ["hiring product manager", "hiring AI engineer", "hiring associate product manager",
          "hiring remote product manager", "hiring technical product manager"]:
    try:
        hits = algolia_search(q, hitsPerPage=15)
        pm_hits = [h for h in hits if (title_matches(h.get('title', '')) or title_matches(h.get('story_text', '')))]
        print(f"Query '{q}': {len(hits)} total, {len(pm_hits)} PM matches")
        for h in pm_hits[:3]:
            title = h.get('title', '')
            url_val = h.get('url', '')
            text = h.get('story_text', '') or h.get('text', '')
            print(f"  MATCH: {title[:70]} | {url_val[:70]}")
            if url_val:
                all_candidates.append({
                    'company': '', 'role_title': title, 'posting_url': url_val,
                    'location': 'Remote', 'salary_range': '',
                    'source': 'hn-algolia-story',
                    'snippet': comment_clean(text),
                    'created_at': h.get('created_at', ''),
                })
    except Exception as e:
        print(f"Query '{q}': ERROR: {e}")

# ── 4. GitHub issues search ──
print("\n" + "=" * 60)
print("4. GITHUB ISSUES SEARCH")
print("=" * 60)

gh_headers = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/vnd.github.v3+json',
}

for q in ['hiring product manager remote', 'hiring AI engineer remote', 'product manager remote hiring']:
    try:
        url = f'https://api.github.com/search/issues?q={quote(q)}&sort=created&order=desc&per_page=10'
        req = urllib.request.Request(url, headers=gh_headers)
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read().decode())
        items = data.get('items', [])
        pm_items = [i for i in items if title_matches(i.get('title', ''))]
        print(f"Query '{q}': {len(items)} results, {len(pm_items)} PM matches")
        for item in pm_items[:3]:
            title = item.get('title', '')
            url_val = item.get('html_url', '')
            repo = item.get('repository_url', '').split('/')[-1]
            print(f"  MATCH: {title[:70]} | {url_val[:70]} | repo: {repo}")
            all_candidates.append({
                'company': repo, 'role_title': title, 'posting_url': url_val,
                'location': 'Remote', 'salary_range': '',
                'source': f'github-{repo}',
                'snippet': (item.get('body','') or '')[:200],
                'created_at': item.get('created_at', ''),
            })
    except Exception as e:
        print(f"Query '{q}': ERROR: {e}")

# ── Summary ──
print(f"\n{'=' * 60}")
print(f"TOTAL CANDIDATES: {len(all_candidates)}")
print(f"{'=' * 60}")
for c in all_candidates:
    print(f"  [{c['source']}] {c['role_title'][:50]} | {c['posting_url'][:60]}")
