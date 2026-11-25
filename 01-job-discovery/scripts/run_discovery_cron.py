#!/usr/bin/env python3
"""
Cron discovery run for job-hunting-discovery.
Checks each source in sources.yaml per the skill methodology:
  - blocked sources: noted and skipped (no retry, no workaround)
  - accessible sources: fetched, parsed, deduped against DB, filtered, queued
"""
import json, re, sqlite3, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path
from bs4 import BeautifulSoup

SKILL_ROOT = Path("C:/Users/rotim/AppData/Local/hermes/skills/job-hunting")
DB_PATH = SKILL_ROOT / "shared" / "applications.db"
CACHE_DIR = Path("C:/Users/rotim/AppData/Local/hermes/cache/web")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# --- Target profile (from shared/target-profile.yaml) ---
TITLE_VARIANTS = [
    "Product Manager", "AI Product Manager", "AI Engineer", "Automation Engineer",
    "Associate Product Manager", "Junior Product Manager", "Workflow Engineer",
    "Product Owner", "Technical Product Manager", "Growth Product Manager",
    "AI/ML Product Manager",
]
SALARY_FLOOR_USD = 36000
SALARY_FLOOR_PERIOD = "year"
VISA_SPONSORSHIP_REQUIRED = True
LOCATIONS_OK = {"remote", "hybrid", "onsite", "worldwide", "united states", "nigeria"}
COMPANIES_EXCLUDE = []
INDUSTRIES_EXCLUDE = []

DAILY_CAP = 15

now = datetime.now(timezone.utc)
cutoff_24h = now - timedelta(hours=24)

def fetch(url, timeout=15):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.read().decode('utf-8', errors='replace'), resp.status
    except urllib.error.HTTPError as e:
        return '', e.code
    except Exception as e:
        return str(e), 0

def load_db():
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("SELECT posting_url FROM applications WHERE posting_url IS NOT NULL")
    existing_urls = set(r[0] for r in c.fetchall())
    c.execute("SELECT posting_fingerprint FROM applications WHERE posting_fingerprint IS NOT NULL")
    existing_fps = set(r[0] for r in c.fetchall())
    c.execute("SELECT posting_url FROM posting_sources WHERE posting_url IS NOT NULL")
    src_urls = set(r[0] for r in c.fetchall())
    c.execute("""SELECT COUNT(*) FROM applications 
                 WHERE date(discovered_at) = date('now', 'localtime')""")
    discovered_today = c.fetchone()[0]
    c.execute("""SELECT COUNT(*) FROM applications 
                 WHERE status IN ('staged','awaiting_approval','approved_sent','edited_then_sent')
                 AND date(staged_at) = date('now', 'localtime')""")
    staged_today = c.fetchone()[0]
    conn.close()
    all_urls = existing_urls | src_urls
    return {
        'existing_urls': existing_urls,
        'existing_fps': existing_fps,
        'all_urls': all_urls,
        'discovered_today': discovered_today,
        'staged_today': staged_today,
        'remaining_slots': DAILY_CAP - discovered_today,
    }

def normalize_title(title):
    t = title.lower().strip()
    t = re.sub(r'\s*\(.*?\)\s*$', '', t)
    t = re.sub(r'\s*-\s*contract\s*$', '', t, flags=re.I)
    t = re.sub(r'\s*-?\s*req\s*#?\d+\s*$', '', t, flags=re.I)
    t = re.sub(r'\s*-\s*#\d+\s*$', '', t)
    t = re.sub(r'\s+(ii|iii|iv|v|i)\s*$', '', t)
    t = re.sub(r'\s+\d+\s*$', '', t)
    t = re.sub(r'^senior\s+', '', t)
    t = re.sub(r'^lead\s+', '', t)
    t = re.sub(r'^staff\s+', '', t)
    t = re.sub(r'^principal\s+', '', t)
    t = re.sub(r'[^a-z0-9\s]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def compute_fingerprint(company, role_title, location):
    norm_title = normalize_title(role_title)
    loc = location.lower().strip() if location else ""
    if 'remote' in loc:
        loc = 'remote'
    elif 'united states' in loc or 'us only' in loc:
        loc = 'united states'
    elif 'nigeria' in loc:
        loc = 'nigeria'
    elif 'canada' in loc:
        loc = 'canada'
    elif 'europe' in loc or 'uk' in loc or 'gb' in loc:
        loc = 'europe'
    elif 'everywhere' in loc or 'global' in loc:
        loc = 'remote'
    return f"{company.lower().strip()}|{norm_title}|{loc}"

def title_matches_variant(role_title):
    title_lower = role_title.lower().strip()
    for variant in TITLE_VARIANTS:
        variant_lower = variant.lower().strip()
        if variant_lower in title_lower or title_lower in variant_lower:
            return variant
    return None

def check_salary_met(salary_text):
    if not salary_text:
        return None, None, None
    nums = re.findall(r'[\$€£₦]?\s*([\d,.]+)([kKmM]?)', salary_text)
    for num_str, suffix in nums:
        num = float(num_str.replace(',', ''))
        if suffix.lower() == 'k':
            num *= 1000
        if suffix.lower() == 'm':
            num *= 1000000
        if num > 0:
            return True, num, "USD"
    return None, None, None

def passes_cheap_filter(job):
    """Check if a job candidate passes the cheap-filter against target profile."""
    title_match = title_matches_variant(job['role_title'])
    if not title_match:
        return False, "no title_variants match"
    # Salary check
    sal_meets, sal_val, _ = check_salary_met(job.get('salary_range', ''))
    if sal_meets is False:
        return False, f"salary below floor (${sal_val})"
    # Companies exclude
    if job.get('company', '').lower() in [c.lower() for c in COMPANIES_EXCLUDE]:
        return False, "company in exclude list"
    # Location check (remote/hybrid/onsite OK)
    loc = job.get('location', '').lower()
    if not any(l in loc for l in ['remote', 'hybrid', 'onsite', 'worldwide', 'united states', 'nigeria', 'global', 'anywhere']):
        if loc and len(loc) > 5:  # Only flag if location is specified and not remote
            return False, f"location not matching ({loc[:40]})"
    return True, title_match

# ========== MAIN ==========
print("=" * 60)
print("JOB DISCOVERY — CRON RUN")
print(f"Run time (UTC): {now.isoformat()}")
print(f"Daily staging cap: {DAILY_CAP}")
print("=" * 60)

db = load_db()
print(f"\nDB state: discovered_today={db['discovered_today']}, staged_today={db['staged_today']}, remaining_slots={db['remaining_slots']}")
print(f"Existing URLs: {len(db['existing_urls'])}, Existing fingerprints: {len(db['existing_fps'])}, All known URLs: {len(db['all_urls'])}")

all_candidates = []
blocked_sources = []
skipped_duplicates = []
skipped_filter = []
new_found = 0

# ===== Source 1: LinkedIn (linkedin_search_url) =====
print("\n" + "=" * 60)
print("SOURCE: LinkedIn (linkedin_search_url)")
print("=" * 60)
content, status = fetch("https://www.linkedin.com/jobs/search/?keywords=Product%20Manager&sortBy=DD")
if status == 200 and 'login' not in content[:500].lower() and 'sign in' not in content[:500].lower():
    print("  OK — page accessible, would parse")
else:
    print(f"  BLOCKED: LinkedIn behind sign-in wall (HTTP {status})")
    blocked_sources.append({"source": "linkedin-global", "type": "linkedin_search_url", "reason": "BLOCKED (sign-in wall)"})

# ===== Source 2: Indeed (indeed_search_url) =====
print("\n" + "=" * 60)
print("SOURCE: Indeed (indeed_search_url)")
print("=" * 60)
content, status = fetch("https://www.indeed.com/worldwide/implement?q=Product+Manager&sort=date")
if status == 403:
    print(f"  BLOCKED: Indeed returns HTTP 403 (sign-in wall / ATS wall)")
    blocked_sources.append({"source": "indeed-global", "type": "indeed_search_url", "reason": "BLOCKED (HTTP 403)"})
else:
    print(f"  HTTP {status} — would parse if 200")
    if status != 200:
        blocked_sources.append({"source": "indeed-global", "type": "indeed_search_url", "reason": f"BLOCKED (HTTP {status})"})

# ===== Source 3: RemoteOK (scrape_and_filter — website) =====
print("\n" + "=" * 60)
print("SOURCE: RemoteOK (scrape_and_filter)")
print("=" * 60)
content, status = fetch("https://remoteok.com/remote-product-manager-jobs")
if status in (301, 302) or "redirect" in content.lower()[:200]:
    print(f"  BLOCKED: RemoteOK returns redirect loop (ATS wall)")
    blocked_sources.append({"source": "remote-ok", "type": "scrape_and_filter", "reason": "BLOCKED (302 redirect loop)"})
else:
    print(f"  HTTP {status} — would parse if 200")
    if status != 200:
        blocked_sources.append({"source": "remote-ok", "type": "scrape_and_filter", "reason": f"BLOCKED (HTTP {status})"})

# ===== Source 4: Wellfound (scrape_and_filter) =====
print("\n" + "=" * 60)
print("SOURCE: Wellfound (scrape_and_filter)")
print("=" * 60)
wf_html_path = CACHE_DIR / "wellfound-jobs-today.html"
content, status = fetch("https://wellfound.com/jobs")
if status == 200:
    wf_html_path.write_text(content, errors='replace')
    soup = BeautifulSoup(content, 'lxml')
    job_links = soup.find_all('a', href=re.compile(r'^/jobs/\d+-'))
    print(f"  OK — page accessible (HTTP 200, {len(content)} bytes)")
    print(f"  Job links found: {len(job_links)}")
    
    for link in job_links:
        href = link.get('href', '')
        title = link.get_text(strip=True)
        if not title:
            continue
        matched_variant = title_matches_variant(title)
        if not matched_variant:
            continue
        
        # Extract card info
        card = link.find_parent()
        company = "unknown"
        location_info = ""
        text_sm = card.find('div', class_='text-sm') if card else None
        if text_sm:
            spans = text_sm.find_all('span')
            if len(spans) >= 2:
                company = re.sub(r'\s*•\s*$', '', spans[0].get_text(strip=True)).strip()
                location_info = spans[1].get_text(strip=True)
            elif len(spans) >= 1:
                company = spans[0].get_text(strip=True).strip()
        
        # Parse date
        date_match = re.search(r'(today|yesterday|just now|\d+\s*days?\s*ago|\d+\s*hours?\s*ago)', location_info, re.I)
        posted_at_raw = date_match.group(1) if date_match else 'unknown'
        posted_at = None
        if 'today' in posted_at_raw.lower():
            posted_at = now.isoformat()
        elif 'yesterday' in posted_at_raw.lower():
            posted_at = (now - timedelta(days=1)).isoformat()
        elif re.match(r'^(\d+)\s*days?\s*ago', posted_at_raw):
            days = int(re.match(r'^(\d+)', posted_at_raw).group(1))
            posted_at = (now - timedelta(days=days)).isoformat()
        
        is_recent = False
        if posted_at:
            try:
                d = datetime.fromisoformat(posted_at)
                is_recent = (now - d).total_seconds() < 86400
            except:
                pass
        
        full_url = f"https://wellfound.com{href}"
        salary_match = re.search(r'\$[\d,]+[kKmM]?\s*[-–]\s*\$[\d,]+[kKmM]?', location_info)
        if not salary_match:
            salary_match = re.search(r'\$[\d,]+[kKmM]?', location_info)
        salary = salary_match.group(0) if salary_match else None
        
        job = {
            'company': company,
            'role_title': title,
            'posting_url': full_url,
            'location': location_info,
            'posted_at_raw': posted_at_raw,
            'posted_at': posted_at,
            'salary_range': salary,
            'source': 'wellfound',
            'matched_variant': matched_variant,
            'is_recent': is_recent,
        }
        all_candidates.append(job)
        print(f"  - {company}: {title} | posted={posted_at_raw} | recent={is_recent} | url={full_url[:80]}")
else:
    print(f"  BLOCKED: Wellfound HTTP {status}")
    blocked_sources.append({"source": "wellfound", "type": "scrape_and_filter", "reason": f"BLOCKED (HTTP {status})"})

# ===== Source 5: Open-web sweep (open_web_search, daily cadence) =====
print("\n" + "=" * 60)
print("SOURCE: Open-web sweep (open_web_search, daily cadence)")
print("=" * 60)

# Remotive API (reliable per memory notes)
print("\n  [Remotive API]")
content, status = fetch("https://remotive.com/api/remote-jobs?category=product-management")
if status == 200:
    try:
        data = json.loads(content)
        jobs = data.get('jobs', [])
        print(f"  OK — HTTP 200, {len(jobs)} jobs in product-management category")
        for j in jobs:
            title = j.get('title', '') or j.get('position', '')
            matched_variant = title_matches_variant(title)
            if not matched_variant:
                continue
            pub = j.get('publication_date', '')
            posted_at = None
            if pub:
                try:
                    posted_at = datetime.fromisoformat(pub.replace('Z', '+00:00')).isoformat()
                except:
                    pass
            company = j.get('company_name', '')
            url = j.get('url', '')
            salary = j.get('salary', '')
            loc = j.get('candidate_required_location', '') or j.get('location', '')
            is_recent = False
            if posted_at:
                try:
                    d = datetime.fromisoformat(posted_at)
                    is_recent = (now - d).total_seconds() < 86400
                except:
                    pass
            job = {
                'company': company,
                'role_title': title,
                'posting_url': url,
                'location': loc,
                'posted_at_raw': f'publication_date: {pub}',
                'posted_at': posted_at,
                'salary_range': salary,
                'source': 'remotive-api',
                'matched_variant': matched_variant,
                'is_recent': is_recent,
            }
            all_candidates.append(job)
            print(f"    [{matched_variant}] {company}: {title} | posted={pub} | recent={is_recent} | sal={salary[:30]} | loc={loc[:40]}")
    except json.JSONDecodeError as e:
        print(f"  ERROR: JSON parse failed ({e})")
else:
    print(f"  BLOCKED: Remotive API HTTP {status}")

# Bing search for product manager jobs (note: site: operators ignored)
print("\n  [Bing search]")
content, status = fetch("https://www.bing.com/search?q=product+manager+remote+hiring+job+opening&count=20")
if status == 200:
    soup = BeautifulSoup(content, 'lxml')
    results = soup.find_all('li', class_='b_algo')
    job_count = 0
    for r in results:
        link = r.find('a', href=True)
        if link:
            title = link.get_text(strip=True)
            href = link['href']
            m = re.search(r'uddg=([^&]+)', href)
            real_url = urllib.parse.unquote(m.group(1)) if m else href
            # Filter out dictionary/encyclopedia pages
            is_dict = any(d in real_url for d in ['wikipedia', 'cambridge.org', 'merriam-webster', 'thefreedictionary', 'thembains', 'simplicable', 'marketingtutor', 'indiatimes'])
            if not is_dict and title_matches_variant(title):
                job_count += 1
                print(f"    [PM MATCH] {title[:70]} | {real_url[:100]}")
    print(f"  Bing returned {len(results)} results, {job_count} non-dictionary PM matches")
    if job_count == 0 and len(results) == 10:
        print("  NOTE: Bing returning dictionary definitions, not job listings (site: operator not supported)")
else:
    print(f"  BLOCKED: Bing HTTP {status}")

# HN Who's Hiring RSS
print("\n  [HNRSS: who's hiring]")
content, status = fetch("https://hnrss.org/newest?q=who%27s+hiring+september", timeout=15)
if status == 200:
    soup = BeautifulSoup(content, 'xml')
    items = soup.find_all('item')
    print(f"  OK — HTTP 200, {len(items)} feed items")
    for item in items[:5]:
        title = item.title.get_text() if item.title else ''
        link = item.link.get_text() if item.link else ''
        print(f"    - {title[:70]} | {link[:80]}")
else:
    print(f"  BLOCKED: HNRSS HTTP {status}")

# Working Nomads
print("\n  [Working Nomads]")
content, status = fetch("https://www.workingnomads.com/jobs?category=product")
if status == 200:
    soup = BeautifulSoup(content, 'lxml')
    pm_links = []
    for a in soup.find_all('a', href=True):
        text = a.get_text(strip=True)
        href = a['href']
        if text and ('product' in text.lower() and 'manager' in text.lower()):
            pm_links.append((text[:70], href[:100]))
    print(f"  OK — HTTP 200, {len(pm_links)} PM links found")
    for t, u in pm_links[:5]:
        print(f"    - {t} | {u}")
else:
    print(f"  BLOCKED: Working Nomads HTTP {status}")

# ===== Dedupe and filter =====
print("\n" + "=" * 60)
print("AGGREGATION: Dedupe + Cheap-filter")
print("=" * 60)

survivors = []
for job in all_candidates:
    # Dedupe by URL
    if job['posting_url'] in db['all_urls']:
        skipped_duplicates.append(job)
        print(f"  DUP (URL): {job['company']} — {job['role_title']} | {job['posting_url'][:80]}")
        continue
    
    # Dedupe by fingerprint
    fp = compute_fingerprint(job['company'], job['role_title'], job.get('location', ''))
    if fp in db['existing_fps']:
        skipped_duplicates.append(job)
        # Would insert into posting_sources instead
        print(f"  DUP (fingerprint): {job['company']} — {job['role_title']} | fp={fp}")
        continue
    
    # Cheap filter
    passes, reason = passes_cheap_filter(job)
    if not passes:
        skipped_filter.append({"company": job['company'], "role_title": job['role_title'], "note": reason})
        print(f"  FILTERED: {job['company']} — {job['role_title']} | {reason}")
        continue
    
    # Check daily cap
    if db['remaining_slots'] <= 0:
        print(f"  CAP REACHED: {job['company']} — {job['role_title']} (no slots left)")
        continue
    
    survivors.append(job)
    new_found += 1
    db['remaining_slots'] -= 1
    print(f"  QUEUED: {job['company']} — {job['role_title']} | posted_at={job['posted_at']} | recent={job['is_recent']} | priority={'high' if job['is_recent'] else 'normal'}")

print(f"\n--- SUMMARY ---")
print(f"  Total candidates collected: {len(all_candidates)}")
print(f"  Duplicates: {len(skipped_duplicates)}")
print(f"  Filtered out: {len(skipped_filter)}")
print(f"  New found (queued): {len(survivors)}")
print(f"  Remaining slots: {db['remaining_slots']}")
print(f"  Blocked sources: {len(blocked_sources)}")
for s in blocked_sources:
    print(f"    - {s['source']} ({s['type']}): {s['reason']}")

# Write results
results = {
    "queued": survivors,
    "skipped_duplicates": skipped_duplicates,
    "skipped_filter": skipped_filter,
    "overflow": [],
}
# Update state files
results_data = {
    "queued": [{"company": s['company'], "role_title": s['role_title'], "posting_url": s['posting_url'], "source": s['source']} for s in survivors],
    "skipped_duplicates": [{"company": s['company'], "role_title": s['role_title'], "posting_url": s['posting_url'], "source": s.get('source', 'unknown')} for s in skipped_duplicates],
    "skipped_filter": skipped_filter,
    "overflow": []
}
with open(SKILL_ROOT / "shared" / ".discovery_results.json", 'w') as f:
    json.dump(results_data, f, indent=2)

raw_results = {
    "run_at": now.isoformat(),
    "sources": {s['source']: s['reason'] for s in blocked_sources},
    "postings": [{"company": s['company'], "role_title": s['role_title'], "posting_url": s['posting_url'], "source": s.get('source', 'unknown')} for s in survivors],
    "count": len(survivors)
}
with open(SKILL_ROOT / "shared" / ".discovery_raw_results.json", 'w') as f:
    json.dump(raw_results, f, indent=2)

gate_state = {
    "last_run_at": now.isoformat(),
    "sources_checked": ["linkedin-global", "indeed-global", "remote-ok", "wellfound", "open_web_sweep (remotive, bing, hnrss, workingnomads)"],
    "new_found": len(survivors),
    "duplicates": len(skipped_duplicates),
    "filtered_out": len(skipped_filter),
    "queued": len(survivors),
    "today_queued": db['discovered_today'] + len(survivors),
    "cap_reached": db['remaining_slots'] <= 0,
    "remaining_slots": db['remaining_slots'],
    "daily_cap": DAILY_CAP
}
with open(SKILL_ROOT / "shared" / ".discovery_gate_state.json", 'w') as f:
    json.dump(gate_state, f, indent=2)

# Save the scan results
scan_results = {
    "scan_time": now.isoformat(),
    "queued": [{"company": s['company'], "role_title": s['role_title'], "posting_url": s['posting_url'], "source": s.get('source', 'unknown'), "posted_at": s.get('posted_at'), "is_recent": s.get('is_recent', False), "matched_variant": s.get('matched_variant', '')} for s in survivors],
    "skipped_duplicates": [{"company": s['company'], "role_title": s['role_title'], "posting_url": s['posting_url'], "source": s.get('source', 'unknown')} for s in skipped_duplicates],
    "skipped_filter": skipped_filter,
    "blocked_sources": blocked_sources,
    "sources_status": raw_results["sources"],
    "daily_cap": DAILY_CAP,
    "discovered_today": db['discovered_today'],
    "staged_today": db['staged_today'],
    "remaining_slots_before_queue": DAILY_CAP - db['discovered_today'],
    "queued_count": len(survivors),
}
results_path = SKILL_ROOT / "01-job-discovery" / "scripts" / "discovery_scan_results.json"
with open(results_path, 'w') as f:
    json.dump(scan_results, f, indent=2)

print(f"\nState files updated. Results saved to {results_path}")
