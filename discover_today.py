#!/usr/bin/env python3
"""Job discovery scan — processes cached sources + live API checks."""
import json, re, sqlite3, urllib.request, html as html_mod
from datetime import datetime, timezone, timedelta

DB_PATH = r'C:\Users\rotim\AppData\Local\hermes\skills\job-hunting\shared/applications.db'
SKILL_ROOT = r'C:\Users\rotim\AppData\Local\hermes\skills\job-hunting'

TITLE_VARIANTS = [
    "product manager", "ai product manager", "ai engineer",
    "automation engineer", "associate product manager", "junior product manager",
    "workflow engineer", "product owner", "technical product manager",
    "growth product manager", "ai/ml product manager"
]
TITLE_VARIANTS_ORIG = [
    "Product Manager", "AI Product Manager", "AI Engineer",
    "Automation Engineer", "Associate Product Manager", "Junary Product Manager",
    "Workflow Engineer", "Product Owner", "Technical Product Manager",
    "Growth Product Manager", "AI/ML Product Manager"
]
SALARY_FLOOR = 36000  # USD/year

def normalize_title(title):
    """Normalize title for fingerprinting — strip level suffixes, punctuation."""
    t = title.lower().strip()
    t = re.sub(r'\s*\(remote\)\s*', '', t)
    t = re.sub(r'\s*-\s*contract\s*', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\s*#\s*[ivx]+\s*$', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\s*\(entry\)\s*$', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\s*\(junior\)\s*$', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\s*\(senior\)\s*$', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\s*\(lead\)\s*$', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\s*\(principal\)\s*$', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\s*\(staff\)\s*$', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\s*\[\d+\]\s*$', '', t)
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

def parse_salary_min(s):
    if not s: return None
    # Try $150k-$200k or $150,000 - $200,000
    nums = re.findall(r'\$?([\d,]+(?:\.\d+)?)', s.replace(',', ''))
    if nums:
        try: return float(nums[0]) * 1000 if 'k' in s.lower() else float(nums[0])
        except: pass
    # Try $150k
    k_match = re.search(r'\$?([\d.]+)k', s, re.IGNORECASE)
    if k_match: return float(k_match.group(1)) * 1000
    return None

def resolve_posted_at(raw, now):
    """Resolve relative date string to ISO timestamp. Returns (posted_at, priority)."""
    pr = raw.lower().strip() if raw else ""
    posted_at = now.strftime('%Y-%m-%dT%H:%M:%SZ')
    priority = 'normal'
    
    try:
        if 'yesterday' in pr or '1 day ago' in pr:
            posted_at = (now - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
        elif m := re.match(r'^(\d+) days? ago$', pr):
            posted_at = (now - timedelta(days=int(m.group(1)))).strftime('%Y-%m-%dT%H:%M:%SZ')
        elif '1 week ago' in pr or 'a week' in pr:
            posted_at = (now - timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%SZ')
        elif '2 weeks ago' in pr:
            posted_at = (now - timedelta(weeks=2)).strftime('%Y-%m-%dT%H:%M:%SZ')
        elif 'today' in pr or 'just now' in pr or '1 hour' in pr or '2 hours' in pr:
            posted_at = now.strftime('%Y-%m-%dT%H:%M:%SZ')
        elif m := re.match(r'^(\d+) hours? ago$', pr):
            posted_at = (now - timedelta(hours=int(m.group(1)))).strftime('%Y-%m-%dT%H:%M:%SZ')
        else:
            posted_at = now.strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception:
        posted_at = now.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    # Check if under 24h
    try:
        posted_dt = datetime.strptime(posted_at, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
        age_hours = (now - posted_dt).total_seconds() / 3600
        if age_hours <= 24:
            priority = 'high'
    except:
        pass
    
    return posted_at, priority

# === Connect to DB ===
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# Check daily cap
c.execute("SELECT COUNT(*) FROM applications WHERE date(discovered_at) = date('now') AND status IN ('discovered', 'building', 'staged', 'awaiting_approval')")
today_count = c.fetchone()[0]
daily_cap = 15
remaining_slots = daily_cap - today_count

# Load existing fingerprints and URLs
c.execute("SELECT posting_fingerprint FROM applications WHERE posting_fingerprint IS NOT NULL")
existing_fingerprints = set(row[0] for row in c.fetchall())
c.execute("SELECT posting_url FROM applications WHERE posting_url IS NOT NULL")
existing_urls = set(row[0] for row in c.fetchall())
c.execute("SELECT posting_url FROM posting_sources WHERE posting_url IS NOT NULL")
for row in c.fetchall():
    existing_urls.add(row[0])

print(f"DB state: {len(existing_fingerprints)} fingerprints, {len(existing_urls)} URLs")
print(f"Daily cap: {daily_cap}, today queued: {today_count}, remaining: {remaining_slots}")

now = datetime.now(timezone.utc)
print(f"Scan time: {now.strftime('%Y-%m-%dT%H:%M:%SZ')}")

# === Source 1: Wellfound (scrape_and_filter) ===
# Parse the cached HTML file
print("\n=== Source: Wellfound (scrape_and_filter) ===")
wellfound_results = []
try:
    with open(f'{SKILL_ROOT}/wellfound_pm_search.html', 'r', encoding='utf-8') as f:
        wf_html = f.read()
    
    job_links = re.findall(r'href="(/jobs/\d+-[^"]+)"', wf_html)
    job_links = list(dict.fromkeys(job_links))  # dedupe
    print(f"  Found {len(job_links)} job links on page")
    
    for link in job_links:
        pos = wf_html.find(f'href="{link}"')
        if pos == -1: continue
        start = max(0, pos - 100)
        end = min(len(wf_html), pos + 1500)
        ctx = wf_html[start:end]
        
        # Title
        title_match = re.search(r'>(.*?)</a>', ctx, re.DOTALL)
        title = ""
        if title_match:
            title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
            title = html_mod.unescape(title)
        
        # Company
        co_match = re.search(r'<span>([^<]*?)<!-- --> • </span>', ctx)
        company = co_match.group(1).strip() if co_match else ""
        company = html_mod.unescape(company)
        
        # Meta (location, salary, posted date)
        meta_match = re.search(r'text-gray-700">(.*?)</span>\s*</div>\s*<div', ctx, re.DOTALL)
        if not meta_match:
            meta_match = re.search(r'text-gray-700">(.*?)</span>', ctx, re.DOTALL)
        
        location = ""
        salary = ""
        posted_raw = ""
        
        if meta_match:
            meta_raw = re.sub(r'<[^>]+>', '', meta_match.group(1)).strip()
            meta_raw = html_mod.unescape(meta_raw)
            parts = [p.strip() for p in meta_raw.split('•')]
            for p in parts:
                pl = p.lower().strip().rstrip('%')
                if any(w in pl for w in ['yesterday', 'today', 'ago', 'hour', 'min', 'days ago', 'week', 'weeks ago', 'day', 'mon,', 'tue,', 'wed,', 'thu,', 'fri,', 'sat,', 'sun,']):
                    posted_raw = p
                elif '$' in p or 'k' in pl or 'usd' in pl or re.search(r'\d+k', pl) or re.search(r'\$[\d,]+', p):
                    salary = p
                elif pl and len(p) > 2:
                    location = p
        
        if title and company:
            wellfound_results.append({
                'company': company,
                'title': title,
                'url': f'https://wellfound.com{link}',
                'location': location or 'Remote',
                'salary': salary,
                'posted_at_raw': posted_raw or None,
                'source_board': 'Wellfound',
                'ats_platform': 'wellfound'
            })
    print(f"  Extracted {len(wellfound_results)} jobs with title+company")
except FileNotFoundError:
    print("  wellfound_pm_search.html not found — skipping")
except Exception as e:
    print(f"  ERROR: {e}")

# === Source 2: RemoteOK API (scrape_and_filter) ===
print("\n=== Source: RemoteOK (scrape_and_filter) ===")
remoteok_results = []
try:
    req = urllib.request.Request('https://remotive.com/api/remote-jobs',
        headers={'User-Agent': 'Mozilla/5.0'})
    resp = urllib.request.urlopen(req, timeout=15)
    data = json.loads(resp.read().decode())
    jobs = data.get('jobs', [])
    print(f"  RemoteOK API returned {len(jobs)} jobs")
    for j in jobs:
        title = j.get('title', '')
        if title_matches_variant(title):
            remoteok_results.append({
                'company': j.get('company_name', ''),
                'title': title,
                'url': j.get('url', ''),
                'location': j.get('candidate_required_location', '') or j.get('location', '') or 'Remote',
                'salary': j.get('salary', '') or '',
                'posted_at_raw': None,  # API doesn't always have date
                'source_board': 'RemoteOK',
                'ats_platform': 'direct'
            })
    print(f"  Matching PM roles: {len(remoteok_results)}")
except Exception as e:
    print(f"  RemoteOK API error: {e} — BLOCKED for this run")

# Also try the full jobs page (not just PM search)
print("\n=== Source: RemoteOK category pages ===")
remotive_results = []
for cat in ['product', 'project-management', 'leadership', 'data', 'design']:
    try:
        req = urllib.request.Request(f'https://remotive.com/remote-jobs/{cat}/',
            headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=10)
        html = resp.read().decode('utf-8', errors='replace')
        # Find job links
        links = re.findall(r'href="(https://remotive\.com/remote-jobs/[^\"]+)"', html)
        print(f"  Category '{cat}': {len(links)} links found")
    except Exception as e:
        print(f"  Category '{cat}': error — {e}")

# === Collect all candidates and process ===
all_candidates = wellfound_results + remoteok_results

print(f"\n=== Processing {len(all_candidates)} candidates ===")
included = []
duplicates = []
non_matches = []
source_breakdown = {}

for p in all_candidates:
    src = p['source_board']
    source_breakdown[src] = source_breakdown.get(src, 0) + 1
    
    fp = compute_fingerprint(p['company'], p['title'], p['location'])
    
    # Check duplicates
    if p['url'] in existing_urls:
        duplicates.append((p, 'existing URL'))
        continue
    if fp in existing_fingerprints:
        duplicates.append((p, f'fingerprint: {fp}'))
        continue
    
    # Check title match
    if not title_matches_variant(p['title']):
        non_matches.append((p, 'title mismatch'))
        continue
    
    # Check salary floor
    if p['salary']:
        min_sal = parse_salary_min(p['salary'])
        if min_sal is not None and min_sal < SALARY_FLOOR:
            non_matches.append((p, f'salary ${min_sal} below floor ${SALARY_FLOOR}'))
            continue
    
    # All checks passed
    included.append(p)

# === Apply daily cap ===
print(f"\n=== Daily cap: {daily_cap}, today: {today_count}, remaining: {remaining_slots} ===")
to_queue = included[:remaining_slots] if remaining_slots > 0 else []
cap_skipped = len(included) - len(to_queue) if remaining_slots <= 0 else 0

if remaining_slots <= 0:
    cap_skipped = len(included)

# === Insert into DB ===
inserted = 0
for p in to_queue:
    fp = compute_fingerprint(p['company'], p['title'], p['location'])
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
         'remote' if (p['location'].lower().find('remote') >= 0) else 'hybrid', 'mid'))
    
    app_id = c.lastrowid
    
    c.execute("""INSERT INTO posting_sources 
        (application_id, posting_url, source_name, discovered_by, is_canonical)
        VALUES (?, ?, ?, ?, ?)""",
        (app_id, p['url'], src.lower(), 'job_1_boards', 1))
    
    inserted += 1
    print(f"  QUEUED #{inserted}: {p['company']} | {p['title']} | {p['url']} | priority={priority}")

conn.commit()
conn.close()

# === Print summary ===
print(f"\n{'='*60}")
print("DISCOVERY SCAN SUMMARY")
print(f"{'='*60}")
print(f"Sources checked: {list(source_breakdown.keys())}")
wf_count = source_breakdown.get('Wellfound', 0)
ro_count = source_breakdown.get('RemoteOK', 0)
wf_status = 'BLOCKED (login wall)' if wf_count == 0 else f'OK -- {wf_count} candidates'
ro_status = 'BLOCKED (403)' if ro_count == 0 else f'OK -- {ro_count} candidates'
print(f"  Wellfound: {wf_status}")
print(f"  RemoteOK: {ro_status}")
print(f"  LinkedIn: BLOCKED (sign-in wall)")
print(f"  Indeed: BLOCKED (sign-in wall)")
print(f"Total candidates found: {len(all_candidates)}")
print(f"New (not duplicate): {len(included)}")
print(f"Duplicates skipped: {len(duplicates)}")
print(f"Non-matches (title/salary): {len(non_matches)}")
print(f"Daily cap: {daily_cap} | Today: {today_count} | Remaining: {remaining_slots}")
print(f"Queued: {inserted}")
if cap_skipped > 0:
    print(f"Cap-skipped: {cap_skipped}")
print(f"\nNon-matches detail:")
for p, reason in non_matches:
    print(f"  {p['company']} | {p['title']} — {reason}")
print(f"\nDuplicates detail:")
for p, reason in duplicates:
    print(f"  {p['company']} | {p['title']} — {reason}")
