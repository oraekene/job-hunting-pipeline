#!/usr/bin/env python3
"""Extract PM job candidates from RemotePMJobs.com and WeLoveProduct.co."""
import requests, re, json, sqlite3
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
from pathlib import Path

SKILL_ROOT = Path("C:/Users/rotim/AppData/Local/hermes/skills/job-hunting")
DB_PATH = SKILL_ROOT / "shared" / "applications.db"

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.6; Win64; x64) AppleWebKit/537.36'}
now = datetime.now(timezone.utc)

pm_titles_raw = [
    'product manager', 'ai product manager', 'ai engineer', 'automation engineer',
    'associate product manager', 'junior product manager', 'workflow engineer',
    'product owner', 'technical product manager', 'growth product manager',
    'ai/ml product manager'
]
pm_titles_lower = [v.lower() for v in pm_titles_raw]

# Load DB URLs
conn = sqlite3.connect(str(DB_PATH))
c = conn.cursor()
c.execute("SELECT posting_url FROM applications WHERE posting_url IS NOT NULL")
db_urls_lower = set(r[0].lower() for r in c.fetchall())
c.execute("SELECT posting_url FROM posting_sources WHERE posting_url IS NOT NULL")
src_urls_lower = set(r[0].lower() for r in c.fetchall())
all_known_urls = db_urls_lower | src_urls_lower
c.execute("SELECT posting_fingerprint FROM applications WHERE posting_fingerprint IS NOT NULL")
db_fps = set(r[0] for r in c.fetchall())
c.execute("SELECT COUNT(*) FROM applications WHERE date(discovered_at) = date('now', 'localtime')")
discovered_today = c.fetchone()[0]
conn.close()

print(f'DB: {len(all_known_urls)} known URLs, {len(db_fps)} fingerprints, {discovered_today} discovered today')

all_candidates = []

# ========== 1. RemotePMJobs.com ==========
print('\n=== RemotePMJobs.com ===')
resp = requests.get('https://www.remotepmjobs.com/', headers=headers, timeout=20)
print(f'HTTP {resp.status_code}, size={len(resp.text)}')

if resp.status_code == 200:
    soup = BeautifulSoup(resp.text, 'lxml')
    job_elements = soup.find_all('a', href=re.compile(r'/companies/'))
    print(f'Job links found: {len(job_elements)}')
    
    for a in job_elements:
        href = a.get('href', '')
        if not href.startswith('http'):
            href = 'https://www.remotepmjobs.com' + href
        text = a.get_text(' ', strip=True)
        
        # Check if PM-related
        matched_variant = None
        for v in pm_titles_lower:
            if v in text.lower():
                matched_variant = pm_titles_raw[pm_titles_lower.index(v)]
                break
        if not matched_variant:
            continue
        
        # Extract salary
        salary_match = re.search(r'\$[\d,.]+[kKmM]?\s*[-\u2013\u2014]\s*\$?[\d,.]+[kKmM]?(?:/yr)?', text)
        if not salary_match:
            salary_match = re.search(r'\$[\d,.]+[kKmM]?(?:/yr)?', text)
        salary = salary_match.group(0) if salary_match else None
        
        # Extract date info
        date_match = re.search(r'(\d+\s*[dwe]\s*ago|Just posted|New)', text, re.I)
        posted_at_raw = date_match.group(1) if date_match else 'unknown'
        
        # Parse date
        posted_at = None
        is_recent = False
        if date_match:
            dm = re.match(r'(\d+)\s*([dwe])', posted_at_raw)
            if dm:
                num = int(dm.group(1))
                unit = dm.group(2).lower()
                days = num if unit == 'd' else (num / 24 if unit == 'e' else num / 168)
                posted_at = (now - timedelta(days=days)).isoformat()
                is_recent = (num <= 1 and unit == 'd')
            elif 'just posted' in posted_at_raw.lower() or 'new' in posted_at_raw.lower():
                posted_at = now.isoformat()
                is_recent = True
        
        # Extract company - look for company names in the URL
        # URL pattern: /companies/<company>/<job-slug>
        company_match = re.search(r'/companies/([^/]+)/', href)
        company = company_match.group(1).title() if company_match else 'unknown'
        
        # Clean up company name
        company = re.sub(r'-', ' ', company).title()
        
        # Extract location
        loc_match = re.search(r'(US|UK|EMEA|Europe|Remote|LatAm|Canada|Australia|Israel|NY|CA|Anywhere|APAC|Global)', text, re.I)
        location = loc_match.group(1) if loc_match else 'unknown'
        
        # Extract title from text (before company)
        title = text[:80]
        
        in_db = href.lower() in all_known_urls
        
        candidate = {
            'company': company,
            'role_title': title,
            'posting_url': href,
            'location': location,
            'posted_at_raw': posted_at_raw,
            'posted_at': posted_at,
            'salary_range': salary,
            'source': 'remotepmjobs.com',
            'matched_variant': matched_variant,
            'is_recent': is_recent,
            'in_db': in_db,
        }
        all_candidates.append(candidate)
        dup_marker = '[DUP]' if in_db else '[NEW]'
        recent_marker = '[RECENT]' if is_recent else '[old  ]'
        print(f'  {dup_marker}{recent_marker} {company[:20]:20s} | {title[:50]} | sal={salary} | loc={location}')

# ========== 2. WeLoveProduct.co ==========
print('\n=== WeLoveProduct.co ===')
resp2 = requests.get('https://weloveproduct.co/product-manager-jobs-remote', headers=headers, timeout=20)
print(f'HTTP {resp2.status_code}, size={len(resp2.text)}')

if resp2.status_code == 200:
    soup2 = BeautifulSoup(resp2.text, 'lxml')
    job_links2 = soup2.find_all('a', href=re.compile(r'/jobs/'))
    print(f'Job links found: {len(job_links2)}')
    
    for a in job_links2:
        href = a.get('href', '')
        if not href.startswith('http'):
            href = 'https://weloveproduct.co' + href
        text = a.get_text(' ', strip=True)
        
        # Check if PM-related
        matched_variant = None
        for v in pm_titles_lower:
            if v in text.lower():
                matched_variant = pm_titles_raw[pm_titles_lower.index(v)]
                break
        if not matched_variant:
            continue
        
        in_db = href.lower() in all_known_urls
        
        # Try to extract company from the page or URL
        # URL pattern: /jobs/<title>-<company>-<id>
        company_match = re.search(r'/jobs/[^/]+-([a-z0-9-]+)-[a-f0-9]+$', href, re.I)
        company = company_match.group(1).title() if company_match else 'unknown'
        company = re.sub(r'-', ' ', company).title()
        
        candidate = {
            'company': company,
            'role_title': text[:80],
            'posting_url': href,
            'location': 'unknown',
            'posted_at_raw': 'unknown',
            'posted_at': None,
            'salary_range': None,
            'source': 'weloveproduct.co',
            'matched_variant': matched_variant,
            'is_recent': False,
            'in_db': in_db,
        }
        all_candidates.append(candidate)
        dup_marker = '[DUP]' if in_db else '[NEW]'
        print(f'  {dup_marker} {company[:20]:20s} | {text[:50]} | url={href[:80]}')

# ========== Summary ==========
print(f'\n{"="*60}')
print(f'SUMMARY')
print(f'{"="*60}')
new_candidates = [c for c in all_candidates if not c['in_db']]
dupes = [c for c in all_candidates if c['in_db']]
recent = [c for c in all_candidates if c['is_recent']]
print(f'Total candidates collected: {len(all_candidates)}')
print(f'New (not in DB): {len(new_candidates)}')
print(f'Duplicates (in DB): {len(dupes)}')
print(f'Recent (within 24h): {len(recent)}')
for c in new_candidates:
    co = c['company']; rt = c['role_title']; pu = c['posting_url'][:80]; ir = c['is_recent']
    print(f'  NEW: {co} — {rt} | {pu} | recent={ir}')
for c in dupes:
    co = c['company']; rt = c['role_title']; pu = c['posting_url'][:80]
    print(f'  DUP: {co} — {rt} | {pu}')
