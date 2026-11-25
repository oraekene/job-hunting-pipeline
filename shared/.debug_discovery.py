#!/usr/bin/env python3
"""Debug: investigate why sources returned 0 candidates."""
import urllib.request, json, urllib.parse, re

SKILL_ROOT = r"C:/Users/rotim/AppData/Local/hermes/skills/job-hunting"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers=HEADERS)
    resp = urllib.request.urlopen(req, timeout=timeout)
    return resp.status, resp.read().decode("utf-8", errors="replace")

# 1. Remotive API
print("=== REMOTIVE API ===")
try:
    st, body = fetch("https://remotive.com/api/remote-jobs?limit=100&search=product-manager")
    data = json.loads(body)
    jobs = data.get("jobs", [])
    print(f"HTTP {st}, {len(jobs)} jobs for 'product-manager'")
    if jobs:
        pm_kw = ["product manager","ai product","technical product","growth product","associate product","junior product","product owner","ai engineer","automation engineer","workflow engineer"]
        matches = [j for j in jobs if any(k in j.get("title","").lower() for k in pm_kw)]
        print(f"PM keyword matches: {len(matches)}")
        for m in matches[:8]:
            print(f"  MATCH: {m.get('company_name','')} | {m.get('title','')} | pub={m.get('publication_date','')}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")

# 2. Bing
print("\n=== BING SEARCH ===")
try:
    query = '"product manager" remote hiring'
    url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}&count=10"
    st, html = fetch(url)
    print(f"HTTP {st}, {len(html)} chars")
    b_algo = len(re.findall(r'b_algo', html))
    print(f"b_algo occurrences: {b_algo}")
    links = re.findall(r'href="(https?://[^"]+)"', html)
    ext = [u for u in links if "bing.com" not in u and "microsoft.com" not in u and "go.microsoft" not in u][:15]
    print(f"External links: {len(ext)}")
    for u in ext[:10]:
        print(f"  {u[:80]}")
    if "captcha" in html.lower() or "challenge" in html.lower():
        print("CAPTCHA/anti-bot detected")
    # Look for actual result content
    title_tags = re.findall(r'<title>(.*?)</title>', html, re.DOTALL)
    print(f"Page title: {title_tags[:1]} {title_tags[0][:80] if title_tags else 'N/A'}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")

# 3. Wellfound
print("\n=== WELLFOUND ===")
try:
    st, html = fetch("https://wellfound.com/jobs")
    print(f"HTTP {st}, {len(html)} chars")
    rel_links = re.findall(r'href="(/jobs/\d+[^\"]+)"', html)
    abs_links = re.findall(r'href="(https://wellfound\.com/jobs/\d+[^\"]+)"', html)
    print(f"Relative /jobs/N links: {len(rel_links)}")
    print(f"Absolute job links: {len(abs_links)}")
    if rel_links:
        for l in rel_links[:5]:
            print(f"  {l}")
    next_data = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if next_data:
        print(f"__NEXT_DATA__ found ({len(next_data.group(1))} chars)")
    else:
        print("No __NEXT_DATA__")
    if "captcha" in html.lower() or "cloudflare" in html.lower() or "javascript required" in html.lower():
        print("Possible anti-bot detected")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")

# 4. HN Algolia
print("\n=== HN ALGOLIA ===")
try:
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc)
    params = {
        "query": "Ask HN: Who is hiring?",
        "restrictSearchableAttributes": "title",
        "tags": "story",
        "hitsPerPage": 5,
        "numericFilters": f"created_at_i>{int((now - datetime.timedelta(days=30)).timestamp())}",
    }
    url = "https://hn.algolia.com/api/v1/search?" + urllib.parse.urlencode(params)
    st, body = fetch(url)
    data = json.loads(body)
    hits = data.get("hits", [])
    print(f"HTTP {st}, {len(hits)} hiring stories")
    if hits:
        h = hits[0]
        print(f"Latest: {h.get('title','')} id={h.get('objectID','')} created={h.get('created_at','')}")
        # Fetch the thread and look for PM keywords
        hn_url = f"https://news.ycombinator.com/item?id={h.get('objectID','')}"
        st2, html2 = fetch(hn_url)
        print(f"  Thread page: HTTP {st2}, {len(html2)} chars")
        pm_kw = ["product manager","ai product","technical product","growth product","associate product","junior product","product owner","ai engineer","automation engineer","workflow engineer"]
        text = re.sub(r'<[^>]+>', '\n', html2)
        lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 30]
        pm_lines = [l for l in lines if any(k in l.lower() for k in pm_kw)]
        print(f"  Lines with PM keywords: {len(pm_lines)}")
        for l in pm_lines[:5]:
            print(f"    {l[:120]}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
