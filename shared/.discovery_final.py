#!/usr/bin/env python
"""Phase 5: Queue verified Wellfound postings, try Remotive API + HN API."""
import requests, json, re, sqlite3, datetime, base64
from bs4 import BeautifulSoup
import yaml

SKILL_ROOT = "C:/Users/rotim/AppData/Local/hermes/skills/job-hunting"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

with open(f"{SKILL_ROOT}/shared/target-profile.yaml") as f:
    target = yaml.safe_load(f)
title_variants = [tv['title'] for tv in target.get('title_variants', [])]
salary_floor = target.get('salary_floor', {})
companies_exclude = target.get('companies_exclude', [])

conn = sqlite3.connect(f"{SKILL_ROOT}/shared/applications.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()
existing_fingerprints = set(r[0] for r in cur.execute('SELECT posting_fingerprint FROM applications WHERE posting_fingerprint IS NOT NULL'))
existing_urls = set(r[0] for r in cur.execute('SELECT DISTINCT posting_url FROM applications'))
conn.close()

now = datetime.datetime.now(datetime.timezone.utc)
recent_cutoff = now - datetime.timedelta(hours=24)

def normalize_title(title):
    t = title.lower().strip()
    t = re.sub(r'\s*#\d+\s*$', '', t)
    t = re.sub(r'\s*\(\s*[IVX]+\s*\)$', '', t)
    t = re.sub(r'\s*\(\s*(senior|junior|lead|principal|staff|mid|entry|associate)\s*\)$', '', t)
    t = re.sub(r'\s*\(\s*(remote|contract|freelance|temp)\s*\)$', '', t)
    t = re.sub(r'[^\w\s]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def compute_fingerprint(company, role_title, location):
    c = (company or '').lower().strip()
    t = normalize_title(role_title or '')
    l = re.sub(r'\s+', ' ', (location or '').lower().strip())
    if l.startswith('[{') or l.startswith('{'):
        try:
            obj = json.loads(l.replace("'", '"'))
            addr = {}
            if isinstance(obj, list) and obj and isinstance(obj[0], dict):
                addr = obj[0].get('address', {})
            elif isinstance(obj, dict):
                addr = obj.get('address', {})
            if isinstance(addr, dict):
                parts = [addr.get('addressLocality',''), addr.get('addressRegion',''), addr.get('addressCountry','')]
                l = ' '.join(p for p in parts if p).lower().strip()
        except:
            l = 'remote'
    l = re.sub(r'\s+', ' ', l)
    return f"{c}|{t}|{l}"

def extract_location(loc_obj):
    if not loc_obj:
        return 'remote'
    if isinstance(loc_obj, list) and loc_obj and isinstance(loc_obj[0], dict):
        addr = loc_obj[0].get('address', {})
    elif isinstance(loc_obj, dict):
        addr = loc_obj.get('address', {})
    else:
        return str(loc_obj)
    if isinstance(addr, dict):
        parts = [addr.get('addressLocality',''), addr.get('addressRegion',''), addr.get('addressCountry','')]
        return ', '.join(p for p in parts if p) if any(parts) else 'remote'
    return 'remote'

def extract_salary(salary_obj):
    if not salary_obj:
        return '', False
    try:
        if isinstance(salary_obj, str):
            return salary_obj, True
        if isinstance(salary_obj, dict):
            cur_sym = salary_obj.get('currency', '')
            value = salary_obj.get('value', {})
            if isinstance(value, dict):
                mn = value.get('minValue', 0)
                mx = value.get('maxValue', 0)
                unit = value.get('unitText', '')
                if mn and mx:
                    return f"{cur_sym} {mn}-{mx} {unit}", True
            elif isinstance(value, (int, float)):
                return f"{cur_sym} {value}", True
        return str(salary_obj), True
    except:
        return '', False

def extract_posted(posted_raw):
    if not posted_raw:
        return None
    try:
        return datetime.datetime.fromisoformat(posted_raw)
    except:
        pass
    for fmt in ['%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%B %d, %Y', '%b %d, %Y']:
        try:
            dt = datetime.datetime.strptime(posted_raw.strip(), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return dt
        except:
            pass
    t = posted_raw.lower().strip()
    n = datetime.datetime.now(datetime.timezone.utc)
    if 'today' in t or 'just now' in t:
        return n
    if 'yesterday' in t:
        return n - datetime.timedelta(days=1)
    m = re.match(r'(\d+)\s+hour', t)
    if m:
        return n - datetime.timedelta(hours=int(m.group(1)))
    m = re.match(r'(\d+)\s+day', t)
    if m:
        return n - datetime.timedelta(days=int(m.group(1)))
    return None

def title_matches(role_title):
    tl = role_title.lower().strip()
    tn = normalize_title(role_title)
    for v in title_variants:
        vl = v.lower().strip()
        vn = normalize_title(v)
        if vl in tl or tl in vl or vn in tn or tn in vn:
            return True
    return False

def passes_salary(salary_text, floor):
    if not salary_text:
        return True
    text = salary_text.lower()
    amounts = []
    for m in re.finditer(r'(\d[\d,]*\.?\d*)', text):
        try:
            v = float(m.group(1).replace(',', ''))
            if 1000 < v < 1000000:
                amounts.append(v)
        except:
            pass
    if amounts:
        mx = max(amounts)
        fa = floor.get('amount', 0)
        if mx >= fa:
            return True
        if 'month' in text and mx * 12 >= fa:
            return True
        if mx < fa * 0.3:
            return False
    return True

def fetch_job_page(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, 'html.parser')
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    data = data[0]
                if isinstance(data, dict) and data.get('@type') in ('JobPosting', 'job'):
                    title = data.get('title') or data.get('jobTitle', '')
                    ho = data.get('hiringOrganization', '')
                    company = ho.get('name', '') if isinstance(ho, dict) else str(ho)
                    loc = extract_location(data.get('jobLocation', {}))
                    pr = data.get('datePosted', '')
                    pa = extract_posted(pr)
                    st, _ = extract_salary(data.get('baseSalary', {}))
                    return {'title': title, 'company': company, 'location': loc,
                            'posted_raw': pr, 'posted_at': pa, 'salary': st, 'url': url}
            except:
                continue
        return None
    except:
        return None

def try_queue(url, title, company, location, posted_raw, posted_at, salary, source_board):
    if url in existing_urls:
        return None, 'SKIP (URL already in DB)'
    if not title_matches(title):
        return None, 'REJECT (title mismatch)'
    if not passes_salary(salary, salary_floor):
        return None, f'REJECT (salary: {salary})'
    if company and any(c.lower() in company.lower() for c in companies_exclude):
        return None, 'REJECT (company excluded)'
    fp = compute_fingerprint(company, title, location)
    if fp in existing_fingerprints:
        return None, f'SKIP (fingerprint: {fp})'
    priority = 'normal'
    if posted_at and posted_at > recent_cutoff:
        priority = 'high'
    elif not posted_at:
        priority = 'high'
    posting = {
        'posting_url': url, 'company': company or 'Unknown', 'role_title': title,
        'location': location or 'remote', 'posted_at': posted_at.strftime('%Y-%m-%dT%H:%M:%SZ') if posted_at else None,
        'posted_at_raw': posted_raw or '', 'salary_disclosed': bool(salary),
        'salary_range': salary or None, 'source_board': source_board,
        'remote_type': 'remote', 'discovered_at': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'priority': priority, 'posting_fingerprint': fp,
    }
    existing_fingerprints.add(fp)
    existing_urls.add(url)
    return posting, None

new_postings = []

# ============================================
# 1. Wellfound postings (verified in phases 1-3)
# ============================================
print("=" * 60)
print("1. Wellfound postings (re-verify and queue)")
print("=" * 60)

wf_urls = [
    "https://wellfound.com/jobs/4704152-principal-product-manager",
    "https://wellfound.com/jobs/4704106-product-manager-platform",
    "https://wellfound.com/jobs/4704104-product-manager-onboarding-and-growth",
    "https://wellfound.com/jobs/4174541-product-manager",
]

for url in wf_urls:
    job = fetch_job_page(url)
    if not job:
        print(f"  FETCH FAILED: {url}")
        continue
    posting, reason = try_queue(url, job['title'], job['company'], job['location'],
                                job['posted_raw'], job['posted_at'], job['salary'], 'wellfound')
    if posting:
        new_postings.append(posting)
        print(f"  QUEUED: {job['company']} | {job['title']} | {job['location']} | salary={job['salary'][:60]} | posted={posting['posted_at']} | priority={posting['priority']}")
    else:
        print(f"  {reason}: {job['title']} @ {job['company']}")

# ============================================
# 2. Remotive API
# ============================================
print("\n" + "=" * 60)
print("2. Remotive API")
print("=" * 60)

try:
    r = requests.get('https://remotive.com/api/remote-jobs', headers=HEADERS, timeout=10)
    print(f"  Status: {r.status_code}, length: {len(r.text)}")
    if r.status_code == 200:
        data = r.json()
        jobs = data.get('jobs', [])
        print(f"  Jobs returned: {len(jobs)}")
        for job in jobs:
            title = job.get('title', '')
            if title_matches(title):
                company = job.get('company_name', '')
                url = job.get('url', '')
                category = job.get('category', '')
                posted_str = job.get('publication_to', '')
                pa = None
                if posted_str:
                    try:
                        pa = datetime.datetime.fromisoformat(posted_str)
                    except:
                        try:
                            pa = datetime.datetime.strptime(posted_str, '%Y-%m-%d %H:%M:%S')
                        except:
                            pass
                posting, reason = try_queue(url, title, company, 'remote', posted_str, pa, '', 'Remotive')
                if posting:
                    new_postings.append(posting)
                    print(f"  QUEUED: {company} | {title} | {url}")
                elif reason and reason.startswith('SKIP'):
                    print(f"  {reason}: {title}")
    else:
        print("  Remotive API not accessible")
except Exception as e:
    print(f"  Remotive API error: {e}")

# ============================================
# 3. HN Algolia API for "Who is Hiring"
# ============================================
print("\n" + "=" * 60)
print("3. HN 'Who is Hiring' via Algolia API")
print("=" * 60)

try:
    # Search for the September 2026 "Who is Hiring" thread
    search_url = 'https://hn.algolia.com/api/v1/search'
    params = {
        'query': 'who is hiring',
        'restrictSearchableAttributes': 'title',
        'tags': 'story',
        'hitsPerPage': 5,
    }
    r = requests.get(search_url, params=params, timeout=15)
    print(f"  HN Algolia search: status={r.status_code}")
    if r.status_code == 200:
        data = r.json()
        hits = data.get('hits', [])
        print(f"  Found {len(hits)} 'who is hiring' stories")
        for hit in hits:
            title = hit.get('title', '')
            hn_url = f"https://news.ycombinator.com/item?id={hit['objectID']}"
            print(f"  Story: {title} (id={hit['objectID']})")
            # Fetch the thread page
            r2 = requests.get(hn_url, headers=HEADERS, timeout=15)
            if r2.status_code == 200:
                soup2 = BeautifulSoup(r2.text, 'html.parser')
                comments = soup2.select('span.commtext')
                print(f"    Comments: {len(comments)}")
                pm_found = 0
                for comment in comments:
                    text = comment.get_text(strip=True)
                    if title_matches(text) and ('hiring' in text.lower() or 'remote' in text.lower() or 'product' in text.lower()):
                        # Extract company and title from HN comment format
                        # Format: "| Company Name | Role | Location | Salary | ..."
                        parts = [p.strip() for p in text.split('|')]
                        if len(parts) >= 2:
                            # Find which part is the company, which is the title
                            company = 'Unknown'
                            role = ''
                            for part in parts[:4]:
                                if title_matches(part):
                                    role = part
                                elif len(part) > 2 and not any(kw in part.lower() for kw in ['remote', 'hiring', 'contract', 'full-time', 'visa', 'salary', 'compensation', '$', 'http']):
                                    company = part
                            # Try to extract URL
                            url_match = re.search(r'((?:https?://|www\.)[^\s|]+)', text)
                            job_url = url_match.group(1) if url_match else hn_url
                            if role and title_matches(role):
                                posting, reason = try_queue(job_url, role, company, 'remote', '', None, '',
                                                            'Hacker News (Who is Hiring)', 'remote')
                                if posting:
                                    new_postings.append(posting)
                                    pm_found += 1
                                    print(f"    -> QUEUED: {company} | {role} | {job_url[:80]}")
                                elif reason and 'fingerprint' in reason.lower():
                                    pass  # duplicate, skip silently
                print(f"    PM postings found: {pm_found}")
except Exception as e:
    print(f"  HN error: {e}")

# ============================================
# 4. Summary + Queue to DB
# ============================================
print("\n" + "=" * 60)
print("FINAL DISCOVERY SUMMARY")
print("=" * 60)

seen_fp = set()
unique = []
for p in new_postings:
    if p['posting_fingerprint'] not in seen_fp:
        seen_fp.add(p['posting_fingerprint'])
        unique.append(p)
    else:
        print(f"  Intra-run dup: {p['company']} | {p['role_title']}")

print(f"Total new postings found: {len(new_postings)}")
print(f"After intra-run dedup: {len(unique)}")

with open(f"{SKILL_ROOT}/shared/.discovery_gate_state.json") as f:
    gate_state = json.load(f)
remaining = gate_state.get('remaining_slots', 15)
print(f"Daily cap remaining: {remaining}")

to_queue = unique[:remaining]
capped = len(unique) - len(to_queue)
print(f"Postings to queue to DB: {len(to_queue)}")
if capped > 0:
    print(f"  (capped: {capped} exceed daily limit)")

# Open DB for insertion
db_conn = sqlite3.connect(f"{DB_PATH if 'DB_PATH' in dir() else f'{SKILL_ROOT}/shared/applications.db'}")
cur = db_conn.cursor()
inserted = 0
for p in to_queue:
    try:
        cur.execute("""
            INSERT INTO applications
            (posting_url, company, role_title, source_board, posted_at, posted_at_raw,
             discovered_at, priority, posting_fingerprint, remote_type, salary_disclosed,
             salary_range, status, last_failure_stage)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'discovered', NULL)
        """, (p['posting_url'], p['company'], p['role_title'], p['source_board'],
              p['posted_at'], p['posted_at_raw'], p['discovered_at'],
              p['priority'], p['posting_fingerprint'], p['remote_type'],
              p['salary_disclosed'], p['salary_range']))
        app_id = cur.lastrowid
        cur.execute("""
            INSERT INTO posting_sources (application_id, posting_url, source_name, discovered_by, is_canonical)
            VALUES (?, ?, ?, 'job_1_boards', 1)
        """, (app_id, p['posting_url'], p['source_board']))
        db_conn.commit()
        inserted += 1
        print(f"  INSERTED #{app_id}: {p['company']} | {p['role_title']} | {p['source_board']} | priority={p['priority']}")
    except Exception as e:
        db_conn.rollback()
        print(f"  INSERT FAILED: {p['company']} | {p['role_title']} | {e}")
db_conn.close()

# Update gate state
gate_state['last_run_at'] = now.strftime('%Y-%m-%dT%H:%M:%SZ')
gate_state['new_found'] = len(to_queue)
gate_state['queued'] = len(to_queue)
gate_state['today_queued'] = gate_state.get('today_queued', 0) + len(to_queue)
gate_state['remaining_slots'] = remaining - len(to_queue)
gate_state['sources_checked'] = ['wellfound', 'remotive', 'hacker_news', 'open_web_search']
gate_state['sources_blocked'] = ['linkedin-global', 'indeed-global', 'remote-ok']
gate_state['open_web_sweep_last_run'] = now.strftime('%Y-%m-%dT%H:%M:%SZ')

with open(f"{SKILL_ROOT}/shared/.discovery_gate_state.json", 'w') as f:
    json.dump(gate_state, f, indent=2)

print(f"\n=== QUEUED {inserted} new postings to DB ===")
print(f"=== Gate state updated ===")
