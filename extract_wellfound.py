#!/usr/bin/env python3
"""Extract PM-matching jobs from Wellfound HTML file."""
import re, html as html_mod, sqlite3
from datetime import datetime, timezone, timedelta

TITLE_VARIANTS = [
    "product manager", "ai product manager", "ai engineer",
    "automation engineer", "associate product manager",
    "junior product manager", "workflow engineer", "product owner",
    "technical product manager", "growth product manager",
    "ai/ml product manager"
]
SALARY_FLOOR_USD_YEAR = 36000

with open("wellfound_pm_search.html", "r", encoding="utf-8") as f:
    content = f.read()

# Find all job links: href="/jobs/{id}-{slug}"
job_links = re.findall(r'href="(/jobs/\d+-[^"]+)"', content)
job_links = list(dict.fromkeys(job_links))  # dedupe preserving order

print(f"Total job links found: {len(job_links)}")

all_jobs = []
for link in job_links:
    # Find position in content
    pos = content.find(f'href="{link}"')
    if pos == -1:
        continue
    
    # Get context around this job link (500 chars before, 1500 chars after)
    start = max(0, pos - 100)
    end = min(len(content), pos + 1500)
    context = content[start:end]
    
    # Extract title: text between > and </a> after the href
    title_match = re.search(r'>(.*?)</a>', context, re.DOTALL)
    title = ""
    if title_match:
        title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
        title = html_mod.unescape(title)
    
    # Extract company: span before <!-- --> • -->
    # Pattern: <span>{company}<!-- --> • </span>
    company_match = re.search(r'<span>([^<]*?)<!-- --> • </span>', context)
    company = ""
    if company_match:
        company = company_match.group(1).strip()
        company = html_mod.unescape(company)
    
    # Extract meta: <span class="text-gray-700">{meta}</span>
    meta_match = re.search(r'text-gray-700">(.*?)</span>\s*</div>\s*<div', context, re.DOTALL)
    if not meta_match:
        # Try without the following div
        meta_match = re.search(r'text-gray-700">(.*?)</span>', context, re.DOTALL)
    
    location = ""
    salary = ""
    posted = ""
    
    if meta_match:
        meta_raw = re.sub(r'<[^>]+>', '', meta_match.group(1)).strip()
        meta_raw = html_mod.unescape(meta_raw)
        parts = [p.strip() for p in meta_raw.split('•')]
        
        for p in parts:
            pl = p.lower().strip().rstrip('%')
            if any(w in pl for w in ['yesterday', 'today', 'ago', 'hour', 'now', 'min', 'days ago', 'week', 'weeks ago', 'month', 'mon,', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']):
                posted = p
            elif '$' in p or 'k' in pl or 'usd' in pl or '£' in p or '€' in p or '₹' in p:
                salary = p
            elif pl and len(p) > 2:
                location = p
    
    if title and company:
        all_jobs.append({
            'company': company,
            'title': title,
            'url': f'https://wellfound.com{link}',
            'location': location,
            'salary': salary,
            'posted_at_raw': posted,
        })

print(f"\n--- All jobs extracted ({len(all_jobs)}) ---")
for j in all_jobs:
    print(f"  {j['title'][:50]:50s} | {j['company'][:25]:25s} | loc={j['location'][:25]:25s} | sal={j['salary'][:20]:20s} | posted={j['posted_at_raw'][:15]}")

# --- Cheap filter: title match ---
pm_jobs = []
for j in all_jobs:
    title_lower = j['title'].lower()
    matched_variant = None
    for variant in TITLE_VARIANTS:
        if variant in title_lower:
            matched_variant = variant
            break
    if matched_variant:
        j['matched_variant'] = matched_variant
        pm_jobs.append(j)

print(f"\n--- PM title matches ({len(pm_jobs)}) ---")
for j in pm_jobs:
    print(f"  {j['title'][:50]:50s} | {j['company'][:25]:25s} | variant={j['matched_variant']}")

# --- Normalize for fingerprint ---
def normalize_title(title):
    t = title.lower().strip()
    t = re.sub(r'\s*\(remote\)\s*', '', t)
    t = re.sub(r'\s*-\s*contract\s*', '', t)
    t = re.sub(r'\s*\b(iv|iii|ii|i|vi|vii|viii|ix|x)\b\s*$', '', t)
    t = re.sub(r'[^\w\s]', '', t).strip()
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def normalize_location(loc):
    l = loc.lower().strip()
    l = re.sub(r'\s*\+\s*\d+\s*more\s*', '', l)
    l = re.sub(r'[^\w\s]', '', l).strip()
    l = re.sub(r'\s+', ' ', l).strip()
    return l

# --- Check against DB ---
conn = sqlite3.connect('shared/applications.db')
c = conn.cursor()
c.execute('SELECT posting_fingerprint FROM applications')
existing_fingerprints = set(row[0] for row in c.fetchall())
c.execute('SELECT posting_url FROM applications')
existing_urls = set(row[0] for row in c.fetchall())
c.execute('SELECT posting_url FROM posting_sources')
existing_source_urls = set(row[0] for row in c.fetchall())

print(f"\n--- Dedup check ---")
print(f"Existing fingerprints: {len(existing_fingerprints)}")
print(f"Existing URLs (applications + posting_sources): {len(existing_urls) + len(existing_source_urls)}")

new_jobs = []
for j in pm_jobs:
    fp_company = j['company'].lower().strip()
    fp_title = normalize_title(j['title'])
    fp_location = normalize_location(j['location'])
    fingerprint = f"{fp_company}|{fp_title}|{fp_location}"
    j['fingerprint'] = fingerprint
    
    if j['url'] in existing_urls or j['url'] in existing_source_urls:
        print(f"  DUP URL: {j['title'][:40]:40s} | {j['url']}")
        continue
    if fingerprint in existing_fingerprints:
        print(f"  DUP FP:  {j['title'][:40]:40s} | {fingerprint}")
        continue
    
    print(f"  NEW:     {j['title'][:40]:40s} | {j['company'][:25]:25s} | {fingerprint}")
    new_jobs.append(j)

# --- Salary floor check ---
print(f"\n--- Salary floor (${SALARY_FLOOR_USD_YEAR}/yr) ---")
qualifying = []
for j in new_jobs:
    sal_text = j['salary']
    nums = re.findall(r'\$(\d+)k', sal_text)
    if nums:
        min_k = int(nums[0])
        max_k = int(nums[-1]) if len(nums) > 1 else int(nums[0])
        min_sal = min_k * 1000
        max_sal = max_k * 1000
        if min_sal >= SALARY_FLOOR_USD_YEAR:
            print(f"  PASS:  {j['title'][:40]:40s} | ${min_sal/1000}k-${max_sal/1000}k")
            j['salary_min'] = min_sal
            j['salary_max'] = max_sal
            qualifying.append(j)
        else:
            print(f"  REJECT:{j['title'][:40]:40s} | ${min_sal/1000}k-${max_sal/1000}k below floor")
    else:
        print(f"  UNKNOWN SALARY (proceeding): {j['title'][:40]:40s}")
        qualifying.append(j)

# --- Posted date resolution ---
now = datetime.now(timezone.utc)
print(f"\n--- Posted date resolution (now={now.strftime('%Y-%m-%dT%H:%M:%SZ')}) ---")
for j in qualifying:
    posted_raw = j['posted_at_raw']
    posted_at = None
    priority = 'normal'
    
    pr = Posted_raw = posted_raw.lower()
    try:
        if 'yesterday' in pr:
            posted_at = (now - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
        elif '1 day ago' in pr:
            posted_at = (now - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
        elif m := re.match(r'^(\d+) days? ago$', pr):
            posted_at = (now - timedelta(days=int(m.group(1)))).strftime('%Y-%m-%dT%H:%M:%SZ')
        elif '1 week ago' in pr or 'a week' in pr:
            posted_at = (now - timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%SZ')
        elif '2 weeks ago' in pr:
            posted_at = (now - timedelta(weeks=2)).strftime('%Y-%m-%dT%H:%M:%SZ')
        else:
            posted_at = now.strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception:
        posted_at = now.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    # Check if under 24h
    if posted_at:
        try:
            posted_dt = datetime.strptime(posted_at, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
            age_hours = (now - posted_dt).total_seconds() / 3600
            if age_hours <= 24:
                priority = 'high'
        except:
            pass
    
    j['posted_at'] = posted_at
    j['priority'] = priority
    print(f"  {j['title'][:40]:40s} | posted_at={posted_at} | raw='{posted_raw}' | age~{(now-datetime.strptime(posted_at,'%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)).total_seconds()/3600:.0f}h | priority={priority}")

# --- Daily cap ---
daily_cap = 15
c.execute("""
    SELECT COUNT(*) FROM applications 
    WHERE date(discovered_at) = date('now') AND status IN ('discovered', 'staged', 'awaiting_approval')
""")
today_count = c.fetchone()[0]
remaining = daily_cap - today_count
print(f"\n--- Daily cap ---")
print(f"Today queued: {today_count}")
print(f"Daily cap: {daily_cap}")
print(f"Remaining: {remaining}")

# --- Queue ---
print(f"\n--- Queuing (max {remaining} of {len(qualifying)} qualifying) ---")
queued = 0
for j in qualifying:
    if queued >= remaining:
        print(f"  CAP REACHED: {j['title'][:40]:40s} | skipped")
        continue
    
    discovered_at = now.strftime('%Y-%m-%dT%H:%M:%SZ')
    c.execute("""
        INSERT INTO applications (
            posting_url, company, role_title, source_board, ats_platform,
            posted_at, posted_at_raw, discovered_at,
            status, posting_fingerprint, priority
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        j['url'], j['company'], j['title'], 'wellfound', 'wellfound',
        j['posted_at'], j['posted_at_raw'], discovered_at,
        'discovered', j['fingerprint'], j['priority']
    ))
    app_id = c.lastrowid
    c.execute("""
        INSERT INTO posting_sources (application_id, posting_url, source_name, discovered_by, is_canonical)
        VALUES (?, ?, ?, ?, ?)
    """, (app_id, j['url'], 'wellfound', 'job_1_boards', 1))
    queued += 1
    print(f"  QUEUED #{queued}: {j['title'][:40]:40s} | {j['company'][:25]:25s} | {j['url']}")

conn.commit()
conn.close()

print(f"\n=== SUMMARY ===")
print(f"Source: wellfound (scrape_and_filter)")
print(f"Jobs on page: {len(all_jobs)}")
print(f"PM title matches: {len(pm_jobs)}")
print(f"New (not dup): {len(new_jobs)}")
print(f"Passed cheap filter: {len(qualifying)}")
print(f"Queued: {queued}")
