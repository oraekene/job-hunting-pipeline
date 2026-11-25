#!/usr/bin/env python3
"""
Discovery scan for cron job #1 (job-hunting-discovery).
Checks each source in sources.yaml:
  - blocked sources: noted and skipped
  - wellfound: parses saved HTML for PM-related jobs
  - open-web sweep: searches Bing for PM jobs on ATS platforms
Dedupes against applications DB, cheap-filters against target profile,
and reports findings for manual queuing.
"""
import json, re, html, sqlite3, os, sys, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: bs4 not available")
    sys.exit(1)

SKILL_ROOT = Path("C:/Users/rotim/AppData/Local/hermes/skills/job-hunting")
DB_PATH = SKILL_ROOT / "shared" / "applications.db"
WELLFOUNDED_HTML = "C:/Users/rotim/AppData/Local/hermes/cache/web/wellfound-jobs-today.html"

# --- Target profile (from shared/target-profile.yaml) ---
TITLE_VARIANTS = [
    "Product Manager", "AI Product Manager", "AI Engineer", "Automation Engineer",
    "Associate Product Manager", "Junior Product Manager", "Workflow Engineer",
    "Product Owner", "Technical Product Manager", "Growth Product Manager",
    "AI/ML Product Manager",
]
SENIORITY_BAND = "mid"
SALARY_FLOOR_USD = 36000
SALARY_FLOOR_PERIOD = "year"
VISA_SPONSORSHIP_REQUIRED = True
LOCATIONS_OK = {"remote", "hybrid", "onsite", "worldwide", "united states", "nigeria"}

# --- Daily cap ---
DAILY_CAP = 15

# --- ATS platforms for open-web dorks ---
ATS_PLATFORMS = [
    ("Greenhouse", "site:jobs.greenhouse.io"),
    ("Lever", "site:jobs.lever.co"),
    ("Ashby", "site:jobs.ashbyhq.com"),
    ("Workday", "site:start.workday.com OR site:workday.com"),
    ("SmartRecruiters", "site:jobs.smartrecruiters.com"),
    ("iCIMS", "site:jobs.icims.com"),
]

def normalize_title(title):
    """Normalize a role title for fingerprinting."""
    t = title.lower().strip()
    # Remove trailing decorations
    t = re.sub(r'\s*\(.*?\)\s*$', '', t)  # trailing parentheses like "(Remote)"
    t = re.sub(r'\s*-\s*contract\s*$', '', t, flags=re.I)
    t = re.sub(r'\s*-?\s*req\s*#?\d+\s*$', '', t, flags=re.I)  # req IDs
    t = re.sub(r'\s*-\s*#\d+\s*$', '', t)  # hash IDs
    # Remove roman numeral suffixes where same job zone
    t = re.sub(r'\s+(ii|iii|iv|v|i)\s*$', '', t)
    # Remove trailing level numbers
    t = re.sub(r'\s+\d+\s*$', '', t)
    # Remove leading "senior" for normalization if base title matches
    # (senior/staff/lead/principal are seniority markers, not title identity)
    t = re.sub(r'^senior\s+', '', t)
    t = re.sub(r'^lead\s+', '', t)
    t = re.sub(r'^staff\s+', '', t)
    t = re.sub(r'^principal\s+', '', t)
    # Strip punctuation
    t = re.sub(r'[^a-z0-9\s]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def compute_fingerprint(company, role_title, location):
    """Compute posting_fingerprint: lower(trim(company))|normalised_role_title|lower(trim(location))"""
    norm_title = normalize_title(role_title)
    loc = location.lower().strip() if location else ""
    # Simplify location for fingerprint
    if 'remote' in loc:
        loc = 'remote'
    elif 'united states' in loc or 'us only' in loc:
        loc = 'united states'
    elif 'nigeria' in loc:
        loc = 'nigeria'
    elif 'canada' in loc or 'ca' in loc.split():
        loc = 'canada'
    elif 'europe' in loc or 'uk' in loc or 'gb' in loc:
        loc = 'europe'
    elif 'everywhere' in loc or 'global' in loc:
        loc = 'remote'
    return f"{company.lower().strip()}|{norm_title}|{loc}"

def title_matches_variant(role_title):
    """Check if role title matches any title variant (substring)."""
    title_lower = role_title.lower().strip()
    for variant in TITLE_VARIANTS:
        variant_lower = variant.lower().strip()
        if variant_lower in title_lower or title_lower in variant_lower:
            # Avoid false matches (e.g., "Product Owner" matching "Product Ownership")
            # but keep it simple per the skill's cheap-filter approach
            return variant
    return None

def check_salary_met(salary_text):
    """Check if salary meets the floor. Returns (meets, parsed_value, currency)."""
    if not salary_text:
        return None, None, None  # can't determine
    # Extract numbers from salary text
    # e.g., "$120k – $145k", "USD $90,000.00/Yr. - USD $110,000.00/Yr."
    nums = re.findall(r'[\$€£₦]?\s*([\d,.]+)([kKmM]?)', salary_text)
    for num_str, suffix in nums:
        num = float(num_str.replace(',', ''))
        if suffix.lower() == 'k':
            num *= 1000
        if suffix.lower() == 'm':
            num *= 1000000
        if num > 0:
            # We check the minimum of a range
            return True, num, "USD"  # assume USD if $ present
    return None, None, None

def load_db():
    """Load existing DB state for dedup."""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # Existing posting URLs
    cursor.execute("SELECT posting_url FROM applications WHERE posting_url IS NOT NULL")
    existing_urls = set(row[0] for row in cursor.fetchall())
    
    # Existing posting_sources URLs
    cursor.execute("SELECT posting_url FROM posting_sources WHERE posting_url IS NOT NULL")
    existing_source_urls = set(row[0] for row in cursor.fetchall())
    
    # Existing fingerprints
    cursor.execute("SELECT posting_fingerprint FROM applications WHERE posting_fingerprint IS NOT NULL")
    existing_fingerprints = set(row[0] for row in cursor.fetchall())
    
    # Also check posting_sources fingerprints (for dupes found via different sources)
    cursor.execute("SELECT DISTINCT posting_url FROM posting_sources WHERE posting_url IS NOT NULL")
    
    # Today's staged count
    cursor.execute("""
        SELECT COUNT(*) FROM applications 
        WHERE status IN ('staged', 'awaiting_approval', 'approved_sent', 'edited_then_sent')
        AND date(staged_at) = date('now', 'localtime')
    """)
    staged_today = cursor.fetchone()[0]
    
    # Today's discovered count
    cursor.execute("""
        SELECT COUNT(*) FROM applications 
        WHERE date(discovered_at) = date('now', 'localtime')
    """)
    discovered_today = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        'existing_urls': existing_urls,
        'existing_source_urls': existing_source_urls,
        'existing_fingerprints': existing_fingerprints,
        'staged_today': staged_today,
        'discovered_today': discovered_today,
        'remaining_slots': DAILY_CAP - discovered_today,
    }

def parse_wellfound():
    """Parse Wellfound jobs HTML for PM-related postings."""
    print("\n" + "="*60)
    print("SOURCE: Wellfound (scrape_and_filter)")
    print("="*60)
    
    html_path = Path(WELLFOUNDED_HTML)
    if not html_path.exists():
        print("  BLOCKED: Wellfound HTML cache not found, re-fetching...")
        req = urllib.request.Request(
            'https://wellfound.com/jobs',
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        try:
            resp = urllib.request.urlopen(req, timeout=15)
            content = resp.read().decode('utf-8', errors='replace')
            html_path.write_text(content)
        except Exception as e:
            print(f"  BLOCKED: Wellfound fetch failed ({e})")
            return []
    else:
        content = html_path.read_text(errors='replace')
    
    print(f"  Page size: {len(content)} bytes")
    soup = BeautifulSoup(content, 'lxml')
    
    # Extract job cards
    # Wellfound job cards have: <a href="/jobs/<id>-<slug>">Title</a>
    # followed by <span>Company • </span> <span class="text-gray-700">Location • salary • date</span>
    job_links = soup.find_all('a', href=re.compile(r'^/jobs/\d+-'))
    
    print(f"  Total job links found: {len(job_links)}")
    
    pm_jobs = []
    for link in job_links:
        href = link.get('href', '')
        title = link.get_text(strip=True)
        if not title:
            continue
        
        # Check if title matches any variant
        matched_variant = title_matches_variant(title)
        if not matched_variant:
            continue
        
        # Extract the parent card's meta info
        parent = link.find_parent('div', class_=re.compile(r'flex-row|mb-1|ml-4'))
        if not parent:
            parent = link.parent
        
        card = link.find_parent('div', class_=re.compile(r'mb-2.*border-b|py-3'))
        if not card:
            card = link.find_parent('div', class_=re.compile(r'flex-row'))
        
        # Find company and meta from the card
        company = "???"
        location_info = ""
        
        # The card structure: after the title link, there's a div.text-sm
        # with <span>Company • </span> and <span class="text-gray-700">Location info</span>
        text_sm_div = card.find('div', class_='text-sm') if card else None
        if text_sm_div:
            spans = text_sm_div.find_all('span')
            if len(spans) >= 2:
                company_raw = spans[0].get_text(strip=True)
                company = re.sub(r'\s*•\s*$', '', company_raw).strip()
                location_raw = spans[1].get_text(strip=True)
                location_info = location_raw
            elif len(spans) >= 1:
                # Sometimes company and location are combined
                combined = spans[0].get_text(strip=True)
                company = combined
        
        # Parse date from location_info (e.g., "Remote • $200k–$275k • today" or "• 3 days ago")
        posted_at_raw = ""
        date_match = re.search(r'(\d+\s+days?\s+ago|toyesterday|today|1\s+day\s+ago|2\s+days?\s+ago|3\s+days?\s+ago|4\s+days?\s+ago|5\s+days?\s+ago|6\s+days?\s+ago)', location_info, re.I)
        if date_match:
            posted_at_raw = date_match.group(1).strip()
        
        # Calculate posted_at from relative text
        posted_at = None
        if posted_at_raw:
            now = datetime.now(timezone.utc)
            if 'today' in posted_at_raw.lower():
                posted_at = now.strftime('%Y-%m-%dT%H:%M:%SZ')
            elif 'yesterday' in posted_at_raw.lower():
                posted_at = (now - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
            elif re.match(r'^(\d+)\s+days?\s+ago', posted_at_raw):
                days = int(re.match(r'^(\d+)', posted_at_raw).group(1))
                posted_at = (now - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%SZ')
        
        full_url = f"https://wellfound.com{href}"
        
        # Check salary
        salary_match = re.search(r'\$[\d,.]+[kKmM]?\s*–\s*\$[\d,.]+[kKmM]?', location_info)
        if not salary_match:
            salary_match = re.search(r'\$[\d,.]+[kKmM]?', location_info)
        salary_text = salary_match.group(0) if salary_match else None
        
        pm_jobs.append({
            'company': company,
            'role_title': title,
            'posting_url': full_url,
            'location': location_info,
            'posted_at_raw': posted_at_raw,
            'posted_at': posted_at,
            'salary_range': salary_text,
            'source': 'wellfound',
            'matched_variant': matched_variant,
        })
    
    print(f"  PM-matching jobs found: {len(pm_jobs)}")
    for job in pm_jobs:
        print(f"  - {job['company']}: {job['role_title']} | loc={job['location'][:80]} | posted_at_raw={job['posted_at_raw']} | url={job['posting_url']}")
    
    return pm_jobs

def search_bing(query, count=10):
    """Search Bing via requests and extract result URLs."""
    search_url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}&count={count}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        resp = requests.get(search_url, headers=headers, timeout=15)
        if resp.status_code != 200:
            print(f"  Bing search returned HTTP {resp.status_code}")
            return []
        soup = BeautifulSoup(resp.text, 'lxml')
        
        # Bing search results are in <li class="b_algo"> elements
        results = []
        for li in soup.find_all('li', class_='b_algo'):
            link = li.find('a', href=True)
            if link:
                url = link.get('href', '')
                title = link.get_text(strip=True)
                # Extract snippet
                snippet_div = li.find('p')
                snippet = snippet_div.get_text(strip=True) if snippet_div else ''
                results.append({
                    'url': url,
                    'title': title,
                    'snippet': snippet
                })
        return results
    except Exception as e:
        print(f"  Bing search error: {e}")
        return []

def extract_job_from_url(url, source_name):
    """Fetch a job posting URL and extract structured info."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        if resp.status_code != 200:
            return None
        
        soup = BeautifulSoup(resp.text, 'lxml')
        
        # Try schema.org JSON-LD first
        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get('@type') == 'JobPosting':
                    return {
                        'company': data.get('hiringOrganization', {}).get('name', '') if isinstance(data.get('hiringOrganization'), dict) else data.get('hiringOrganization', ''),
                        'role_title': data.get('title', ''),
                        'posting_url': url,
                        'location': data.get('jobLocation', {}).get('address', {}).get('addressLocality', '') if isinstance(data.get('jobLocation'), dict) else '',
                        'posted_at_raw': f"json_ld datePosted: {data.get('datePosted', '')}",
                        'posted_at': data.get('datePosted', ''),
                        'salary_range': data.get('baseSalary', ''),
                        'source': source_name,
                    }
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get('@type') == 'JobPosting':
                            return {
                                'company': item.get('hiringOrganization', {}).get('name', '') if isinstance(item.get('hiringOrganization'), dict) else '',
                                'role_title': item.get('title', ''),
                                'posting_url': url,
                                'location': '',
                                'posted_at_raw': f"json_ld datePosted: {item.get('datePosted', '')}",
                                'posted_at': item.get('datePosted', ''),
                                'salary_range': item.get('baseSalary', ''),
                                'source': source_name,
                            }
            except (json.JSONDecodeError, TypeError):
                continue
        
        # Fallback: meta tags
        title_tag = soup.find('title')
        title = title_tag.get_text(strip=True) if title_tag else ''
        
        # Try to extract company from og:company or page title
        company = ''
        og_company = soup.find('meta', attrs={'property': 'og:company'})
        if og_company:
            company = og_company.get('content', '')
        
        # Try to extract datePosted from meta
        posted_at_raw = ''
        date_posted = soup.find('meta', attrs={'property': 'article:published_time'})
        if date_posted:
            posted_at_raw = f"meta published_time: {date_posted.get('content', '')}"
            posted_at = date_posted.get('content', '')
        else:
            posted_at = None
        
        # Try to extract salary
        salary_range = None
        salary_match = re.search(r'\$[\d,.]+[kKmM]?\s*-\s*\$[\d,.]+[kKmM]?', resp.text)
        if salary_match:
            salary_range = salary_match.group(0)
        
        return {
            'company': company,
            'role_title': title,
            'posting_url': url,
            'location': '',
            'posted_at_raw': posted_at_raw,
            'posted_at': posted_at,
            'salary_range': salary_range,
            'source': source_name,
        }
    except Exception as e:
        print(f"  Error extracting {url}: {e}")
        return None

def run_open_web_sweep():
    """Run the open-web sweep: search Bing per ATS platform + generic."""
    print("\n" + "="*60)
    print("SOURCE: Open-web sweep (open_web_search, daily cadence)")
    print("="*60)
    
    # Build queries from title variants
    title_query = ' OR '.join(f'"{v}"' for v in TITLE_VARIANTS)
    location_filter = 'remote OR worldwide OR "united states"'
    time_filter = '2026'
    
    all_results = []
    
    # Per-platform queries
    for platform_name, site_dork in ATS_PLATFORMS:
        query = f'{site_dork} {title_query} {location_filter} {time_filter}'
        print(f"\n  Querying {platform_name}: {query[:100]}...")
        results = search_bing(query, count=10)
        print(f"  Found {len(results)} Bing results from {platform_name}")
        for r in results[:10]:
            print(f"    - {r['title'][:80]} | {r['url'][:100]}")
            all_results.append({
                'url': r['url'],
                'title': r['title'],
                'snippet': r['snippet'],
                'source': platform_name.lower(),
                'search_method': 'bing_search'
            })
    
    # Generic open query
    query = f'{title_query} {location_filter} {time_filter} "hiring" OR "job opening"'
    print(f"\n  Querying generic: {query[:100]}...")
    results = search_bing(query, count=15)
    print(f"  Found {len(results)} Bing results from generic search")
    for r in results[:15]:
        print(f"    - {r['title'][:80]} | {r['url'][:100]}")
        all_results.append({
            'url': r['url'],
            'title': r['title'],
            'snippet': r['snippet'],
            'source': 'generic_web',
            'search_method': 'bing_search'
        })
    
    return all_results

def main():
    print("=" * 60)
    print("JOB DISCOVERY SCAN")
    print(f"Run time: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
    print(f"Daily staging cap: {DAILY_CAP}")
    print("=" * 60)
    
    # Load DB state
    db = load_db()
    print(f"\nDB state: staged_today={db['staged_today']}, discovered_today={db['discovered_today']}, remaining_slots={db['remaining_slots']}")
    print(f"Existing URLs: {len(db['existing_urls'])}, Existing fingerprints: {len(db['existing_fingerprints'])}")
    
    if db['remaining_slots'] <= 0:
        print(f"\nDAILY CAP REACHED ({DAILY_CAP} staged today). No new queuing.")
    
    # ===== Source 1: LinkedIn (blocked) =====
    print("\n" + "="*60)
    print("SOURCE: LinkedIn (linkedin_search_url)")
    print("="*60)
    print("  BLOCKED: LinkedIn behind sign-in wall (login page returned)")
    
    # ===== Source 2: Indeed (blocked) =====
    print("\n" + "="*60)
    print("SOURCE: Indeed (indeed_search_url)")
    print("="*60)
    print("  BLOCKED: Indeed returns HTTP 403 (sign-in wall / ATS wall)")
    
    # ===== Source 3: RemoteOK (blocked) =====
    print("\n" + "="*60)
    print("SOURCE: RemoteOK (scrape_and_filter)")
    print("="*60)
    print("  BLOCKED: RemoteOK returns 302 redirect loop to / (ATS wall)")
    
    # ===== Source 4: Wellfound (scrape_and_filter) =====
    wellfound_jobs = parse_wellfound()
    
    # ===== Source 5: Open-web sweep (open_web_search, daily) =====
    openweb_results = run_open_web_sweep()
    
    # ===== Aggregate: filter, dedupe, prioritize =====
    print("\n" + "="*60)
    print("AGGREGATION: Filter + Dedup + Prioritize")
    print("="*60)
    
    all_candidates = []
    
    # Wellfound jobs
    for job in wellfound_jobs:
        all_candidates.append(job)
    
    # Open-web results — extract job details from promising URLs
    for result in openweb_results:
        url = result['url']
        # Skip if URL already in DB
        if url in db['existing_urls'] or url in db['existing_source_urls']:
            print(f"  DUP (existing URL): {result['title']} | {url}")
            continue
        
        # Check if URL looks like a job posting (not a search page)
        if '/search' in url or '/jobs/search' in url or 'bing.com' in url:
            continue
        
        # Extract job details
        job_detail = extract_job_from_url(url, result['source'])
        if job_detail:
            # Check title match
            matched = title_matches_variant(job_detail.get('role_title', ''))
            if matched:
                job_detail['matched_variant'] = matched
                all_candidates.append(job_detail)
            else:
                print(f"  FILTER OUT (no title match): {job_detail.get('role_title', '')[:60]}")
        else:
            print(f"  Could not extract: {url[:100]}")
    
    # Apply dedup + filter + priority
    new_postings = []
    duplicates = []
    filtered_out = []
    
    for candidate in all_candidates:
        url = candidate.get('posting_url') or candidate.get('url', '')
        company = candidate.get('company', '')
        title = candidate.get('role_title', candidate.get('title', ''))
        location = candidate.get('location', '')
        
        # Dedup check 1: URL in existing
        if url in db['existing_urls'] or url in db['existing_source_urls']:
            duplicates.append({
                'company': company,
                'role_title': title,
                'posting_url': url,
                'reason': 'duplicate URL in DB'
            })
            continue
        
        # Dedup check 2: Fingerprint match
        if company and title:
            fp = compute_fingerprint(company, title, location)
            if fp in db['existing_fingerprints']:
                duplicates.append({
                    'company': company,
                    'role_title': title,
                    'posting_url': url,
                    'reason': f'duplicate fingerprint: {fp}'
                })
                continue
        
        # Title filter
        if not candidate.get('matched_variant'):
            matched = title_matches_variant(title)
            if not matched:
                filtered_out.append({
                    'company': company,
                    'role_title': title,
                    'note': f'no title match against target profile'
                })
                continue
        
        # Check if newly discovered (posted_at within 24h, or discovered_at is today)
        posted_at = candidate.get('posted_at')
        discovered_at = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        
        priority = 'normal'
        if posted_at:
            try:
                posted_dt = datetime.fromisoformat(posted_at.replace('Z', '+00:00'))
                age_hours = (datetime.now(timezone.utc) - posted_dt).total_seconds() / 3600
                if age_hours <= 24:
                    priority = 'high'
            except:
                pass
        else:
            # Fall back to discovered_at being today
            priority = 'high'  # fresh discovery
        
        new_postings.append({
            'company': company,
            'role_title': title,
            'posting_url': url,
            'location': location,
            'posted_at': posted_at,
            'posted_at_raw': candidate.get('posted_at_raw') or candidate.get('posted_at_raw', ''),
            'salary_range': candidate.get('salary_range'),
            'source': candidate.get('source'),
            'discovered_at': discovered_at,
            'priority': priority,
            'matched_variant': candidate.get('matched_variant', title_matches_variant(title)),
        })
    
    # Apply daily cap
    slots_remaining = db['remaining_slots']
    to_queue = new_postings[:slots_remaining]
    overflow = new_postings[slots_remaining:]
    
    # Save results
    results = {
        'scan_time': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'sources_status': {
            'linkedin': 'BLOCKED (login wall)',
            'indeed': 'BLOCKED (HTTP 403)',
            'remoteok': 'BLOCKED (302 redirect loop)',
            'wellfound': f'OK - {len(wellfound_jobs)} PM jobs found on page',
            'open_web_sweep': f'OK - {len(openweb_results)} search results, {len([c for c in all_candidates if c.get("source") != "wellfound"])} candidates extracted',
        },
        'new_postings': to_queue,
        'duplicates': duplicates,
        'filtered_out': filtered_out,
        'overflow': overflow,
        'daily_cap': DAILY_CAP,
        'discovered_today': db['discovered_today'],
        'staged_today': db['staged_today'],
        'remaining_slots_before_queue': db['remaining_slots'],
        'queued_count': len(to_queue),
    }
    
    # Save to results file
    results_path = SKILL_ROOT / "01-job-discovery" / "scripts" / "discovery_scan_results.json"
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n{'='*60}")
    print("DISCOVERY SCAN COMPLETE")
    print(f"{'='*60}")
    print(f"Sources checked: 5")
    print(f"  Blocked: LinkedIn (login wall), Indeed (403), RemoteOK (redirect loop)")
    print(f"  Wellfound: {len(wellfound_jobs)} PM jobs found on page")
    print(f"  Open-web sweep: {len(openweb_results)} search results")
    print(f"")
    print(f"New postings (post-filter): {len(new_postings)}")
    print(f"Duplicates: {len(duplicates)}")
    print(f"Filtered out: {len(filtered_out)}")
    print(f"")
    print(f"Daily cap: {DAILY_CAP}")
    print(f"Discovered today: {db['discovered_today']}")
    print(f"Staged today: {db['staged_today']}")
    print(f"Remaining slots: {db['remaining_slots']}")
    print(f"To queue: {len(to_queue)}")
    print(f"Overflow: {len(overflow)}")
    print(f"")
    if to_queue:
        print("POSTING TO QUEUE:")
        for p in to_queue:
            print(f"  [{p['priority'].upper()}] {p['company']}: {p['role_title']}")
            print(f"    URL: {p['posting_url']}")
            print(f"    Posted: {p['posted_at'] or 'unknown'} | Salary: {p['salary_range'] or 'N/A'}")
    else:
        print("NO NEW POSTINGS TO QUEUE")
    
    if filtered_out:
        print(f"\nFILTERED OUT:")
        for f in filtered_out:
            print(f"  - {f.get('company','')}: {f.get('role_title','')} | {f.get('note','')}")
    
    if duplicates:
        print(f"\nDUPLICATES (already in DB):")
        for d in duplicates:
            print(f"  - {d.get('company','')}: {d.get('role_title','')} | {d['reason']}")
    
    print(f"\nResults saved to: {results_path}")

if __name__ == "__main__":
    main()
