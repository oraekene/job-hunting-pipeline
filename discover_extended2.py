#!/usr/bin/env python
"""Extended scan v2: try RemoteOK API, Wellfound API, workingnomads."""
import json, re, sqlite3, urllib.request, urllib.parse
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
    return re.sub(r'\s+', ' ', t).strip()

def normalize_location(loc):
    l = loc.lower().strip()
    l = re.sub(r'\s*\+\s*\d+\s*more\s*', '', l)
    l = re.sub(r'[^\w\s]', '', l).strip()
    return re.sub(r'\s+', ' ', l).strip()

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
    sl = str(s).lower().strip()
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

def fetch_url(url, timeout=10):
    req = urllib.request.Request(url,
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'})
    resp = urllib.request.urlopen(req, timeout=timeout)
    return resp.read().decode('utf-8', errors='replace')

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

# === Source: RemoteOK API (different from Remotive API) ===
print("\n=== RemoteOK API ===")
ro_new = []
try:
    data = json.loads(fetch_url('https://remoteok.com/api'))
    if isinstance(data, list):
        jobs = data
    else:
        jobs = data.get('jobs', data.get('data', []))
    print(f"  API returned {len(jobs)} jobs")
    for j in jobs:
        title = j.get('title', '') or j.get('position', '')
        if not title or not title_matches_variant(title): continue
        url = j.get('url', '') or j.get('apply_url', '') or j.get('company_url', '')
        if not url or url in existing_urls: continue
        company = j.get('company', '') or j.get('company_name', '')
        loc = j.get('location', '') or 'Remote'
        salary = j.get('salary', '') or j.get('salary_range', '')
        epoch = j.get('epoch', 0) or j.get('timestamp', 0)
        
        posted_at_raw = None
        if epoch:
            from datetime import timezone as tz
            posted_at_raw = datetime.fromtimestamp(int(epoch), tz=tz.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        
        fp = compute_fingerprint(company, title, loc)
        if fp in existing_fingerprints: continue
        
        min_sal, max_sal, sal_raw = parse_salary(salary)
        if min_sal is not None and min_sal < SALARY_FLOOR:
            print(f"  SKIP: {company} | {title} | salary ${int(min_sal)}")
            continue
        
        ro_new.append({
            'company': company, 'title': title, 'url': url,
            'location': loc, 'salary': salary or '',
            'posted_at_raw': posted_at_raw,
            'source_board': 'RemoteOK', 'ats_platform': 'direct'
        })
    source_results['RemoteOK-API'] = f'OK — {len(jobs)} total, {len(ro_new)} new PM matches'
except Exception as e:
    source_results['RemoteOK-API'] = f'BLOCKED — {e}'
    print(f"  Error: {e}")
all_candidates.extend(ro_new)

# === Source: Wellfound API ===
print("\n=== Wellfound API ===")
wf_new = []
try:
    # Try Wellfound's internal API
    api_url = 'https://wellfound.com/api/v2/jobs?keywords=product%20manager&remote=true'
    data = json.loads(fetch_url(api_url))
    if isinstance(data, dict):
        jobs = data.get('jobs', data.get('results', []))
    else:
        jobs = data
    print(f"  API returned {len(jobs)} jobs")
    for j in jobs:
        title = j.get('title', '') or j.get('position', '')
        if not title or not title_matches_variant(title): continue
        url = j.get('url', '') or j.get('apply_url', '')
        if url and url not in existing_urls:
            if not url.startswith('http'): url = 'https://wellfound.com' + url
            if url in existing_urls: continue
            company = j.get('company', '') or j.get('company_name', '') or j.get('organization', '')
            loc = j.get('location', '') or 'Remote'
            salary = j.get('salary', '') or j.get('compensation', '')
            fp = compute_fingerprint(company, title, loc)
            if fp in existing_fingerprints: continue
            min_sal, max_sal, sal_raw = parse_salary(salary)
            if min_sal is not None and min_sal < SALARY_FLOOR: continue
            wf_new.append({
                'company': company, 'title': title, 'url': url,
                'location': loc, 'salary': salary or '',
                'posted_at_raw': None,
                'source_board': 'Wellfound', 'ats_platform': 'wellfound'
            })
    source_results['Wellfound-API'] = f'OK — {len(jobs)} total, {len(wf_new)} new'
except Exception as e:
    source_results['Wellfound-API'] = f'ERROR — {e}'
    print(f"  Error: {e}")
all_candidates.extend(wf_new)

# === Source: Working Nomads ===
print("\n=== Working Nomads ===")
wn_new = []
try:
    xml = fetch_url('https://workingnomads.co/brand/api/jobs')
    jobs = json.loads(xml)
    print(f"  API returned {len(jobs)} jobs")
    for j in jobs:
        title = j.get('title', '')
        if not title or not title_matches_variant(title): continue
        url = j.get('url', '')
        if url in existing_urls: continue
        company = j.get('company', '').replace('Working Nomads', '').strip()
        loc = j.get('location', '') or 'Remote'
        fp = compute_fingerprint(company, title, loc)
        if fp in existing_fingerprints: continue
        wn_new.append({
            'company': company, 'title': title, 'url': url,
            'location': loc, 'salary': '',
            'posted_at_raw': None,
            'source_board': 'WorkingNomads', 'ats_platform': 'workingnomads'
        })
    source_results['WorkingNomads'] = f'OK — {len(jobs)} total, {len(wn_new)} new PM matches'
except Exception as e:
    source_results['WorkingNomads'] = f'ERROR — {e}'
    print(f"  Error: {e}")
all_candidates.extend(wn_new)

# === Process candidates ===
print(f"\n=== Processing {len(all_candidates)} new candidates ===")
included = []
duplicates = []
non_matches = []

for p in all_candidates:
    fp = compute_fingerprint(p['company'], p['title'], p['location'] or 'Remote')
    if p['url'] in existing_urls:
        duplicates.append((p, 'existing URL')); continue
    if fp in existing_fingerprints:
        duplicates.append((p, 'fingerprint')); continue
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
    co = p['company'] or '(unknown)'
    print(f"  QUEUED #{len(inserted)}: {co} | {p['title']} | {p['url']}")

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

# Update gate state
import json as jsonmod
gate = {
    'last_run_at': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
    'sources_checked': list(source_results.keys()),
    'new_found': len(included),
    'duplicates': len(duplicates),
    'filtered_out': len(non_matches),
    'queued': len(inserted),
    'today_queued': today_count + len(inserted),
    'cap_reached': remaining_slots <= 0,
    'remaining_slots': remaining_slots - len(inserted),
    'daily_cap': daily_cap,
}
with open(f'{SKILL_ROOT}/shared/.discovery_gate_state.json', 'w') as f:
    jsonmod.dump(gate, f, indent=2)

# Save results digest
digest = {
    'run_at': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
    'sources': source_results,
    'total_candidates': len(all_candidates),
    'new_found': len(included),
    'duplicates': len(duplicates),
    'non_matches': len(non_matches),
    'queued': len(inserted),
    'daily_cap': daily_cap,
    'today_queued': today_count + len(inserted),
    'remaining_slots': remaining_slots - len(inserted),
    'included_jobs': [{'company': p['company'], 'title': p['title'], 'url': p['url'], 'source': p['source_board']} for p in inserted],
}
with open(f'{SKILL_ROOT}/.discovery_results.json', 'w') as f:
    jsonmod.dump(digest, f, indent=2)
