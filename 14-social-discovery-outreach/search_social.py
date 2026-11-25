#!/usr/bin/env python3
"""
Multi-backend social search — tries Reddit RSS, old.reddit.com HTML,
DuckDuckGo HTML, and Bing HTML to find hiring-style posts.
"""
import json, re, html as html_mod, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from datetime import datetime, timezone

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (X11; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0 (Hermes-JobHunt/1.0)"

def fetch(url, accept="text/html,application/xhtml+xml"):
    headers = {"User-Agent": UA, "Accept": accept, "Accept-Language": "en-US,en;q=0.9"}
    req = urllib.request.Request(url, headers=headers)
    resp = urllib.request.urlopen(req, timeout=20)
    return resp.read().decode('utf-8', errors='replace')

def search_bing(q, count=20):
    """Search Bing HTML and extract result links + snippets."""
    url = f"https://www.bing.com/search?q={urllib.parse.quote(q)}&count={count}"
    try:
        html = fetch(url)
        results = []
        # Bing result links are in <cite> tags or in <h2><a href="...">
        # Also try the data-piu attribute
        links = re.findall(r'<h2><a href="(https?://[^"]+)"', html)
        if not links:
            links = re.findall(r'<cite[^>]*>(.*?)</cite>', html, re.DOTALL)
            links = [re.search(r'https?://\S+', l) for l in links if l]
            links = [m.group(0) for m in links if m]
        snippets = re.findall(r'<p class="b_lineclamp[^"]*"[^>]*>(.*?)</p>', html, re.DOTALL)
        for i, link in enumerate(links[:count]):
            snip = ""
            if i < len(snippets):
                snip = re.sub(r'<[^>]+>', '', snippets[i])[:200]
            results.append({"url": link, "snippet": html_mod.unescape(snip)})
        return results, html
    except Exception as e:
        return [], f"ERROR: {e}"

def search_ddg(q):
    """Search DuckDuckGo HTML."""
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(q)}"
    try:
        html = fetch(url)
        results = []
        # DDG result links
        links = re.findall(r'class="result__a"[^>]*href="([^"]+)"', html)
        snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
        for i, link in enumerate(links[:15]):
            # DDG redirects through uddg= parameter
            m = re.search(r'uddg=([^&]+)', link)
            real_url = urllib.parse.unquote(m.group(1)) if m else link
            snip = ""
            if i < len(snippets):
                snip = re.sub(r'<[^>]+>', '', snippets[i])[:200]
            results.append({"url": real_url, "snippet": html_mod.unescape(snip)})
        return results, html
    except Exception as e:
        return [], f"ERROR: {e}"

def reddit_rss(subreddit, limit=15):
    """Fetch Reddit subreddit RSS feed."""
    url = f"https://www.reddit.com/r/{subreddit}/.rss"
    try:
        raw = fetch(url, accept="application/rss+xml")
        if not raw or len(raw.strip()) == 0:
            return [], "Empty response (blocked)"
        root = ET.fromstring(raw)
        items = root.findall('.//item')
        results = []
        for item in items[:limit]:
            title = item.findtext('title', '').strip()
            link = item.findtext('link', '').strip()
            desc = item.findtext('description', '')
            desc_clean = re.sub(r'<[^>]+>', '', desc)[:300]
            results.append({"url": link, "title": title, "snippet": html_mod.unescape(desc_clean),
                           "subreddit": subreddit})
        return results, f"OK — {len(results)} items"
    except Exception as e:
        return [], f"ERROR: {e}"

def reddit_search_json(query, limit=15):
    """Try Reddit search JSON endpoint."""
    url = f"https://www.reddit.com/search.json?q={urllib.parse.quote(query)}&sort=new&limit={limit}&restrict_sr=0"
    try:
        raw = fetch(url, accept="application/json")
        data = json.loads(raw)
        posts = data.get("data", {}).get("children", [])
        results = []
        for c in posts[:limit]:
            p = c["data"]
            results.append({"url": f"https://www.reddit.com{p['permalink']}",
                           "title": p["title"],
                           "snippet": p.get("selftext", "")[:300],
                           "subreddit": p.get("subreddit", ""),
                           "score": p.get("score", 0),
                           "num_comments": p.get("num_comments", 0)})
        return results, f"OK — {len(results)} posts"
    except Exception as e:
        return [], f"ERROR: {e}"

# === Build queries from target profile + discovery_queries.yaml ===
# These are the search terms we'll use across platforms
search_queries = [
    # DM-focused hiring posts (from query: reddit-pm-hiring-dm)
    '"hiring" "product manager" "DM me" remote 2026 site:reddit.com',
    '"hiring" "AI engineer" "DM me" remote 2026 site:reddit.com',
    '"hiring" "automation engineer" "message me" remote 2026 site:reddit.com',
    # Forhire subreddit (from query: reddit-forhire-techjobs-hiring)
    'site:reddit.com "we are hiring" "product manager" remote',
    'site:reddit.com "looking for" "product manager" remote',
    'site:reddit.com r/forhire "product manager" "remote"',
    # AI-focused subreddits
    'site:reddit.com r/AIProductManagers "hiring"',
    'site:reddit.com r/AIJobs "product manager" "hiring"',
    # Broad: need someone
    '"need someone" "product manager" remote',
    '"drowning" "product manager" "help" remote',
    # X/Twitter
    'site:x.com "hiring" "product manager" "DM" remote',
    'site:twitter.com "hiring" "AI engineer" remote',
    # n8n community
    'site:community.n8n.io "hiring" "automation"',
]

# Also generate Reddit-specific search terms
reddit_searches = [
    ('forhire', 'hiring product manager remote'),
    ('forhire', 'hiring AI engineer automation engineer remote'),
    ('forhire', 'looking for product manager AI engineer remote'),
    ('jobbit', 'hiring product manager remote'),
    ('techjobs', 'hiring product manager remote'),
    ('remotework', 'hiring product manager remote'),
    ('AIProductManagers', 'hiring product manager'),
    ('AIJobs', 'hiring product manager remote'),
    (None, 'hiring product manager AI engineer automation engineer remote DM message'),
    (None, 'looking for product manager remote'),
    (None, 'need someone product manager AI automation remote'),
]

now = datetime.now(timezone.utc)
print(f"Social discovery scan started at {now.strftime('%Y-%m-%dT%H:%M:%SZ')}")
print("=" * 70)

# === Phase 1: Reddit RSS feeds ===
print("\n--- Phase 1: Reddit RSS feeds ---")
reddit_posts = []
rss_subs = ["forhire", "jobbit", "techjobs", "remotework", "AIProductManagers", "AIJobs", "product_management", "ArtificialInteligence"]
for sub in rss_subs:
    results, status = reddit_rss(sub)
    if results:
        print(f"  r/{sub}: {len(results)} items — {status}")
        for r in results:
            reddit_posts.append(r)
    else:
        print(f"  r/{sub}: BLOCKED/EMPTY — {status}")

# Also try general Reddit search via RSS
results, status = reddit_rss("all", 25)
if results:
    print(f"  r/all: {len(results)} items")
    reddit_posts.extend(results)
else:
    print(f"  r/all: BLOCKED — {status}")

# === Phase 2: Reddit JSON search (backup) ===
print("\n--- Phase 2: Reddit JSON search (backup) ---")
for sub, q in reddit_searches:
    if sub:
        url = f"https://www.reddit.com/r/{sub}/search.json?q={urllib.parse.quote(q)}&sort=new&limit=15&restrict_sr=1"
    else:
        url = f"https://www.reddit.com/search.json?q={urllib.parse.quote(q)}&sort=new&limit=15&restrict_sr=0"
    try:
        raw = fetch(url, accept="application/json")
        data = json.loads(raw)
        posts = data.get("data", {}).get("children", [])
        label = f"r/{sub}" if sub else "r/all"
        if posts:
            print(f"  {label} q='{q[:40]}': {len(posts)} posts")
            for c in posts[:8]:
                p = c["data"]
                reddit_posts.append({
                    "url": f"https://www.reddit.com{p['permalink']}",
                    "title": p["title"],
                    "snippet": (p.get("selftext", "") or "")[:300],
                    "subreddit": p.get("subreddit", ""),
                    "score": p.get("score", 0),
                    "num_comments": p.get("num_comments", 0),
                })
        else:
            print(f"  {label} q='{q[:40]}': empty")
    except Exception as e:
        label = f"r/{sub}" if sub else "r/all"
        print(f"  {label} q='{q[:40]}': BLOCKED — {str(e)[:60]}")

# === Phase 3: Bing web search (no site: filter to get broader results) ===
print("\n--- Phase 3: Bing web search ---")
bing_results = []
search_terms = [
    '"hiring" "product manager" remote "DM me" reddit',
    '"hiring" "AI engineer" remote "DM" reddit',
    '"looking for" "product manager" "automation engineer" remote',
    '"hiring" "product manager" "automation" remote "apply"',
    'reddit forhire "product manager" remote hiring 2026',
    'reddit AIJobs "product manager" hiring',
    'site:reddit.com "hiring" "product manager" remote',
]
for q in search_terms:
    results, html = search_bing(q, count=10)
    if results:
        print(f"  '{q[:50]}': {len(results)} results")
        for r in results:
            bing_results.append({"query": q, **r})
    else:
        print(f"  '{q[:50]}': {str(html)[:80] if isinstance(html, str) else 'no HTML'}")

# === Phase 4: DuckDuckGo search ===
print("\n--- Phase 4: DuckDuckGo search ---")
ddg_queries = [
    '"hiring" "product manager" remote "DM me"',
    'reddit hiring product manager AI engineer remote',
    '"looking for" "automation engineer" remote',
]
ddg_results = []
for q in ddg_queries:
    results, html = search_ddg(q)
    if results:
        print(f"  '{q[:50]}': {len(results)} results")
        for r in results:
            ddg_results.append({"query": q, **r})
    else:
        print(f"  '{q[:50]}': BLOCKED — {str(html)[:80] if isinstance(html, str) else 'error'}")

# === Collect all unique URLs ===
print("\n" + "=" * 70)
all_urls = {}

for p in reddit_posts:
    url = p.get("url", "")
    if url and url not in all_urls:
        all_urls[url] = {"platform": "reddit", "title": p.get("title", ""), "snippet": p.get("snippet", ""),
                         "subreddit": p.get("subreddit", ""), "score": p.get("score", 0)}

for r in bing_results:
    url = r.get("url", "")
    if "reddit" in url.lower() and url not in all_urls:
        all_urls[url] = {"platform": "bing→reddit", "title": "", "snippet": r.get("snippet", "")}

for r in ddg_results:
    url = r.get("url", "")
    if "reddit" in url.lower() and url not in all_urls:
        all_urls[url] = {"platform": "ddg→reddit", "title": "", "snippet": r.get("snippet", "")}

print(f"\nTotal unique candidate URLs: {len(all_urls)}")
for url, info in list(all_urls.items())[:30]:
    print(f"  [{info['platform']}] {info['title'][:70]}")
    print(f"    {url[:120]}")
    if info.get('snippet'):
        print(f"    Snippet: {info['snippet'][:120]}")
    print()

# Save raw results
results = {
    "scan_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "total_unique_urls": len(all_urls),
    "candidates": [{"url": u, **info} for u, info in all_urls.items()],
}
out_path = r"C:/Users/rotim/AppData/Local/hermes/cache/web/social_discovery_raw.json"
with open(out_path, 'w') as f:
    json.dump(results, f, indent=2)
print(f"\nRaw results saved to {out_path}")
