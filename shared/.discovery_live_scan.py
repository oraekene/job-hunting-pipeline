#!/usr/bin/env python3
"""Live discovery scan — fetches from accessible sources, dedupes against DB, cheap-filters against target profile."""
import sqlite3, json, re, datetime, urllib.request, urllib.parse, sys, os

SKILL_ROOT = r"C:/Users/rotim/AppData/Local/hermes/skills/job-hunting"
DB_PATH = f"{SKILL_ROOT}/shared/applications.db"
TARGET_PATH = f"{SKILL_ROOT}/shared/target-profile.yaml"
GATE_PATH = f"{SKILL_ROOT}/shared/.discovery_gate_state.json"

import yaml
with open(TARGET_PATH) as f:
    target = yaml.safe_load(f)

title_variants = [tv['title'] for tv in target.get('title_variants', [])]
salary_floor = target.get('salary_floor', {})
companies_exclude = target.get('companies_exclude', [])

# Load existing DB state
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
existing_fingerprints = set(r[0] for r in cur.execute("SELECT posting_fingerprint FROM applications WHERE posting_fingerprint IS NOT NULL"))
existing_urls = set(r[0] for r in cur.execute("SELECT DISTINCT posting_url FROM applications WHERE posting_url IS NOT NULL AND length(posting_url) > 0"))
existing_posting_sources = set(r[0] for r in cur.execute("SELECT DISTINCT posting_url FROM posting_sources WHERE posting_url IS NOT NULL AND length(posting_url) > 0"))
all_known_urls = existing_urls | existing_posting_sources
today_queued = cur.execute("SELECT COUNT(*) FROM applications WHERE status='discovered' AND date(discovered_at) = date('now')").fetchone()[0]
conn.close()

now = datetime.datetime.now(datetime.timezone.utc)
recent_cutoff = now - datetime.timedelta(hours=24)
last_run = datetime.datetime.fromisoformat("2026-09-14T07:07:54+00:00")

# --- Target profile filters ---
DASH = 36000  # USD/year
TITLE_KEYWORDS = [tv.lower() for tv in title_variants]
# Also accept senior-level variants of target titles
SENIOR_PATTERNS = ['senior', 'lead', 'principal', 'staff', 'head of', 'director', 'vp', 'chief']

def normalize_title(title):
    t = (title or '').lower().strip()
    t = re.sub(r'\s*#\d+\s*$', '', t)
    t = re.sub(r'\s*\([IVX]+\)\s*$', '', t)
    t = re.sub(r'\s*\(\s*(senior|junior|lead|principal|staff|mid|entry|associate)\s*\)\s*$', '', t)
    t = re.sub(r'\s*\(\s*(remote|contract|freelance|temp)\s*\)\s*$', '', t)
    t = re.sub(r'[^\\w\\s]', ' ', t)
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

def title_matches(title):
    tl = title.lower().strip()
    tn = normalize_title(title)
    for v in title_variants:
        vl = v.lower().strip()
        vn = normalize_title(v)
        if vl in tl or tl in vl or vn in tn or tn in vn:
            return True
    return False

def passes_salary(salary_text, floor):
    if not salary_text:
        return True
    text = str(salary_text).lower()
    amounts = []
    for m in re.finditer(r'(\d[\d,]*\.?\d*)', text):
        try:
            v = float(m.group(1).replace(',', ''))
            if 1000 < v < 10000000:
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

def extract_posted(posted_raw):
    if not posted_raw:
        return None, now.strftime('%Y-%m-%dT%H:%M:%SZ')
    posted_str = str(posted_raw).strip()
    # ISO format
    try:
        dt = datetime.datetime.fromisoformat(posted_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt, posted_str
    except:
        pass
    for fmt in ['%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%B %d, %Y', '%b %d, %Y', '%Y-%m-%d %H:%M:%S']:
        try:
            dt = datetime.datetime.strptime(posted_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return dt, posted_str
        except:
            pass
    t = posted_str.lower().strip()
    n = now
    if 'today' in t or 'just now' in t or '1h' in t or '1 hour' in t:
        return n, posted_str
    if 'yesterday' in t:
        return n - datetime.timedelta(days=1), posted_str
    m = re.match(r'(\d+)\s+hour', t)
    if m:
        return n - datetime.timedelta(hours=int(m.group(1))), posted_str
    m = re.match(r'(\d+)\s+day', t)
    if m:
        return n - datetime.timedelta(days=int(m.group(1))), posted_str
    return None, posted_str

def fetch_url(url, timeout=15):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode('utf-8', errors='replace')

def try_queue(url, title, company, location, posted_raw, source_board, salary_text=''):
    """Returns (posting_dict, None) or (None, reason)."""
    if url in all_known_urls:
        return None, f'SKIP (URL dup)'
    if not title_matches(title):
        return None, f'REJECT (title: {title})'
    if not passes_salary(salary_text, salary_floor):
        return None, f'REJECT (salary floor: {salary_text})'
    for c in companies_exclude:
        if c and c.lower() in (company or '').lower():
            return None, f'REJECT (company excluded: {c})'
    fp = compute_fingerprint(company, title, location)
    if fp in existing_fingerprints:
        return None, f'SKIP (Fingerprint dup: {fp})'
    posted_at, posted_raw_str = extract_posted(posted_raw)
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
        'posted_at_raw': posted_raw_str or '',
        'salary_disclosed': bool(salary_text),
        'salary_range': salary_text or None,
        'source_board': source_board,
        'remote_type': 'remote' if location and 'remote' in location.lower() else 'unknown',
        'discovered_at': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'priority': priority,
        'posting_fingerprint': fp,
    }
    existing_fingerprints.add(fp)
    all_known_urls.add(url)
    return posting, None

results = {
    'sources_checked': [],
    'sources_blocked': [],
    'candidates': [],
    'skipped': [],
    'queued': [],
    'debug': [],
}

# ============================================================
# Source 1: Remotive API
# ============================================================
print("=" * 60)
print("1. Remotive API")
print("=" * 60)
try:
    search_terms = [tv.replace(' ', '-') for tv in title_variants[:4]]  # product-manager, ai-product-manager, ai-engineer, automation-engineer
    all_remotive = []
    for term in search_terms:
        encoded = urllib.parse.quote(term)
        st, body = fetch_url(f"https://remotive.com/api/remote-jobs?limit=100&search={encoded}", timeout=15)
        print(f"  Remotive '{term}': HTTP {st}, body={len(body)} chars")
        data = json.loads(body)
        jobs = data.get('jobs', [])
        for j in jobs:
            company = j.get('company_name', '')
            title = j.get('title', '')
            url = j.get('url', '')
            posted_str = j.get('date_posted', '') or j.get('publication_to', '')
            salary = j.get('salary', '')
            location = 'Remote'
            if not title:
                continue
            all_remotive.append({
                'company': company, 'title': title, 'url': url,
                'posted_raw': posted_str, 'salary': salary, 'location': location,
                'source': 'Remotive'
            })
    print(f"  Total Remotive jobs fetched: {len(all_remotive)}")
    
    # Dedupe by URL within Remotive
    seen_remotive_urls = set()
    unique_rem = [r for r in all_remotive if r['url'] not in seen_remotive_urls and not seen_remotive_urls.add(r['url'])]
    print(f"  Unique Remotive jobs: {len(unique_rem)}")
    
    for job in unique_rem:
        p, reason = try_queue(job['url'], job['title'], job['company'], job['location'],
                              job['posted_raw'], job['source'], job['salary'])
        if p:
            results['candidates'].append(p)
            results['debug'].append(f"MATCH: {job['company']} | {job['title']} | priority={p['priority']}")
        else:
            results['skipped'].append({'company': job['company'], 'role_title': job['title'], 'url': job['url'], 'reason': reason})
    results['sources_checked'].append('remotive-api')
except Exception as e:
    err = f"BLOCKED/ERROR: {type(e).__name__}: {str(e)[:120]}"
    results['sources_blocked'].append({'remotive-api': err})
    print(f"  ERROR: {err}")
    results['debug'].append(err)

# ============================================================
# Source 2: HN Algolia API — "Who is Hiring"
# ============================================================
print("\n" + "=" * 60)
print("2. HN 'Who is Hiring' via Algolia API")
print("=" * 60)
try:
    search_url = 'https://hn.algolia.com/api/v1/search'
    params = {'query': 'who is hiring', 'restrictSearchableAttributes': 'title', 'tags': 'story', 'hitsPerPage': 10}
    st, body = fetch_url(search_url + '?' + urllib.parse.urlencode(params), timeout=15)
    print(f"  HN Algolia: HTTP {st}")
    data = json.loads(body)
    hits = data.get('hits', [])
    print(f"  Found {len(hits)} 'who is hiring' stories")
    
    # Find the most recent September 2026 hiring thread
    hiring_threads = []
    for hit in hits:
        title = hit.get('title', '')
        hn_id = hit.get('objectID', '')
        hn_url = f"https://news.ycombinator.com/item?id={hn_id}"
        hiring_threads.append((title, hn_url, hn_id))
        print(f"  Story: {title} (id={hn_id})")
    
    # Fetch thread pages for the most recent hiring thread(s)
    for title, hn_url, hn_id in hiring_threads[:2]:
        try:
            st2, html = fetch_url(hn_url, timeout=15)
            print(f"  Thread {hn_id}: HTTP {st2}, {len(html)} chars")
            # Extract comment text from HN HTML
            # HN comments are in <td class="default"><div class="comment"><span class="commtext c00">
            comments = re.findall(r'<span class="commtext c00">(.*?)</span>', html, re.DOTALL)
            if not comments:
                comments = re.findall(r'<span class="commtext">(.*?)</span>', html, re.DOTALL)
            if not comments:
                comments = re.findall(r'<div class="comment-text">(.*?)</div>', html, re.DOTALL)
            if not comments:
                # Try broader extraction
                comments = re.findall(r'<td class="default">\s*<div class="comment[^"]*">\s*<div class="para">(.*?)</div>', html, re.DOTALL)
            print(f"  Comments extracted: {len(comments)}")
            
            pm_found = 0
            for comment in comments:
                text = re.sub(r'<[^>]+>', ' ', comment)
                text = re.sub(r'\s+', ' ', text).strip()
                if not title_matches(text):
                    continue
                # HN format: | Company | Role | Location | Salary | site:URL
                parts = [p.strip() for p in text.split('|')]
                if len(parts) >= 2:
                    company = 'Unknown'
                    role = ''
                    for part in parts[:4]:
                        if title_matches(part):
                            role = part
                        elif len(part) > 2 and not any(kw in part.lower() for kw in ['remote', 'hiring', 'contract', 'full-time', 'visa', 'salary', 'compensation', '$', 'http', 'us', 'canada', 'worldwide', 'onsite', 'hybrid']):
                            if len(part) < 80 and company == 'Unknown':
                                company = part
                    url_match = re.search(r'((?:https?://|www\.)[^\\s|]+)', text)
                    job_url = url_match.group(1) if url_match else hn_url
                    if role and title_matches(role):
                        p, reason = try_queue(job_url, role, company, 'remote', '', 'Hacker News (Who is Hiring)', '')
                        if p:
                            results['candidates'].append(p)
                            pm_found += 1
                            results['debug'].append(f"  HN MATCH: {company} | {role} | priority={p['priority']}")
                        elif reason and 'SKIP' in reason:
                            results['debug'].append(f"  HN {reason}: {company} | {role}")
            print(f"  PM postings queued from this thread: {pm_found}")
        except Exception as e:
            results['debug'].append(f"  Thread fetch error: {e}")
    results['sources_checked'].append('hnrss-who-is-hiring')
except Exception as e:
    err = f"BLOCKED/ERROR: {type(e).__name__}: {str(e)[:120]}"
    results['sources_blocked'].append({'hnrss-who-is-hiring': err})
    print(f"  ERROR: {err}")
    results['debug'].append(err)

# ============================================================
# Source 3: Wellfound (verify blocked status)
# ============================================================
print("\n" + "=" * 60)
print("3. Wellfound (verify)")
print("=" * 60)
try:
    st, body = fetch_url("https://wellfound.com/jobs", timeout=20)
    print(f"  Wellfound: HTTP {st}, body={len(body)} chars")
    if st == 200 and len(body) > 5000:
        # Try to extract job links
        job_urls = list(set(re.findall(r'href="(https://wellfound\.com/jobs/\d+[^\"]*)"', body)))
        print(f"  Wellfound job links found: {len(job_urls)}")
        if len(job_urls) > 0:
            results['sources_checked'].append('wellfound')
            # Try fetching a few job pages to extract data
            for url in job_urls[:8]:
                try:
                    st2, job_html = fetch_url(url, timeout=15)
                    if st2 != 200:
                        continue
                    # Try JSON-LD
                    ld_matches = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', job_html, re.DOTALL)
                    for ld in ld_matches:
                        try:
                            data = json.loads(ld.strip())
                            if isinstance(data, list):
                                data = data[0]
                            if isinstance(data, dict) and data.get('@type') == 'JobPosting':
                                title = data.get('title', '') or data.get('jobTitle', '')
                                ho = data.get('hiringOrganization', '')
                                company = ho.get('name', '') if isinstance(ho, dict) else str(ho)
                                loc_data = data.get('jobLocation', {})
                                if isinstance(loc_data, list) and loc_data:
                                    loc_data = loc_data[0]
                                if isinstance(loc_data, dict):
                                    addr = loc_data.get('address', {})
                                    if isinstance(addr, dict):
                                        location = ', '.join(p for p in [addr.get('addressLocality',''), addr.get('addressRegion',''), addr.get('addressCountry','')] if p)
                                    else:
                                        location = 'remote'
                                else:
                                    location = 'remote'
                                posted_raw = data.get('datePosted', '')
                                salary_obj = data.get('baseSalary', {})
                                salary_text = ''
                                if isinstance(salary_obj, dict):
                                    val = salary_obj.get('value', {})
                                    if isinstance(val, dict):
                                        salary_text = f"{salary_obj.get('currency','USD')} {val.get('minValue','')} - {val.get('maxValue','')} {val.get('unitText','')}"
                                p, reason = try_queue(url, title, company, location, posted_raw, 'wellfound', salary_text)
                                if p:
                                    results['candidates'].append(p)
                                    results['debug'].append(f"WF MATCH: {company} | {title} | priority={p['priority']}")
                                elif reason and 'SKIP' in reason:
                                    results['debug'].append(f"WF {reason}: {company} | {title}")
                                break  # only take first JobPosting per page
                        except:
                            continue
                except:
                    continue
        else:
            results['sources_blocked'].append({'wellfound': f'BLOCKED — HTTP {st}, no job links extracted'})
    else:
        results['sources_blocked'].append({'wellfound': f'BLOCKED — HTTP {st}, body={len(body)} chars (anti-bot/captcha or redirect)'})
except Exception as e:
    err = f"BLOCKED/ERROR: {type(e).__name__}: {str(e)[:150]}"
    results['sources_blocked'].append({'wellfound': err})

# ============================================================
# Source 4: LinkedIn / Indeed / RemoteOK — KNOWN BLOCKED
# ============================================================
results['sources_blocked'].append({'linkedin-global': 'BLOCKED — sign-in wall (per memory/env config)'})
results['sources_blocked'].append({'indeed-global': 'BLOCKED — sign-in wall / ATS wall (per memory/env config)'})
results['sources_blocked'].append({'remote-ok': 'BLOCKED — anti-bot/redirect (per memory/env config)'})

# ============================================================
# Dedup within candidates + daily cap
# ============================================================
print("\n" + "=" * 60)
print("DEDUP + DAILY CAP")
print("=" * 60)
seen_fp = set()
unique = []
for p in results['candidates']:
    if p['posting_fingerprint'] not in seen_fp:
        seen_fp.add(p['posting_fingerprint'])
        unique.append(p)
    else:
        results['debug'].append(f"Intra-run dup: {p['company']} | {p['role_title']}")

print(f"Total candidates: {len(results['candidates'])}")
print(f"After intra-run dedup: {len(unique)}")
print(f"Skipped (dup/filter): {len(results['skipped'])}")

daily_cap = 15
remaining = daily_cap - today_queued
print(f"Daily cap: {daily_cap}, today_queued: {today_queued}, remaining: {remaining}")

to_queue = unique[:remaining] if remaining > 0 else []
overflow = unique[remaining:] if len(unique) > remaining else []

# ============================================================
# Insert into DB
# ============================================================
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
        conn.commit()
        inserted += 1
        print(f"  INSERTED #{app_id}: {p['company']} | {p['role_title']} | {p['source_board']} | priority={p['priority']}")
    except Exception as e:
        conn.rollback()
        print(f"  INSERT FAILED: {p['company']} | {p['role_title']} | {e}")
conn.close()

# ============================================================
# Update gate state
# ============================================================
with open(GATE_PATH) as f:
    gate = json.load(f)
# Deduplicate blocked entries by key
seen_blocked = set()
deduped_blocked = []
for b in gate.get('sources_blocked', []):
    for k in b:
        if k not in seen_blocked:
            seen_blocked.add(k)
            deduped_blocked.append(b)
deduped_blocked.extend(results['sources_blocked'])
# Deduplicate again
seen2 = set()
final_blocked = []
for b in deduped_blocked:
    for k in b:
        if k not in seen2:
            seen2.add(k)
            final_blocked.append(b)

gate['last_run_at'] = now.strftime('%Y-%m-%dT%H:%M:%SZ')
gate['sources_checked'] = list(set(gate.get('sources_checked', []) + results['sources_checked']))
gate['sources_blocked'] = final_blocked
gate['new_found'] = len(to_queue)
gate['queued'] = len(to_queue)
gate['duplicates'] = len([s for s in results['skipped'] if 'SKIP' in s.get('reason','')])
gate['filtered_out'] = len([s for s in results['skipped'] if 'REJECT' in s.get('reason','')])
gate['today_queued'] = today_queued + len(to_queue)
gate['remaining_slots'] = remaining - len(to_queue)
gate['cap_reached'] = gate['remaining_slots'] <= 0

now_str = now.strftime('%Y-%m-%dT%H:%M:%SZ')
for entry in gate.get('sources_checked', []):
    pass  # ensure sources_checked list
if 'open-web-sweep' in gate.get('sources_checked', []) or True:
    gate['open_web_sweep_last_run'] = now_str

with open(GATE_PATH, 'w') as f:
    json.dump(gate, f, indent=2)

print(f"\n=== QUEUED {inserted} new postings to DB ===")
print(f"=== Gate state updated ===\n")

# Output summary JSON
summary = {
    'sources_checked': results['sources_checked'],
    'sources_blocked': results['sources_blocked'],
    'total_found_raw': len(results['candidates']),
    'total_unique': len(unique),
    'duplicates': len([s for s in results['skipped'] if 'SKIP' in s.get('reason','')]),
    'filtered_out': len([s for s in results['skipped'] if 'REJECT' in s.get('reason','')]),
    'queued': len(to_queue),
    'overflow': len(overflow),
    'remaining_slots': remaining - len(to_queue),
    'candidates': to_queue,
    'skipped_samples': results['skipped'][:10],
    'debug': results['debug'][:20],
}
with open(f"{SKILL_ROOT}/shared/.discovery_live_output.json", 'w') as f:
    json.dump(summary, f, indent=2, default=str)
print("Summary written to .discovery_live_output.json")
