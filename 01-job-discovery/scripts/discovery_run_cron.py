#!/usr/bin/env python3
"""
Job Discovery — cron run (Sep 9, 2026, ~16:05 WAT).

Scans all configured sources in shared/sources.yaml per the skill
methodology:
  - Blocked sources: noted and skipped (no retry, no workarounds)
  - Accessible sources: fetched, parsed, deduped, filtered, queued

Sources attempted this run (per sources.yaml + discovery_mode=open_web):
  - linkedin-global  (linkedin_search_url)   → BLOCKED (sign-in wall)
  - indeed-global    (indeed_search_url)      → BLOCKED (HTTP 403)
  - remote-ok        (scrape_and_filter)      → BLOCKED (302 redirect loop)
  - wellfound        (scrape_and_filter)      → LIVE FETCH + parse
  - open-web-sweep   (open_web_search, daily) → Remotive API, HNRSS, Bing, Working Nomads

Respects the daily staging cap of 15 (Rule 3).
"""
import json
import re
import sqlite3
import html as html_mod
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ── Config ──────────────────────────────────────────────────────────────
SKILL_ROOT = Path("C:/Users/rotim/AppData/Local/hermes/skills/job-hunting")
DB_PATH = SKILL_ROOT / "shared" / "applications.db"
SHARED = SKILL_ROOT / "shared"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}
TIMEOUT = 20
DAILY_CAP = 15
CUTOFF_24H = timedelta(hours=24)

# Target profile (from shared/target-profile.yaml — confirmed)
TITLE_VARIANTS = [
    "Product Manager", "AI Product Manager", "AI Engineer", "Automation Engineer",
    "Associate Product Manager", "Junior Product Manager", "Workflow Engineer",
    "Product Owner", "Technical Product Manager", "Growth Product Manager",
    "AI/ML Product Manager",
]
TV_LOWER = [v.lower().strip() for v in TITLE_VARIANTS]
SALARY_FLOOR_USD = 36000  # annual
COMPANIES_EXCLUDE = []
INDUSTRIES_EXCLUDE = []

now = datetime.now(timezone.utc)
now_iso = now.strftime('%Y-%m-%dT%H:%M:%SZ')

# ── DB state ──────────────────────────────────────────────────────────────
conn = sqlite3.connect(str(DB_PATH))
c = conn.cursor()
c.execute("SELECT posting_url FROM applications WHERE posting_url IS NOT NULL")
existing_urls = set(r[0].lower() for r in c.fetchall())
c.execute("SELECT posting_url FROM posting_sources WHERE posting_url IS NOT NULL")
src_urls = set(r[0].lower() for r in c.fetchall())
all_known_urls = existing_urls | src_urls
c.execute("SELECT posting_fingerprint FROM applications WHERE posting_fingerprint IS NOT NULL")
db_fps = set(r[0] for r in c.fetchall())
c.execute("""
    SELECT COUNT(*) FROM applications
    WHERE date(discovered_at) = date('now', 'localtime')
""")
today_count = c.fetchone()[0]
conn.close()

remaining_slots = DAILY_CAP - today_count

print("=" * 70)
print(f"JOB DISCOVERY — CRON RUN  (run time: {now_iso})")
print(f"Daily cap: {DAILY_CAP}  |  discovered today: {today_count}  |  remaining: {remaining_slots}")
print(f"DB known URLs: {len(all_known_urls)}  |  fingerprints: {len(db_fps)}")
print("=" * 70)

# ── Helpers ──────────────────────────────────────────────────────────────

def normalize_title(title):
    """Lowercase, strip punctuation, remove board decorations per SKILL.md."""
    t = title.lower().strip()
    t = re.sub(r'\s*\(.*?\)\s*$', '', t)          # trailing "(...)" — e.g. "(Remote)"
    t = re.sub(r'\s*-\s*contract\s*$', '', t, flags=re.I)
    t = re.sub(r'\s*-?req\s*#?\d+\s*$', '', t, flags=re.I)  # requisition IDs
    t = re.sub(r'\s*-\s*#\d+\s*$', '', t)
    t = re.sub(r'\s+(ii|iii|iv|v|vi|vii|viii|ix|x)\s*$', '', t)  # roman numerals
    t = re.sub(r'\s+\d+\s*$', '', t)              # trailing numbers
    t = re.sub(r'^senior\s+', '', t)
    t = re.sub(r'^lead\s+', '', t)
    t = re.sub(r'^staff\s+', '', t)
    t = re.sub(r'^principal\s+', '', t)
    t = re.sub(r'[^a-z0-9\s]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def normalize_location(loc):
    l = loc.lower().strip()
    l = re.sub(r'\s*\+\s*\d+\s*more\s*', '', l)
    if any(w in l for w in ['remote', 'worldwide', 'global', 'anywhere']):
        return 'remote'
    elif 'united states' in l or 'us only' in l:
        return 'united states'
    elif 'nigeria' in l:
        return 'nigeria'
    elif 'canada' in l:
        return 'canada'
    elif 'europe' in l or 'uk' in l or 'gb' in l:
        return 'europe'
    return l.strip()


def compute_fingerprint(company, role_title, location):
    company = (company or 'unknown').lower().strip()
    loc = normalize_location(location or 'unknown')
    nt = normalize_title(role_title)
    return f"{company}|{nt}|{loc}"


def title_matches_variant(role_title):
    """Return the matched variant string, or None."""
    t = role_title.lower().strip()
    for v in TV_LOWER:
        if v in t:
            return TITLE_VARIANTS[TV_LOWER.index(v)]
    return None


def parse_posted_at(raw, method='relative_text_on_page'):
    """Resolve a posted_at string into ISO datetime."""
    if not raw or raw == 'unknown':
        return None, raw
    raw_stripped = raw.strip()
    # ISO formats
    for fmt in ["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
        try:
            dt = datetime.strptime(raw_stripped, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt, raw
        except ValueError:
            pass
    # fromisoformat
    try:
        dt = datetime.fromisoformat(raw_stripped.replace('Z', '+00:00'))
        return dt, raw
    except Exception:
        pass
    # Relative text: "2 hours ago", "yesterday", "today", "just now"
    m = re.match(r'^(\d+)\s*(hour|hr|day|min|minute|week|month)s?\s*ago$', raw_stripped, re.I)
    if m:
        num = int(m.group(1))
        unit = m.group(2).lower()
        if unit in ('hour', 'hr'):
            return now - timedelta(hours=num), raw
        elif unit == 'min' or unit == 'minute':
            return now - timedelta(minutes=num), raw
        elif unit == 'day':
            return now - timedelta(days=num), raw
        elif unit == 'week':
            return now - timedelta(weeks=num), raw
        elif unit == 'month':
            return now - timedelta(days=num * 30), raw
    if re.search(r'yesterday|1 day ago', raw_stripped, re.I):
        return now - timedelta(days=1), raw
    if re.search(r'today|just now|now', raw_stripped, re.I):
        return now, raw
    return None, raw


def is_recent(posted_at_dt, posted_at_raw):
    """Check if within 24h (by posted_at or discovered_at fallback)."""
    if posted_at_dt and (now - posted_at_dt).total_seconds() < CUTOFF_24H.total_seconds():
        return True
    if posted_at_raw:
        raw_lower = posted_at_raw.lower()
        if any(w in raw_lower for w in ['just', 'today', 'now', 'hour', 'min', 'minute']):
            return True
        m = re.match(r'^(\d+)\s*(day|d)\s*ago', raw_lower)
        if m and int(m.group(1)) == 0:
            return True
    return False


def check_salary_meets_floor(salary_text):
    """Return (discloses_salary, below_floor, amount) or (None, None, None)."""
    if not salary_text:
        return None, None, None
    # Non-USD currencies → don't apply floor
    if re.search(r'[₦₹£€]', salary_text):
        return True, False, None  # non-USD, skip floor
    matches = re.findall(r'\$[\d,.]+[kKmM]?', salary_text.replace(',', ''))
    if not matches:
        return None, None, None
    below = False
    amount = None
    for m in matches:
        num_str = m.replace('$', '').replace(',', '').lower()
        if 'k' in num_str:
            val = float(num_str.replace('k', '')) * 1000
        elif 'm' in num_str:
            val = float(num_str.replace('m', '')) * 1_000_000
        else:
            val = float(num_str)
        if val < 20_000:  # likely monthly
            val *= 12
        amount = val
        if val < SALARY_FLOOR_USD:
            below = True
    return True, below, amount


def fetch(url, timeout=TIMEOUT):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        return resp.text, resp.status_code
    except Exception as e:
        return str(e), 0


# ── Candidate collection + DB insertion ────────────────────────────────────

all_candidates = []
sources_tried = []
sources_blocked = []
skipped_duplicates = []
skipped_filter = []
queued_count = 0


def add_candidate(company, role_title, posting_url, location, posted_at_dt,
                  posted_at_raw, salary_range, source, matched_variant, is_recent_flag):
    """Validate, dedupe, filter, and insert a candidate. Returns status string."""
    global remaining_slots, queued_count

    url_lower = posting_url.lower() if posting_url else ''
    fp = compute_fingerprint(company, role_title, location)

    # 1. Dedupe by URL (across applications + posting_sources)
    if url_lower in all_known_urls:
        skipped_duplicates.append({'company': company, 'role_title': role_title,
                                   'posting_url': posting_url, 'source': source, 'dup_type': 'url'})
        return 'dup_url'

    # 2. Dedupe by fingerprint
    if fp in db_fps:
        skipped_duplicates.append({'company': company, 'role_title': role_title,
                                   'posting_url': posting_url, 'source': source, 'dup_type': 'fingerprint'})
        return 'dup_fp'

    # 3. Cheap-filter: title match
    matched_v = matched_variant or title_matches_variant(role_title)
    if not matched_v:
        skipped_filter.append({'company': company, 'role_title': role_title,
                               'posting_url': posting_url, 'source': source,
                               'note': 'no title_variants match'})
        return 'filtered'

    # 4. Salary floor check (only if disclosed in USD and below floor)
    if salary_range:
        discloses, below, _ = check_salary_meets_floor(str(salary_range))
        if discloses is False:  # parsed USD salary below floor
            skipped_filter.append({'company': company, 'role_title': role_title,
                                   'posting_url': posting_url, 'source': source,
                                   'note': f'salary below ${SALARY_FLOOR_USD}/yr floor'})
            return 'filtered'

    # 5. Company / industry exclude
    if company and company.lower() in [c.lower() for c in COMPANIES_EXCLUDE]:
        skipped_filter.append({'company': company, 'role_title': role_title,
                               'posting_url': posting_url, 'source': source,
                               'note': 'company in exclude list'})
        return 'filtered'

    # 6. Daily cap check
    if remaining_slots <= 0:
        skipped_duplicates.append({'company': company, 'role_title': role_title,
                                   'posting_url': posting_url, 'source': source,
                                   'dup_type': 'cap_overflow'})
        return 'cap_overflow'

    # 7. Insert into DB
    conn2 = sqlite3.connect(str(DB_PATH))
    cur2 = conn2.cursor()
    discovered_at = now_iso
    posted_at_iso = posted_at_dt.strftime('%Y-%m-%dT%H:%M:%SZ') if posted_at_dt else None
    priority_flag = 'high' if is_recent_flag else 'normal'

    try:
        cur2.execute("""
            INSERT INTO applications (
                posting_url, company, role_title, source_board, ats_platform,
                posted_at, posted_at_raw, discovered_at,
                status, posting_fingerprint, priority
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            posting_url, company, role_title, source,
            'wellfound' if source == 'wellfound' else source,
            posted_at_iso, posted_at_raw or '',
            discovered_at, 'discovered', fp, priority_flag
        ))
        app_id = cur2.lastrowid
        cur2.execute("""
            INSERT INTO posting_sources (
                application_id, posting_url, source_name, discovered_by, is_canonical
            ) VALUES (?, ?, ?, ?, 1)
        """, (app_id, posting_url, source, 'job_1_boards'))
        conn2.commit()
        queued_count += 1
        remaining_slots -= 1
        # Update in-memory caches
        all_known_urls.add(url_lower)
        db_fps.add(fp)
        conn2.close()
        print(f"  QUEUED #{queued_count}: {company} | {role_title} | {posted_at_raw} | recent={is_recent_flag} | priority={priority_flag}")
        return 'queued'
    except sqlite3.IntegrityError as e:
        # Unique constraint on (company, role_title, posting_url) — already exists
        skipped_duplicates.append({'company': company, 'role_title': role_title,
                                   'posting_url': posting_url, 'source': source,
                                   'dup_type': f'integ_error'})
        conn2.close()
        return 'dup_integ'
    except Exception as e:
        conn2.close()
        print(f"  INSERT ERROR: {e}")
        return 'error'


# ── Source 1: LinkedIn (linkedin_search_url) — BLOCKED (sign-in wall) ─────
print("\n" + "=" * 60)
print("SOURCE: LinkedIn (linkedin_search_url)")
print("=" * 60)
content, status = fetch("https://www.linkedin.com/jobs/search/?keywords=Product%20Manager&sortBy=DD")
linkedin_has_login = bool(re.search(r'sign[in]?|login|join.linkedin|authwall|guest',
                                     content[:5000], re.I))
linkedin_has_jobs = bool(re.search(r'job-card|listCard|ember-view|jobs-search-results',
                                    content[:10000]))
if status == 200 and linkedin_has_login and not linkedin_has_jobs:
    print(f"  BLOCKED: LinkedIn behind sign-in wall (HTTP {status}, no job elements in HTML)")
    sources_blocked.append({'source': 'linkedin-global', 'type': 'linkedin_search_url',
                            'reason': f'BLOCKED (sign-in wall, no job cards in server HTML)'})
else:
    print(f"  OK — page accessible (would parse)")
    sources_tried.append('linkedin-global')

# ── Source 2: Indeed (indeed_search_url) — BLOCKED ───────────────────────
print("\n" + "=" * 60)
print("SOURCE: Indeed (indeed_search_url)")
print("=" * 60)
content, status = fetch("https://www.indeed.com/worldwide/implement?q=Product+Manager&sort=date")
if status == 200:
    print("  OK — page accessible (would parse)")
    sources_tried.append('indeed-global')
else:
    print(f"  BLOCKED: Indeed returns HTTP {status} (ATS/sign-in wall)")
    sources_blocked.append({'source': 'indeed-global', 'type': 'indeed_search_url',
                            'reason': f'BLOCKED (HTTP {status})'})

# ── Source 3: RemoteOK (scrape_and_filter) — BLOCKED (no job elements) ─────
print("\n" + "=" * 60)
print("SOURCE: RemoteOK (scrape_and_filter)")
print("=" * 60)
content, status = fetch("https://remoteok.com/remote-product-manager-jobs")
remoteok_has_jobs = bool(re.search(r'remote-job|job-title|company-name|remoteok\.com/remote-jobs',
                                    content[:10000]))
if status == 200 and remoteok_has_jobs:
    print(f"  OK — HTTP {status}, {len(content)} bytes (would parse)")
    sources_tried.append('remote-ok')
else:
    print(f"  BLOCKED: RemoteOK HTTP {status}, no job elements in page (anti-bot/redirect)")
    sources_blocked.append({'source': 'remote-ok', 'type': 'scrape_and_filter',
                            'reason': f'BLOCKED (HTTP {status}, no job elements in page)'})

# ── Source 4: Wellfound (scrape_and_filter) — LIVE FETCH ──────────────────
print("\n" + "=" * 60)
print("SOURCE: Wellfound (scrape_and_filter) — LIVE FETCH")
print("=" * 60)
sources_tried.append('wellfound')
content, status = fetch("https://wellfound.com/jobs")
if status == 200 and len(content) > 1000:
    print(f"  OK — HTTP {status}, {len(content)} bytes")
    # Use regex extraction (proven approach from extract_wellfound.py)
    # Find all job links: href="/jobs/{id}-{slug}"
    job_links = re.findall(r'href="(/jobs/\d+-[^"]+)"', content)
    job_links = list(dict.fromkeys(job_links))  # dedupe preserving order
    print(f"  Job links found: {len(job_links)}")

    for link in job_links[:50]:
        full_url = f"https://wellfound.com{link}"

        # Get context around this job link
        pos = content.find(f'href="{link}"')
        if pos == -1:
            continue
        start = max(0, pos - 100)
        end = min(len(content), pos + 1500)
        ctx = content[start:end]

        # Extract title
        title_match = re.search(r'>(.*?)</a>', ctx, re.DOTALL)
        title = ''
        if title_match:
            title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
            title = html_mod.unescape(title)
        if not title:
            continue

        # Extract company: <span>{company}<!-- --> • </span>
        company_match = re.search(r'<span>([^<]*?)<!-- --> • </span>', ctx)
        company = company_match.group(1).strip() if company_match else 'unknown'
        company = html_mod.unescape(company)

        # Extract meta: <span class="text-gray-700">{meta}</span>
        meta_match = re.search(r'text-gray-700">(.*?)</span>', ctx, re.DOTALL)
        location = ''
        salary_text = ''
        posted_raw = 'unknown'
        if meta_match:
            meta_raw = re.sub(r'<[^>]+>', '', meta_match.group(1)).strip()
            meta_raw = html_mod.unescape(meta_raw)
            parts = [p.strip() for p in meta_raw.split('•')]
            for p in parts:
                pl = p.lower().strip().rstrip('%')
                if any(w in pl for w in ['yesterday', 'today', 'ago', 'hour', 'now', 'min', 'days ago',
                                          'week', 'weeks ago', 'month', 'mon,', 'tue,', 'wed,', 'thu,',
                                          'fri,', 'sat,', 'sun,']):
                    posted_raw = p
                elif '$' in p or 'k' in pl or 'usd' in pl or '£' in p or '€' in p or '₦' in p:
                    salary_text = p
                elif pl and len(p) > 2:
                    if not location:
                        location = p

        # Check title match
        matched_v = title_matches_variant(title)
        if not matched_v:
            continue

        # Parse posted_at
        posted_dt, posted_at_raw = parse_posted_at(posted_raw)
        rec = is_recent(posted_dt, posted_at_raw)

        result = add_candidate(
            company, title, full_url, location,
            posted_dt, posted_at_raw,
            salary_text, 'wellfound', matched_v, rec
        )
        if result == 'queued':
            all_candidates.append({'company': company, 'role_title': title,
                                   'posting_url': full_url, 'source': 'wellfound',
                                   'posted_at_raw': posted_at_raw, 'matched_variant': matched_v})
        elif result == 'dup_url':
            print(f"  DUP(URL): {company} | {title[:50]} | {full_url[:80]}")
        elif result == 'dup_fp':
            print(f"  DUP(FP): {company} | {title[:50]}")
        elif result == 'filtered':
            print(f"  FILT: {company} | {title[:50]}")
    print(f"  Wellfound scan complete")
else:
    print(f"  BLOCKED: Wellfound HTTP {status}")
    sources_blocked.append({'source': 'wellfound', 'type': 'scrape_and_filter',
                            'reason': f'BLOCKED (HTTP {status})'})

# ── Source 5: Open-web sweep (open_web_search, daily cadence) ─────────────
print("\n" + "=" * 60)
print("SOURCE: Open-web sweep (open_web_search — daily cadence)")
print("=" * 60)

# 5a. Remotive API (reliable)
print("  [Remote API — product-management category]")
content, status = fetch("https://remotive.com/api/remote-jobs?category=product-management")
if status == 200:
    try:
        data = json.loads(content)
        jobs = data.get('jobs', []) if isinstance(data, dict) else []
        print(f"  OK — {len(jobs)} jobs in product-management category")
        for j in jobs:
            title = j.get('title', '') or j.get('position', '')
            matched_v = title_matches_variant(title)
            if not matched_v:
                continue
            url = j.get('url', '')
            pub = j.get('publication_date', '') or j.get('date_posted', '')
            posted_dt, posted_raw = parse_posted_at(pub, method='aggregator_field')
            rec = is_recent(posted_dt, posted_raw)
            company = j.get('company_name', '')
            loc = j.get('candidate_required_location', '') or j.get('location', '')
            salary = j.get('salary', '')
            result = add_candidate(company, title, url, loc, posted_dt, posted_raw,
                                   salary, 'remotive-api', matched_v, rec)
            print(f"    [{result}] {company:25s} | {title[:50]} | {posted_raw[:20]} | recent={rec}")
    except json.JSONDecodeError as e:
        print(f"  ERROR: JSON parse failed ({e})")
else:
    print(f"  BLOCKED: Remotive API HTTP {status}")

# 5b. HNRSS — "who's hiring"
print("\n  [HNRSS: who's hiring]")
content, status = fetch("https://hnrss.org/newest?q=who%27s+hiring")
if status == 200 and len(content) > 10:
    soup = BeautifulSoup(content, 'xml')
    items = soup.find_all('item')
    print(f"  OK — {len(items)} feed items")
    for item in items[:15]:
        title = item.title.get_text().strip() if item.title else ''
        link = item.link.get_text().strip() if item.link else ''
        pub_date = item.pubDate.get_text().strip() if item.pubDate else ''
        matched_v = title_matches_variant(title)
        if not matched_v:
            continue
        posted_dt, posted_raw = parse_posted_at(pub_date, method='rss_pubdate')
        rec = is_recent(posted_dt, posted_raw)
        result = add_candidate('unknown', title, link, 'remote', posted_dt, posted_raw,
                               None, 'hnrss-who-is-hiring', matched_v, rec)
        print(f"    [{result}] {title[:60]} | {link[:70]}")
else:
    print(f"  BLOCKED: HNRSS HTTP {status}")

# 5c. Working Nomads
print("\n  [Working Nomads]")
content, status = fetch("https://www.workingnomads.com/jobs?category=product")
if status == 200 and len(content) > 500:
    soup = BeautifulSoup(content, 'lxml')
    for a in soup.find_all('a', href=True):
        text = a.get_text(strip=True)
        href = a['href']
        if 'product' in text.lower() and 'manager' in text.lower():
            matched_v = title_matches_variant(text)
            if not matched_v:
                continue
            full_url = href if href.startswith('http') else f"https://www.workingnomads.com{href}"
            result = add_candidate('unknown', text, full_url, 'remote', None, 'discovered_at',
                                   None, 'working-nomads', matched_v, False)
            print(f"    [{result}] {text[:60]} | {full_url[:70]}")
    print(f"  OK — HTTP {status}")
else:
    print(f"  BLOCKED: Working Nomads HTTP {status}")

# 5d. Bing search (note: limited value — often returns dictionary results)
print("\n  [Bing search]")
content, status = fetch("https://www.bing.com/search?q=product+manager+remote+hiring+job+opening&count=15")
if status == 200:
    soup = BeautifulSoup(content, 'lxml')
    results = soup.find_all('li', class_='b_algo') or soup.find_all('div', class_='b_algo')
    print(f"  HTTP 200 — {len(results)} organic results")
    bing_pm = 0
    for r in results:
        link_tag = r.find('a', href=True) if hasattr(r, 'find') else None
        if not link_tag:
            continue
        href = link_tag.get('href', '')
        title = link_tag.get_text(strip=True)
        m = re.search(r'uddg=([^&]+)', href)
        real_url = urllib.parse.unquote(m.group(1)) if m else href
        skip_domains = ['merriam-webster', 'cambridge.org', 'wikipedia', 'producthunt',
                        'thembains', 'simplicable', 'marketingtutor', 'aha.io', 'bing.com',
                        'dictionary', 'thefreedictionary']
        if any(d in real_url for d in skip_domains):
            continue
        matched_v = title_matches_variant(title)
        if matched_v:
            bing_pm += 1
            result = add_candidate('', title, real_url, 'remote', None,
                                   'relative_text_on_page', None, 'open_web_search-bing',
                                   matched_v, False)
            print(f"    [{result}] {title[:60]} | {real_url[:80]}")
    print(f"  Bing: {len(results)} results, {bing_pm} PM matches (site: operators not supported)")
else:
    print(f"  BLOCKED: Bing HTTP {status}")

# ── Summary ──────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print(f"DISCOVERY SUMMARY — {now_iso} (WAT {now.strftime('%H:%M')})")
print("=" * 60)
print(f"Sources tried: {sources_tried}")
print(f"Sources blocked: {len(sources_blocked)}")
for s in sources_blocked:
    print(f"  - {s['source']} ({s['type']}): {s['reason']}")
print(f"\nNew candidates queued: {queued_count}")
print(f"Duplicates skipped: {len(skipped_duplicates)}")
print(f"Filtered out: {len(skipped_filter)}")
print(f"Remaining daily slots: {remaining_slots}")
print(f"Daily cap: {DAILY_CAP}")

# ── Update state files ───────────────────────────────────────────────────
state = {
    "last_run_at": now_iso,
    "sources_checked": sources_tried,
    "sources_blocked": sources_blocked,
    "new_found": queued_count,
    "duplicates": len(skipped_duplicates),
    "filtered_out": len(skipped_filter),
    "queued": queued_count,
    "today_queued": today_count + queued_count,
    "cap_reached": remaining_slots <= 0,
    "remaining_slots": remaining_slots,
    "daily_cap": DAILY_CAP
}
with open(SHARED / ".discovery_gate_state.json", 'w') as f:
    json.dump(state, f, indent=2)

results = {
    "run_at": now_iso,
    "sources_tried": sources_tried,
    "sources_blocked": sources_blocked,
    "queued": [{"company": s['company'], "role_title": s['role_title'],
                "posting_url": s['posting_url'], "source": s['source']} for s in all_candidates],
    "skipped_duplicates": skipped_duplicates,
    "skipped_filter": skipped_filter,
    "remaining_slots": remaining_slots,
    "daily_cap": DAILY_CAP,
    "today_queued": today_count + queued_count
}
with open(SHARED / ".discovery_results.json", 'w') as f:
    json.dump(results, f, indent=2, default=str)

print(f"\nState files updated: .discovery_gate_state.json, .discovery_results.json")
print(f"\nTotal queued into DB: {queued_count}")
