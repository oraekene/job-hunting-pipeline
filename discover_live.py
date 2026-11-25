#!/usr/bin/env python3
"""Live discovery scan — checks blocked sources and runs open-web sweep."""
import json, re, html as html_mod
from datetime import datetime, timezone
import urllib.request, urllib.parse, xml.etree.ElementTree as ET

TITLE_VARIANTS = [
    "product manager", "ai product manager", "ai engineer",
    "automation engineer", "associate product manager", "junior product manager",
    "workflow engineer", "product owner", "technical product manager",
    "growth product manager", "ai/ml product manager"
]
SALARY_FLOOR = 36000

# ── DB fingerprints (pre-loaded at import time in real run) ──
import sqlite3
DB_PATH = r'C:\Users\rotim\AppData\Local\hermes\skills\job-hunting\shared/applications.db'
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute("SELECT posting_fingerprint FROM applications WHERE posting_fingerprint IS NOT NULL")
existing_fps = set(row[0] for row in c.fetchall())
c.execute("SELECT posting_url FROM applications WHERE posting_url IS NOT NULL")
existing_urls = set(row[0] for row in c.fetchall())
c.execute("SELECT posting_url FROM posting_sources WHERE posting_url IS NOT NULL")
for row in c.fetchall():
    existing_urls.add(row[0])
c.execute("SELECT COUNT(*) FROM applications WHERE date(discovered_at) = date('now') AND status IN ('discovered','building','staged','awaiting_approval')")
today_count = c.fetchone()[0]
conn.close()

daily_cap = 15
remaining = daily_cap - today_count

print(f"DB: {len(existing_fps)} fingerprints, {len(existing_urls)} URLs")
print(f"Cap: {daily_cap} | Today: {today_count} | Remaining: {remaining}")

now = datetime.now(timezone.utc)
all_candidates = []
source_results = {}

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
    return f"{company.lower().strip()}|{normalize_title(title)}|{normalize_location(location)}"

def title_matches_variant(title):
    tl = title.lower()
    return any(v in tl for v in TITLE_VARIANTS)

def parse_salary_min(s):
    if not s: return None
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

# ── Source 1: LinkedIn → BLOCKED ──
source_results['LinkedIn'] = 'BLOCKED — sign-in wall (per env config)'

# ── Source 2: Indeed → BLOCKED ──
source_results['Indeed'] = 'BLOCKED — sign-in wall (per env config)'

# ── Source 3: RemoteOK → BLOCKED ──
source_results['RemoteOK'] = 'BLOCKED — remoteok.com blocked (per env config)'

# ── Source 4: Wellfound → live browser attempt ──
# (handled separately — see browser result below)

# ── Source 5: Open-web sweep via Bing RSS ──
# Platforms: Greenhouse, Lever, Ashby, SmartRecruiters, iCIMS
platforms = [
    ('greenhouse', 'site:boards.greenhouse.io OR site:greenhouse.io'),
    ('lever', 'site:jobs.lever.co'),
    ('ashby', 'site:jobs.ashbyhq.com'),
    ('smartrecruiters', 'site:careers.smartrecruiters.com'),
    ('icims', 'site:careers.icims.com'),
]

search_titles = ['Product Manager', 'AI Product Manager', 'Technical Product Manager',
                 'Growth Product Manager', 'Associate Product Manager']

for plat_name, plat_dork in platforms:
    titles_q = ' OR '.join('"%s"' % v for v in search_titles)
    query = '%s (%s) remote' % (plat_dork, titles_q)
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
                # Only keep if title matches a variant OR has job keyword
                if not (title_matches_variant(title) or 'job' in title.lower() or 'hiring' in title.lower()):
                    continue

                desc_clean = re.sub(r'<[^>]+>', ' ', desc).strip() if desc else ''
                desc_clean = html_mod.unescape(desc_clean)

                # Extract company from title
                company = ''
                if ' — ' in title:
                    parts = title.split(' — ')
                    company = parts[-1].strip()
                elif ' | ' in title:
                    parts = title.split(' | ')
                    company = parts[-1].strip()

                # Extract salary from description
                salary = ''
                salary_match = re.search(r'\$[\d,.]+(?:\s*k)?', desc_clean)
                if salary_match:
                    salary = salary_match.group(0)

                # Extract location
                location = ''
                for kw in ['remote', 'hybrid', 'onsite', 'united states', 'san francisco',
                           'new york', 'austin', 'seattle', 'london', 'germany', 'canada']:
                    if kw in desc_clean.lower():
                        location = kw.title() if kw in ['remote','hybrid','onsite'] else desc_clean[:100]
                        break

                plat_jobs.append({
                    'company': company,
                    'title': title,
                    'url': url,
                    'location': location or 'Remote',
                    'salary': salary,
                    'posted_at_raw': None,
                    'source_board': 'OpenWeb',
                    'ats_platform': plat_name,
                    'snippet': desc_clean[:200] if desc_clean else '',
                })

        source_results['Bing-%s' % plat_name] = '%d candidates from %d items' % (len(plat_jobs), len(items))
        all_candidates.extend(plat_jobs)
        for j in plat_jobs:
            print("  [%s] %s | %s | %s" % (plat_name, j['company'], j['title'][:50], j['url'][:80]))
    except Exception as e:
        source_results['Bing-%s' % plat_name] = 'ERROR — %s' % e
        print("  [%s] ERROR: %s" % (plat_name, e))

# Generic query — all title variants
titles_q_gen = ' OR '.join('"%s"' % v for v in ['Product Manager', 'AI Product Manager', 'Technical Product Manager', 'Growth Product Manager', 'Associate Product Manager'])
generic_query = '(%s) remote hiring 2026' % titles_q_gen
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
                parts = title.split(' — ')
                company = parts[-1].strip()
            elif ' | ' in title:
                parts = title.split(' | ')
                company = parts[-1].strip()

            salary = ''
            salary_match = re.search(r'\$[\d,.]+(?:\s*k)?', desc_clean)
            if salary_match:
                salary = salary_match.group(0)

            generic_jobs.append({
                'company': company,
                'title': title,
                'url': url,
                'location': 'Remote',
                'salary': salary,
                'posted_at_raw': None,
                'source_board': 'OpenWeb',
                'ats_platform': 'search-generic',
                'snippet': desc_clean[:200] if desc_clean else '',
            })

    source_results['Bing-generic'] = '%d candidates from %d items' % (len(generic_jobs), len(items))
    all_candidates.extend(generic_jobs)
    for j in generic_jobs:
        print("  [generic] %s | %s | %s" % (j['company'], j['title'][:50], j['url'][:80]))
except Exception as e:
    source_results['Bing-generic'] = 'ERROR — %s' % e
    print("  [generic] ERROR: %s" % e)

# ── Dedup + filter ──
included = []
duplicates = []
non_matches = []

for p in all_candidates:
    fp = compute_fingerprint(p['company'], p['title'], p['location'])
    if p['url'] in existing_urls:
        duplicates.append((p, 'existing URL'))
        continue
    if fp in existing_fps:
        duplicates.append((p, 'fingerprint: %s' % fp))
        continue
    if not title_matches_variant(p['title']):
        non_matches.append((p, 'title mismatch'))
        continue
    # Salary filter
    if p['salary']:
        min_sal = parse_salary_min(p['salary'])
        if min_sal is not None and min_sal < SALARY_FLOOR:
            non_matches.append((p, '$%d below floor $%d' % (int(min_sal), SALARY_FLOOR)))
            continue
    included.append(p)

# Apply daily cap
to_queue = included[:max(0, remaining)] if remaining > 0 else []
cap_skipped = len(included) - len(to_queue) if len(included) > remaining else 0

print("\n=== PROCESSING RESULTS ===")
print("Total candidates: %d" % len(all_candidates))
print("New (not dup): %d" % len(included))
print("Duplicates: %d" % len(duplicates))
print("Non-matches: %d" % len(non_matches))
print("Remaining slots: %d" % remaining)
print("To queue: %d" % len(to_queue))
if cap_skipped:
    print("Cap skipped: %d" % cap_skipped)

# Save all candidates with dedup/filter info
digest = {
    'run_at': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
    'sources': source_results,
    'total_candidates': len(all_candidates),
    'new_found': len(included),
    'duplicates': len(duplicates),
    'non_matches': len(non_matches),
    'queued': len(to_queue),
    'cap_skipped': cap_skipped,
    'daily_cap': daily_cap,
    'today_count': today_count,
    'remaining_slots': remaining - len(to_queue),
    'candidates': [{
        'company': p['company'], 'title': p['title'], 'url': p['url'],
        'location': p['location'], 'salary': p['salary'], 'ats_platform': p['ats_platform'],
        'snippet': p.get('snippet', '')
    } for p in included],
    'duplicate_jobs': [{'company': p['company'], 'title': p['title'], 'url': p['url'], 'reason': r} for p, r in duplicates],
    'non_match_jobs': [{'company': p['company'], 'title': p['title'], 'url': p['url'], 'reason': r} for p, r in non_matches],
}

with open('openweb_candidates.json', 'w') as f:
    json.dump(digest, f, indent=2)
print("\nSaved to openweb_candidates.json")
print("\n=== SOURCE RESULTS ===")
for src, status in source_results.items():
    print("  %s: %s" % (src, status))
