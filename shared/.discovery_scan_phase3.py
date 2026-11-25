#!/usr/bin/env python
"""Phase 3: Better extraction from Wellfound (fix location), try more sources,
decode Bing redirect URLs, try Remotive with correct URL."""

import requests, json, re, sqlite3, datetime, urllib.parse, base64
from bs4 import BeautifulSoup
import yaml

SKILL_ROOT = "C:/Users/rotim/AppData/Local/hermes/skills/job-hunting"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

with open(f"{SKILL_ROOT}/shared/target-profile.yaml") as f:
    target = yaml.safe_load(f)
title_variants = [tv['title'] for tv in target.get('title_variants', [])]

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
    t = re.sub(r'\s*\(\s*(senior|junior|lead|principal|staff|mid|mid-level|entry|associate)\s*\)$', '', t)
    t = re.sub(r'\s*\(\s*(remote|contract|freelance|temp)\s*\)$', '', t)
    t = re.sub(r'[^\w\s]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def compute_fingerprint(company, role_title, location):
    c = (company or '').lower().strip()
    t = normalize_title(role_title or '')
    # Normalize location: if it's a dict/list JSON, extract country/locality
    l = str(location or '').lower().strip()
    # Try to extract from JSON-LD location object
    if isinstance(location, (dict, list)):
        if isinstance(location, list) and location and isinstance(location[0], dict):
            addr = location[0].get('address', {})
            locality = addr.get('addressLocality', '')
            region = addr.get('addressRegion', '')
            country = addr.get('addressCountry', '')
            parts = [p for p in [locality, region, country] if p]
            l = ' '.join(parts).lower().strip()
        elif isinstance(location, dict):
            addr = location.get('address', {})
            locality = addr.get('addressLocality', '')
            region = addr.get('addressRegion', '')
            country = addr.get('addressCountry', '')
            parts = [p for p in [locality, region, country] if p]
            l = ' '.join(parts).lower().strip()
    # If it looks like a JSON blob, clean it up
    if l.startswith('[{') or l.startswith('{'):
        try:
            obj = json.loads(l.replace("'", '"'))
            if isinstance(obj, list) and obj and isinstance(obj[0], dict):
                addr = obj[0].get('address', {})
                parts = [addr.get('addressLocality',''), addr.get('addressRegion',''), addr.get('addressCountry','')]
                l = ' '.join(p for p in parts if p).lower().strip()
        except:
            pass
    l = re.sub(r'\s+', ' ', l)
    return f"{c}|{t}|{l}"

def extract_location_from_jsonld(loc_obj):
    """Cleanly extract location string from JSON-LD jobLocation."""
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
    
    locality = addr.get('addressLocality', '') if isinstance(addr, dict) else ''
    region = addr.get('addressRegion', '') if isinstance(addr, dict) else ''
    country = addr.get('addressCountry', '') if isinstance(addr, dict) else ''
    address_full = addr.get('address', '') if isinstance(addr, dict) else ''
    
    if isinstance(address_full, str) and address_full:
        return address_full
    
    parts = [p for p in [locality, region, country] if p]
    if not parts:
        # Check if there's an address string
        return 'remote'
    return ', '.join(parts)

def extract_salary_from_jsonld(salary_obj):
    """Extract salary info from JSON-LD baseSalary."""
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
                    text = f"{currency} {min_val}-{max_val} {unit}"
                    return text, True
            elif isinstance(value, (int, float)):
                return f"{currency} {value}", True
            elif isinstance(value, str):
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
    dollar_matches = re.findall(r'(\d[\d,]*\.?\d*)\s*(?:thousand|\bk\b)', text)
    raw_matches = re.findall(r'\$?\s*([\d,]+\.?\d*)\s*(?:thousand|k)', text, re.I)
    for m in raw_matches:
        try:
            amounts.append(float(m.replace(',', '')) * 1000)
        except:
            pass
    if 'minvalue' in text and 'maxvalue' in text:
        nums = re.findall(r'([\d.]+)', text)
        for n in nums:
            try:
                val = float(n)
                if val > 1000:
                    amounts.append(val)
            except:
                pass
    # Simple: extract all dollar amounts
    all_nums = re.findall(r'(\d[\d,.]*)\.?\d*', text.replace(' ', ''))
    for n in all_nums:
        try:
            val = float(n.replace(',', ''))
            if 1000 < val < 1000000:
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

def decode_bing_url(bing_href):
    """Decode Bing redirect URL to get the actual target."""
    if not bing_href or not bing_href.startswith('https://www.bing.com/ck/a'):
        return bing_href
    # Bing redirect format: https://www.bing.com/ck/a?!...&u=a1<base64_encoded_url>&...
    match = re.search(r'&u=a1([A-Za-z0-9+/=]+)', bing_href)
    if match:
        encoded = match.group(1)
        # Bing uses URL-safe base64 with some obfuscation
        # Try standard base64
        try:
            # Pad the base64 string
            padding = 4 - len(encoded) % 4
            if padding != 4:
                encoded += '=' * padding
            decoded = base64.b64decode(encoded).decode('utf-8', errors='ignore')
            if decoded.startswith('http'):
                return decoded
        except:
            pass
    return None

def fetch_job_page(url):
    """Fetch a job page and extract structured info from JSON-LD."""
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
                    
                    # Check remote type from JSON-LD
                    remote_type = 'remote'
                    jt = data.get('jobType', '')
                    if isinstance(jt, str):
                        remote_type = jt
                    
                    return {
                        'title': title,
                        'company': company,
                        'location': location,
                        'posted_at_raw': posted_raw,
                        'posted_at': posted_at,
                        'salary': salary_text if has_salary else '',
                        'url': url,
                        'remote_type': remote_type,
                    }
            except (json.JSONDecodeError, TypeError):
                continue
        
        # Fallback: page title as title
        title_tag = soup.find('title')
        title = title_tag.get_text(strip=True)[:200] if title_tag else ''
        og_title = soup.find('meta', property='og:title')
        if og_title:
            title = og_title.get('content', '')[:200]
        og_desc = soup.find('meta', property='og:description')
        desc = og_desc.get('content', '')[:500] if og_desc else ''
        
        # Try company name from h1/h2 near title
        company = ''
        company_selectors = ['[data-test="company-name"]', '.company-name', '[data-testid="company"]', 
                            '.company', '[class*="company"]', '.employer', '.organization']
        for sel in company_selectors:
            elem = soup.select_one(sel)
            if elem:
                company = elem.get_text(strip=True)[:100]
                break
        
        # Try posted date
        posted_raw = ''
        date_elem = soup.find('time')
        if date_elem:
            posted_raw = date_elem.get('datetime', date_elem.get_text(strip=True))
        if not posted_raw:
            date_match = re.search(r'(?:posted|updated|datePosted)\s*(?:on)?\s*([A-Z][a-z]+ \d{1,2}, \d{4})', r.text, re.I)
            if date_match:
                posted_raw = date_match.group(1)
        
        # Try location from JSON-LD or page
        location = 'remote'
        loc_match = re.search(r'(?:location|Location)[:]\s*([^\n<,]+)', desc, re.I)
        if loc_match:
            location = loc_match.group(1).strip()[:100]
        
        return {
            'title': title,
            'company': company,
            'location': location,
            'posted_at_raw': posted_raw,
            'posted_at': extract_posted_from_date(posted_raw),
            'salary': '',
            'url': url,
            'remote_type': 'remote' if 'remote' in (title + desc).lower() else '',
        }
    except Exception as e:
        return None

# ============================================
# Wellfound: fetch more pages and extract detail pages
# ============================================
print("=" * 60)
print("Wellfound: fetching detail pages for PM roles")
print("=" * 60)

# First, get more job links from Wellfound
wf_job_urls = set()
for page in range(1, 4):  # Check first 3 pages
    url = f"https://wellfound.com/jobs?page={page}" if page > 1 else "https://wellfound.com/jobs"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            job_links = soup.find_all('a', href=re.compile(r'/jobs/\d+'))
            for link in job_links:
                href = link.get('href', '')
                full_url = f"https://wellfound.com{href}" if href.startswith('/') else href
                text = link.get_text(strip=True).lower()
                if any(kw in text for kw in ['product manager', 'ai product', 'technical product', 'growth product',
                     'product owner', 'workflow engineer', 'ai engineer', 'automation engineer',
                     'junior product', 'associate product', 'principal product', 'senior product']):
                    wf_job_urls.add(full_url)
            print(f"  Page {page}: {len(job_links)} total links, {len(wf_job_urls)} PM-related unique URLs so far")
    except Exception as e:
        print(f"  Page {page} error: {e}")
        break

print(f"\nTotal Wellfound PM URLs to check: {len(wf_job_urls)}")

new_postings = []
for url in sorted(wf_job_urls):
    if url in existing_urls:
        print(f"  SKIP (existing URL): {url}")
        continue
    job = fetch_job_page(url)
    if not job:
        print(f"  FETCH FAILED: {url}")
        continue
    if not title_matches(job['title']):
        print(f"  SKIP (title mismatch): {job['title']}")
        continue
    if not passes_salary(job['salary'], target.get('salary_floor', {})):
        print(f"  SKIP (salary below floor): {job['company']} | {job['title']} | {job['salary']}")
        continue
    if job['company'] and any(c.lower() in job['company'].lower() for c in target.get('companies_exclude', [])):
        print(f"  SKIP (company excluded): {job['company']}")
        continue
    
    fingerprint = compute_fingerprint(job['company'], job['title'], job['location'])
    if fingerprint in existing_fingerprints:
        print(f"  SKIP (fingerprint dup): {fingerprint}")
        continue
    
    priority = 'normal'
    if job['posted_at'] and job['posted_at'] > recent_cutoff:
        priority = 'high'
    elif not job['posted_at']:
        priority = 'high'
    
    posting = {
        'posting_url': url,
        'company': job['company'] or 'Unknown',
        'role_title': job['title'],
        'location': job['location'] or 'remote',
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
    print(f"  QUEUED: {job['company']} | {job['title']} | {job['location']} | posted={posting['posted_at']} | {url}")

# ============================================
# Bing platform search — decode redirect URLs
# ============================================
print("\n" + "=" * 60)
print("Bing platform searches (decoding redirect URLs)")
print("=" * 60)

BING_URL = 'https://www.bing.com/search'
platforms = {
    'greenhouse': 'site:greenhouse.io',
    'lever': 'site:jobs.lever.co',
    'ashby': 'site:ashby.io',
}

focus_titles = ['AI Product Manager', 'Product Manager']
for platform, dork in platforms.items():
    for title in focus_titles:
        query = f'{dork} "{title}" remote'
        try:
            r = requests.get(BING_URL, params={'q': query, 'count': 8}, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                result_links = soup.select('li.b_algo h2 a')
                found_job_urls = []
                for a in result_links[:8]:
                    href = a.get('href', '')
                    title_text = a.get_text(strip=True)[:150]
                    # Decode Bing redirect if present
                    if href.startswith('https://www.bing.com/ck/a'):
                        decoded = decode_bing_url(href)
                        if decoded:
                            found_job_urls.append((decoded, title_text))
                        else:
                            found_job_urls.append((href, title_text))
                    elif href and not 'bing.com' in href:
                        found_job_urls.append((href, title_text))
                
                print(f"\n  [{platform}] \"{title}\" remote: {len(found_job_urls)} results")
                for job_url, title_text in found_job_urls:
                    if job_url.startswith('https://www.bing.com/ck/a'):
                        print(f"    (couldn't decode: {title_text[:60]})")
                        continue
                    if 'bing.com' in job_url:
                        continue
                    print(f"    -> {title_text[:80]} @ {job_url[:80]}")
                    if job_url not in existing_urls:
                        job = fetch_job_page(job_url)
                        if job and title_matches(job['title']):
                            fingerprint = compute_fingerprint(job['company'], job['title'], job['location'])
                            if fingerprint not in existing_fingerprints:
                                priority = 'high' if (job['posted_at'] and job['posted_at'] > recent_cutoff) or not job['posted_at'] else 'normal'
                                posting = {
                                    'posting_url': job_url,
                                    'company': job['company'] or 'Unknown',
                                    'role_title': job['title'],
                                    'location': job['location'] or 'remote',
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
                                print(f"    -> QUEUED: {job['company']} | {job['title']} (priority={priority})")
                            else:
                                print(f"    SKIP (fingerprint dup)")
                        else:
                            if title_text:
                                print(f"    SKIP (title mismatch or fetch failed)")
        except Exception as e:
            print(f"  [{platform}] \"{title}\": Error - {e}")

# ============================================
# Try Remotive with correct URL
# ============================================
print("\n" + "=" * 60)
print("Remotive (corrected URL)")
print("=" * 60)

remotive_urls = [
    'https://remotive.com/remote-jobs',
    'https://remotive.com/categories/product-jobs',
    'https://remotive.com/categories/ai-jobs',
]
for rurl in remotive_urls:
    try:
        r = requests.get(rurl, headers=HEADERS, timeout=15)
        print(f"  {rurl}: status={r.status_code}, len={len(r.text)}")
        if r.status_code == 200 and len(r.text) > 5000:
            soup = BeautifulSoup(r.text, 'html.parser')
            # Try JSON-LD
            scripts = soup.find_all('script', type='application/ld+json')
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict) and data.get('@type') == 'JobPosting':
                        title = data.get('title', '')
                        hiring_org = data.get('hiringOrganization', '')
                        company = hiring_org.get('name', '') if isinstance(hiring_org, dict) else str(hiring_org)
                        location = extract_location_from_jsonld(data.get('jobLocation', {}))
                        posted_raw = data.get('datePosted', '')
                        posted_at = extract_posted_from_date(posted_raw)
                        print(f"    JSON-LD: {title} @ {company} ({location}) posted={posted_raw}")
                        if title_matches(title):
                            fingerprint = compute_fingerprint(company, title, location)
                            if fingerprint not in existing_fingerprints and data.get('url', '') not in existing_urls:
                                priority = 'high' if (posted_at and posted_at > recent_cutoff) or not posted_at else 'normal'
                                posting = {
                                    'posting_url': data.get('url', rurl),
                                    'company': company or 'Unknown',
                                    'role_title': title,
                                    'location': location or 'remote',
                                    'posted_at': posted_at.strftime('%Y-%m-%dT%H:%M:%SZ') if posted_at else None,
                                    'posted_at_raw': posted_raw,
                                    'salary_disclosed': bool(data.get('baseSalary')),
                                    'salary_range': '',
                                    'source_board': 'Remotive',
                                    'remote_type': 'remote',
                                    'discovered_at': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
                                    'priority': priority,
                                    'posting_fingerprint': fingerprint,
                                }
                                new_postings.append(posting)
                                print(f"    -> QUEUED: {company} | {title}")
                except (json.JSONDecodeError, TypeError):
                    continue
            # Also try finding job links
            job_links = soup.find_all('a', href=re.compile(r'remotive\.com.*job|/jobs/'))
            pm_links = [a for a in job_links if any(kw in a.get_text(strip=True).lower() for kw in ['product manager', 'ai product', 'technical product'])]
            if pm_links:
                print(f"    Found {len(pm_links)} PM-related links")
                for a in pm_links[:5]:
                    href = a.get('href', '')
                    full_url = f"https://remotive.com{href}" if href.startswith('/') else href
                    if full_url not in existing_urls:
                        job = fetch_job_page(full_url)
                        if job and title_matches(job['title']):
                            fingerprint = compute_fingerprint(job['company'], job['title'], job['location'])
                            if fingerprint not in existing_fingerprints:
                                priority = 'high' if (job['posted_at'] and job['posted_at'] > recent_cutoff) or not job['posted_at'] else 'normal'
                                posting = {
                                    'posting_url': full_url,
                                    'company': job['company'] or 'Unknown',
                                    'role_title': job['title'],
                                    'location': job['location'] or 'remote',
                                    'posted_at': job['posted_at'].strftime('%Y-%m-%dT%H:%M:%SZ') if job['posted_at'] else None,
                                    'posted_at_raw': job.get('posted_at_raw', ''),
                                    'salary_disclosed': bool(job['salary']),
                                    'salary_range': job['salary'] or None,
                                    'source_board': 'Remotive',
                                    'remote_type': job.get('remote_type') or 'remote',
                                    'discovered_at': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
                                    'priority': priority,
                                    'posting_fingerprint': fingerprint,
                                }
                                new_postings.append(posting)
                                print(f"    -> QUEUED: {job['company']} | {job['title']}")
    except Exception as e:
        print(f"  {rurl}: Error - {e}")

# ============================================
# Summary
# ============================================
print("\n" + "=" * 60)
print("PHASE 3 DISCOVERY SUMMARY")
print("=" * 60)

# Dedupe within new postings
seen_fp = set()
unique = []
for p in new_postings:
    if p['posting_fingerprint'] not in seen_fp:
        seen_fp.add(p['posting_fingerprint'])
        unique.append(p)
    else:
        print(f"  Intra-run dup filtered: {p['company']} | {p['role_title']}")

print(f"\nTotal new postings (raw): {len(new_postings)}")
print(f"After intra-run dedup: {len(unique)}")

# Load gate state for cap
with open(f"{SKILL_ROOT}/shared/.discovery_gate_state.json") as f:
    gate_state = json.load(f)
remaining = gate_state.get('remaining_slots', 15)
print(f"Daily cap remaining: {remaining}")

to_queue = unique[:remaining]
capped = len(unique) - len(to_queue)

print(f"\nFinal postings to queue: {len(to_queue)}")
if capped > 0:
    print(f"  (would have queued {len(unique)} but daily cap leaves {remaining} slots)")

# Save results
with open(f"{SKILL_ROOT}/shared/.discovery_results.json", 'w') as f:
    json.dump({
        'timestamp': now.isoformat(),
        'total_found_raw': len(new_postings),
        'total_unique': len(unique),
        'to_queue': len(to_queue),
        'capped': capped,
        'remaining_slots': remaining,
        'postings': to_queue,
    }, f, indent=2, default=str)

print("\n" + "-" * 60)
for p in to_queue:
    print(f"[{p['priority']}] {p['company']} | {p['role_title']} | {p['location']} | posted={p['posted_at']} | posted_at_raw={p['posted_at_raw'][:50]} | posted={p['posted_at']} | src={p['source_board']} | {p['posting_url']}")
