#!/usr/bin/env python
"""01-job-discovery scan: fetch new postings from in-play sources,
dedupe against applications.db, cheap-filter against target-profile,
and queue survivors. Run as one batch for reliability."""

import requests, json, re, sqlite3, datetime
from bs4 import BeautifulSoup

SKILL_ROOT = "C:/Users/rotim/AppData/Local/hermes/skills/job-hunting"
DB_PATH = f"{SKILL_ROOT}/shared/applications.db"
SOURCES_PATH = f"{SKILL_ROOT}/shared/sources.yaml"
TARGET_PATH = f"{SKILL_ROOT}/shared/target-profile.yaml"
STATE_PATH = f"{SKILL_ROOT}/shared/.discovery_gate_state.json"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}
BING_URL = 'https://www.bing.com/search'

import yaml
with open(TARGET_PATH) as f:
    target = yaml.safe_load(f)

title_variants = [tv['title'] for tv in target.get('title_variants', [])]
seniority_band = target.get('seniority_band', 'mid')
locations = target.get('locations', {})
salary_floor = target.get('salary_floor', {})
visa_required = target.get('visa_sponsorship_required', True)
companies_exclude = target.get('companies_exclude', [])
industries_exclude = target.get('industries_exclude', [])
discovery_mode = target.get('discovery_mode', 'poll_only')

print(f"Discovery mode: {discovery_mode}")
print(f"Title variants: {title_variants}")
print(f"Salary floor: {salary_floor}")
print(f"Visa required: {visa_required}")
print(f"Seniority band: {seniority_band}")
print(f"Companies exclude: {companies_exclude}")
print(f"Industries exclude: {industries_exclude}")

# Load gate state for daily cap
with open(STATE_PATH) as f:
    gate_state = json.load(f)
print(f"\nGate state: remaining_slots={gate_state.get('remaining_slots', 0)}, daily_cap={gate_state.get('daily_cap', 0)}")

# Load existing fingerprints for dedup
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
existing_fingerprints = set()
for r in cur.execute('SELECT posting_fingerprint FROM applications WHERE posting_fingerprint IS NOT NULL'):
    existing_fingerprints.add(r[0])
print(f"\nExisting fingerprints: {len(existing_fingerprints)}")

# Also load existing posting URLs for dedup
existing_urls = set()
for r in cur.execute('SELECT DISTINCT posting_url FROM applications'):
    existing_urls.add(r[0])

now = datetime.datetime.now(datetime.timezone.utc)
recent_cutoff = now - datetime.timedelta(hours=24)

# --- Title normalisation for fingerprint ---
def normalize_title(title):
    """Lowercase, strip punctuation, remove board decorations."""
    t = title.lower().strip()
    # Remove trailing requisition IDs like "#12345"
    t = re.sub(r'\s*#\d+\s*$', '', t)
    # Remove roman numeral suffixes: " (II)" " (III)" etc.
    t = re.sub(r'\s*\(\s*[IVX]+\s*\)$', '', t)
    # Remove level suffixes: " (Senior)" " (Junior)" etc. — but keep
    # titles that are specifically "Senior Product Manager" since
    # that's a distinct title variant. The decoration to strip is the
    # parenthetical version: "Product Manager (Senior)"
    # For fingerprint purposes, strip parenthetical level annotations
    t = re.sub(r'\s*\(\s*(senior|junior|lead|principal|staff|mid|mid-level|entry|associate)\s*\)$', '', t)
    # Remove trailing "(Remote)", "(Contract)", etc.
    t = re.sub(r'\s*\(\s*(remote|contract|freelance|temp)\s*\)$', '', t)
    # Remove trailing department like "Product Manager, Growth"
    # Actually, keep these — they distinguish roles. Just strip simple decorations.
    t = re.sub(r'[^\w\s]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def compute_fingerprint(company, role_title, location):
    """Compute posting_fingerprint: lower(trim(company)) | normalised_role_title | lower(trim(location))"""
    c = (company or '').lower().strip()
    t = normalize_title(role_title or '')
    l = (location or '').lower().strip()
    # Clean location: remove extra whitespace
    l = re.sub(r'\s+', ' ', l)
    return f"{c}|{t}|{l}"

# --- Cheap filter: does role title match any title_variant? ---
def title_matches(role_title, variants):
    """Check if role_title matches any variant (case-insensitive, substring)."""
    t_lower = role_title.lower().strip()
    for v in variants:
        v_lower = v.lower().strip()
        if v_lower in t_lower or t_lower in v_lower:
            return True
    # Also check if the normalized title contains any variant keyword
    for v in variants:
        v_norm = normalize_title(v)
        t_norm = normalize_title(role_title)
        if v_norm in t_norm or t_norm in v_norm:
            return True
    return False

# --- Check salary against floor ---
def passes_salary(salary_text, floor):
    """Check if salary meets floor. Returns True if no salary disclosed or meets floor."""
    if not salary_text:
        return True  # no salary info — don't reject
    # Extract numbers and currency
    # Look for patterns like "$80,000", "80k", "80,000 USD", "NGN 500,000", etc.
    text = salary_text.lower()
    # USD amounts
    usd_matches = re.findall(r'\$?\s*([\d,.]+)\s*(?:k|thousand)?\s*(?:usd|per year|annual|yr)', text)
    # Also try: "80k", "$80k"
    k_matches = re.findall(r'\$?\s*([\d,,.]+)k\b', text)
    amounts = []
    for m in usd_matches:
        try:
            val = float(m.replace(',', '').replace('.', ''))
            if 'k' in text[max(0, text.find(m)-3):text.find(m)+len(m)+3]:
                val *= 1000
            amounts.append(val)
        except:
            pass
    for m in k_matches:
        try:
            amounts.append(float(m.replace(',', '')) * 1000)
        except:
            pass
    if amounts:
        max_amount = max(amounts)
        floor_amount = floor.get('amount', 0)
        floor_currency = floor.get('currency', 'USD')
        floor_period = floor.get('period', 'year')
        if floor_currency == 'USD' and max_amount >= floor_amount:
            return True
        if floor_currency == 'USD' and max_amount < floor_amount:
            # Check if it might be monthly and annualized
            if max_amount * 12 >= floor_amount:
                return True
            return False
    return True  # if we can't determine, don't reject

# --- Source: Wellfound (scrape_and_filter) ---
found_postings = []

print("\n" + "="*60)
print("SOURCE 1: Wellfound (scrape_and_filter)")
print("="*60)

try:
    r = requests.get('https://wellfound.com/jobs', headers=HEADERS, timeout=15, allow_redirects=True)
    print(f"Wellfound status: {r.status_code}, length: {len(r.text)}")
    if r.status_code == 200 and len(r.text) > 500:
        soup = BeautifulSoup(r.text, 'html.parser')
        # Wellfound uses React — links to /jobs/NNNNN-title
        job_links = soup.find_all('a', href=re.compile(r'/jobs/\d+'))
        print(f"Job links found in HTML: {len(job_links)}")
        if job_links:
            for link in job_links[:20]:
                href = link.get('href', '')
                full_url = f"https://wellfound.com{href}" if href.startswith('/') else href
                # Try to find title/company in nearby text
                text = link.get_text(strip=True)[:200]
                nearby = link.find_parent(class_=re.compile(r'card|job|listing|posting', re.I))
                nearby_text = nearby.get_text(strip=True)[:300] if nearby else ''
                print(f"  Link: {full_url}")
                print(f"  Text: {text[:150]}")
                if nearby_text:
                    print(f"  Nearby: {nearby_text[:150]}")
        else:
            # Check if page is JS-rendered (minimal HTML)
            scripts = soup.find_all('script')
            print(f"Scripts found: {len(scripts)}")
            # Check for Next.js data
            nextjs_data = soup.find('script', id='__NEXT_DATA__')
            if nextjs_data:
                print("Found __NEXT_DATA__ — page uses Next.js SSR")
                data = json.loads(nextjs_data.string)
                print(f"Next.js data keys: {list(data.keys())[:10]}")
            else:
                print("No __NEXT_DATA__ — likely requires JS rendering")
                # Check for any JSON blob in script tags
                for s in scripts:
                    content = s.string or s.get('src', '')
                    if content and 'job' in content.lower()[:200]:
                        print(f"  Script with job content: {content[:100]}")
    else:
        print(f"Wellfound not accessible (status {r.status_code}) — BLOCKED or needs JS rendering")
except Exception as e:
    print(f"Wellfound fetch error: {e}")
    print("Wellfound BLOCKED — marking as blocked for this run")

# --- Source: Open-web sweep (open_web_search with platform_dorks) ---
print("\n" + "="*60)
print("SOURCE 2: Open-web sweep (open_web_search, platform_dorks)")
print("="*60)

ats_platforms = {
    'greenhouse': ('site:greenhouse.io', 'Greenhouse'),
    'lever': ('site:jobs.lever.co', 'Lever'),
    'ashby': ('site:ashby.io', 'Ashby'),
    'workday': ('site:my.workday.com OR site:workday.com', 'Workday'),
    'smartrecruiters': ('site:company.smartrecruiters.com', 'SmartRecruiters'),
    'icims': ('site:icims.com OR site:jobs.icims.com', 'iCIMS'),
}

title_query = ' OR '.join([f'"{t}"' for t in title_variants])

for platform, (dork, label) in ats_platforms.items():
    query = f'{dork} {title_query} remote'
    try:
        r = requests.get(BING_URL, params={'q': query, 'count': 10}, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            # Bing organic results: <li class="b_algo"> with <h2><a href>
            result_links = soup.select('li.b_algo h2 a')
            if result_links:
                print(f"\n[{platform}/{label}] Found {len(result_links)} results:")
                for a in result_links[:8]:
                    href = a.get('href', '')
                    title = a.get_text(strip=True)[:150]
                    print(f"  -> {title}")
                    print(f"     {href}")
                    found_postings.append({
                        'url': href, 'title': title, 'source': label,
                        'posted_at': None, 'posted_at_raw': None,
                        'discovered_at': now.isoformat(),
                    })
            else:
                # Try alternate extraction
                all_links = soup.find_all('a', href=True)
                job_links = [a for a in all_links if any(p in a['href'] for p in [label.lower(), 'job', 'career'])]
                print(f"\n[{platform}/{label}] {len(all_links)} total links, {len(job_links)} job-related")
                for a in job_links[:5]:
                    href = a.get('href', '')
                    title = a.get_text(strip=True)[:150]
                    print(f"  -> {title}")
                    print(f"     {href}")
                    found_postings.append({
                        'url': href, 'title': title, 'source': label,
                        'posted_at': None, 'posted_at_raw': None,
                        'discovered_at': now.isoformat(),
                    })
        else:
            print(f"\n[{platform}/{label}] Bing returned status {r.status_code}")
    except Exception as e:
        print(f"\n[{platform}/{label}] Error: {e}")

# Generic open search
query = f'{title_query} remote job -site:linkedin.com -site:indeed.com'
try:
    r = requests.get(BING_URL, params={'q': query, 'count': 10}, headers=HEADERS, timeout=15)
    if r.status_code == 200:
        soup = BeautifulSoup(r.text, 'html.parser')
        result_links = soup.select('li.b_algo h2 a')
        print(f"\n[Generic] Found {len(result_links)} results:")
        for a in result_links[:8]:
            href = a.get('href', '')
            title = a.get_text(strip=True)[:150]
            print(f"  -> {title}")
            print(f"     {href}")
            found_postings.append({
                'url': href, 'title': title, 'source': 'bing_generic',
                'posted_at': None, 'posted_at_raw': None,
                'discovered_at': now.isoformat(),
            })
except Exception as e:
    print(f"\n[Generic] Error: {e}")

conn.close()
print(f"\n{'='*60}")
print(f"Total postings found: {len(found_postings)}")
