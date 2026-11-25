#!/usr/bin/env python3
"""
Live discovery scan v2 — corrected title matching, proper HN extraction,
Bing open-web sweep for ATS platforms.
Fetches from accessible sources, dedupes against DB, cheap-filters against
target profile, and queues new postings.
"""
import sqlite3, json, re, datetime, urllib.request, urllib.parse, sys, os
import yaml

SKILL_ROOT = r"C:/Users/rotim/AppData/Local/hermes/skills/job-hunting"
DB_PATH = f"{SKILL_ROOT}/shared/applications.db"
TARGET_PATH = f"{SKILL_ROOT}/shared/target-profile.yaml"
GATE_PATH = f"{SKILL_ROOT}/shared/.discovery_gate_state.json"

# --- Load target profile ---
with open(TARGET_PATH) as f:
    target = yaml.safe_load(f)
title_variants = [tv['title'] for tv in target.get('title_variants', [])]
salary_floor = target.get('salary_floor', {})
companies_exclude = target.get('companies_exclude', [])
seniority_band = target.get('seniority_band', 'mid')

# --- Load DB state ---
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
existing_fingerprints = set(r[0] for r in cur.execute("SELECT posting_fingerprint FROM applications WHERE posting_fingerprint IS NOT NULL"))
existing_urls = set(r[0] for r in cur.execute("SELECT DISTINCT posting_url FROM applications WHERE posting_url IS NOT NULL AND length(posting_url) > 0"))
existing_source_urls = set(r[0] for r in cur.execute("SELECT DISTINCT posting_url FROM posting_sources WHERE posting_url IS NOT NULL AND length(posting_url) > 0"))
all_known_urls = existing_urls | existing_source_urls
today_queued = cur.execute("SELECT COUNT(*) FROM applications WHERE status='discovered' AND date(discovered_at) = date('now')").fetchone()[0]
total_db = cur.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
conn.close()

now = datetime.datetime.now(datetime.timezone.utc)
recent_cutoff = now - datetime.timedelta(hours=24)
last_run = datetime.datetime.fromisoformat("2026-09-14T07:07:54+00:00")

# --- Target profile filters ---
PM_KEYWORDS = [
    'product manager', 'ai product manager', 'technical product manager',
    'growth product manager', 'associate product manager', 'junior product manager',
    'product owner', 'ai engineer', 'automation engineer', 'workflow engineer',
    'ai/ml product manager', 'machine learning product manager',
    'head of product', 'lead product manager', 'staff product manager',
    'principal product manager', 'product manager', 'ai product',
]

# Senior-level variants we also accept (seniority_band is 'mid', but senior PM roles are fine)
SENIOR_ACCEPT = ['senior', 'lead', 'principal', 'staff', 'head of', 'director']

def normalize_title(title):
    """Normalize a job title for fingerprinting — lowercase, strip decorations."""
    t = (title or '').lower().strip()
    t = re.sub(r'\s*#\d+\s*$', '', t)  # trailing req IDs like "#123"
    t = re.sub(r'\s*\([IVX]+\)\s*$', '', t)  # roman numerals
    t = re.sub(r'\s*\(\s*(senior|junior|lead|principal|staff|mid|entry|associate)\s*\)\s*$', '', t)
    t = re.sub(r'\s*\(\s*(remote|contract|freelance|temp)\s*\)\s*$', '', t)
    t = re.sub(r'[^\\w\\s]', ' ', t)  # FIX: single backslash in file = \\w in regex
    t = re.sub(r'\\s+', ' ', t).strip()
    return t

def compute_fingerprint(company, role_title, location):
    c = (company or '').lower().strip()
    t = normalize_title(role_title or '')
    l = re.sub(r'\\s+', ' ', (location or '').lower().strip())
    return f"{c}|{t}|{l}"

def title_matches(title):
    """Check if a job title matches any target title variant — substring match only."""
    if not title:
        return False
    tl = title.lower().strip()
    # Check if any PM keyword is a substring of the title
    for kw in PM_KEYWORDS:
        if kw in tl:
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
    """Parse a posted-at date string; returns (datetime, raw_str)."""
    if not posted_raw:
        return None, ''
    ps = str(posted_raw).strip()
    # ISO format
    try:
        dt = datetime.datetime.fromisoformat(ps)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt, ps
    except:
        pass
    for fmt in ['%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%B %d, %Y', '%b %d, %Y', '%Y-%m-%d %H:%M:%S']:
        try:
            dt = datetime.datetime.strptime(ps, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return dt, ps
        except:
            pass
    t = ps.lower().strip()
    n = now
    if 'today' in t or 'just now' in t:
        return n, ps
    if 'yesterday' in t:
        return n - datetime.timedelta(days=1), ps
    m = re.match(r'(\\d+)\s+hour', t)
    if m:
        return n - datetime.timedelta(hours=int(m.group(1))), ps
    m = re.match(r'(\\d+)\s+day', t)
    if m:
        return n - datetime.timedelta(days=int(m.group(1))), ps
    return None, ps

def try_queue(url, title, company, location, posted_raw, source_board, salary_text=''):
    """Returns (posting_dict, None) or (None, reason)."""
    if not url:
        return None, 'SKIP (no URL)'
    if url in all_known_urls:
        return None, 'SKIP (URL already in DB)'
    if not title_matches(title):
        return None, f'REJECT (title: {title[:60]})'
    if not passes_salary(salary_text, salary_floor):
        return None, f'REJECT (salary floor: {salary_text})'
    if company and any(c.lower() in company.lower() for c in companies_exclude):
        return None, f'REJECT (company excluded: {company})'
    fp = compute_fingerprint(company, title, location)
    if fp in existing_fingerprints:
        return None, f'SKIP (Fingerprint dup: {fp})'
    posted_at, posted_raw_str = extract_posted(posted_raw)
    priority = 'normal'
    if posted_at and posted_at > recent_cutoff:
        priority = 'high'
    elif not posted_at:
        priority = 'high'
    # Recency check: only keep postings from the last 7 days
    if posted_at and posted_at < (now - datetime.timedelta(days=7)):
        return None, f'REJECT (too old: {posted_at})'
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

# ============================================================
# HTTP helper
# ============================================================
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

def fetch_url(url, timeout=20):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode('utf-8', errors='replace')

# ============================================================
# Results collection
# ============================================================
candidates = []
skipped = []
sources_checked = []
sources_blocked = []

# ============================================================
# 1. Remotive API
# ============================================================
print("=" * 60)
print("1. Remotive API")
print("=" * 60)
try:
    remotive_search_terms = ['product-manager', 'ai-product-manager', 'ai-engineer', 
                             'automation-engineer', 'workflow-engineer', 'product-owner',
                             'technical-product-manager']
    seen_remotive = set()
    total_remotive = 0
    for term in remotive_search_terms:
        encoded = urllib.parse.quote(term)
        url = f"https://remotive.com/api/remote-jobs?limit=100&search={encoded}"
        try:
            st, body = fetch_url(url, timeout=15)
            print(f"  Remotive '{term}': HTTP {st}, body={len(body)} chars")
            if st == 200:
                data = json.loads(body)
                jobs = data.get('jobs', [])
                for j in jobs:
                    title = j.get('title', '')
                    company = j.get('company_name', '')
                    jurl = j.get('url', '')
                    if jurl in seen_remotive:
                        continue
                    seen_remotive.add(jurl)
                    total_remotive += 1
                    # Parse posted date
                    posted_str = j.get('date_posted', '') or j.get('publication_to', '')
                    salary = j.get('salary', '')
                    category = j.get('category', {}).get('title', '') if isinstance(j.get('category'), dict) else ''
                    location = 'Remote'
                    
                    p, reason = try_queue(jurl, title, company, location, posted_str, 'Remotive', salary)
                    if p:
                        candidates.append(p)
                        print(f"  MATCH: {company} | {title} | priority={p['priority']}")
                    elif reason and 'SKIP' in reason:
                        pass  # duplicate
                    elif reason:
                        print(f"  Filter: {reason}")
                print(f"  Jobs: {len(jobs)}, unique URLs: {len(seen_remotive)}")
        except Exception as e:
            print(f"  Remotive '{term}' error: {type(e).__name__}: {str(e)[:80]}")
    
    sources_checked.append('remotive-api')
    print(f"  Total unique Remotive jobs: {total_remotive}")
except Exception as e:
    err = f"BLOCKED/ERROR: {type(e).__name__}: {str(e)[:120]}"
    sources_blocked.append({'remotive-api': err})
    print(f"  Remotive error: {err}")

# ============================================================
# 2. HN "Who is Hiring" via Algolia API
# ============================================================
print("\n" + "=" * 60)
print("2. HN 'Who is Hiring' via Algolia")
print("=" * 60)
try:
    # Search for the most recent "who is hiring" story
    search_url = 'https://hn.algolia.com/api/v1/search'
    params = {'query': 'who is hiring', 'restrictSearchableAttributes': 'title', 'tags': 'story', 'hitsPerPage': 10}
    st, body = fetch_url(search_url + '?' + urllib.parse.urlencode(params), timeout=15)
    print(f"  HN Algolia: HTTP {st}")
    if st == 200:
        data = json.loads(body)
        hits = data.get('hits', [])
        print(f"  Found {len(hits)} 'who is hiring' stories")
        
        # Find most recent hiring thread from September 2026
        best_thread = None
        for hit in hits:
            title = hit.get('title', '')
            created = hit.get('created_at', '')
            hn_id = hit.get('objectID', '')
            print(f"  Story: {title} (id={hn_id}, created={created})")
            # Look for September 2026 threads
            if '2026' in created and ('september' in created.lower() or 'sep' in created.lower() or '2026-09' in created):
                best_thread = (title, hn_id, created)
            elif not best_thread and '2026' in created:
                best_thread = (title, hn_id, created)
        
        if best_thread:
            title, hn_id, created = best_thread
            hn_url = f"https://news.ycombinator.com/item?id={hn_id}"
            print(f"  Fetching thread: {title} ({hn_url})")
            st2, html = fetch_url(hn_url, timeout=20)
            print(f"  Thread: HTTP {st2}, body={len(html)} chars")
            
            if st2 == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, 'html.parser')
                
                # Extract comment text — HN comments are in various structures
                # Try span.commtext first, then broader approaches
                comment_texts = []
                
                # Method 1: span.commtext (older HN)
                for span in soup.select('span.commtext'):
                    text = span.get_text(separator=' ', strip=True)
                    if text and len(text) > 10:
                        comment_texts.append(text)
                
                # Method 2: div.comment-text (newer HN)
                if not comment_texts or len(comment_texts) < 5:
                    for div in soup.select('div.comment-text'):
                        text = div.get_text(separator=' ', strip=True)
                        if text and len(text) > 10:
                            comment_texts.append(text)
                
                # Method 3: Find all text containing PM keywords
                if not comment_texts or len(comment_texts) < 10:
                    page_text = soup.get_text(separator='\n', strip=True)
                    for line in page_text.split('\n'):
                        line = line.strip()
                        if len(line) > 15 and any(kw in line.lower() for kw in ['product manager', 'ai product', 'ai engineer', 'automation engineer', 'workflow engineer', 'product owner']):
                            comment_texts.append(line)
                
                print(f"  Extracted {len(comment_texts)} comments")
                
                # Look for pipe-delimited PM listings
                pm_found = 0
                for text in comment_texts:
                    if not title_matches(text) and not any(kw in text.lower() for kw in PM_KEYWORDS):
                        continue
                    # HN hiring format: Company | Role | Location | Salary | site:URL
                    parts = [p.strip() for p in text.split('|')]
                    if len(parts) >= 2:
                        company = 'Unknown'
                        role = ''
                        for part in parts[:5]:
                            part_stripped = part.strip()
                            if not part_stripped:
                                continue
                            if title_matches(part_stripped):
                                role = part_stripped
                            elif len(part_stripped) > 2 and len(part_stripped) < 80 and company == 'Unknown':
                                # Skip parts that are clearly not company names
                                lower_p = part_stripped.lower()
                                if any(kw in lower_p for kw in ['remote', 'hiring', 'contract', 'full-time', 'part-time', 'visa', 
                                    'salary', 'compensation', '$', 'http', 'us', 'canada', 'worldwide', 'onsite', 'hybrid',
                                    'equity', 'stock', 'pto', 'pto', 'benefits', 'w-2', '1099', 'today', 'yesterday',
                                    'day ago', 'week ago', 'month', 'year', 'usd', 'eur', 'gbp', 'ngn']):
                                    continue
                                if not re.search(r'[a-z]', lower_p):
                                    continue
                                company = part_stripped
                        
                        # Extract URL
                        url_match = re.search(r'((?:https?://|www\.)[^\s|]+)', text)
                        job_url = url_match.group(1) if url_match else hn_url
                        
                        if role and title_matches(role) and company != 'Unknown':
                            p, reason = try_queue(job_url, role, company, 'remote', '', 'Hacker News (Who is Hiring)', '')
                            if p:
                                candidates.append(p)
                                pm_found += 1
                                print(f"  HN MATCH: {company} | {role} | priority={p['priority']}")
                            elif reason and 'SKIP' in reason:
                                pass
                            elif reason:
                                print(f"  HN Filter: {reason}")
                
                print(f"  PM postings queued from HN: {pm_found}")
                sources_checked.append('hnrss-who-is-hiring')
            else:
                sources_blocked.append({'hnrss-who-is-hiring': f'BLOCKED — HTTP {st2}'})
        else:
            print("  No September 2026 'Who is Hiring' thread found")
            sources_checked.append('hnrss-who-is-hiring')
except Exception as e:
    err = f"BLOCKED/ERROR: {type(e).__name__}: {str(e)[:120]}"
    sources_blocked.append({'hnrss-who-is-hiring': err})
    print(f"  HN error: {err}")

# ============================================================
# 3. Wellfound (verify)
# ============================================================
print("\n" + "=" * 60)
print("3. Wellfound (verify)")
print("=" * 60)
try:
    st, body = fetch_url("https://wellfound.com/jobs", timeout=20)
    print(f"  Wellfound: HTTP {st}, body={len(body)} chars")
    if st == 200:
        job_urls = list(set(re.findall(r'href="(https://wellfound\.com/jobs/\d+[^\"]*)"', body)))
        if len(job_urls) > 0:
            print(f"  Wellfound job links: {len(job_urls)}")
            sources_checked.append('wellfound')
            # Try fetching a few job pages for JSON-LD
            from bs4 import BeautifulSoup
            for jurl in job_urls[:10]:
                try:
                    st2, jhtml = fetch_url(jurl, timeout=15)
                    if st2 != 200:
                        continue
                    soup = BeautifulSoup(jhtml, 'html.parser')
                    ld_scripts = soup.find_all('script', type='application/ld+json')
                    for script in ld_scripts:
                        try:
                            data = json.loads(script.string)
                            if isinstance(data, list):
                                data = data[0]
                            if isinstance(data, dict) and data.get('@type') == 'JobPosting':
                                title = data.get('title', '') or data.get('jobTitle', '')
                                ho = data.get('hiringOrganization', '')
                                company = ho.get('name', '') if isinstance(ho, dict) else str(ho)
                                loc_data = data.get('jobLocation', {})
                                if isinstance(loc_data, list) and loc_data:
                                    loc_data = loc_data[0]
                                location = 'remote'
                                if isinstance(loc_data, dict):
                                    addr = loc_data.get('address', {})
                                    if isinstance(addr, dict):
                                        parts = [addr.get('addressLocality',''), addr.get('addressRegion',''), addr.get('addressCountry','')]
                                        location = ', '.join(p for p in parts if p) or 'remote'
                                posted_raw = data.get('datePosted', '')
                                salary_obj = data.get('baseSalary', {})
                                salary_text = ''
                                if isinstance(salary_obj, dict):
                                    val = salary_obj.get('value', {})
                                    if isinstance(val, dict):
                                        salary_text = f"{salary_obj.get('currency','USD')} {val.get('minValue','')} - {val.get('maxValue','')} {val.get('unitText','')}"
                                p, reason = try_queue(jurl, title, company, location, posted_raw, 'wellfound', salary_text)
                                if p:
                                    candidates.append(p)
                                    print(f"  WF MATCH: {company} | {title} | priority={p['priority']}")
                                elif reason and 'SKIP' in reason:
                                    pass
                                break
                        except:
                            continue
                except:
                    continue
        else:
            sources_blocked.append({'wellfound': f'BLOCKED — HTTP {st}, no job links extracted (anti-bot/captcha or JS-rendered)'})
    else:
        sources_blocked.append({'wellfound': f'BLOCKED — HTTP {st}'})
except Exception as e:
    err = f"BLOCKED/ERROR: {type(e).__name__}: {str(e)[:150]}"
    sources_blocked.append({'wellfound': err})

# ============================================================
# 4. Bing Open-Web Sweep (ATS platforms)
# ============================================================
print("\n" + "=" * 60)
print("4. Bing Open-Web Sweep (ATS platforms)")
print("=" * 60)

ATS_QUERIES = [
    ('greenhouse', 'site:boards.greenhouse.io "product manager" remote'),
    ('lever', 'site:jobs.lever.co "product manager" remote'),
    ('ashby', 'site:jobs.ashbyhq.com "product manager" remote'),
    ('workday', '"product manager" remote site:.workday.com jobs'),
    ('smartrecruiters', 'site:jobs.smartrecruit.co "product manager" remote'),
    ('generic', '"hiring" "product manager" remote job 2026'),
]

bing_sources_checked = []
ats_domains = {
    'greenhouse': 'boards.greenhouse.io',
    'lever': 'jobs.lever.co',
    'ashby': 'jobs.ashbyhq.com',
    'workday': 'workday.com',
    'smartrecruiters': 'jobs.smartrecruit.co',
}

for source_name, query in ATS_QUERIES:
    try:
        encoded = urllib.parse.quote(query)
        bing_url = f"https://www.bing.com/search?q={encoded}&count=20"
        st, html = fetch_url(bing_url, timeout=20)
        print(f"  Bing '{query[:50]}': HTTP {st}, body={len(html)} chars")
        if st != 200 or len(html) < 500:
            print(f"    BLOCKED or empty response")
            sources_blocked.append({f'open_web_bing_{source_name}': f'BLOCKED — HTTP {st}, body={len(html)}'})
            continue
        
        # Parse Bing search results
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract result URLs from Bing HTML
        # Bing uses <li class="b_algo"> with <h2><a href="url">
        result_urls = []
        for li in soup.select('li.b_algo'):
            a = li.select_one('h2 a') or li.select_one('a')
            if a and a.get('href'):
                href = a.get('href')
                if href.startswith('http') and 'bing.com' not in href:
                    result_urls.append((href, a.get_text(strip=True)[:100]))
        
        # Fallback: extract all external HTTP links from <h2> tags
        if not result_urls:
            for h2 in soup.select('h2'):
                a = h2.find('a')
                if a and a.get('href') and a.get('href').startswith('http'):
                    result_urls.append((a['href'], a.get_text(strip=True)[:100]))
        
        print(f"    Found {len(result_urls)} result URLs")
        
        # For each result URL, check if it's a job posting on an ATS domain
        for url, title_text in result_urls:
            if url in all_known_urls:
                continue
            # Fetch the job page and extract JSON-LD
            try:
                st2, job_html = fetch_url(url, timeout=15)
                if st2 != 200:
                    continue
                soup2 = BeautifulSoup(job_html, 'html.parser')
                ld_scripts = soup2.find_all('script', type='application/ld+json')
                for script in ld_scripts:
                    try:
                        data = json.loads(script.string)
                        if isinstance(data, list):
                            data = data[0]
                        if isinstance(data, dict) and data.get('@type') == 'JobPosting':
                            title = data.get('title', '') or data.get('jobTitle', '')
                            ho = data.get('hiringOrganization', '')
                            company = ho.get('name', '') if isinstance(ho, dict) else str(ho)
                            loc_data = data.get('jobLocation', {})
                            if isinstance(loc_data, list) and loc_data:
                                loc_data = loc_data[0]
                            location = 'remote'
                            if isinstance(loc_data, dict):
                                addr = loc_data.get('address', {})
                                if isinstance(addr, dict):
                                    parts = [addr.get('addressLocality',''), addr.get('addressRegion',''), addr.get('addressCountry','')]
                                    location = ', '.join(p for p in parts if p) or 'remote'
                            posted_raw = data.get('datePosted', '')
                            salary_obj = data.get('baseSalary', {})
                            salary_text = ''
                            if isinstance(salary_obj, dict):
                                val = salary_obj.get('value', {})
                                if isinstance(val, dict):
                                    salary_text = f"{salary_obj.get('currency','USD')} {val.get('minValue','')} - {val.get('maxValue','')} {val.get('unitText','')}"
                            elif isinstance(salary_obj, str):
                                salary_text = salary_obj
                            p, reason = try_queue(url, title, company, location, posted_raw, f'bing_{source_name}', salary_text)
                            if p:
                                candidates.append(p)
                                print(f"  BING MATCH: {company} | {title} | priority={p['priority']}")
                            elif reason and 'SKIP' in reason:
                                pass
                            elif reason:
                                print(f"  BING Filter: {reason}")
                            break  # one JobPosting per page
                    except:
                        continue
            except:
                continue
        
        bing_sources_checked.append(f'open_web_bing_{source_name}')
        
    except Exception as e:
        sources_blocked.append({f'open_web_bing_{source_name}': f'BLOCKED/ERROR: {type(e).__name__}: {str(e)[:100]}'})
        print(f"  Bing '{source_name}' error: {e}")

sources_checked.extend(bing_sources_checked)

# ============================================================
# 5. Blocked sources (LinkedIn, Indeed, RemoteOK)
# ============================================================
sources_blocked.append({'linkedin-global': 'BLOCKED — sign-in wall (per memory/env config)'})
sources_blocked.append({'indeed-global': 'BLOCKED — sign-in wall / ATS wall (per memory/env config)'})
sources_blocked.append({'remote-ok': 'BLOCKED — anti-bot/redirect (per memory/env config)'})

# ============================================================
# Dedup + daily cap
# ============================================================
print("\n" + "=" * 60)
print("DEDUP + DAILY CAP")
print("=" * 60)
seen_fp = set()
unique = []
for p in candidates:
    if p['posting_fingerprint'] not in seen_fp:
        seen_fp.add(p['posting_fingerprint'])
        unique.append(p)
    else:
        print(f"  Intra-run dup: {p['company']} | {p['role_title']}")

daily_cap = 15
remaining = daily_cap - today_queued
print(f"Total candidates: {len(candidates)}")
print(f"After intra-run dedup: {len(unique)}")
print(f"Skipped (dup/filter): tracked separately")
print(f"Daily cap: {daily_cap}, today_queued: {today_queued}, remaining: {remaining}")

to_queue = unique[:remaining] if remaining > 0 else []
overflow = unique[remaining:] if len(unique) > remaining else []

# ============================================================
# Insert into DB
# ============================================================
print(f"\nInserting {len(to_queue)} postings into DB...")
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

# Merge sources
gate['sources_checked'] = list(set(gate.get('sources_checked', []) + sources_checked))
# Merge blocked: accumulate unique by key
existing_blocked_keys = set()
for b in gate.get('sources_blocked', []):
    for k in b:
        existing_blocked_keys.add(k)
for b in sources_blocked:
    for k in b:
        if k not in existing_blocked_keys:
            gate['sources_blocked'].append(b)
            existing_blocked_keys.add(k)

now_str = now.strftime('%Y-%m-%dT%H:%M:%SZ')
gate['last_run_at'] = now_str
gate['new_found'] = len(to_queue)
gate['queued'] = len(to_queue)
gate['duplicates'] = gate.get('duplicates', 0) + len([c for c in candidates if c.get('_dup', False)])
gate['filtered_out'] = gate.get('filtered_out', 0)
gate['today_queued'] = today_queued + len(to_queue)
gate['remaining_slots'] = daily_cap - gate['today_queued']
gate['cap_reached'] = gate['remaining_slots'] <= 0
gate['daily_cap'] = daily_cap
if any('bing' in s for s in sources_checked):
    gate['open_web_sweep_last_run'] = now_str

with open(GATE_PATH, 'w') as f:
    json.dump(gate, f, indent=2)

print(f"\n{'='*60}")
print(f"DISCOVERY COMPLETE")
print(f"{'='*60}")
print(f"Sources checked: {sources_checked}")
print(f"Sources blocked: {[list(b.keys())[0] for b in sources_blocked]}")
print(f"Total candidates found: {len(candidates)}")
print(f"Unique candidates: {len(unique)}")
print(f"Inserted into DB: {inserted}")
print(f"Overflow (cap): {len(overflow)}")
print(f"Remaining slots: {gate['remaining_slots']}")
print(f"Gate state updated at: {now_str}")

# Write summary
summary = {
    'timestamp': now_str,
    'sources_checked': sources_checked,
    'sources_blocked': sources_blocked,
    'total_found_raw': len(candidates),
    'total_unique': len(unique),
    'duplicates': len([c for c in candidates if c.get('_dup', False)]),
    'filtered_out': 0,
    'queued': len(to_queue),
    'overflow': len(overflow),
    'remaining_slots': gate['remaining_slots'],
    'candidates': to_queue,
    'debug_last': candidates[:10],
}
# Don't save candidates with sensitive data
with open(f"{SKILL_ROOT}/shared/.discovery_live_output.json", 'w') as f:
    json.dump({
        'timestamp': now_str,
        'sources_checked': sources_checked,
        'sources_blocked': sources_blocked,
        'total_found_raw': len(candidates),
        'total_unique': len(unique),
        'queued': len(to_queue),
        'overflow': len(overflow),
        'remaining_slots': gate['remaining_slots'],
    }, f, indent=2, default=str)
