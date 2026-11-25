#!/usr/bin/env python3
"""Run discovery scan for today — checks all accessible sources.

Sources:
  open_web mode = poll_only (declared sources) + open_web_search (daily sweep)
  Declared sources from sources.yaml:
    - linkedin-global   (BLOCKED — LinkedIn anti-bot)        -> skip
    - indeed-global     (BLOCKED — HTTP 404)                -> skip
    - remote-ok         (BLOCKED — RemoteOK anti-bot)      -> skip
    - wellfound         (scrape_and_filter — wellfound.com) -> try
    - open-web-sweep    (open_web_search, daily, platform_dorks: true)
        -> Bing search per ATS platform + generic
        -> Remotive API (reliable)
        -> HNRSS "who's hiring" (reliable)
        -> Working Nomads (try)
"""
import json, re, sqlite3, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

SKILL_ROOT = Path("C:/Users/rotim/AppData/Local/hermes/skills/job-hunting")
DB_PATH = SKILL_ROOT / "shared" / "applications.db"
SHARED = SKILL_ROOT / "shared"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}
TIMEOUT = 20
DAILY_CAP = 15

# --- Target profile (from shared/target-profile.yaml) ---
TITLE_VARIANTS = [
    "Product Manager", "AI Product Manager", "AI Engineer", "Automation Engineer",
    "Associate Product Manager", "Junior Product Manager", "Workflow Engineer",
    "Product Owner", "Technical Product Manager", "Growth Product Manager",
    "AI/ML Product Manager",
]
TV_LOWER = [v.lower().strip() for v in TITLE_VARIANTS]
SENIORITY_BAND = "mid"   # open to junior/associate too
REMOTE_OK = True
HYBRID_OK = True
ONSITE_OK = True
SALARY_FLOOR = 36000  # USD/year
VISA_SPONSORSHIP_REQUIRED = True

# --- DB state ---
conn = sqlite3.connect(str(DB_PATH))
c = conn.cursor()
c.execute("SELECT posting_url FROM applications WHERE posting_url IS NOT NULL")
db_urls = set(r[0].lower() for r in c.fetchall())
c.execute("SELECT posting_url FROM posting_sources WHERE posting_url IS NOT NULL")
src_urls = set(r[0].lower() for r in c.fetchall())
all_known_urls = db_urls | src_urls
c.execute("SELECT posting_fingerprint FROM applications WHERE posting_fingerprint IS NOT NULL")
db_fps = set(r[0] for r in c.fetchall())
c.execute("SELECT COUNT(*) FROM applications WHERE status='discovered' AND date(discovered_at) = date('now', 'localtime')")
today_queued = c.fetchone()[0]
conn.close()

NOW = datetime.now(timezone.utc)
remaining_slots = DAILY_CAP - today_queued
print(f"DB state: {len(all_known_urls)} known URLs, {len(db_fps)} fingerprints")
print(f"Today queued: {today_queued}, daily cap: {DAILY_CAP}, remaining: {remaining_slots}")

def normalise_title(title):
    """Lowercase, strip punctuation, remove board decorations."""
    t = title.lower().strip()
    t = re.sub(r'[^\w\s]', ' ', t)
    # Remove trailing decorations
    for suffix in ['(remote)', 'remote', '- contract', 'contract', 'fulltime', 'full time',
                    ' requisition ', ' req ', ' opening ']:
        t = t.replace(suffix, ' ')
    # Remove roman-numeral suffixes (I, II, III, IV, V)
    t = re.sub(r'\s+(I|II|III|IV|V|VI|VII)\s*$', '', t)
    # Remove trailing numbers (requisition IDs)
    t = re.sub(r'\s+\d+\s*$', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def build_fingerprint(company, title, location):
    company = (company or 'unknown').lower().strip()
    loc = (location or 'unknown').lower().strip()
    nt = normalise_title(title)
    return f"{company}|{nt}|{loc}"

def title_matches(title):
    t = title.lower().strip() if title else ''
    for v in TV_LOWER:
        if v in t:
            return True
    return False

def parse_posted_at(raw):
    """Parse various date formats into ISO datetime."""
    if not raw:
        return None
    raw = raw.strip()
    # Try ISO format
    for fmt in ["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
        try:
            dt = datetime.strptime(raw, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except:
            pass
    # Try fromisoformat
    try:
        dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        return dt
    except:
        pass
    return None

def is_recent(posted_at_raw, posted_at_dt):
    """Check if posting is within 24h."""
    if posted_at_dt:
        age_h = (NOW - posted_at_dt).total_seconds() / 3600
        return age_h < 24
    if posted_at_raw:
        raw_lower = posted_at_raw.lower()
        if 'just' in raw_lower or 'today' in raw_lower or 'now' in raw_lower:
            return True
        m = re.match(r'(\d+)\s*(hour|hr|day|d|min|minute)', raw_lower)
        if m:
            num = int(m.group(1))
            unit = m.group(2)
            if unit in ('hour', 'hr'):
                return num < 24
            elif unit in ('day', 'd'):
                return num <= 0  # today
            elif unit in ('min', 'minute'):
                return True
    return False

def check_salary_floor(salary_str):
    """Return (discloses_salary, below_floor, detail)."""
    if not salary_str:
        return False, False, None
    # Extract dollar amounts
    matches = re.findall(r'\$[\d,.]+[kKmM]?', salary_str.replace(',', ''))
    if not matches:
        # Maybe it's in another currency like NGN
        matches = re.findall(r'₦[\d,.]+', salary_str)
        return True, False, None  # non-USD, don't apply floor
    below = False
    for m in matches:
        num_str = m.replace('$', '').replace(',', '').lower()
        if 'k' in num_str:
            val = float(num_str.replace('k', '')) * 1_000
        elif 'm' in num_str:
            val = float(num_str.replace('m', '')) * 1_000_000
        else:
            val = float(num_str)
        # Annualize: if monthly (and < 20k), multiply by 12
        if val < 20_000:  # likely monthly or raw number
            val = val * 12
        if val < SALARY_FLOOR:
            below = True
    return True, below, salary_str

# --- Collect all new candidates across sources ---
all_candidates = []
sources_tried = []
sources_blocked = []

def add_candidate(company, role_title, posting_url, location, posted_at, posted_at_raw,
                  salary_range, source, matched_variant, is_recent_flag):
    """Add candidate if not in DB; return status string."""
    url_lower = posting_url.lower() if posting_url else ''
    fp = build_fingerprint(company, role_title, location)

    # Check fingerprint first
    if fp in db_fps:
        return 'dup_fp'
    if url_lower in all_known_urls:
        return 'dup_url'

    # Cheap filter: title match
    if not matched_variant:
        if not title_matches(role_title):
            return 'filtered'
    # Salary floor check (only if disclosed AND below floor)
    if salary_range:
        discloses, below, _ = check_salary_floor(str(salary_range))
        if discloses and below:
            return 'filtered'  # below $36k floor
    # Location filter — open_web mode, worldwide, all location types OK
    # (no specific locations/cities to exclude)

    return 'new', {
        'company': company or 'unknown',
        'role_title': role_title,
        'posting_url': posting_url,
        'location': location,
        'posted_at': posted_at.isoformat() if isinstance(posted_at, datetime) else (posted_at or None),
        'posted_at_raw': posted_at_raw,
        'salary_range': salary_range,
        'source': source,
        'matched_variant': matched_variant or None,
        'is_recent': is_recent_flag,
        'fingerprint': fp,
        'in_db': False
    }

# ============================================================
# 1. REMOTIVE API (reliable source)
# ============================================================
sources_tried.append('remotive-api')
print("\n=== [1] Remotive API ===")
try:
    resp = requests.get("https://remotive.com/api/remote-jobs",
                       headers=HEADERS, timeout=TIMEOUT)
    print(f"  HTTP {resp.status_code}, size={len(resp.text)}")
    if resp.status_code == 200:
        data = resp.json()
        jobs = data.get('jobs', []) if isinstance(data, dict) else []
        new_count = dup_count = filt_count = 0
        for j in jobs:
            title = j.get('title', '')
            matched_v = TITLE_VARIANTS[TV_LOWER.index(v)] if (v := next((tv for tv in TV_LOWER if tv in (title or '').lower()), None)) else None
            if not matched_v:
                continue
            url = j.get('url', '')
            pub = j.get('publication_date', '') or j.get('date_posted', '')
            posted_dt = parse_posted_at(pub)
            age_h = f"{(NOW - posted_dt).total_seconds()/3600:.1f}h" if posted_dt else "unknown"
            rec = is_recent(posted_dt and pub, posted_dt)
            salary = j.get('salary', '')
            company = j.get('company_name', '')
            location = j.get('candidate_required_location', '')
            result = add_candidate(company, title, url, location, posted_dt, pub,
                                   salary, 'remotive-api', matched_v, rec)
            if result == 'filtered':
                filt_count += 1
            elif isinstance(result, tuple) and result[0] == 'new':
                all_candidates.append(result[1])
                new_count += 1
            else:
                dup_count += 1
            m = '[NEW]' if result == 'new' or (isinstance(result, tuple) and result[0] == 'new') else '[DUP]'
            print(f"  {m} {title[:50]} | {company[:25]} | age={age_h} | {url[:70]}")
        print(f"  Remotive: {new_count} new, {dup_count} dup, {filt_count} filtered")
except Exception as e:
    sources_blocked.append('remotive-api')
    print(f"  ERROR: {e}")

# ============================================================
# 2. HNRSS — "who's hiring" (reliable source)
# ============================================================
sources_tried.append('hnrss-who-is-hiring')
print("\n=== [2] HNRSS: who's hiring ===")
try:
    resp = requests.get("https://hnrss.org/newest?q=who%27s+hiring+september",
                       headers=HEADERS, timeout=TIMEOUT)
    print(f"  HTTP {resp.status_code}, size={len(resp.text)}")
    if resp.status_code == 200 and len(resp.text) > 10:
        soup = BeautifulSoup(resp.text, 'xml')
        items = soup.find_all('item')
        new_count = dup_count = 0
        for item in items[:15]:
            title = item.title.get_text().strip() if item.title else ''
            link = item.link.get_text().strip() if item.link else ''
            matched_v = TITLE_VARIANTS[TV_LOWER.index(v)] if (v := next((tv for tv in TV_LOWER if tv in title.lower()), None)) else None
            pub_date = item.pubDate.get_text().strip() if item.pubDate else ''
            posted_dt = parse_posted_at(pub_date)
            rec = is_recent(posted_dt and pub_date, posted_dt)
            result = add_candidate('unknown', title, link, 'unknown', posted_dt, pub_date,
                                   None, 'hnrss-who-is-hiring', matched_v, rec)
            if isinstance(result, tuple) and result[0] == 'new':
                all_candidates.append(result[1])
                new_count += 1
                print(f"  [NEW] {title[:70]} | {link[:80]}")
            elif result == 'dup_fp' or result == 'dup_url':
                dup_count += 1
            # Non-PM HNRSS items are just skipped silently
        print(f"  HNRSS: {new_count} new PM, {dup_count} dup")
except Exception as e:
    sources_blocked.append('hnrss-who-is-hiring')
    print(f"  ERROR: {e}")

# ============================================================
# 3. WELLFOUND (scrape_and_filter)
# ============================================================
sources_tried.append('wellfound')
print("\n=== [3] Wellfound ===")
try:
    resp = requests.get("https://wellfound.com/jobs", headers=HEADERS, timeout=TIMEOUT)
    print(f"  HTTP {resp.status_code}, size={len(resp.text)}")
    if resp.status_code == 200 and len(resp.text) > 1000:
        soup = BeautifulSoup(resp.text, 'lxml')
        # Wellfound: job cards link to /jobs/<id>-<slug>
        job_links = soup.find_all('a', href=re.compile(r'/jobs/\d+'))
        print(f"  Job links found: {len(job_links)}")
        pm_count = 0
        for a in job_links[:50]:
            href = a.get('href', '')
            if not href.startswith('http'):
                href = 'https://wellfound.com' + href
            text = a.get_text(' ', strip=True)
            matched_v = TITLE_VARIANTS[TV_LOWER.index(v)] if (v := next((tv for tv in TV_LOWER if tv in text.lower()), None)) else None
            if matched_v:
                pm_count += 1
                # Try to extract date nearby
                date_raw = 'unknown'
                # Look for date indicators in nearby text
                parent = a.parent
                if parent:
                    nearby = parent.get_text()
                    date_match = re.search(r'(today|yesterday|just now|\d+\s*(?:hours?|days?)\s*ago)', nearby, re.I)
                    if date_match:
                        date_raw = date_match.group(1)
                    company_match = re.search(r'>([^<]+)<!-- --> • </', str(parent)[:500])
                    company = company_match.group(1) if company_match else 'unknown'
                else:
                    company = 'unknown'
                posted_dt = parse_posted_at(date_raw) if date_raw != 'unknown' else None
                loc_match = re.search(r'(remote|on-site|onsite|usa|uk|emea|europe)', text, re.I)
                loc = loc_match.group(1) if loc_match else 'unknown'
                result = add_candidate(company, text.strip(), href, loc, posted_dt, date_raw,
                                       None, 'wellfound', matched_v, is_recent(date_raw, posted_dt))
                if isinstance(result, tuple) and result[0] == 'new':
                    all_candidates.append(result[1])
                    print(f"  [NEW] {text[:50]} | {company[:25]} | {href[:70]}")
                elif result == 'filtered':
                    print(f"  [FILT] {text[:50]} | {href[:70]}")
        print(f"  Wellfound: {pm_count} PM links, {len([c for c in all_candidates if c['source']=='wellfound'])} new")
    else:
        sources_blocked.append('wellfound')
        print(f"  Blocked/unreachable (HTTP {resp.status_code})")
except Exception as e:
    sources_blocked.append('wellfound')
    print(f"  ERROR: {e}")

# ============================================================
# 4. BING SEARCH — open_web sweep per ATS platform (reliable)
# ============================================================
ATS_PLATFORMS = [
    ("Lever", "site:jobs.lever.co"),
    ("Ashby", "site:jobs.ashbyhq.com"),
    ("Greenhouse", "site:boards.greenhouse.io"),
    ("Workday", "site:my.workday.com"),
    ("SmartRecruiters", "site:company.smartrecruiters.com"),
    ("iCIMS", "site:icims.com"),
]
sources_tried.append('open_web_search (bing, per-ATS)')
print("\n=== [4] Bing search — per-ATS PM sweep ===")

ats_new = 0
ats_dup = 0
ats_filtered = 0
for platform_name, site_op in ATS_PLATFORMS:
    query = f'product manager remote hiring 2026 {site_op}'
    print(f"\n  -- {platform_name} ({site_op}) --")
    try:
        resp = requests.get("https://www.bing.com/search",
                           params={'q': query, 'count': '15'},
                           headers=HEADERS, timeout=TIMEOUT)
        print(f"  HTTP {resp.status_code}, size={len(resp.text)}")
        if resp.status_code != 200 or len(resp.text) < 200:
            print("  Blocked or empty")
            continue
        soup = BeautifulSoup(resp.text, 'lxml')
        # Bing organic results
        results = soup.find_all('li', class_='b_algo')
        if not results:
            # Try alternate structure
            results = soup.find_all('div', class_='b_algo')
        print(f"  Organic results: {len(results)}")
        for r in results:
            # Extract link and title
            link_tag = r.find('a', href=True) if hasattr(r, 'find') else None
            if not link_tag:
                continue
            href = link_tag.get('href', '')
            title = link_tag.get_text(strip=True)
            # Resolve Bing redirect
            real_url = href
            m = re.search(r'uddg=([^&]+)', href)
            if m:
                from urllib.parse import unquote
                real_url = unquote(m.group(1))
            if not real_url.startswith('http'):
                continue
            # Skip non-job sites
            skip_domains = ['merriam-webster', 'cambridge.org', 'wikipedia', 'producthunt',
                           'thembains', 'simplicable', 'marketingtutor', 'aha.io', 'bing.com']
            if any(d in real_url for d in skip_domains):
                continue

            matched_v = TITLE_VARIANTS[TV_LOWER.index(v)] if (v := next((tv for tv in TV_LOWER if tv in title.lower()), None)) else None
            if not matched_v:
                continue

            result = add_candidate('', title, real_url, 'remote', None, 'relative_text_on_page',
                                   None, 'open_web_search', matched_v, False)
            if isinstance(result, tuple) and result[0] == 'new':
                all_candidates.append(result[1])
                ats_new += 1
                print(f"  [NEW] {title[:60]} | {real_url[:80]}")
            elif result == 'dup_fp' or result == 'dup_url':
                ats_dup += 1
            elif result == 'filtered':
                ats_filtered += 1
    except Exception as e:
        print(f"  ERROR: {e}")

# --- Generic Bing search (non-ATS) ---
print("\n  -- Generic open-web sweep --")
query = '"product manager" "hiring" remote 2026'
try:
    resp = requests.get("https://www.bing.com/search",
                       params={'q': query, 'count': '15'},
                       headers=HEADERS, timeout=TIMEOUT)
    print(f"  HTTP {resp.status_code}, size={len(resp.text)}")
    if resp.status_code == 200 and len(resp.text) > 200:
        soup = BeautifulSoup(resp.text, 'lxml')
        results = soup.find_all('li', class_='b_algo')
        if not results:
            results = soup.find_all('div', class_='b_algo')
        print(f"  Organic results: {len(results)}")
        for r in results:
            link_tag = r.find('a', href=True) if hasattr(r, 'find') else None
            if not link_tag:
                continue
            href = link_tag.get('href', '')
            title = link_tag.get_text(strip=True)
            m = re.search(r'uddg=([^&]+)', href)
            if m:
                from urllib.parse import unquote
                href = unquote(m.group(1))
            if not href.startswith('http'):
                continue
            skip_domains = ['merriam-webster', 'cambridge.org', 'wikipedia', 'producthunt',
                           'thembains', 'simplicable', 'marketingtutor', 'aha.io', 'bing.com']
            if any(d in href for d in skip_domains):
                continue
            matched_v = TITLE_VARIANTS[TV_LOWER.index(v)] if (v := next((tv for tv in TV_LOWER if tv in title.lower()), None)) else None
            if not matched_v:
                continue
            result = add_candidate('', title, href, 'remote', None, 'relative_text_on_page',
                                   None, 'open_web_search', matched_v, False)
            if isinstance(result, tuple) and result[0] == 'new':
                all_candidates.append(result[1])
                ats_new += 1
                print(f"  [NEW] {title[:60]} | {href[:80]}")
            elif result == 'dup_fp' or result == 'dup_url':
                ats_dup += 1
            elif result == 'filtered':
                ats_filtered += 1
except Exception as e:
    print(f"  ERROR: {e}")

# ============================================================
# SUMMARY
# ============================================================
print(f"\n{'='*60}")
print(f"DISCOVERY SUMMARY — {NOW.strftime('%Y-%m-%d %H:%M:%W UTC')}")
print(f"{'='*60}")
print(f"Sources tried: {sources_tried}")
print(f"Sources blocked: {sources_blocked}")
print(f"Total new candidates: {len(all_candidates)}")
print(f"Remaining daily slots: {remaining_slots}")
print(f"Would queue: {min(len(all_candidates), remaining_slots)}")
print()
for c in all_candidates:
    recent = '[RECENT]' if c['is_recent'] else '[old]   '
    print(f"  {recent} {c['company'][:25]} | {c['role_title'][:45]} | {c['posting_url'][:80]} | {c['source']}")

# Save for the queue step
out = {
    'scan_at': NOW.isoformat(),
    'sources_tried': sources_tried,
    'sources_blocked': sources_blocked,
    'all_new': all_candidates,
    'remaining_slots': remaining_slots,
    'daily_cap': DAILY_CAP,
}
outpath = SHARED / ".discovery_scan_results.json"
with open(outpath, 'w') as f:
    json.dump(out, f, indent=2, default=str)
print(f"\nResults saved to: {outpath}")
