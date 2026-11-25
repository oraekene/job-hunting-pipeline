#!/usr/bin/env python
"""Extended scan: Remotive categories, direct board scrapes, more Bing queries."""
import json, re, sqlite3, urllib.request, urllib.parse, html as html_mod
from datetime import datetime, timezone, timedelta

DB_PATH = r'C:\Users/rotim/AppData/Local/hermes/skills/job-hunting/shared/applications.db'
SKILL_ROOT = r'C:\Users/rotim/AppData/Local/hermes/skills/job-hunting'

TITLE_VARIANTS = [
    "product manager", "ai product manager", "ai engineer",
    "automation engineer", "associate product manager", "junior product manager",
    "workflow engineer", "product owner", "technical product manager",
    "growth product manager", "ai/ml product manager"
]
SALARY_FLOOR = 36000

def normalize_title(title):
    t = title.lower().strip()
    for pat in [r'\s*\(remote\)\s*', r'\s*-\s*contract\s*', r'\s*\(entry\)\s*$',
                r'\s*\(junior\)\s*$', r'\s*\(senior\)\s*$', r'\s*\(lead\)\s*$',
                r'\s*\(principal\)\s*$', r'\s*\(staff\)\s*$', r'\s*#\s*[ivx]+\s*$',
                r'\s*\[\d+\]\s*$']:
        t = re.sub(pat, '', t, flags=re.IGNORECASE)
    t = re.sub(r'[^\w\s]', '', t).strip()
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def normalize_location(loc):
    l = loc.lower().strip()
    l = re.sub(r'\s*\+\s*\d+\s*more\s*', '', l)
    l = re.sub(r'[^\w\s]', '', l).strip()
    l = re.sub(r'\s+', ' ', l).strip()
    return l

def compute_fingerprint(company, title, location):
    return f"{company.lower().strip()}|{normalize_title(title)}|{normalize_location(location)}"

def title_matches_variant(title):
    tl = title.lower()
    for variant in TITLE_VARIANTS:
        if variant in tl:
            return True
    return False

def parse_salary(s):
    if not s: return (None, None, s or '')
    sl = s.lower().strip()
    is_hourly = '/hour' in sl or 'per hour' in sl
    amounts = []
    for m in re.finditer(r'\$?\s*([\d,.]+)\s*(k|thousand)?', sl):
        val = float(m.group(1).replace(',', ''))
        if m.group(2): val *= 1000
        amounts.append(val)
    if not amounts: return (None, None, s)
    min_val, max_val = min(amounts), max(amounts)
    if is_hourly: min_val *= 2080; max_val *= 2080
    return (min_val, max_val, s)

def resolve_posted_at(raw, now):
    pr = raw.lower().strip() if raw else ""
    posted_at = now.strftime('%Y-%m-%dT%H:%M:%SZ')
    priority = 'normal'
    try:
        if 'yesterday' in pr or '1 day ago' in pr:
            posted_at = (now - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
        elif re.match(r'^(\d+) days? ago$', pr):
            posted_at = (now - timedelta(days=int(re.match(r'^(\d+) days? ago$', pr).group(1)))).strftime('%Y-%m-%dT%H:%M:%SZ')
        elif '1 week ago' in pr or 'a week' in pr:
            posted_at = (now - timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%SZ')
        elif '2 weeks ago' in pr:
            posted_at = (now - timedelta(weeks=2)).strftime('%Y-%m-%dT%H:%M:%SZ')
        elif 'just now' in pr or '1 hour' in pr or '2 hours' in pr or 'today' in pr:
            posted_at = now.strftime('%Y-%m-%dT%H:%M:%SZ')
    except: posted_at = now.strftime('%Y-%m-%dT%H:%M:%SZ')
    try:
        posted_dt = datetime.strptime(posted_at, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
        if (now - posted_dt).total_seconds() / 3600 <= 24: priority = 'high'
    except: pass
    return posted_at, priority

# === DB setup ===
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute("SELECT COUNT(*) FROM applications WHERE date(discovered_at) = date('now') AND status IN ('discovered','building','staged','awaiting_approval')")
today_count = c.fetchone()[0]
daily_cap = 15
remaining_slots = daily_cap - today_count
c.execute("SELECT posting_fingerprint FROM applications WHERE posting_fingerprint IS NOT NULL")
existing_fingerprints = set(row[0] for row in c.fetchall())
c.execute("SELECT posting_url FROM applications WHERE posting_url IS NOT NULL")
existing_urls = set(row[0] for row in c.fetchall())
c.execute("SELECT posting_url FROM posting_sources WHERE posting_url IS NOT NULL")
for row in c.fetchall(): existing_urls.add(row[0])
now = datetime.now(timezone.utc)

print(f"Cap: {daily_cap} | Today: {today_count} | Remaining: {remaining_slots}")

source_results = {}
all_candidates = []

# === Remotive category pages ===
print("\n=== Remotive category pages ===")
remotive_cats = ['product', 'project-management', 'data', 'design', 'devops', 'sales', 'customer-support']
remotive_new = []
for cat in remotive_cats:
    try:
        req = urllib.request.Request(f'https://remotive.com/remote-jobs/{cat}/',
            headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=10)
        html = resp.read().decode('utf-8', errors='replace')
        # Extract job links
        links = re.findall(r'href="(https://remotive\.com/remote-jobs/[^\"]+)"', html)
        links = list(dict.fromkeys(links))
        # Also extract titles from the page
        for link in links:
            # Find the title in the HTML near this link
            pos = html.find(link)
            if pos == -1: continue
            ctx = html[max(0,pos-200):pos+200]
            # Try to find title near the link
            title_match = re.search(r'aria-label="([^"]+)"', ctx)
            title = title_match.group(1) if title_match else ""
            if not title:
                # Try finding in nearby text
                text_parts = re.findall(r'>([^<]+)<', ctx)
                title = text_parts[0].strip() if text_parts else ""
            if title and title_matches_variant(title):
                if link not in existing_urls:
                    remotive_new.append({
                        'company': '', 'title': title, 'url': link,
                        'location': 'Remote', 'salary': '',
                        'posted_at_raw': None,
                        'source_board': 'Remotive', 'ats_platform': 'remotive'
                    })
        print(f"  Category '{cat}': {len(links)} links, {sum(1 for l in links if True)} total")
    except Exception as e:
        print(f"  Category '{cat}': error — {e}")

source_results['Remotive'] = f'OK — {len(remotive_new)} new PM candidates'
all_candidates.extend(remotive_new)

# === Bing search — direct HTML parsing ===
print("\n=== Bing HTML search ===")
bing_new = []
bing_queries = [
    '"AI Product Manager" remote',
    '"Product Manager" remote hiring',
    '"Technical Product Manager" remote',
    '"AI Engineer" remote',
    '"Product Owner" remote',
]
for q in bing_queries:
    search_url = f'https://www.bing.com/search?q={urllib.parse.quote(q)}'
    try:
        req = urllib.request.Request(search_url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'})
        resp = urllib.request.urlopen(req, timeout=10)
        html = resp.read().decode('utf-8', errors='replace')
        
        # Bing organic results: <li class="b_algo"> with <h2><a href="...">
        results = re.findall(r'<h2><a[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a></h2>', html, re.DOTALL)
        print(f"  Query '{q[:40]}...': {len(results)} results")
        for url, anchor in results:
            anchor_text = re.sub(r'<[^>]+>', '', anchor).strip()
            if any(d in url for d in ['bing.com', 'microsoft.com', 'msn.com', 'go.microsoft', 'w3.org']):
                continue
            if title_matches_variant(anchor_text):
                if url not in existing_urls:
                    fp = compute_fingerprint('', anchor_text, 'Remote')
                    if fp not in existing_fingerprints:
                        bing_new.append({
                            'company': '', 'title': anchor_text, 'url': url,
                            'location': 'Remote', 'salary': '',
                            'posted_at_raw': None,
                            'source_board': 'OpenWeb-Bing', 'ats_platform': 'unknown'
                        })
        if results:
            for url, anchor in results[:3]:
                anchor_text = re.sub(r'<[^>]+>', '', anchor).strip()
                print(f"    {anchor_text[:55]} | {url[:70]}")
    except Exception as e:
        print(f"  Query '{q[:40]}...': error — {e}")

source_results['OpenWeb-Bing'] = f'OK — {len(bing_new)} candidates'
all_candidates.extend(bing_new)

# === Process candidates ===
print(f"\n=== Processing {len(all_candidates)} candidates ===")
included = []
duplicates = []
non_matches = []

for p in all_candidates:
    fp = compute_fingerprint(p['company'], p['title'], p['location'] or 'Remote')
    if p['url'] in existing_urls:
        duplicates.append((p, 'existing URL')); continue
    if fp in existing_fingerprints:
        duplicates.append((p, f'fingerprint')); continue
    if not title_matches_variant(p['title']):
        non_matches.append((p, 'title mismatch')); continue
    min_sal, max_sal, sal_raw = parse_salary(p['salary'])
    if min_sal is not None and min_sal < SALARY_FLOOR:
        non_matches.append((p, f'salary ${int(min_sal)} below floor')); continue
    included.append(p)

to_queue = included[:remaining_slots] if remaining_slots > 0 else []
inserted = []
for p in to_queue:
    fp = compute_fingerprint(p['company'], p['title'], p['location'] or 'Remote')
    posted_at, priority = resolve_posted_at(p['posted_at_raw'], now)
    c.execute("""INSERT INTO applications 
        (posting_url, company, role_title, source_board, ats_platform,
         posted_at, posted_at_raw, discovered_at, status, posting_fingerprint, 
         priority, overall_match_score, keyword_match_score, title_matched,
         build_attempts, outcome, salary_disclosed, salary_range, remote_type, seniority)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (p['url'], p['company'], p['title'], p['source_board'], p['ats_platform'],
         posted_at, p['posted_at_raw'], now.strftime('%Y-%m-%dT%H:%M:%SZ'),
         'discovered', fp, priority, 70, 70, 1, 0, 'pending',
         1 if p['salary'] else 0, p['salary'] or None,
         'remote' if 'remote' in (p['location'] or '').lower() else 'hybrid', 'mid'))
    app_id = c.lastrowid
    c.execute("""INSERT INTO posting_sources 
        (application_id, posting_url, source_name, discovered_by, is_canonical)
        VALUES (?, ?, ?, ?, ?)""",
        (app_id, p['url'], p['source_board'].lower(), 'job_1_boards', 1))
    inserted.append(p)
    print(f"  QUEUED #{len(inserted)}: {p['company']} | {p['title']} | {p['url']}")

conn.commit()
conn.close()

print(f"\n{'='*60}")
print("SUMMARY")
print(f"{'='*60}")
for src, status in source_results.items():
    print(f"  {src}: {status}")
print(f"Candidates: {len(all_candidates)} | New: {len(included)} | Dups: {len(duplicates)} | Non-matches: {len(non_matches)}")
print(f"Cap: {daily_cap} | Today: {today_count} | Remaining: {remaining_slots - len(inserted)}")
print(f"Queued this run: {len(inserted)}")
