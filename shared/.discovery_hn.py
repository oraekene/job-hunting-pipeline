#!/usr/bin/env python
"""Fetch HN September 2026 'Who is Hiring' thread and extract PM roles."""

import requests, json, re, datetime, sqlite3
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
    t = re.sub(r'\s*\(\s*(senior|junior|lead|principal|staff|entry|associate)\s*\)$', '', t)
    t = re.sub(r'\s*\(\s*(remote|contract|freelance|temp)\s*\)$', '', t)
    t = re.sub(r'[^\w\s]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def compute_fingerprint(company, role_title, location):
    c = (company or '').lower().strip()
    t = normalize_title(role_title or '')
    l = re.sub(r'\s+', ' ', (location or '').lower().strip())
    return f"{c}|{t}|{l}"

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

def try_queue(url, title, company, location, posted_raw, posted_at, salary, source_board):
    if url in existing_urls:
        return None, 'DUP_URL'
    if not title_matches(title):
        return None, 'NO_MATCH'
    if not passes_salary(salary, salary_floor):
        return None, f'SALARY_FAIL({salary})'
    if company and any(c.lower() in company.lower() for c in companies_exclude):
        return None, 'EXCLUDED'
    fp = compute_fingerprint(company, title, location)
    if fp in existing_fingerprints:
        return None, 'DUP_FP'
    priority = 'normal'
    if not posted_at:
        priority = 'high'  # HN posts don't have individual timestamps
    posting = {
        'posting_url': url, 'company': company or 'Unknown', 'role_title': title,
        'location': location or 'remote', 'posted_at': None, 'posted_at_raw': posted_raw or '',
        'salary_disclosed': bool(salary), 'salary_range': salary or None,
        'source_board': source_board, 'remote_type': 'remote',
        'discovered_at': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'priority': priority, 'posting_fingerprint': fp,
    }
    existing_fingerprints.add(fp)
    existing_urls.add(url)
    return posting, None

# ============================================
# Fetch HN September 2026 "Who is Hiring" thread
# ============================================
hn_thread_url = 'https://news.ycombinator.com/item?id=49522897'
print(f"Fetching HN thread: {hn_thread_url}")
r = requests.get(hn_thread_url, headers=HEADERS, timeout=30)
print(f"Status: {r.status_code}, length: {len(r.text)}")

if r.status_code == 200:
    soup = BeautifulSoup(r.text, 'html.parser')
    comments = soup.select('span.commtext')
    print(f"Found {len(comments)} comments")
    
    pm_keywords = ['product manager', 'ai product', 'technical product', 'growth product',
                   'product owner', 'workflow engineer', 'ai engineer', 'automation engineer',
                   'junior product', 'associate product', 'ai/ml product', 'principal product',
                   'senior product manager', 'product manager']
    
    new_postings = []
    matched = 0
    
    for comment in comments:
        text = comment.get_text(strip=True)
        
        # Check if this comment mentions a PM/AI role
        has_pm = any(kw in text.lower() for kw in pm_keywords)
        if not has_pm:
            continue
        
        matched += 1
        # HN job comment format often looks like:
        # Company Name | Role | Location | Salary | ...
        parts = [p.strip() for p in text.split('|')]
        
        # Try to extract company, role, salary from the pipe-delimited format
        company = 'Unknown'
        role = ''
        salary_str = ''
        job_url = None
        
        # Find the role by matching against title_variants
        for part in parts[:6]:
            part_lower = part.lower()
            # Skip parts that are clearly not company names or roles
            if any(skip in part_lower for skip in ['hiring', 'remote', 'onsite', 'hybrid', 'visa',
                    'salary', 'compensation', 'benefits', 'equity', '$', 'http', 'www', 'pto',
                    'time off', 'healthcare', '401k', 'dental', 'vision', 'full-time', 'contract']):
                if '$' in part or 'salary' in part_lower or 'compensation' in part_lower:
                    salary_str = part
                continue
            if title_matches(part):
                role = part
            elif len(part) > 2 and len(part) < 80 and not any(c.isdigit() for c in part[:3]):
                if company == 'Unknown':
                    company = part
        
        # Extract URL
        url_match = re.search(r'((?:https?://|www\.)[^\s|]+)', text)
        if url_match:
            job_url = url_match.group(1)
            job_url = job_url.rstrip('>')
        
        if not role:
            # Try matching the full text for a role
            for v in title_variants:
                if v.lower() in text.lower():
                    role = v
                    break
        
        if role and title_matches(role):
            # Use the HN thread URL as the posting URL since individual job URLs aren't reliable
            # Try to construct a per-comment URL
            comment_elem = comment.find_parent('div', class_='comment')
            if comment_elem:
                # Try to find the comment ID for a direct link
                pass
            hn_url = hn_thread_url
            posting, reason = try_queue(hn_url, role, company, 'Remote', '', None,
                                        salary_str, 'Hacker News (Sep 2026)')
            if posting:
                new_postings.append(posting)
                print(f"  PM #{matched}: {company} | {role} | salary={salary_str[:50]} | URL={job_url[:60] if job_url else 'N/A'}")
            # else: skip silently
    
    print(f"\n  Total comments with PM keywords: {matched}")
    print(f"  New postings queued: {len(new_postings)}")
    
    # Show a few sample comments for reference
    print("\n  Sample PM comments:")
    shown = 0
    for comment in comments:
        text = comment.get_text(strip=True)
        if any(kw in text.lower() for kw in pm_keywords):
            print(f"    ---")
            print(f"    {text[:300]}")
            shown += 1
            if shown >= 5:
                break

# ============================================
# Queue to DB
# ============================================
print("\n" + "=" * 60)
print("FINAL QUEUE")
print("=" * 60)

seen_fp = set()
unique = []
for p in new_postings:
    if p['posting_fingerprint'] not in seen_fp:
        seen_fp.add(p['posting_fingerprint'])
        unique.append(p)

print(f"Total new postings: {len(new_postings)}")
print(f"After intra-run dedup: {len(unique)}")

with open(f"{SKILL_ROOT}/shared/.discovery_gate_state.json") as f:
    gate_state = json.load(f)
remaining = gate_state.get('remaining_slots', 15)
print(f"Daily cap remaining: {remaining}")

to_queue = unique[:remaining]
if len(unique) > remaining:
    print(f"  (capped: {len(unique) - remaining} exceed daily limit)")

db_conn = sqlite3.connect(f"{SKILL_ROOT}/shared/applications.db")
cur2 = db_conn.cursor()
inserted = 0
for p in to_queue:
    try:
        cur2.execute("""
            INSERT INTO applications
            (posting_url, company, role_title, source_board, posted_at, posted_at_raw,
             discovered_at, priority, posting_fingerprint, remote_type, salary_disclosed,
             salary_range, status, last_failure_stage)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'discovered', NULL)
        """, (p['posting_url'], p['company'], p['role_title'], p['source_board'],
              p['posted_at'], p['posted_at_raw'], p['discovered_at'],
              p['priority'], p['posting_fingerprint'], p['remote_type'],
              p['salary_disclosed'], p['salary_range']))
        app_id = cur2.lastrowid
        cur2.execute("""
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

gate_state['last_run_at'] = now.strftime('%Y-%m-%dT%H:%M:%SZ')
gate_state['new_found'] = len(to_queue)
gate_state['queued'] = len(to_queue)
gate_state['today_queued'] = gate_state.get('today_queued', 0) + len(to_queue)
gate_state['remaining_slots'] = remaining - len(to_queue)
gate_state['open_web_sweep_last_run'] = now.strftime('%Y-%m-%dT%H:%M:%SZ')

with open(f"{SKILL_ROOT}/shared/.discovery_gate_state.json", 'w') as f:
    json.dump(gate_state, f, indent=2)

print(f"\n=== QUEUED {inserted} new postings to DB ===")
