#!/usr/bin/env python3
"""Quick check Wellfound live for PM job postings."""
import urllib.request, re, html as html_mod, json, sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

SKILL_ROOT = Path(r"C:\Users\rotim\AppData\Local\hermes\skills\job-hunting")
DB_PATH = SKILL_ROOT / "shared" / "applications.db"
SHARED = SKILL_ROOT / "shared"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml',
    'Accept-Language': 'en-US,en;q=0.9',
}

# Load DB state
conn = sqlite3.connect(str(DB_PATH))
c = conn.cursor()
c.execute("SELECT DISTINCT posting_url FROM applications WHERE posting_url IS NOT NULL")
all_known_urls = set(r[0].lower() for r in c.fetchall())
c.execute("SELECT DISTINCT posting_url FROM posting_sources WHERE posting_url IS NOT NULL")
for r in c.fetchall():
    all_known_urls.add(r[0].lower())
c.execute("SELECT DISTINCT posting_fingerprint FROM applications WHERE posting_fingerprint IS NOT NULL")
db_fps = set(r[0] for r in c.fetchall())
conn.close()

print(f"DB: {len(all_known_urls)} known URLs, {len(db_fps)} fingerprints")

TITLE_VARIANTS = [
    "Product Manager", "AI Product Manager", "AI Engineer", "Automation Engineer",
    "Associate Product Manager", "Junior Product Manager", "Workflow Engineer",
    "Product Owner", "Technical Product Manager", "Growth Product Manager",
    "AI/ML Product Manager",
]
TV_LOWER = [v.lower().strip() for v in TITLE_VARIANTS]

def title_matches_variant(role_title):
    t = role_title.lower().strip()
    for v in TV_LOWER:
        if v in t:
            return TITLE_VARIANTS[TV_LOWER.index(v)]
    return None

def normalize_title(title):
    import re as re_mod
    t = title.lower().strip()
    t = re_mod.sub(r'\s*\(.*?\)', '', t)
    t = re_mod.sub(r'\s*-\s*contract\s*$', '', t, flags=re_mod.I)
    t = re_mod.sub(r'\s*-?req\s*#?\d+\s*$', '', t)
    t = re_mod.sub(r'\s*\[\d+\]\s*$', '', t)
    t = re_mod.sub(r'\s+(ii|iii|iv|v|vi)\s*$', '', t)
    t = re_mod.sub(r'^senior\s+', '', t)
    t = re_mod.sub(r'^lead\s+', '', t)
    t = re_mod.sub(r'^staff\s+', '', t)
    t = re_mod.sub(r'^principal\s+', '', t)
    t = re_mod.sub(r'[^a-z0-9\s]', ' ', t)
    t = re_mod.sub(r'\s+', ' ', t).strip()
    return t

def normalize_location(loc):
    import re as re_mod
    l = loc.lower().strip()
    l = re_mod.sub(r'\s*\+\s*\d+\s*more\s*', '', l)
    if any(w in l for w in ['remote', 'worldwide', 'global', 'anywhere']):
        return 'remote'
    elif 'united states' in l or 'us only' in l:
        return 'united states'
    l = re_mod.sub(r'[^a-z0-9\s]', ' ', l)
    l = re_mod.sub(r'\s+', ' ', l).strip()
    return l

def compute_fingerprint(company, role_title, location):
    company = (company or 'unknown').lower().strip()
    loc = normalize_location(location or 'unknown')
    nt = normalize_title(role_title)
    return f"{company}|{nt}|{loc}"

def parse_posted_at(raw):
    if not raw or raw == 'unknown':
        return None, raw
    raw_stripped = raw.strip()
    for fmt in ["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
        try:
            dt = datetime.strptime(raw_stripped, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt, raw
        except ValueError:
            pass
    now = datetime.now(timezone.utc)
    m = re.match(r'^(\d+)\s*(hour|hr|day|min|minute|week|month)s?\s*ago$', raw_stripped, re.IGNORECASE)
    if m:
        num = int(m.group(1))
        unit = m.group(2).lower()
        if unit in ('hour', 'hr'): return now - timedelta(hours=num), raw
        elif unit in ('min', 'minute'): return now - timedelta(minutes=num), raw
        elif unit == 'day': return now - timedelta(days=num), raw
        elif unit == 'week': return now - timedelta(weeks=num), raw
        elif unit == 'month': return now - timedelta(days=num*30), raw
    if re.search(r'yesterday|1 day ago', raw_stripped, re.I):
        return now - timedelta(days=1), raw
    if re.search(r'today|just now|now', raw_stripped, re.I):
        return now, raw
    return None, raw

# ── Check Wellfound live ──
print("\n" + "=" * 60)
print("SOURCE: Wellfound (scrape_and_filter) — LIVE FETCH")
print("=" * 60)

# Try the product-manager filtered page
urls_to_try = [
    "https://wellfound.com/jobs",
    "https://wellfound.com/jobs/product-manager",
    "https://wellfound.com/jobs?role=Product%20Manager",
]

html_content = None
http_status = 0
for wf_url in urls_to_try:
    try:
        req = urllib.request.Request(wf_url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=20)
        html_content = resp.read().decode('utf-8', errors='replace')
        http_status = resp.status
        body_lower = html_content.lower()
        if 'captcha' in body_lower or 'challenge' in body_lower or len(html_content) < 2000:
            print(f"  {wf_url}: HTTP {http_status} — BLOCKED (anti-bot or too small)")
            html_content = None
            continue
        else:
            print(f"  {wf_url}: HTTP {http_status}, {len(html_content)} chars — OK")
            break
    except Exception as e:
        print(f"  {wf_url}: ERROR — {e}")

if html_content:
    # Find all job links
    job_links = re.findall(r'href="(/jobs/\d+-[^"]+)"', html_content)
    job_links = list(dict.fromkeys(job_links))
    print(f"\n  Job links found: {len(job_links)}")

    now = datetime.now(timezone.utc)
    candidates = []
    dups = []
    non_matches = []

    for link in job_links[:80]:
        full_url = f"https://wellfound.com{link}"
        url_lower = full_url.lower()
        if url_lower in all_known_urls:
            dups.append({'company': '?', 'title': link[:60], 'url': full_url, 'dup_type': 'url', 'reason': 'already in DB'})
            continue

        pos = html_content.find(f'href="{link}"')
        if pos == -1:
            continue
        start = max(0, pos - 200)
        end = min(len(html_content), pos + 2000)
        ctx = html_content[start:end]

        # Extract title
        title_match = re.search(r'>(.*?)</a>', ctx, re.DOTALL)
        title = ''
        if title_match:
            title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
            title = html_mod.unescape(title)
        if not title or len(title) < 3:
            continue

        # Extract company
        company_match = re.search(r'<span>([^<]*?)<!-- --> • </span>', ctx)
        company = company_match.group(1).strip() if company_match else 'unknown'
        company = html_mod.unescape(company)

        # Extract meta (location, salary, date)
        meta_match = re.search(r'text-gray-700">(.*?)</span>', ctx, re.DOTALL)
        location = ''
        salary_text = ''
        posted_raw = 'unknown'
        if meta_match:
            meta_raw = re.sub(r'<[^>]+>', '', meta_match.group(1)).strip()
            meta_raw = html_mod.unescape(meta_raw)
            parts = [p.strip() for p in meta_raw.split('•')]
            for p in parts:
                pl = p.lower().strip()
                if any(w in pl for w in ['yesterday', 'today', 'ago', 'hour', 'now', 'min', 'day', 'week', 'month', 'mon,', 'tue,', 'wed,', 'thu,', 'fri,', 'sat,', 'sun,']):
                    posted_raw = p
                elif '$' in p or 'usd' in pl or 'k' in pl or '£' in p or '€' in p or '₦' in p:
                    salary_text = p
                elif pl and len(p) > 2:
                    if not location:
                        location = p

        # Check title match
        matched_v = title_matches_variant(title)
        if not matched_v:
            non_matches.append({'company': company, 'title': title[:60], 'reason': 'no title match'})
            continue

        # Fingerprint dedup
        fp = compute_fingerprint(company, title, location)
        if fp in db_fps:
            dups.append({'company': company, 'title': title[:60], 'url': full_url, 'dup_type': 'fingerprint', 'reason': f'fp={fp}'})
            continue

        # Parse posted_at
        posted_dt, posted_at_raw = parse_posted_at(posted_raw)
        is_recent = False
        if posted_dt and (now - posted_dt).total_seconds() < 86400:
            is_recent = True
        elif posted_at_raw:
            raw_lower = posted_at_raw.lower()
            if any(w in raw_lower for w in ['just', 'today', 'now', 'hour', 'min', 'minute']):
                is_recent = True
            m2 = re.match(r'^(\d+)\s*(day|d)\s*ago', raw_lower)
            if m2 and int(m2.group(1)) == 0:
                is_recent = True

        candidates.append({
            'company': company,
            'role_title': title,
            'posting_url': full_url,
            'location': location,
            'posted_at': posted_dt.strftime('%Y-%m-%dT%H:%M:%SZ') if posted_dt else None,
            'posted_at_raw': posted_at_raw,
            'salary_range': salary_text,
            'source': 'wellfound',
            'matched_variant': matched_v,
            'is_recent': is_recent,
        })
        print(f"  CANDIDATE: {company} | {title[:50]} | recent={is_recent} | salary={salary_text} | loc={location}")

    print(f"\n  Wellfound scan: {len(candidates)} new candidates, {len(dups)} dups, {len(non_matches)} non-matches")
    # Save results
    result = {
        'run_at': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'source': 'wellfound',
        'candidates': candidates,
        'duplicates': dups,
        'non_matches': non_matches,
    }
    with open(SHARED / ".wellfound_live_check.json", 'w') as f:
        json.dump(result, f, indent=2, default=str)
    print(f"  Saved to shared/.wellfound_live_check.json")
else:
    print("  Wellfound BLOCKED — cannot fetch live page")
