#!/usr/bin/env python
"""Phase 5: Check HN 'Who is Hiring' thread, verify Wellfound postings, queue to DB."""

import requests, json, re, sqlite3, datetime
from bs4 import BeautifulSoup
import yaml

SKILL_ROOT = "C:/Users/rotim/AppData/Local/hermes/skills/job-hunting"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}
BING_URL = 'https://www.bing.com/search'

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

now = datetime.datetime.now(datetime.timezone.utc)
recent_cutoff = now - datetime.timedelta(hours=24)

def normalize_title(title):
    t = title.lower().strip()
    t = re.sub(r'\s*#\d+\s*$', '', t)
    t = re.sub(r'\s*\(\s*[IVX]+\s*\)$', '', t)
    t = re.sub(r'\s*\(\s*(senior|junior|lead|principal|staff|mid|mid-level|entry|associate)\s*\)$', '', t)
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
            if isinstance(obj, list) and obj and isinstance(obj[0], dict):
                addr = obj[0].get('address', {})
            elif isinstance(obj, dict):
                addr = obj.get('address', {})
            else:
                addr = {}
            if isinstance(addr, dict):
                parts = [addr.get('addressLocality',''), addr.get('addressRegion',''), addr.get('addressCountry','')]
                l = ' '.join(p for p in parts if p).lower().strip()
        except:
            l = 'remote'
    l = re.sub(r'\s+', ' ', l)
    return f"{c}|{t}|{l}"

def extract_location_from_jsonld(loc_obj):
    if not loc_obj:
        return 'remote'
    if isinstance(loc_obj, list):
        if loc_obj and isinstance(loc_obj[0], dict):
            addr = loc_obj[0].get('address', {})
        else:
            return 'remote'
    elif isinstance(loc_obj, dict):
        addr = loc_obj.get('address', {})
    else:
        return str(loc_obj)
    if isinstance(addr, dict):
        locality = addr.get('addressLocality', '')
        region = addr.get('addressRegion', '')
        country = addr.get('addressCountry', '')
        address_full = addr.get('address', '')
        if isinstance(address_full, str) and address_full:
            return address_full
        parts = [p for p in [locality, region, country] if p]
        return ', '.join(parts) if parts else 'remote'
    return 'remote'

def extract_salary_from_jsonld(salary_obj):
    if not salary_obj:
        return '', False
    try:
        if isinstance(salary_obj, str):
            return salary_obj, True
        if isinstance(salary_obj, dict):
            currency = salary_obj.get('currency', '')
            value = salary_obj.get('value', {})
            if isinstance(value, dict):
                min_val = value.get('minValue', 0)
                max_val = value.get('maxValue', 0)
                unit = value.get('unitText', '')
                if min_val and max_val:
                    return f"{currency} {min_val}-{max_val} {unit}", True
            elif isinstance(value, (int, float)):
                return f"{currency} {value}", True
        return str(salary_obj), True
    except:
        return '', False

def extract_posted_from_date(posted_raw):
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
    text_lower = posted_raw.lower().strip()
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    if 'today' in text_lower or 'just now' in text_lower:
        return now_utc
    if 'yesterday' in text_lower:
        return now_utc - datetime.timedelta(days=1)
    hours_match = re.match(r'(\d+)\s+hour', text_lower)
    if hours_match:
        return now_utc - datetime.timedelta(hours=int(hours_match.group(1)))
    days_match = re.match(r'(\d+)\s+day', text_lower)
    if days_match:
        return now_utc - datetime.timedelta(days=int(days_match.group(1)))
    return None

def title_matches(role_title):
    t_lower = role_title.lower().strip()
    t_norm = normalize_title(role_title)
    for v in title_variants:
        v_lower = v.lower().strip()
        v_norm = normalize_title(v)
        if v_lower in t_lower or t_lower in v_lower:
            return True
        if v_norm in t_norm or t_norm in v_norm:
            return True
    return False

def passes_salary(salary_text, floor):
    if not salary_text:
        return True
    text = salary_text.lower()
    amounts = []
    # Match dollar amounts like $160,000 or $160k or 160000
    for m in re.finditer(r'\$?\s*([\d,]+\.?\d*)\s*(?:k|thousand)?', text):
        try:
            val = float(m.group(1).replace(',', ''))
            amounts.append(val)
        except:
            pass
    # Also extract raw numbers that look like dollar amounts
    for m in re.finditer(r'(\d[\d,]*)\.?\d*', text):
        try:
            val = float(m.group(1).replace(',', ''))
            if 10000 < val < 1000000:
                amounts.append(val)
        except:
            pass
    if amounts:
        max_amount = max(amounts)
        floor_amount = floor.get('amount', 0)
        if max_amount >= floor_amount:
            return True
        if 'month' in text and max_amount * 12 >= floor_amount:
            return True
        if max_amount < floor_amount * 0.3:
            return False
    return True

def fetch_job_page(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, 'html.parser')
        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    data = data[0]
                if isinstance(data, dict) and data.get('@type') in ('JobPosting', 'job'):
                    title = data.get('title') or data.get('jobTitle', '')
                    hiring_org = data.get('hiringOrganization', '')
                    if isinstance(hiring_org, dict):
                        company = hiring_org.get('name', '')
                    else:
                        company = str(hiring_org)
                    location = extract_location_from_jsonld(data.get('jobLocation', {}))
                    posted_raw = data.get('datePosted', '')
                    posted_at = extract_posted_from_date(posted_raw)
                    salary_text, has_salary = extract_salary_from_jsonld(data.get('baseSalary', {}))
                    remote_type = 'remote'
                    return {
                        'title': title, 'company': company, 'location': location,
                        'posted_at_raw': posted_raw, 'posted_at': posted_at,
                        'salary': salary_text if has_salary else '',
                        'url': url, 'remote_type': remote_type,
                    }
            except (json.JSONDecodeError, TypeError):
                continue
        return None
    except Exception:
        return None

def try_queue(url, title, company, location, posted_raw, posted_at, salary, source_board, remote_type='remote'):
    global existing_fingerprints, existing_urls
    if url in existing_urls:
        return None, 'SKIP (URL already in DB)'
    if not title_matches(title):
        return None, 'REJECT (title mismatch)'
    if not passes_salary(salary, salary_floor):
        return None, f'REJECT (salary below floor: {salary})'
    if company and any(c.lower() in company.lower() for c in companies_exclude):
        return None, 'REJECT (company excluded)'
    
    fingerprint = compute_fingerprint(company, title, location)
    if fingerprint in existing_fingerprints:
        return None, f'SKIP (fingerprint dup: {fingerprint})'
    
    priority = 'normal'
    if posted_at and posted_at > recent_cutoff:
        priority = 'high'
    elif not posted_at:
        priority = 'high'
    
    posting = {
        'posting_url': url,
        'company': company or 'Unknown',
        'role_title': title,
        'location': location or 'remote',
        'posted_at': posted_at.strftime('%Y-%m-%dT%H:%M:%SZ') if posted_at else None,
        'posted_at_raw': posted_raw,
        'salary_disclosed': bool(salary),
        'salary_range': salary or None,
        'source_board': source_board,
        'remote_type': remote_type,
        'discovered_at': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'priority': priority,
        'posting_fingerprint': fingerprint,
    }
    existing_fingerprints.add(fingerprint)
    existing_urls.add(url)
    return posting, None

# ============================================
# 1. Verify Wellfound postings (re-fetch detail pages)
# ============================================
print("=" * 60)
print("1. Verifying Wellfound postings (re-fetch)")
print("=" * 60)

wf_urls = [
    "https://wellfound.com/jobs/4704152-principal-product-manager",
    "https://wellfound.com/jobs/4704106-product-manager-platform",
    "https://wellfound.com/jobs/4704104-product-manager-onboarding-and-growth",
    "https://wellfound.com/jobs/4174541-product-manager",
]

new_postings = []
for url in wf_urls:
    job = fetch_job_page(url)
    if not job:
        print(f"  FETCH FAILED: {url}")
        continue
    posting, reason = try_queue(
        url, job['title'], job['company'], job['location'],
        job['posted_at_raw'], job['posted_at'], job['salary'],
        'wellfound', job.get('remote_type', 'remote')
    )
    if posting:
        new_postings.append(posting)
        print(f"  QUEUED: {job['company']} | {job['title']} | {job['location']} | salary={job['salary'][:60]} | posted={posting['posted_at']} | priority={posting['priority']}")
    else:
        print(f"  {reason}: {url}")

# ============================================
# 2. Check HN "Who is Hiring" thread
# ============================================
print("\n" + "=" * 60)
print("2. HN 'Who is Hiring' — September 2026 thread")
print("=" * 60)

# Search for the September 2026 "Who is Hiring" thread
# It's typically posted on the 1st of each month on news.ycombinator.com
hn_search_url = f"{BING_URL}"
hn_query = '"who is hiring" "september 2026" site:news.ycombinator.com'
try:
    r = requests.get(hn_search_url, params={'q': hn_query, 'count': 5}, headers=HEADERS, timeout=15)
    if r.status_code == 200:
        soup = BeautifulSoup(r.text, 'html.parser')
        results = soup.select('li.b_algo h2 a')
        hn_thread_url = None
        for a in results:
            href = a.get('href', '')
            title = a.get_text(strip=True)
            if 'hiring' in href.lower() or 'hiring' in title.lower():
                # Decode Bing redirect
                if 'bing.com/ck/a' in href:
                    match = re.search(r'&u=a1([A-Za-z0-9+/=]+)', href)
                    if match:
                        import base64
                        encoded = match.group(1)
                        padding = 4 - len(encoded) % 4
                        if padding != 4:
                            encoded += '=' * padding
                        try:
                            hn_thread_url = base64.b64decode(encoded).decode('utf-8', errors='ignore')
                        except:
                            hn_thread_url = None
                else:
                    hn_thread_url = href
                if hn_thread_url and 'ycombinator' in hn_thread_url:
                    print(f"  Found HN thread: {title}")
                    print(f"  URL: {hn_thread_url}")
                    break
        if not hn_thread_url:
            # Try direct: the Who is Hiring thread for September 2026
            # HN post ID for September 2026 hiring: typically around 43xxxxx or 44xxxxx
            # Let's try fetching the HN front page / search
            print("  Bing search didn't find the thread. Trying HN API directly...")
            hn_api_url = 'https://hacker-news.firebaseio.com/v0/search?query=who+is+hiring+september+2026&orderBy=relevance&limit=5'
            # Actually HN API uses Algolia: https://hn.algolia.com/api
            hn_algolia = 'https://hn.algolia.com/api/v1/search'
            params = {'query': 'who is hiring september 2026', 'restrictSearchableAttributes': 'title', 'numericFilters': ['created_at_i>1788259200']}
            r2 = requests.get(hn_algolia, params=params, timeout=15)
            if r2.status_code == 200:
                data = r2.json()
                print(f"  HN Algolia API: {len(data.get('hits', []))} results")
                for hit in data.get('hits', [])[:3]:
                    if 'hiring' in hit.get('title', '').lower():
                        print(f"    -> {hit['title']} (id={hit['objectID']})")
                        story_url = hit.get('url', hit.get('story_text', ''))
                        if 'ycombinator' in story_url or story_url:
                            hn_thread_url = story_url
            if not hn_thread_url:
                # Try the most recent "Who is Hiring" - it's posted on the 1st of the month
                # For September 2026, it might be item 439xxxxx or similar
                # Let's try fetching the HNMODS who is hiring page
                for try_id in range(4400000, 4390000, -1):
                    pass  # Don't brute force
                # Try a known pattern: https://news.ycombinator.com/submitted?id=whoishiring
                # The September thread is usually https://news.ycombinator.com/item?id=XXXXX
                # Let's search HN directly
                print("  Trying HN search page...")
                r3 = requests.get('https://news.ycombinator.com/search?q=who+is+hiring', headers=HEADERS, timeout=15)
                print(f"  HN search: status={r3.status_code}, len={len(r3.text)}")
except Exception as e:
    print(f"  HN search error: {e}")

if hn_thread_url:
    print(f"\n  Fetching HN thread: {hn_thread_url}")
    try:
        r = requests.get(hn_thread_url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            # Extract comments - PM job postings are in top-level comments
            # HN uses <span class="commtext"> for comment text
            comments = soup.select('span.commtext')
            print(f"  Found {len(comments)} comments")
            
            pm_keywords = ['product manager', 'ai product', 'technical product', 'growth product',
                          'product owner', 'workflow engineer', 'ai engineer', 'automation engineer',
                          'junior product', 'associate product', 'ai/ml product', 'principal product',
                          'senior product manager']
            
            hn_pm_postings = []
            for comment in comments:
                text = comment.get_text(strip=True)
                # Filter for PM roles
                if any(kw in text.lower() for kw in pm_keywords):
                    # Extract company name and job description
                    # HN comments typically start with company name | job title
                    lines = text.split('\n')
                    first_line = lines[0] if lines else text[:200]
                    # Try to extract company from format "Company | Role"
                    parts = first_line.split('|')
                    if len(parts) >= 2:
                        company = parts[0].strip()[:100]
                        role = parts[1].strip()[:150]
                        hn_pm_postings.append({
                            'text': text[:500],
                            'company': company,
                            'role': role,
                            'url': hn_thread_url,
                        })
            
            print(f"  PM-related comments: {len(hn_pm_postings)}")
            for p in hn_pm_postings[:10]:
                print(f"    {p['company']} | {p['role']}")
                print(f"      {p['text'][:100]}")
    except Exception as e:
        print(f"  HN thread error: {e}")
else:
    print("  Could not locate HN 'Who is Hiring' thread")

# ============================================
# 3. Try direct company career pages (Ashby/Greenhouse/Lever)
# ============================================
print("\n" + "=" * 60)
print("3. Trying direct company career pages")
print("=" * 60)

# Companies from existing DB that use Ashby (9 existing)
ashby_companies = set(r[0] for r in cur.execute("SELECT DISTINCT company FROM applications WHERE source_board='Ashby'"))
print(f"  Companies with Ashby source: {ashby_companies}")
# These are companies we've already seen — unlikely to have NEW postings
# Skip re-checking these

# Try some known companies that post PM roles and use accessible platforms
known_companies = [
    ('Toptal', 'https://www.toptal.com/careers'),
    ('Automattic', 'https://automattic.com/work-with-us/'),
    ('GitLab', 'https://about.gitlab.com/jobs/'),
    ('Zapier', 'https://zapier.com/jobs/'),
    ('Basecamp', 'https://basecamp.com/jobs'),
    ('Doist', 'https://doist.com/careers'),
]

for company, url in known_companies:
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            scripts = soup.find_all('script', type='application/ld+json')
            for s in scripts:
                try:
                    data = json.loads(s.string)
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and item.get('@type') == 'JobPosting':
                                title = item.get('title', '')
                                hiring_org = item.get('hiringOrganization', '')
                                company_name = hiring_org.get('name', '') if isinstance(hiring_org, dict) else str(hiring_org)
                                if title_matches(title):
                                    location = extract_location_from_jsonld(item.get('jobLocation', {}))
                                    posted_raw = item.get('datePosted', '')
                                    posted_at = extract_posted_from_date(posted_raw)
                                    salary_text, _ = extract_salary_from_jsonld(item.get('baseSalary', {}))
                                    posting, reason = try_queue(
                                        item.get('url', url), title, company_name, location,
                                        posted_raw, posted_at, salary_text,
                                        company_name if company_name else company,
                                        'career_page'
                                    )
                                    if posting:
                                        new_postings.append(posting)
                                        print(f"  QUEUED: {company_name} | {title} | {location} | {posting['posting_url']}")
                                    elif reason:
                                        print(f"  {reason}: {title}")
                elif isinstance(data, dict) and data.get('@type') == 'JobPosting':
                    title = data.get('title', '')
                    hiring_org = data.get('hiringOrganization', '')
                    company_name = hiring_org.get('name', '') if isinstance(hiring_org, dict) else str(hiring_org)
                    if title_matches(title):
                        location = extract_location_from_jsonld(data.get('jobLocation', {}))
                        posted_raw = data.get('datePosted', '')
                        posted_at = extract_posted_from_date(posted_raw)
                        salary_text, _ = extract_salary_from_jsonld(data.get('baseSalary', {}))
                        posting, reason = try_queue(
                            data.get('url', url), title, company_name, location,
                            posted_raw, posted_at, salary_text,
                            company_name if company_name else company,
                            'career_page'
                        )
                        if posting:
                            new_postings.append(posting)
                            print(f"  QUEUED: {company_name} | {title} | {location} | {posting['posting_url']}")
                        elif reason:
                            print(f"  {reason}: {title}")
    except Exception as e:
        print(f"  {company} ({url}): Error - {str(e)[:60]}")

# ============================================
# 4. Try GitHub Jobs replacement / AngelList API
# ============================================
print("\n" + "=" * 60)
print("4. Try direct job board scrapes")
print("=" * 60)

# Try Remotive API
try:
    r = requests.get('https://remotive.com/api/remote-jobs', headers=HEADERS, timeout=10)
    print(f"  Remotive API: status={r.status_code}, len={len(r.text)}")
    if r.status_code == 200:
        data = r.json()
        jobs = data.get('jobs', [])
        print(f"  Remotive API jobs: {len(jobs)}")
        for job in jobs[:20]:
            title = job.get('title', '')
            if title_matches(title):
                company = job.get('company_name', '')
                location = job.get('category', '') + ', remote'
                url = job.get('url', '')
                posted_raw = job.get('publication_to', '')
                posting, reason = try_queue(url, title, company, 'remote', posted_raw, None, '', 'Remotive', 'remote')
                if posting:
                    new_postings.append(posting)
                    print(f"  QUEUED: {company} | {title} | {url}")
                elif reason:
                    print(f"  {reason}: {title}")
except Exception as e:
    print(f"  Remotive API: Error - {str(e)[:80]}")

# ============================================
# Summary and Queue to DB
# ============================================
print("\n" + "=" * 60)
print("FINAL DISCOVERY SUMMARY")
print("=" * 60)

# Dedupe within new postings
seen_fp = set()
unique = []
for p in new_postings:
    if p['posting_fingerprint'] not in seen_fp:
        seen_fp.add(p['posting_fingerprint'])
        unique.append(p)
    else:
        print(f"  Intra-run dup: {p['company']} | {p['role_title']}")

print(f"Total new postings: {len(new_postings)}")
print(f"After intra-run dedup: {len(unique)}")

# Load gate state for cap
with open(f"{SKILL_ROOT}/shared/.discovery_gate_state.json") as f:
    gate_state = json.load(f)
remaining = gate_state.get('remaining_slots', 15)
print(f"Daily cap remaining: {remaining}")

to_queue = unique[:remaining]
capped = len(unique) - len(to_queue)

print(f"\nPostings to queue to DB: {len(to_queue)}")
if capped > 0:
    print(f"  (capped: {capped} exceed daily limit)")

# Queue to DB
inserted = 0
for p in to_queue:
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO applications 
            (posting_url, company, role_title, source_board, posted_at, posted_at_raw,
             discovered_at, priority, posting_fingerprint, remote_type, salary_disclosed,
             salary_range, status, last_failure_stage)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'discovered', NULL)
        """, (
            p['posting_url'], p['company'], p['role_title'], p['source_board'],
            p['posted_at'], p['posted_at_raw'], p['discovered_at'],
            p['priority'], p['posting_fingerprint'], p['remote_type'],
            p['salary_disclosed'], p['salary_range']
        ))
        app_id = cur.lastrowid
        # Insert into posting_sources
        cur.execute("""
            INSERT INTO posting_sources (application_id, posting_url, source_name, discovered_by, is_canonical)
            VALUES (?, ?, ?, 'job_1_boards', 1)
        """, (app_id, p['posting_url'], p['source_board']))
        conn.commit()
        inserted += 1
        print(f"  INSERTED #{app_id}: {p['company']} | {p['role_title']} | {p['source_board']} | priority={p['priority']}")
    except Exception as e:
        print(f"  INSERT FAILED: {p['company']} | {p['role_title']} | {e}")

conn.close()

# Update gate state
gate_state['last_run_at'] = now.strftime('%Y-%m-%dT%H:%M:%SZ')
gate_state['new_found'] = len(to_queue)
gate_state['queued'] = len(to_queue)
gate_state['today_queued'] = gate_state.get('today_queued', 0) + len(to_queue)
gate_state['remaining_slots'] = remaining - len(to_queue)
gate_state['sources_checked'] = ['wellfound', 'remotive', 'hacker_news', 'career_pages', 'open_web_search']
gate_state['sources_blocked'] = ['linkedin-global', 'indeed-global', 'remote-ok']
gate_state['open_web_sweep_last_run'] = now.strftime('%Y-%m-%dT%H:%M:%SZ')

with open(f"{SKILL_ROOT}/shared/.discovery_gate_state.json", 'w') as f:
    json.dump(gate_state, f, indent=2)

print(f"\n=== QUEUED {inserted} new postings to DB ===")
print(f"=== Gate state updated ===")
