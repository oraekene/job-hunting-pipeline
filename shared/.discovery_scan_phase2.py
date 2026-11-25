#!/usr/bin/env python
"""Phase 2: extract detailed info from source URLs found in phase 1."""

import requests, json, re, sqlite3, datetime
from bs4 import BeautifulSoup
import yaml

SKILL_ROOT = "C:/Users/rotim/AppData/Local/hermes/skills/job-hunting"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

# Load target profile
with open(f"{SKILL_ROOT}/shared/target-profile.yaml") as f:
    target = yaml.safe_load(f)

title_variants = [tv['title'] for tv in target.get('title_variants', [])]
title_variants_norm = [t.lower().strip() for t in title_variants]

# Load DB
conn = sqlite3.connect(f"{SKILL_ROOT}/shared/applications.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()
existing_fingerprints = set()
for r in cur.execute('SELECT posting_fingerprint FROM applications WHERE posting_fingerprint IS NOT NULL'):
    existing_fingerprints.add(r[0])
existing_urls = set()
for r in cur.execute('SELECT DISTINCT posting_url FROM applications'):
    existing_urls.add(r[0])
conn.close()

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
    return f"{c}|{t}|{l}"

def title_matches(role_title):
    t_lower = role_title.lower().strip()
    t_norm = normalize_title(role_title)
    for v in title_variants:
        v_lower = v.lower().strip()
        v_norm = normalize_title(v)
        # Match if variant is substring of title or vice versa
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
    # Find $XX,XXX or $XX.Xk or $XXk
    dollar_matches = re.findall(r'\$?\s*([\d,]+\.?\d*)\s*(?:k|thousand|per year|annual|yr|yearly)?', text)
    for m in dollar_matches:
        try:
            val = float(m.replace(',', ''))
            if val < 1000 and ('k' in text or 'thousand' in text):
                val *= 1000
            amounts.append(val)
        except:
            pass
    if amounts:
        max_amount = max(amounts)
        floor_amount = floor.get('amount', 0)
        if max_amount >= floor_amount:
            return True
        # Check if monthly (e.g., $3,000/month -> $36k/year)
        if 'month' in text and max_amount * 12 >= floor_amount:
            return True
        if max_amount < floor_amount * 0.3:  # clearly below floor
            return False
    return True  # can't determine — don't reject

def extract_posted_from_date(posted_raw):
    """Parse posted_at from various date formats. Returns ISO datetime or None."""
    if not posted_raw:
        return None
    # Try ISO format
    try:
        return datetime.datetime.fromisoformat(posted_raw)
    except:
        pass
    # Try common formats
    for fmt in ['%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%B %d, %Y', '%b %d, %Y']:
        try:
            dt = datetime.datetime.strptime(posted_raw.strip(), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return dt
        except:
            pass
    # Try relative ("2 hours ago", "today", "yesterday")
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

def fetch_job_page(url):
    """Fetch a job page and extract structured info."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Try JSON-LD
        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    data = data[0]
                if isinstance(data, dict) and data.get('@type') in ('JobPosting', 'job'):
                    return {
                        'title': data.get('title') or data.get('jobTitle', ''),
                        'company': data.get('hiringOrganization', {}).get('name', '') if isinstance(data.get('hiringOrganization'), dict) else data.get('hiringOrganization', ''),
                        'location': data.get('jobLocation', {}).get('address', {}).get('addressLocality', '') if isinstance(data.get('jobLocation'), dict) else str(data.get('jobLocation', '')),
                        'posted_at_raw': data.get('datePosted', ''),
                        'posted_at': extract_posted_from_date(data.get('datePosted', '')),
                        'salary': json.dumps(data.get('baseSalary', '')) if data.get('baseSalary') else '',
                        'url': url,
                        'remote_type': 'remote' if data.get('telecom') or 'remote' in str(data.get('jobLocation', '')).lower() else '',
                    }
            except (json.JSONDecodeError, TypeError):
                continue
        
        # Fallback: extract from page text/og tags
        title_tag = soup.find('title')
        title = title_tag.get_text(strip=True)[:200] if title_tag else ''
        
        # Try to get meta tags
        og_title = soup.find('meta', property='og:title')
        og_desc = soup.find('meta', property='og:description')
        title = og_title.get('content', '')[:200] if og_title else title
        desc = og_desc.get('content', '')[:500] if og_desc else ''
        
        # Try to extract company from text patterns
        company = ''
        # Wellfound: looks for "at" in title or a company selector
        wf_company = soup.select_one('[data-test="company-name"], .company-name, [data-testid="company"]')
        if wf_company:
            company = wf_company.get_text(strip=True)
        
        # Try to find posted date
        posted_raw = ''
        date_elem = soup.find('time')
        if date_elem:
            posted_raw = date_elem.get('datetime', date_elem.get_text(strip=True))
        
        # Try "Posted" or "Updated" text
        if not posted_raw:
            date_match = re.search(r'(?:posted|updated)\s+(?:on\s+)?([A-Z][a-z]+ \d{1,2}, \d{4})', r.text, re.I)
            if date_match:
                posted_raw = date_match.group(1)
        
        location = ''
        loc_match = re.search(r'(?:location|remote|onsite|hybrid)[:]\s*([^\n<]+)', desc, re.I)
        if loc_match:
            location = loc_match.group(1).strip()[:100]
        
        salary = ''
        salary_match = re.search(r'(?:salary|pay|compensation)[:\s$]+([\d,.]+(?:k|K)?(?:-\s*[\d,.]+(?:k|K)?)?)\s*(USD|usd|per year|monthly|/month)?', r.text, re.I)
        if salary_match:
            salary = salary_match.group(0)[:100]
        
        return {
            'title': title,
            'company': company,
            'location': location,
            'posted_at_raw': posted_raw,
            'posted_at': extract_posted_from_date(posted_raw),
            'salary': salary,
            'url': url,
            'remote_type': 'remote' if 'remote' in (title + desc).lower() else '',
            'raw_desc': desc,
        }
    except Exception as e:
        return None

# ============================================
# Process Wellfound job links from phase 1
# ============================================
print("=" * 60)
print("Processing Wellfound job detail pages")
print("=" * 60)

# These are the Wellfound URLs found in phase 1 that match PM titles
wf_urls = [
    "https://wellfound.com/jobs/4704152-principal-product-manager",
    "https://wellfound.com/jobs/4704106-product-manager-platform",
    "https://wellfound.com/jobs/4704104-product-manager-onboarding-and-growth",
    "https://wellfound.com/jobs/4174541-product-manager",
]

new_postings = []
for url in wf_urls:
    if url in existing_urls:
        print(f"  SKIP (duplicate URL): {url}")
        continue
    print(f"\n  Fetching: {url}")
    job = fetch_job_page(url)
    if job:
        print(f"    Title: {job['title']}")
        print(f"    Company: {job['company']}")
        print(f"    Location: {job['location']}")
        print(f"    Posted: {job['posted_at_raw']} -> {job['posted_at']}")
        print(f"    Salary: {job['salary']}")
        print(f"    Remote: {job.get('remote_type', '')}")
        
        # Check title match
        if not title_matches(job['title']):
            print(f"    REJECTED: title doesn't match variants")
            continue
        
        # Check salary
        if not passes_salary(job['salary'], target.get('salary_floor', {})):
            print(f"    REJECTED: salary below floor")
            continue
        
        # Check company exclusions
        if job['company'] and any(c.lower() in job['company'].lower() for c in target.get('companies_exclude', [])):
            print(f"    REJECTED: company in exclude list")
            continue
        
        # Compute fingerprint
        fingerprint = compute_fingerprint(job['company'], job['title'], job.get('location', 'remote'))
        if fingerprint in existing_fingerprints:
            print(f"    REJECTED: fingerprint already exists ({fingerprint})")
            continue
        
        # Determine priority
        priority = 'normal'
        if job['posted_at']:
            if job['posted_at'] > recent_cutoff:
                priority = 'high'
        else:
            # Use discovered_at — recent means high priority
            priority = 'high'
        
        posting = {
            'posting_url': url,
            'company': job['company'] or 'Unknown',
            'role_title': job['title'],
            'location': job.get('location') or 'remote',
            'posted_at': job['posted_at'].strftime('%Y-%m-%dT%H:%M:%SZ') if job['posted_at'] else None,
            'posted_at_raw': job.get('posted_at_raw', ''),
            'salary_disclosed': bool(job['salary']),
            'salary_range': job['salary'] or None,
            'source_board': 'wellfound',
            'remote_type': job.get('remote_type') or 'remote',
            'discovered_at': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'priority': priority,
            'posting_fingerprint': fingerprint,
        }
        new_postings.append(posting)
        print(f"    -> QUEUED as new posting (priority={priority}, fingerprint={fingerprint})")
    else:
        print(f"    FAILED to fetch")

# ============================================
# Try more Wellfound job links from the page
# ============================================
print("\n" + "=" * 60)
print("Fetching more Wellfound job links from main page")
print("=" * 60)

try:
    r = requests.get('https://wellfound.com/jobs', headers=HEADERS, timeout=15)
    soup = BeautifulSoup(r.text, 'html.parser')
    job_links = soup.find_all('a', href=re.compile(r'/jobs/\d+'))
    
    # Filter for PM-related titles
    pm_keywords = ['product manager', 'ai product', 'technical product', 'growth product',
                   'product owner', 'workflow engineer', 'product manager ai', 'ai engineer',
                   'automation engineer', 'junior product', 'associate product']
    
    pm_urls = []
    for link in job_links:
        href = link.get('href', '')
        full_url = f"https://wellfound.com{href}" if href.startswith('/') else href
        text = link.get_text(strip=True).lower()
        if any(kw in text for kw in pm_keywords) and full_url not in existing_urls and full_url not in wf_urls:
            pm_urls.append(full_url)
    
    print(f"Found {len(pm_urls)} Wellfound PM-related job links (new)")
    
    for url in pm_urls[:15]:
        if url in existing_urls:
            continue
        job = fetch_job_page(url)
        if not job:
            continue
        if not title_matches(job['title']):
            continue
        if not passes_salary(job['salary'], target.get('salary_floor', {})):
            continue
        company = job['company'] or 'Unknown'
        if any(c.lower() in company.lower() for c in target.get('companies_exclude', [])):
            continue
        
        fingerprint = compute_fingerprint(company, job['title'], job.get('location') or 'remote')
        if fingerprint in existing_fingerprints:
            print(f"  SKIP (fingerprint dup): {company} | {job['title']}")
            continue
        
        priority = 'normal'
        if job['posted_at'] and job['posted_at'] > recent_cutoff:
            priority = 'high'
        elif not job['posted_at']:
            priority = 'high'
        
        posting = {
            'posting_url': url,
            'company': company,
            'role_title': job['title'],
            'location': job.get('location') or 'remote',
            'posted_at': job['posted_at'].strftime('%Y-%m-%dT%H:%M:%SZ') if job['posted_at'] else None,
            'posted_at_raw': job.get('posted_at_raw', ''),
            'salary_disclosed': bool(job['salary']),
            'salary_range': job['salary'] or None,
            'source_board': 'wellfound',
            'remote_type': job.get('remote_type') or 'remote',
            'discovered_at': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'priority': priority,
            'posting_fingerprint': fingerprint,
        }
        new_postings.append(posting)
        print(f"  QUEUED: {company} | {job['title']} (priority={priority})")
except Exception as e:
    print(f"Wellfound main page error: {e}")

# ============================================
# Try Remotive (known reliable source)
# ============================================
print("\n" + "=" * 60)
print("Checking Remotive (reliable source per memory)")
print("=" * 60)

try:
    r = requests.get('https://remotive.com/remote-jobs/product-manager', headers=HEADERS, timeout=15)
    print(f"Remotive status: {r.status_code}, len: {len(r.text)}")
    if r.status_code == 200 and len(r.text) > 1000:
        soup = BeautifulSoup(r.text, 'html.parser')
        # Remotive uses structured data
        job_cards = soup.select('[class*="card"], [class*="job"], [data-testid="card"]')
        # Also try finding links with "product-manager" in href
        job_links = soup.find_all('a', href=re.compile(r'remotive\.com/remote-jobs/|/jobs/product-manager'))
        # Filter for job listing links
        job_links = [a for a in job_links if 'remote-jobs' in (a.get('href', '') or '') and not a.get('href', '').endswith('/')]
        print(f"Job cards found: {len(job_cards)}, job links: {len(job_links)}")
        
        # Try JSON-LD
        scripts = soup.find_all('script', type='application/ld+json')
        for i, script in enumerate(scripts):
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get('@type') == 'JobPosting':
                    title = data.get('title', '')
                    company = data.get('hiringOrganization', {}).get('name', '') if isinstance(data.get('hiringOrganization'), dict) else data.get('hiringOrganization', '')
                    location = data.get('jobLocation', {}).get('address', {}).get('addressLocality', '') if isinstance(data.get('jobLocation'), dict) else 'remote'
                    posted_raw = data.get('datePosted', '')
                    print(f"  JSON-LD Job: {title} at {company} ({location}) posted={posted_raw}")
                    
                    if title_matches(title):
                        fingerprint = compute_fingerprint(company, title, location or 'remote')
                        if fingerprint not in existing_fingerprints:
                            posting = {
                                'posting_url': data.get('applyLink', '') or data.get('url', '#'),
                                'company': company or 'Unknown',
                                'role_title': title,
                                'location': location or 'remote',
                                'posted_at': extract_posted_from_date(posted_raw).strftime('%Y-%m-%dT%H:%M:%SZ') if extract_posted_from_date(posted_raw) else None,
                                'posted_at_raw': posted_raw,
                                'salary_disclosed': bool(data.get('baseSalary')),
                                'salary_range': str(data.get('baseSalary', '')) if data.get('baseSalary') else None,
                                'source_board': 'Remotive',
                                'remote_type': 'remote',
                                'discovered_at': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
                                'priority': 'high',
                                'posting_fingerprint': fingerprint,
                            }
                            new_postings.append(posting)
                            print(f"  -> QUEUED: {company} | {title}")
            except (json.JSONDecodeError, TypeError):
                continue
        
        # Also try to extract from page text if no JSON-LD
        if not scripts:
            # Try b_class listings
            listings = soup.select('[class*="list"], article')
            for listing in listings[:10]:
                title_elem = listing.find(['h1', 'h2', 'h3', 'a'])
                title = title_elem.get_text(strip=True)[:150] if title_elem else ''
                if title and title_matches(title):
                    print(f"  Page listing: {title}")
                    # Would need to fetch detail page for full info
    else:
        print("Remotive returned non-200 or too little content")
except Exception as e:
    print(f"Remotive error: {e}")

# ============================================
# Try simplified Bing searches (single variant + platform)
# ============================================
print("\n" + "=" * 60)
print("Simplified Bing platform searches (single title at a time)")
print("=" * 60)

BING_URL = 'https://www.bing.com/search'
platforms = {
    'greenhouse': 'site:greenhouse.io',
    'lever': 'site:jobs.lever.co',
    'ashby': 'site:ashby.io',
}

# Focus on AI Product Manager and Product Manager (highest priority variants)
focus_titles = ['AI Product Manager', 'Product Manager', 'Technical Product Manager']
for platform, dork in platforms.items():
    for title in focus_titles:
        query = f'{dork} "{title}" remote'
        try:
            r = requests.get(BING_URL, params={'q': query, 'count': 8}, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                result_links = soup.select('li.b_algo h2 a')
                if result_links:
                    print(f"\n  [{platform}] \"{title}\" remote: {len(result_links)} results")
                    for a in result_links[:5]:
                        href = a.get('href', '')
                        title_text = a.get_text(strip=True)[:150]
                        # Check if it looks like a real job posting
                        if href and not href.startswith('https://www.bing.com/ck/a'):
                            print(f"    -> {title_text}")
                            print(f"       {href}")
                            if href not in existing_urls:
                                job = fetch_job_page(href)
                                if job and title_matches(job['title']):
                                    company = job['company'] or 'Unknown'
                                    fingerprint = compute_fingerprint(company, job['title'], job.get('location') or 'remote')
                                    if fingerprint not in existing_fingerprints:
                                        priority = 'high' if (job['posted_at'] and job['posted_at'] > recent_cutoff) or not job['posted_at'] else 'normal'
                                        posting = {
                                            'posting_url': href,
                                            'company': company,
                                            'role_title': job['title'],
                                            'location': job.get('location') or 'remote',
                                            'posted_at': job['posted_at'].strftime('%Y-%m-%dT%H:%M:%SZ') if job['posted_at'] else None,
                                            'posted_at_raw': job.get('posted_at_raw', ''),
                                            'salary_disclosed': bool(job['salary']),
                                            'salary_range': job['salary'] or None,
                                            'source_board': platform.capitalize(),
                                            'remote_type': job.get('remote_type') or 'remote',
                                            'discovered_at': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
                                            'priority': priority,
                                            'posting_fingerprint': fingerprint,
                                        }
                                        new_postings.append(posting)
                                        print(f"    -> QUEUED: {company} | {job['title']} (priority={priority})")
                                    else:
                                        print(f"    SKIP (fingerprint dup)")
                                else:
                                    if title_text:
                                        print(f"    SKIP (title doesn't match or fetch failed)")
        except Exception as e:
            print(f"  [{platform}] \"{title}\" remote: Error - {e}")

# ============================================
# Summary and save to DB
# ============================================
print("\n" + "=" * 60)
print("DISCOVERY SUMMARY")
print("=" * 60)
print(f"Total new postings found: {len(new_postings)}")

# Dedupe within the new postings by fingerprint
seen_fp = set()
unique_postings = []
for p in new_postings:
    if p['posting_fingerprint'] not in seen_fp:
        seen_fp.add(p['posting_fingerprint'])
        unique_postings.append(p)
    else:
        print(f"  Intra-run duplicate filtered: {p['company']} | {p['role_title']}")

print(f"After intra-run dedup: {len(unique_postings)}")

# Check daily cap
import yaml
with open(f"{SKILL_ROOT}/shared/.discovery_gate_state.json") as f:
    gate_state = json.load(f)
remaining = gate_state.get('remaining_slots', 15)
print(f"Daily cap remaining: {remaining}")

to_queue = unique_postings[:remaining]
capped = len(unique_postings) - len(to_queue)
if capped > 0:
    print(f"Capped by daily limit: {capped} postings would exceed today's slot count")

# Write results to file for review
with open(f"{SKILL_ROOT}/shared/.discovery_results.json", 'w') as f:
    json.dump({
        'timestamp': now.isoformat(),
        'discovery_mode': 'open_web',
        'total_found': len(new_postings),
        'total_unique': len(unique_postings),
        'to_queue': len(to_queue),
        'capped': capped,
        'remaining_slots': remaining,
        'postings': to_queue,
    }, f, indent=2, default=str)

print(f"\nResults written to shared/.discovery_results.json")
for p in to_queue:
    age = "NEW" if (p['posted_at'] and extract_posted_from_date(p['posted_at']) and extract_posted_from_date(p['posted_at']) > recent_cutoff) else "recent?"
    print(f"  [{p['priority']}] {p['company']} | {p['role_title']} | {p['source_board']} | posted={p['posted_at']} | {p['posting_url']}")
