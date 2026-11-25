#!/usr/bin/env python
"""Focused re-scan: fix salary parsing, check additional sources, insert new."""
import json, re, sqlite3, urllib.request, urllib.parse, html as html_mod
from datetime import datetime, timezone, timedelta

DB_PATH = r'C:\Users\rotim\AppData\Local\hermes\skills\job-hunting\shared/applications.db'
SKILL_ROOT = r'C:\Users\rotim\AppData\Local\hermes\skills\job-hunting'

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
    """Returns (min_annual, max_annual, raw_string) or (None, None, raw)."""
    if not s: return (None, None, s or '')
    sl = s.lower().strip()
    is_hourly = '/hour' in sl or 'per hour' in sl or ' hourly' in sl
    # Extract all dollar amounts with k multipliers
    amounts = []
    for m in re.finditer(r'\$?\s*([\d,.]+)\s*(k|thousand)?', sl):
        val = float(m.group(1).replace(',', ''))
        if m.group(2):  # has 'k' or 'thousand'
            val *= 1000
        amounts.append(val)
    if not amounts:
        return (None, None, s)
    min_val = min(amounts)
    max_val = max(amounts)
    if is_hourly:
        # Convert hourly to annual (2080 hrs/year)
        min_val *= 2080
        max_val *= 2080
    return (min_val, max_val, s)

def resolve_posted_at(raw, now):
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
        elif 'just now' in pr or '1 hour' in pr or '2 hours' in pr:
            posted_at = now.strftime('%Y-%m-%dT%H:%M:%SZ')
        elif m := re.match(r'^(\d+) hours? ago$', pr):
            posted_at = (now - timedelta(hours=int(m.group(1)))).strftime('%Y-%m-%dT%H:%M:%SZ')
        elif 'today' in pr or 'now' in pr:
            posted_at = now.strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception:
        posted_at = now.strftime('%Y-%m-%dT%H:%M:%SZ')
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

c.execute("SELECT COUNT(*) FROM applications WHERE date(discovered_at) = date('now') AND status IN ('discovered', 'building', 'staged', 'awaiting_approval')")
today_count = c.fetchone()[0]
daily_cap = 15
remaining_slots = daily_cap - today_count

c.execute("SELECT posting_fingerprint FROM applications WHERE posting_fingerprint IS NOT NULL")
existing_fingerprints = set(row[0] for row in c.fetchall())
c.execute("SELECT posting_url FROM applications WHERE posting_url IS NOT NULL")
existing_urls = set(row[0] for row in c.fetchall())
c.execute("SELECT posting_url FROM posting_sources WHERE posting_url IS NOT NULL")
for row in c.fetchall():
    existing_urls.add(row[0])

now = datetime.now(timezone.utc)
print(f"DB: {len(existing_fingerprints)} fingerprints, {len(existing_urls)} URLs")
print(f"Cap: {daily_cap} | Today queued: {today_count} | Remaining: {remaining_slots}")

all_candidates = []
source_results = {}

# === Source 1: Wellfound (already processed, but let's try fresh scrape) ===
print("\n=== Wellfound (scrape_and_filter) ===")
wf_count = 0
new_wf = []
try:
    with open(f'{SKILL_ROOT}/wellfound_pm_search.html', 'r', encoding='utf-8') as f:
        wf_html = f.read()
    job_links = re.findall(r'href="(/jobs/\d+-[^"]+)"', wf_html)
    job_links = list(dict.fromkeys(job_links))
    
    for link in job_links:
        pos = wf_html.find(f'href="{link}"')
        if pos == -1: continue
        start = max(0, pos - 100)
        end = min(len(wf_html), pos + 1500)
        ctx = wf_html[start:end]
        
        title_match = re.search(r'>(.*?)</a>', ctx, re.DOTALL)
        title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip() if title_match else ""
        title = html_mod.unescape(title)
        
        co_match = re.search(r'<span>([^<]*?)<!-- --> • </span>', ctx)
        company = co_match.group(1).strip() if co_match else ""
        company = html_mod.unescape(company)
        
        if not title or not company: continue
        if not title_matches_variant(title): continue
        
        url = f'https://wellfound.com{link}'
        if url in existing_urls:
            wf_count += 1  # still counted
            continue
        
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
                if any(w in pl for w in ['yesterday', 'today', 'ago', 'hour', 'min', 'days ago', 'day', 'mon,', 'tue,', 'wed,', 'thu,', 'fri,', 'sat,', 'sun,']):
                    posted_raw = p
                elif '$' in p or re.search(r'\d+k\b', pl) or 'usd' in pl or re.search(r'\d{3,}', pl):
                    salary = p
                elif pl and len(p) > 2:
                    location = p
        
        fp = compute_fingerprint(company, title, location or 'Remote')
        if fp in existing_fingerprints:
            continue
        
        min_sal, max_sal, sal_raw = parse_salary(salary)
        if min_sal is not None and min_sal < SALARY_FLOOR:
            print(f"  SKIP (salary): {company} | {title} | min=${int(min_sal)}")
            continue
        
        new_wf.append({
            'company': company, 'title': title, 'url': url,
            'location': location or 'Remote', 'salary': salary or '',
            'posted_at_raw': posted_raw or None,
            'source_board': 'Wellfound', 'ats_platform': 'wellfound'
        })
    source_results['Wellfound'] = f'OK — {len(job_links)} links, {len(new_wf)} new PM matches'
    all_candidates.extend(new_wf)
except Exception as e:
    source_results['Wellfound'] = f'ERROR — {e}'

# === Source 2: RemoteOK API (Remotive) — with FIXED salary parsing ===
print("\n=== RemoteOK API (Remotive) ===")
ro_new = []
try:
    req = urllib.request.Request('https://remotive.com/api/remote-jobs',
        headers={'User-Agent': 'Mozilla/5.0'})
    resp = urllib.request.urlopen(req, timeout=15)
    data = json.loads(resp.read().decode())
    jobs = data.get('jobs', [])
    
    for j in jobs:
        title = j.get('title', '')
        if not title_matches_variant(title): continue
        url = j.get('url', '')
        if url in existing_urls: continue
        
        company = j.get('company_name', '')
        loc = j.get('candidate_required_location', '') or j.get('location') or 'Remote'
        salary_str = j.get('salary', '') or ''
        
        fp = compute_fingerprint(company, title, loc)
        if fp in existing_fingerprints: continue
        
        min_sal, max_sal, sal_raw = parse_salary(salary_str)
        if min_sal is not None and min_sal < SALARY_FLOOR:
            print(f"  SKIP (salary): {company} | {title} | min=${int(min_sal)}")
            continue
        
        ro_new.append({
            'company': company, 'title': title, 'url': url,
            'location': loc, 'salary': salary_str,
            'posted_at_raw': None,
            'source_board': 'RemoteOK', 'ats_platform': 'direct'
        })
    
    source_results['RemoteOK'] = f'OK — {len(jobs)} total, {len(ro_new)} new PM matches'
    all_candidates.extend(ro_new)
except Exception as e:
    source_results['RemoteOK'] = f'BLOCKED — {e}'

# === Source 3: LinkedIn — BLOCKED ===
source_results['LinkedIn'] = 'BLOCKED — sign-in wall (per env config)'

# === Source 4: Indeed — BLOCKED ===
source_results['Indeed'] = 'BLOCKED — sign-in wall (per env config)'

# === Source 5: Open-web sweep via Bing direct search ===
print("\n=== Open-web sweep (open_web_search) ===")
ow_new = []
try:
    search_terms = [
        '"Product Manager" remote hiring site:greenhouse.io',
        '"AI Product Manager" remote site:lever.co',
        '"Product Manager" remote site:ashbyhq.com',
        '"Product Manager" remote site:wellfound.com',
        '"AI Product Manager" remote site:wellfound.com',
    ]
    
    for term in search_terms:
        search_url = f'https://www.bing.com/search?q={urllib.parse.quote(term)}'
        try:
            req = urllib.request.Request(search_url,
                headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'})
            resp = urllib.request.urlopen(req, timeout=10)
            html = resp.read().decode('utf-8', errors='replace')
        except Exception as e:
            print(f"  Search '{term[:40]}...': error — {e}")
            continue
            
            # Extract organic result links
            links = re.findall(r'<a[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL)
            filtered = []
            for url, anchor in links:
                if any(d in url for d in ['bing.com', 'microsoft.com', 'msn.com', 'go.microsoft',
                                          'w3.org', '.xml', 'microsoft.com']):
                    continue
                anchor_text = re.sub(r'<[^>]+>', '', anchor).strip()
                # Look for job-like titles
                if title_matches_variant(anchor_text) or 'product manager' in anchor_text.lower():
                    filtered.append((url, anchor_text))
            
            print(f"  Search: '{term[:50]}...' -> {len(filtered)} job-like results")
            for url, anchor in filtered[:3]:
                print(f"    {anchor[:50]} | {url[:80]}")
            
            for url, anchor in filtered:
                if url in existing_urls: continue
                if not title_matches_variant(anchor): continue
                ow_new.append({
                    'company': anchor.split('|')[0].strip() if '|' in anchor else '',
                    'title': anchor, 'url': url,
                    'location': 'Remote', 'salary': '',
                    'posted_at_raw': None,
                    'source_board': 'OpenWeb-Bing', 'ats_platform': 'unknown'
                })
    
    source_results['OpenWeb-Bing'] = f'OK — {len(ow_new)} candidates found'
    all_candidates.extend(ow_new)
except Exception as e:
    source_results['OpenWeb-Bing'] = f'ERROR — {e}'

# === Process candidates ===
print(f"\n=== Processing {len(all_candidates)} new candidates ===")
included = []
duplicates = []
non_matches = []

for p in all_candidates:
    fp = compute_fingerprint(p['company'], p['title'], p['location'])
    
    if p['url'] in existing_urls:
        duplicates.append((p, 'existing URL'))
        continue
    if fp in existing_fingerprints:
        duplicates.append((p, f'fingerprint: {fp}'))
        continue
    if not title_matches_variant(p['title']):
        non_matches.append((p, 'title mismatch'))
        continue
    
    min_sal, max_sal, sal_raw = parse_salary(p['salary'])
    if min_sal is not None and min_sal < SALARY_FLOOR:
        non_matches.append((p, f'salary ${int(min_sal)} below floor ${SALARY_FLOOR}'))
        continue
    
    included.append(p)

to_queue = included[:remaining_slots] if remaining_slots > 0 else []

inserted = []
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
         'remote' if 'remote' in (p['location'] or '').lower() else 'hybrid', 'mid'))
    
    app_id = c.lastrowid
    c.execute("""INSERT INTO posting_sources 
        (application_id, posting_url, source_name, discovered_by, is_canonical)
        VALUES (?, ?, ?, ?, ?)""",
        (app_id, p['url'], p['source_board'].lower(), 'job_1_boards', 1))
    
    inserted.append(p)
    print(f"  QUEUED #{len(inserted)}: {p['company']} | {p['title']} | {p['url']} | priority={priority}")

conn.commit()
conn.close()

print(f"\n{'='*60}")
print("SUMMARY")
print(f"{'='*60}")
for src, status in source_results.items():
    print(f"  {src}: {status}")
print(f"Candidates: {len(all_candidates)} | New: {len(included)} | Dups: {len(duplicates)} | Non-matches: {len(non_matches)}")
print(f"Cap: {daily_cap} | Today: {today_count} | Remaining: {remaining_slots}")
print(f"Queued this run: {len(inserted)}")

# Save digest
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
    'included_jobs': [{'company': p['company'], 'title': p['title'], 'url': p['url']} for p in inserted],
}
with open(f'{SKILL_ROOT}/.discovery_results.json', 'w') as f:
    json.dump(digest, f, indent=2)
