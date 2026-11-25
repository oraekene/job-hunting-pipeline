#!/usr/bin/env python3
"""Discovery scan — checks open-web sources (Bing RSS + Remotive API)."""
import urllib.request, urllib.parse, json, re, html as html_mod, sqlite3
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

SKILL_ROOT = r'C:\Users\rotim\AppData\Local\hermes\skills\job-hunting'
DB_PATH = SKILL_ROOT + r'\shared\applications.db'

TITLE_VARIANTS = [
    'product manager', 'ai product manager', 'ai engineer',
    'automation engineer', 'associate product manager', 'junior product manager',
    'workflow engineer', 'product owner', 'technical product manager',
    'growth product manager', 'ai/ml product manager'
]
SALARY_FLOOR = 36000

def normalize_title(title):
    t = title.lower().strip()
    for pat in [r'\s*\(remote\)\s*', r'\s*-\s*contract\s*', r'\s*\(entry\)\s*$',
                r'\s*\(junior\)\s*$', r'\s*\(senior\)\s*$', r'\s*\(lead\)\s*$',
                r'\s*\(principal\)\s*$', r'\s*\(staff\)\s*$', r'\s*#\s*[ivx]+\s*$',
                r'\s*\[\d+\]\s*$', r'\s*\(\d+\)\s*$']:
        t = re.sub(pat, '', t, flags=re.IGNORECASE)
    t = re.sub(r'[^\w\s]', '', t).strip()
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def normalize_location(loc):
    l = loc.lower().strip()
    l = re.sub(r'\s*\+\s*\d+\s*more\s*', '', l)
    l = re.sub(r'[^\w\s]', '', l).strip()
    l = re.sub(r'\s+', ' ', l).strip()
    return l

def compute_fingerprint(company, title, location):
    return f'{company.lower().strip()}|{normalize_title(title)}|{normalize_location(location)}'

def title_matches_variant(title):
    tl = title.lower()
    return any(v in tl for v in TITLE_VARIANTS)

def parse_salary_min(s):
    if not s:
        return None
    sl = s.lower()
    k_match = re.search(r'\$?\s*([\d.]+)\s*k\b', sl)
    if k_match:
        return float(k_match.group(1)) * 1000
    nums = re.findall(r'\$?([\d,]+(?:\.\d+)?)', s.replace(',', ''))
    if nums:
        try:
            val = float(nums[0])
            if 'k' in sl or 'thousand' in sl:
                return val * 1000
            return val
        except:
            pass
    return None

# ── DB setup ──
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute('SELECT posting_fingerprint FROM applications WHERE posting_fingerprint IS NOT NULL')
existing_fps = set(row[0] for row in c.fetchall())
c.execute('SELECT posting_url FROM applications WHERE posting_url IS NOT NULL')
existing_urls = set(row[0] for row in c.fetchall())
c.execute('SELECT posting_url FROM posting_sources WHERE posting_url IS NOT NULL')
for row in c.fetchall():
    existing_urls.add(row[0])
conn.close()

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute("SELECT COUNT(*) FROM applications WHERE date(discovered_at) = date('now') AND status IN ('discovered','building','staged','awaiting_approval')")
today_count = c.fetchone()[0]
conn.close()

daily_cap = 15
remaining = daily_cap - today_count
print(f'Cap: {daily_cap} | Today discovered: {today_count} | Remaining slots: {remaining}')

# ── Source 1: Remotive API (reliable per env config) ──
print('\n=== Remotive API ===')
ro_jobs = []
try:
    req = urllib.request.Request('https://remotive.com/api/remote-jobs',
        headers={'User-Agent': 'Mozilla/5.0'})
    resp = urllib.request.urlopen(req, timeout=15)
    data = json.loads(resp.read().decode())
    jobs = data.get('jobs', [])
    print(f'  API returned {len(jobs)} total jobs')
    for j in jobs:
        title = j.get('title', '')
        if title_matches_variant(title):
            ro_jobs.append({
                'company': j.get('company_name', ''),
                'title': title,
                'url': j.get('url', ''),
                'location': j.get('candidate_required_location', '') or j.get('location') or 'Remote',
                'salary': j.get('salary', '') or '',
                'posted_at_raw': None,
                'source_board': 'Remotive',
                'ats_platform': 'direct',
                'snippet': ''
            })
            print(f'  MATCH: {j.get("company_name","")} | {title} | {j.get("url","")}')
    print(f'  Matching titles: {len(ro_jobs)} of {len(jobs)}')
except Exception as e:
    print(f'  ERROR: {e}')

# ── Source 2: Open-web sweep via Bing RSS ──
print('\n=== Open-web sweep (Bing RSS) ===')
platforms = [
    ('greenhouse', 'site:boards.greenhouse.io OR site:greenhouse.io'),
    ('lever', 'site:jobs.lever.co'),
    ('ashby', 'site:jobs.ashbyhq.com'),
    ('smartrecruiters', 'site:careers.smartrecruiters.com'),
    ('icims', 'site:careers.icims.com'),
]
search_titles = ['Product Manager', 'AI Product Manager', 'Technical Product Manager',
                 'Growth Product Manager', 'Associate Product Manager',
                 'AI Engineer', 'Automation Engineer']

all_candidates = []
source_results = {}
all_candidates.extend(ro_jobs)

for plat_name, plat_dork in platforms:
    titles_q = ' OR '.join(f'"{v}"' for v in search_titles)
    query = f'{plat_dork} ({titles_q}) remote'
    rss_url = 'https://www.bing.com/search?q=' + urllib.parse.quote(query) + '&format=rss'
    try:
        req = urllib.request.Request(rss_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
        resp = urllib.request.urlopen(req, timeout=15)
        xml_text = resp.read().decode('utf-8', errors='replace')
        root = ET.fromstring(xml_text)
        items = root.findall('.//item')
        plat_jobs = []
        for item in items:
            link_el = item.find('link')
            title_el = item.find('title')
            desc_el = item.find('description')
            if link_el is not None and title_el is not None:
                url = (link_el.text or '').strip()
                title = (title_el.text or '').strip()
                desc = (desc_el.text or '').strip() if desc_el is not None else ''
                if not url or not title:
                    continue
                if not (title_matches_variant(title) or 'job' in title.lower() or 'hiring' in title.lower()):
                    continue
                desc_clean = re.sub(r'<[^>]+>', ' ', desc).strip() if desc else ''
                desc_clean = html_mod.unescape(desc_clean)
                company = ''
                if ' — ' in title:
                    company = title.split(' — ')[-1].strip()
                elif ' | ' in title:
                    company = title.split(' | ')[-1].strip()
                salary = ''
                salary_match = re.search(r'\$[\d,.]+(?:\s*k)?', desc_clean)
                if salary_match:
                    salary = salary_match.group(0)
                location = 'Remote'
                for kw in ['remote', 'hybrid', 'onsite', 'united states', 'san francisco',
                           'new york', 'austin', 'seattle', 'london', 'germany', 'canada']:
                    if kw in desc_clean.lower():
                        location = kw.title() if kw in ['remote', 'hybrid', 'onsite'] else desc_clean[:100]
                        break
                plat_jobs.append({
                    'company': company, 'title': title, 'url': url,
                    'location': location or 'Remote', 'salary': salary,
                    'posted_at_raw': None, 'source_board': 'OpenWeb-Bing',
                    'ats_platform': plat_name, 'snippet': desc_clean[:200] if desc_clean else ''
                })
        source_results[f'Bing-{plat_name}'] = f'{len(plat_jobs)} candidates from {len(items)} items'
        all_candidates.extend(plat_jobs)
        for j in plat_jobs:
            print(f'  [{plat_name}] {j["company"]} | {j["title"][:60]} | {j["url"][:80]}')
    except Exception as e:
        source_results[f'Bing-{plat_name}'] = f'ERROR — {e}'
        print(f'  [{plat_name}] ERROR: {e}')

# Generic Bing query
titles_q_gen = ' OR '.join(f'"{v}"' for v in ['Product Manager', 'AI Product Manager', 'AI Engineer'])
generic_query = f'({titles_q_gen}) remote hiring 2026'
rss_url = 'https://www.bing.com/search?q=' + urllib.parse.quote(generic_query) + '&format=rss'
try:
    req = urllib.request.Request(rss_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
    resp = urllib.request.urlopen(req, timeout=15)
    xml_text = resp.read().decode('utf-8', errors='replace')
    root = ET.fromstring(xml_text)
    items = root.findall('.//item')
    generic_jobs = []
    for item in items:
        link_el = item.find('link')
        title_el = item.find('title')
        desc_el = item.find('description')
        if link_el is not None and title_el is not None:
            url = (link_el.text or '').strip()
            title = (title_el.text or '').strip()
            desc = (desc_el.text or '').strip() if desc_el is not None else ''
            if not url or not title:
                continue
            if not title_matches_variant(title):
                continue
            desc_clean = re.sub(r'<[^>]+>', ' ', desc).strip() if desc else ''
            desc_clean = html_mod.unescape(desc_clean)
            company = ''
            if ' — ' in title:
                company = title.split(' — ')[-1].strip()
            elif ' | ' in title:
                company = title.split(' | ')[-1].strip()
            salary = ''
            salary_match = re.search(r'\$[\d,.]+(?:\s*k)?', desc_clean)
            if salary_match:
                salary = salary_match.group(0)
            generic_jobs.append({
                'company': company, 'title': title, 'url': url,
                'location': 'Remote', 'salary': salary,
                'posted_at_raw': None, 'source_board': 'OpenWeb-Bing',
                'ats_platform': 'search-generic', 'snippet': desc_clean[:200] if desc_clean else ''
            })
    source_results['Bing-generic'] = f'{len(generic_jobs)} candidates from {len(items)} items'
    all_candidates.extend(generic_jobs)
    for j in generic_jobs:
        print(f'  [generic] {j["company"]} | {j["title"][:60]} | {j["url"][:80]}')
except Exception as e:
    source_results['Bing-generic'] = f'ERROR — {e}'
    print(f'  [generic] ERROR: {e}')

# ── Blocked sources ──
source_results['LinkedIn'] = 'BLOCKED — sign-in wall (per env config)'
source_results['Indeed'] = 'BLOCKED — sign-in wall / ATS wall (per env config)'
source_results['RemoteOK'] = 'BLOCKED — remoteok.com blocked (per env config, Remotive is the reliable alternative)'

# ── Dedup + filter ──
print('\n=== Dedup + Filter ===')
included = []
duplicates = []
non_matches = []

for p in all_candidates:
    fp = compute_fingerprint(p['company'], p['title'], p['location'])
    if p['url'] in existing_urls:
        duplicates.append((p, 'existing URL'))
        continue
    if fp in existing_fps:
        duplicates.append((p, f'fingerprint: {fp}'))
        continue
    if not title_matches_variant(p['title']):
        non_matches.append((p, 'title mismatch'))
        continue
    if p['salary']:
        min_sal = parse_salary_min(p['salary'])
        if min_sal is not None and min_sal < SALARY_FLOOR:
            non_matches.append((p, f'${int(min_sal)} below floor ${SALARY_FLOOR}'))
            continue
    included.append(p)

to_queue = included[:max(0, remaining)] if remaining > 0 else []
cap_skipped = len(included) - len(to_queue) if len(included) > remaining else 0

print(f'\n=== RESULTS ===')
print(f'Sources:')
for src, status in source_results.items():
    print(f'  {src}: {status}')
print(f'Total candidates: {len(all_candidates)}')
print(f'New (not dup): {len(included)}')
print(f'Duplicates: {len(duplicates)}')
print(f'Non-matches: {len(non_matches)}')
print(f'Cap: {daily_cap} | Today: {today_count} | Remaining: {remaining}')
print(f'Queued: {len(to_queue)}')
if cap_skipped:
    print(f'Cap skipped: {cap_skipped}')

if included and remaining <= 0:
    print('NEW POSTINGS FOUND but DAILY CAP (15) is FULL — cannot queue today.')
    print('New candidates:')
    for p in included:
        print(f'  {p["company"]} | {p["title"][:60]} | {p["url"][:80]}')

if not included and not duplicates and not non_matches and remaining <= 0:
    print('NOTHING NEW found from available sources.')
