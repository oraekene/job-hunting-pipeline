#!/usr/bin/env python3
"""Comprehensive discovery: Remotive API (all jobs), HN Who Is Hiring, Wellfound."""
import urllib.request, json, re, sqlite3, datetime

DB_PATH = "C:/Users/rotim/AppData/Local/hermes/skills/job-hunting/shared/applications.db"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# --- DB state ---
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
existing_urls = set(r[0] for r in cur.execute("SELECT DISTINCT posting_url FROM applications WHERE posting_url IS NOT NULL"))
existing_fps = set(r[0] for r in cur.execute("SELECT posting_fingerprint FROM applications WHERE posting_fingerprint IS NOT NULL"))
source_urls = set(r[0] for r in cur.execute("SELECT DISTINCT posting_url FROM posting_sources WHERE posting_url IS NOT NULL"))
all_known = existing_urls | source_urls
today_queued = cur.execute("SELECT COUNT(*) FROM applications WHERE status='discovered' AND date(discovered_at) = date('now')").fetchone()[0]
conn.close()
print(f"DB: {len(existing_urls)} app URLs, {len(existing_fps)} fingerprints, {len(all_known)} known, {today_queued} queued today")

# --- Title matching ---
PM_KEYWORDS = [
    "product manager", "ai product manager", "technical product manager",
    "growth product manager", "associate product manager", "junior product manager",
    "product owner", "ai engineer", "ai/ml engineer", "machine learning engineer",
    "automation engineer", "workflow engineer", "mlops engineer",
]
def title_matches(title):
    if not title: return False
    tl = title.lower().strip()
    # Decode HTML entities
    tl = re.sub(r'&#x2f;', '/', tl).replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    return any(kw in tl for kw in PM_KEYWORDS)

def normalize_title(title):
    t = (title or "").lower().strip()
    t = re.sub(r'\s*#\d+\s*$', '', t)
    t = re.sub(r'\s*\(\s*[IVX]+\s*\)\s*$', '', t)
    t = re.sub(r'\s*\(\s*(senior|junior|lead|principal|staff|mid|entry|associate)\s*\)\s*$', '', t)
    t = re.sub(r'\s*\(\s*(remote|contract|freelance|temp)\s*\)\s*$', '', t)
    t = re.sub(r'[^\w\s]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def compute_fingerprint(company, role_title, location):
    c = (company or "").lower().strip()
    t = normalize_title(role_title)
    l = re.sub(r'\s+', ' ', (location or "").lower().strip())
    return f"{c}|{t}|{l}"

def parse_posted_date(s):
    if not s: return None, ""
    s = str(s).strip()
    try:
        dt = datetime.datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt, s
    except: pass
    try:
        dt = datetime.datetime.strptime(s, "%Y-%m-%d")
        return dt.replace(tzinfo=datetime.timezone.utc), s
    except: pass
    t = s.lower()
    n = datetime.datetime.now(datetime.timezone.utc)
    if "today" in t or "just now" in t: return n, s
    if "yesterday" in t: return n - datetime.timedelta(days=1), s
    m = re.match(r'(\d+)\s+hour', t)
    if m: return n - datetime.timedelta(hours=int(m.group(1))), s
    m = re.match(r'(\d+)\s+day', t)
    if m: return n - datetime.timedelta(days=int(m.group(1))), s
    return None, s

now = datetime.datetime.now(datetime.timezone.utc)
recent_cutoff = now - datetime.timedelta(hours=24)
week_cutoff = now - datetime.timedelta(days=7)

candidates = []
skipped = []
sources_checked = []
sources_blocked = []

# ─── 1. Remotive API — fetch ALL and filter client-side ─────────────
print("=" * 60)
print("1. Remotive API (all jobs, filter client-side)")
print("=" * 60)
try:
    url = "https://remotive.com/api/remote-jobs?limit=100"
    resp = urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=15)
    data = json.loads(resp.read().decode('utf-8'))
    jobs = data.get("jobs", [])
    print(f"  Total jobs from Remotive API: {len(jobs)}")
    sources_checked.append("remotive-api")
    matched = 0
    for j in jobs:
        title = j.get("title", "")
        if not title_matches(title):
            continue
        matched += 1
        company = j.get("company_name", "").strip()
        jurl = j.get("url", "")
        if not jurl:
            continue
        if jurl in all_known:
            skipped.append(f"DUPLICATE URL (Remotive): {jurl[:80]}")
            continue
        fp = compute_fingerprint(company, title, "Remote")
        if fp in existing_fps:
            skipped.append(f"DUPLICATE FP (Remotive): {fp}")
            continue
        posted_raw = j.get("publication_date", "") or ""
        posted_at, posted_raw_str = parse_posted_date(posted_raw)
        salary_text = j.get("salary", "") or ""
        # Salary check
        if salary_text:
            amounts = re.findall(r'(\d[\d,]*\.?\d*)', salary_text)
            if amounts:
                mx = max(float(a.replace(",", "")) for a in amounts)
                if mx < 36000 * 0.3:
                    skipped.append(f"SALARY (Remotive): {company} | {title} | {salary_text}")
                    continue
        priority = "high" if (posted_at and posted_at > recent_cutoff) or not posted_at else "normal"
        if posted_at and posted_at < week_cutoff:
            skipped.append(f"OLD (Remotive): {company} | {title} | posted {posted_at}")
            continue
        candidates.append({
            "posting_url": jurl, "company": company or "Unknown", "role_title": title,
            "location": "Remote", "posted_at": posted_at.strftime("%Y-%m-%dT%H:%M:%SZ") if posted_at else None,
            "posted_at_raw": posted_raw_str, "salary_disclosed": bool(salary_text), "salary_range": salary_text or None,
            "source_board": "Remotive", "remote_type": "remote",
            "discovered_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "priority": priority,
            "posting_fingerprint": fp,
        })
        print(f"  MATCH: {company} | {title} | priority={priority} | posted={posted_at}")
    print(f"  Total matched: {matched}")
except Exception as e:
    sources_blocked.append({"remotive-api": f"BLOCKED/ERROR: {type(e).__name__}: {str(e)[:150]}"})
    print(f"  Error: {e}")

# ─── 2. HN "Who is Hiring" — parse September thread ───────────────
print("\n" + "=" * 60)
print("2. HN 'Who is Hiring' — September 2026 thread")
print("=" * 60)
try:
    # Find the current "Who is hiring" thread
    params = "?query=Ask+HN:+Who+is+hiring?&restrictSearchableAttributes=title&tags=story&hitsPerPage=5"
    url = "https://hn.algolia.com/api/v1/search?" + params
    resp = urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=15)
    data = json.loads(resp.read().decode('utf-8'))
    hits = data.get("hits", [])
    sources_checked.append("hnrss-who-is-hiring")
    for hit in hits:
        story_id = hit.get("objectID", "")
        created = hit.get("created_at", "")
        print(f"  Story: {hit.get('title','')} (id={story_id}, created={created})")
        # Fetch the HN thread page HTML (not individual comments via API)
        hn_url = f"https://news.ycombinator.com/item?id={story_id}"
        resp2 = urllib.request.urlopen(urllib.request.Request(hn_url, headers=HEADERS), timeout=20)
        hn_html = resp2.read().decode('utf-8', errors='replace')
        # Extract hiring comments - HN uses <td class="ind"> for indentation, <span class="c00"> for text
        # Look for comments that contain PM/AI keywords
        # Parse comment blocks
        # HN comments are in <tr> elements with class "athing" or in <div class="comment">
        # Actually, HN uses: <td class="indy"><div class="comment ...">
        comment_texts = re.findall(r'<div[^>]*class="comment[^"]*"[^>]*>(.*?)</div>\s*</td>', hn_html, re.DOTALL)
        print(f"  Found {len(comment_texts)} comment blocks")
        for ct in comment_texts:
            # Clean HTML
            text = re.sub(r'<[^>]+>', '\n', ct)
            text = re.sub(r'<[^>]+>', '', text)
            text = text.replace('&#x2014;', '—').replace('&amp;', '&').replace('&#x2F;', '/').replace('&lt;', '<').replace('&gt;', '>')
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if len(line) < 20:
                    continue
                if any(kw in line.lower() for kw in ['hiring', 'who is', 'thread', 'discussion', 'guidelines', 'show hn', 'ask hn']):
                    continue
                if title_matches(line):
                    # Parse HN hiring format: Company | Role | Location | ...
                    parts = [p.strip() for p in line.split('|')]
                    if len(parts) < 2:
                        continue
                    company = ""
                    role = ""
                    job_url = ""
                    url_match = re.search(r'((?:https?://|www\.)[^\s|]+)', line)
                    job_url = url_match.group(1) if url_match else hn_url
                    for part in parts[:6]:
                        if title_matches(part) and not role:
                            role = part
                        elif len(part) > 2 and len(part) < 60 and not company:
                            # Check it's not a metadata part
                            pl = part.lower()
                            if not any(skip in pl for skip in ['remote', 'hiring', 'contract', 'full-time', 'part-time',
                                'visa', 'salary', 'compensation', '$', 'http', 'us', 'canada', 'worldwide',
                                'onsite', 'hybrid', 'equity', 'stock', 'pto', 'benefits', 'w-2', '1099',
                                'today', 'yesterday', 'day ago', 'week ago', 'month', 'year', 'usd', 'eur', 'gbp', 'ngn']):
                                if not re.search(r'[\d\$]', pl) and re.search(r'[a-z]', pl):
                                    company = part
                    if role and title_matches(role) and company:
                        fp = compute_fingerprint(company, role, "remote")
                        if fp in existing_fps:
                            skipped.append(f"DUPLICATE FP (HN): {fp}")
                            continue
                        if job_url in all_known:
                            skipped.append(f"DUPLICATE URL (HN): {job_url[:80]}")
                            continue
                        candidates.append({
                            "posting_url": job_url, "company": company, "role_title": role,
                            "location": "remote", "posted_at": None, "posted_at_raw": "",
                            "salary_disclosed": False, "salary_range": None,
                            "source_board": "Hacker News (Who is Hiring)", "remote_type": "remote",
                            "discovered_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "priority": "high", "posting_fingerprint": fp,
                        })
                        print(f"    -> MATCH: {company} | {role} | {job_url[:60]}")
except Exception as e:
    sources_blocked.append({"hnrss-who-is-hiring": f"BLOCKED/ERROR: {type(e).__name__}: {str(e)[:150]}"})
    print(f"  Error: {e}")

# ─── 3. Wellfound — try fetching the job listing page ───────────────
print("\n" + "=" * 60)
print("3. Wellfound")
print("=" * 60)
# Wellfound is JS-rendered, so we need to look at the raw HTML for embedded data
try:
    url = "https://wellfound.com/jobs"
    resp = urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=15)
    wf_html = resp.read().decode('utf-8', errors='replace')
    print(f"  Wellfound: HTTP {resp.status}, body={len(wf_html)} chars")
    sources_checked.append("wellfound")
    # Look for embedded JSON data
    # Wellfound uses Next.js / React - look for __NEXT_DATA__
    next_data = re.search(r'__NEXT_DATA__.*?(\{.*?\})', wf_html, re.DOTALL)
    if next_data:
        print(f"  Found __NEXT_DATA__")
        try:
            data = json.loads(next_data.group(1))
            # Search for job data in the JSON
            def find_jobs(obj, path=""):
                found = []
                if isinstance(obj, dict):
                    if "jobPosting" in str(obj).lower() or "jobListings" in str(obj).lower() or "jobs" in str(obj).lower():
                        found.append((path, obj))
                    for k, v in obj.items():
                        found.extend(find_jobs(v, f"{path}.{k}"))
                elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                        found.extend(find_jobs(item, f"{path}[{i}]"))
                return found
            jobs = find_jobs(data)
            print(f"  Potential job data nodes: {len(jobs)}")
            for p, j in jobs[:3]:
                print(f"    Path: {p}")
                s = json.dumps(j)[:200]
                print(f"    Data: {s}")
        except Exception as e:
            print(f"  JSON parse error: {e}")
    else:
        # Look for job links in the HTML
        job_links = re.findall(r'href="(/jobs/[\d-]+[^"]*)"', wf_html)
        print(f"  Job links found: {len(job_links)}")
        # Also look for data in script tags
        for script in re.findall(r'<script[^>]*>(.*?)</script>', wf_html, re.DOTALL):
            if 'product manager' in script.lower() or 'ai product' in script.lower():
                print(f"  Found PM/AI reference in script: {script[:200]}")
except Exception as e:
    sources_blocked.append({"wellfound": f"BLOCKED/ERROR: {type(e).__name__}: {str(e)[:150]}"})
    print(f"  Error: {e}")

# ─── 4. Bing search with better query ───────────────────────────────
print("\n" + "=" * 60)
print("4. Bing search (open-web sweep)")
print("=" * 60)
bing_queries = [
    '"AI product manager" remote hiring',
    '"technical product manager" remote site:greenhouse.io OR site:lever.co',
    '"product manager" AI remote site:lever.co OR site:greenhouse.io',
    '"AI engineer" remote site:lever.co OR site:greenhouse.io',
    '"automation engineer" remote site:lever.co',
]
import urllib.parse
for query in bing_queries:
    try:
        encoded = urllib.parse.quote(query)
        bing_url = f"https://www.bing.com/search?q={encoded}&count=20"
        resp = urllib.request.urlopen(urllib.request.Request(bing_url, headers=HEADERS), timeout=15)
        html = resp.read().decode('utf-8', errors='replace')
        print(f"  Bing '{query[:40]}': HTTP {resp.status}, {len(html)} chars")
        # Extract actual result URLs from Bing's redirect links
        # Bing uses /url?q= or r.bing.com redirects or direct bing.com/ck/a links
        # Get the actual destination URLs
        actual_urls = []
        # Method 1: /url?q= format
        urls1 = re.findall(r'/url\?q=(https?://[^&]+)', html)
        actual_urls.extend(urls1)
        # Method 2: Check if results have cite tags
        cites = re.findall(r'<cite>(.*?)</cite>', html, re.DOTALL)
        if cites:
            for c in cites[:5]:
                c = re.sub(r'<[^>]+>', '', c).strip()
                if c and not any(b in c for b in ['bing.com', 'microsoft.com']):
                    actual_urls.append(c)
        # Method 3: Look for h2 a tags (search results)
        h2s = re.findall(r'<h[12][^>]*>(.*?)</h[12]>', html, re.DOTALL)
        if h2s:
            for h2 in h2s:
                a_match = re.search(r'href="([^"]+)"', h2)
                if a_match:
                    href = a_match.group(1)
                    text = re.sub(r'<[^>]+>', '', h2).strip()
                    if href and not 'bing.com' in href:
                        # Decode Bing redirect if needed
                        if '/url?q=' in href:
                            actual_urls.append(href)
                        print(f"    Result: {text[:60]} -> {href[:80]}")
        # Filter to non-bing
        real_urls = [u for u in actual_urls if not any(b in u for b in ['bing.com', 'microsoft.com', 'r.bing', 'th.bing'])]
        print(f"    Real URLs: {len(real_urls)}")
        for u in real_urls[:5]:
            print(f"    - {u[:100]}")
        sources_checked.append(f"open_web_bing_{query[:30]}")
    except Exception as e:
        sources_blocked.append({f"open_web_bing_{query[:30]}": f"BLOCKED/ERROR: {type(e).__name__}: {str(e)[:100]}"})
        print(f"  Error: {e}")

# ─── Intra-run dedup & cap ──────────────────────────────────────────
print("\n" + "=" * 60)
print("DEDUP + DAILY CAP")
print("=" * 60)
daily_cap = 15
remaining = daily_cap - today_queued
seen_fp = set()
unique = []
for p in candidates:
    if p["posting_fingerprint"] not in seen_fp:
        seen_fp.add(p["posting_fingerprint"])
        unique.append(p)
    else:
        skipped.append(f"INTRA-RUN DUP: {p['company']} | {p['role_title']}")
to_queue = unique[:max(0, remaining)]
overflow = unique[max(0, remaining):]

print(f"Total candidates: {len(candidates)}")
print(f"After intra-run dedup: {len(unique)}")
print(f"Daily cap: {daily_cap}, today_queued: {today_queued}, remaining: {remaining}")
print(f"To queue: {len(to_queue)}, overflow (cap): {len(overflow)}")

# Insert into DB
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
inserted = 0
for p in to_queue:
    try:
        cur.execute("""
            INSERT INTO applications
            (posting_url, company, role_title, source_board, posted_at, posted_at_raw,
             discovered_at, priority, posting_fingerprint, remote_type, salary_disclosed,
             salary_range, status, last_failure_stage, ats_platform)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'discovered', NULL, ?)
        """, (p["posting_url"], p["company"], p["role_title"], p["source_board"],
              p.get("posted_at"), p.get("posted_at_raw", ""), p["discovered_at"], p["priority"],
              p["posting_fingerprint"], p["remote_type"], p["salary_disclosed"],
              p.get("salary_range"), p.get("ats_platform", None)))
        app_id = cur.lastrowid
        cur.execute("""
            INSERT INTO posting_sources (application_id, posting_url, source_name, discovered_by, is_canonical)
            VALUES (?, ?, ?, 'job_1_boards', 1)
        """, (app_id, p["posting_url"], p["source_board"]))
        conn.commit()
        inserted += 1
        print(f"  INSERTED #{app_id}: {p['company']} | {p['role_title']} | {p['source_board']} | priority={p['priority']}")
    except Exception as e:
        conn.rollback()
        print(f"  INSERT FAILED: {p.get('company', '?')} | {p.get('role_title', '?')} | {e}")
conn.close()

# Summary
print(f"\n{'='*60}")
print(f"DISCOVERY COMPLETE")
print(f"{'='*60}")
print(f"Sources checked: {sources_checked}")
print(f"Sources blocked: {[list(b.keys())[0] for b in sources_blocked]}")
print(f"Total candidates found: {len(candidates)}")
print(f"Unique candidates: {len(unique)}")
print(f"Inserted into DB: {inserted}")
print(f"Overflow (cap): {len(overflow)}")
print(f"Skipped/duplicates: {len(skipped)}")
print(f"Remaining slots: {daily_cap - today_queued - inserted}")
print(f"High priority: {len([p for p in unique if p.get('priority') == 'high'])}")
print(f"Normal priority: {len([p for p in unique if p.get('priority') == 'normal'])}")
