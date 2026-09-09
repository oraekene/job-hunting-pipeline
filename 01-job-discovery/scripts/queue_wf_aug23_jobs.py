#!/usr/bin/env python3
"""Queue 2 live Wellfound PM jobs found in the Aug 23 raw HTML extraction
that were never inserted into the DB. Both are confirmed live (HTTP 200)
with full JSON-LD data."""
import re
import json
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

SKILL_ROOT = Path("C:/Users/rotim/AppData/Local/hermes/skills/job-hunting")
DB_PATH = SKILL_ROOT / "shared" / "applications.db"
SHARED = SKILL_ROOT / "shared"

DAILY_CAP = 15
now = datetime.now(timezone.utc)
now_iso = now.strftime('%Y-%m-%dT%H:%M:%SZ')

# ── Helpers (mirrors discovery_run_cron.py) ────────────────────────────────

def normalize_title(title):
    t = title.lower().strip()
    t = re.sub(r'\s*\(.*?\)\s*$', '', t)
    t = re.sub(r'\s*-\s*contract\s*$', '', t, flags=re.I)
    t = re.sub(r'\s*-?req\s*#?\d+\s*$', '', t, flags=re.I)
    t = re.sub(r'\s*-\s*#\d+\s*$', '', t)
    t = re.sub(r'\s+(ii|iii|iv|v|vi|vii|viii|ix|x)\s*$', '', t)
    t = re.sub(r'\s+\d+\s*$', '', t)
    t = re.sub(r'^senior\s+', '', t, flags=re.I)
    t = re.sub(r'^lead\s+', '', t, flags=re.I)
    t = re.sub(r'^staff\s+', '', t, flags=re.I)
    t = re.sub(r'^principal\s+', '', t, flags=re.I)
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
    TV_LOWER = [
        "product manager", "ai product manager", "ai engineer", "automation engineer",
        "associate product manager", "junior product manager", "workflow engineer",
        "product owner", "technical product manager", "growth product manager",
        "ai/ml product manager",
    ]
    TITLE_VARIANTS = [
        "Product Manager", "AI Product Manager", "AI Engineer", "Automation Engineer",
        "Associate Product Manager", "Junior Product Manager", "Workflow Engineer",
        "Product Owner", "Technical Product Manager", "Growth Product Manager",
        "AI/ML Product Manager",
    ]
    t = role_title.lower().strip()
    for v in TV_LOWER:
        if v in t:
            return TITLE_VARIANTS[TV_LOWER.index(v)]
    return None

# ── DB state ───────────────────────────────────────────────────────────────

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
print(f"Daily cap: {DAILY_CAP} | discovered today: {today_count} | remaining: {remaining_slots}")
print(f"DB known URLs: {len(all_known_urls)} | fingerprints: {len(db_fps)}")
print()

# ── New Wellfound PM jobs (from Aug 23 extraction, confirmed live Sep 9) ────

new_jobs = [
    {
        "company": "IR Labs",
        "role_title": "Principal Product Manager - Agentic SQA",
        "posting_url": "https://wellfound.com/jobs/4616099-principal-product-manager-agentic-sqa",
        "location": "Denver, Colorado, United States",
        "posted_at": "2026-08-21T06:11:53Z",
        "posted_at_raw": "2026-08-21T06:11:53Z",
        "salary_range": "$170k - $250k USD/year",
        "source": "wellfound",
        "discovery_source": "wellfound_pm_search_html_aug23_extraction",
    },
    {
        "company": "Stepful",
        "role_title": "Staff Product Manager, B2B",
        "posting_url": "https://wellfound.com/jobs/3542480-staff-product-manager-b2b",
        "location": "New York, United States",
        "posted_at": "2026-08-19T23:40:46Z",
        "posted_at_raw": "2026-08-19T23:40:46Z",
        "salary_range": "$200k - $250k USD/year",
        "source": "wellfound",
        "discovery_source": "wellfound_pm_search_html_aug23_extraction",
    },
]

# ── Validate, dedupe, filter, and insert ───────────────────────────────────

queued = 0
all_candidates = []

for j in new_jobs:
    url_lower = j["posting_url"].lower()
    fp = compute_fingerprint(j["company"], j["role_title"], j["location"])
    matched_v = title_matches_variant(j["role_title"])

    # Dedupe checks
    if url_lower in all_known_urls:
        print(f"  DUP(URL): {j['company']} | {j['role_title'][:50]} | {j['posting_url'][:80]}")
        continue
    if fp in db_fps:
        print(f"  DUP(FP): {j['company']} | {j['role_title'][:50]} | fp={fp}")
        continue

    # Title filter
    if not matched_v:
        print(f"  FILT: {j['company']} | {j['role_title'][:50]} — no title match")
        continue

    # Salary floor check (USD salaries only)
    salary = j.get("salary_range") or ""
    if salary:
        if re.search(r'[₦₹£€]', salary):
            # non-USD, skip floor
            pass
        else:
            matches = re.findall(r'\$\d[\d,.]*[kKmM]?', salary.replace(',', ''))
            below = False
            for m in matches:
                num_str = m.replace('$', '').replace(',', '').lower()
                if 'k' in num_str:
                    val = float(num_str.replace('k', '')) * 1000
                elif 'm' in num_str:
                    val = float(num_str.replace('m', '')) * 1_000_000
                else:
                    val = float(num_str)
                if val < 20_000:
                    val *= 12
                if val < 36000:
                    below = True
            if below:
                print(f"  FILT: {j['company']} | {j['role_title'][:50]} — salary below $36k floor")
                continue

    # Daily cap check
    if remaining_slots <= 0:
        print(f"  CAP: {j['company']} | {j['role_title'][:50]} — no remaining slots")
        continue

    # Determine priority
    posted_dt = datetime.strptime(j["posted_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    is_recent = (now - posted_dt).total_seconds() < 24 * 3600
    priority_flag = 'high' if is_recent else 'normal'

    # Insert
    conn2 = sqlite3.connect(str(DB_PATH))
    cur2 = conn2.cursor()
    try:
        cur2.execute("""
            INSERT INTO applications (
                posting_url, company, role_title, source_board, ats_platform,
                posted_at, posted_at_raw, discovered_at,
                status, posting_fingerprint, priority
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            j["posting_url"], j["company"], j["role_title"], j["source"],
            'wellfound', j["posted_at"], j["posted_at_raw"],
            now_iso, 'discovered', fp, priority_flag
        ))
        app_id = cur2.lastrowid
        cur2.execute("""
            INSERT INTO posting_sources (
                application_id, posting_url, source_name, discovered_by, is_canonical
            ) VALUES (?, ?, ?, ?, 1)
        """, (app_id, j["posting_url"], j["source"], 'job_1_boards'))
        conn2.commit()
        queued += 1
        remaining_slots -= 1
        all_known_urls.add(url_lower)
        db_fps.add(fp)
        all_candidates.append({
            'company': j["company"],
            'role_title': j["role_title"],
            'posting_url': j["posting_url"],
            'source': j["source"],
            'matched_variant': matched_v,
            'posted_at_raw': j["posted_at_raw"],
            'priority': priority_flag,
            'discovered_via': j["discovery_source"],
        })
        print(f"  QUEUED #{queued}: {j['company']:20s} | {j['role_title'][:45]} | posted {j['posted_at'][:10]} | priority={priority_flag} | salary={salary}")
        print(f"    fingerprint: {fp}")
    except sqlite3.IntegrityError as e:
        print(f"  DUP(integ): {j['company']} | {j['role_title'][:50]} — {e}")
    except Exception as e:
        print(f"  INSERT ERROR: {e}")
    finally:
        conn2.close()

print(f"\nTotal queued: {queued}")
print(f"Remaining daily slots: {remaining_slots}")
