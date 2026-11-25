#!/usr/bin/env python
"""One-run discovery processing: dedupe + cheap-filter + queue Wellfound postings.

Run discipline (from SKILL.md "Run discipline"):
  - Process each source at most once; on a block, note it and continue.
  - No retries, no workarounds (proxy tricks, headless bypasses, captcha hacks).
  - If every source is blocked/unreachable, report in one line and stop.
"""
import sqlite3, json, os, re
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'shared', 'applications.db')

# --- Wellfound postings (verified JSON-LD data from this run) ---
CANDIDATES = [
    {
        "company": "Oklo",
        "role_title": "Product Manager - Reactors",
        "posting_url": "https://wellfound.com/jobs/4735289-product-manager-reactors",
        "posted_at": "2026-09-18T20:16:13Z",
        "posted_at_raw": "2026-09-18T20:16:13Z",
        "posted_at_method": "json_ld_dateposted",
        "salary_disclosed": 1,
        "salary_range": "$140000-200000 USD YEAR",
        "currency": "USD",
        "salary_min": 140000, "salary_max": 200000, "salary_period": "YEAR",
        "remote_type": "onsite",
        "seniority": "mid",
        "industry": "Clean Energy, Nuclear",
        "location_raw": "Sunnyvale, California, United States",
        "city": "sunnyvale", "region": "california", "country": "united states",
        "title_matched": "Product Manager",
        "borderline": False,
        "source": "wellfound",
        "source_type": "scrape_and_filter",
    },
    {
        "company": "Garner Health",
        "role_title": "Product Manager II",
        "posting_url": "https://wellfound.com/jobs/4735287-product-manager-ii",
        "posted_at": "2026-09-18T20:14:55Z",
        "posted_at_raw": "2026-09-18T20:14:55Z",
        "posted_at_method": "json_ld_dateposted",
        "salary_disclosed": 1,
        "salary_range": "$143000-170000 USD YEAR",
        "currency": "USD",
        "salary_min": 143000, "salary_max": 170000, "salary_period": "YEAR",
        "remote_type": "hybrid",
        "seniority": "mid",
        "industry": "Healthcare, Digital Health",
        "location_raw": "New York, New York, United States",
        "city": "new york", "region": "new york", "country": "united states",
        "title_matched": "Product Manager",
        "borderline": False,
        "source": "wellfound",
        "source_type": "scrape_and_filter",
    },
    {
        "company": "Latitude",
        "role_title": "Technical Product Lead",
        "posting_url": "https://wellfound.com/jobs/4644462-technical-product-lead",
        "posted_at": "2026-09-18T00:00:00Z",
        "posted_at_raw": "2026-09-18T00:00:00Z",
        "posted_at_method": "json_ld_dateposted",
        "salary_disclosed": 1,
        "salary_range": "$175000-220000 USD YEAR",
        "currency": "USD",
        "salary_min": 175000, "salary_max": 220000, "salary_period": "YEAR",
        "remote_type": "hybrid",
        "seniority": "senior",
        "industry": "FinTech, Blockchain",
        "location_raw": "New York, San Francisco, United States",
        "city": "new york, san francisco", "region": "multiple", "country": "united states",
        "title_matched": "Technical Product Lead",
        "borderline": True,
        "source": "wellfound",
        "source_type": "scrape_and_filter",
    },
    {
        "company": "Tradeify.co",
        "role_title": "Junior Product Manager",
        "posting_url": "https://wellfound.com/jobs/4618116-junior-product-manager",
        "posted_at": "2026-09-17T23:57:30Z",
        "posted_at_raw": "2026-09-17T23:57:30Z",
        "posted_at_method": "json_ld_dateposted",
        "salary_disclosed": 1,
        "salary_range": "$60000-65000 USD YEAR",
        "currency": "USD",
        "salary_min": 60000, "salary_max": 65000, "salary_period": "YEAR",
        "remote_type": "remote",
        "seniority": "junior",
        "industry": "Finance Technology",
        "location_raw": "United States",
        "city": "remote", "region": "remote", "country": "united states",
        "title_matched": "Junior Product Manager",
        "borderline": False,
        "source": "wellfound",
        "source_type": "scrape_and_filter",
    },
    {
        "company": "Sardine",
        "role_title": "Head of Fraud Product",
        "posting_url": "https://wellfound.com/jobs/4735152-head-of-fraud-product",
        "posted_at": "2026-09-18T11:21:30Z",
        "posted_at_raw": "2026-09-18T11:21:30Z",
        "posted_at_method": "json_ld_dateposted",
        "salary_disclosed": 1,
        "salary_range": "$220000-275000 USD YEAR",
        "currency": "USD",
        "salary_min": 220000, "salary_max": 275000, "salary_period": "YEAR",
        "remote_type": "hybrid",
        "seniority": "senior",
        "industry": "Financial Services, Payments, Fraud Detection",
        "location_raw": "Austin, Texas, United States",
        "city": "austin", "region": "texas", "country": "united states",
        "title_matched": "Head of Fraud Product",
        "borderline": True,
        "source": "wellfound",
        "source_type": "scrape_and_filter",
    },
]

# --- Target profile filters (from shared/target-profile.yaml) ---
TITLE_VARIANTS = [
    "product manager", "ai product manager", "ai engineer", "automation engineer",
    "associate product manager", "junior product manager", "workflow engineer",
    "product owner", "technical product manager", "growth product manager",
    "ai/ml product manager",
]
# Root keywords for borderline detection: titles containing these roots
# but not an exact variant match are [BORDERLINE PASS] — they are PM/eng
# function roles whose exact title string is inferred rather than explicit.
ROOT_KEYWORDS = ["product manager", "product owner", "ai engineer",
                 "automation engineer", "workflow engineer",
                 "product lead", "product director", "head of product",
                 "head of .*product", "technical product"]
SALARY_FLOOR_USD = 36000
COMPANIES_EXCLUDE = set()
INDUSTRIES_EXCLUDE = set()


def normalize_title(title):
    """Per addendum_8: lowercase, strip punctuation, remove board decorations
    (trailing '(Remote)', '- Contract', req IDs, roman-numeral/level suffixes
    where taxonomy confirms same job zone)."""
    t = title.lower().strip()
    t = re.sub(r'\s*\([^)]*\)\s*$', '', t)
    t = re.sub(r'\s*-\s*(contract|freelance|internship)\s*$', '', t, flags=re.I)
    t = re.sub(r'\s+(i|ii|iii|iv|v|vi)\s*$', '', t)
    t = re.sub(r'[^\w\s]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def compute_fingerprint(company, title, country):
    """posting_fingerprint = lower(trim(company)) | normalised_title | lower(trim(location))"""
    return f"{company.lower().strip()}|{normalize_title(title)}|{country.strip()}"


def check_duplicate(db, candidate):
    """Check posting_fingerprint + posting_url against existing applications."""
    fp = compute_fingerprint(candidate["company"], candidate["role_title"], candidate["country"])
    row = db.execute(
        "SELECT id, company, role_title FROM applications WHERE posting_fingerprint = ?", (fp,)
    ).fetchone()
    if row:
        return True, fp, f"fingerprint match: existing id={row[0]} ({row[1]} | {row[2]})"
    row = db.execute("SELECT id FROM applications WHERE posting_url = ?", (candidate["posting_url"],)).fetchone()
    if row:
        return True, fp, f"url match: existing id={row[0]}"
    return False, fp, None


def cheap_filter(candidate):
    """Apply cheap filter against target profile.
    Returns (passes: bool, reason: str, is_borderline: bool)."""
    norm = normalize_title(candidate["role_title"])

    # 1) Exact substring match against a title_variant
    matched_variant = None
    for v in TITLE_VARIANTS:
        if v in norm or norm in v or v.startswith(norm) or norm.startswith(v):
            matched_variant = v
            break

    # 2) Borderline: root keyword present but no exact variant match
    is_borderline = False
    if not matched_variant:
        for kw in ROOT_KEYWORDS:
            if re.search(kw, norm):
                matched_variant = kw
                is_borderline = True
                break

    if not matched_variant:
        return False, f"title '{candidate['role_title']}' (normalized: '{norm}') does not match any title_variant or root keyword", False

    # 3) Salary floor (USD only; per memory, non-USD stays NULL → skip)
    if candidate.get("salary_min") and candidate.get("currency") == "USD":
        if candidate["salary_min"] < SALARY_FLOOR_USD:
            return False, (f"salary ${candidate['salary_min']}/{candidate['salary_period']} "
                           f"below ${SALARY_FLOOR_USD}/yr floor"), False

    # 4) Companies / industries exclude
    if candidate["company"].lower() in COMPANIES_EXCLUDE:
        return False, f"company '{candidate['company']}' in exclude list", False

    reason = f"matched='{matched_variant}'" + (" [BORDERLINE PASS]" if is_borderline else "")
    # Seniority note for borderline cases that are above the target band
    if candidate["seniority"] in ("senior", "staff", "lead") and candidate["seniority"] != "mid":
        reason += f" (seniority={candidate['seniority']} above mid band; overqualification gate will evaluate)"
    return True, reason, is_borderline


def check_daily_cap(db, cap):
    count = db.execute(
        "SELECT COUNT(*) FROM applications WHERE DATE(discovered_at) = DATE('now')"
    ).fetchone()[0]
    return cap - count


def main():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA journal_mode=WAL")
    db = conn.cursor()

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    daily_cap = 15
    slots_remaining = check_daily_cap(db, daily_cap)
    used_today = daily_cap - slots_remaining
    print(f"Daily cap: {daily_cap}, used today: {used_today}, remaining: {slots_remaining}")

    log = {
        "source": "01-job-discovery (cron)",
        "timestamp": now_iso,
        "discovery_mode": "open_web",
        "sources_attempted": ["linkedin-global", "indeed-global", "remote-ok",
                              "wellfound", "open-web-sweep"],
        "sources_blocked": [
            {"source": "linkedin-global", "type": "linkedin_search_url",
             "reason": "blocked in browser environment (bot-detection / LinkedIn ATS wall)"},
            {"source": "indeed-global", "type": "indeed_search_url",
             "reason": "blocked in browser environment (bot-detection / Indeed ATS wall)"},
            {"source": "remote-ok", "type": "scrape_and_filter",
             "reason": "blocked in browser environment (ATS wall)"},
            {"source": "open-web-sweep", "type": "open_web_search",
             "reason": "Bing bot-detection (403) blocks programmatic API; browser-based search returns irrelevant results (site: operator not applied correctly); no Adzuna aggregator API configured"},
        ],
        "sources_reachable": ["wellfound"],
        "candidates_found": len(CANDIDATES),
        "skipped_duplicates": 0,
        "skipped_non_match": 0,
        "skipped_cap": 0,
        "queued": 0,
        "details": [],
    }

    queued_count = 0
    for c in CANDIDATES:
        # --- Step 3: Dedup ---
        is_dup, fp, dup_reason = check_duplicate(db, c)
        if is_dup:
            log["skipped_duplicates"] += 1
            log["details"].append({
                "company": c["company"], "title": c["role_title"],
                "action": "skipped_duplicate", "reason": dup_reason,
            })
            print(f"SKIP (dup): {c['company']} | {c['role_title']} | {dup_reason}")
            continue

        # --- Step 4: Cheap filter ---
        passes, filter_reason, is_borderline = cheap_filter(c)
        if not passes:
            log["skipped_non_match"] += 1
            log["details"].append({
                "company": c["company"], "title": c["role_title"],
                "action": "skipped_non_match", "reason": filter_reason,
            })
            print(f"SKIP (filter): {c['company']} | {c['role_title']} | {filter_reason}")
            continue

        # --- Step 6: Daily cap ---
        if queued_count >= slots_remaining:
            log["skipped_cap"] += 1
            log["details"].append({
                "company": c["company"], "title": c["role_title"],
                "action": "skipped_cap", "reason": f"daily cap ({daily_cap}) reached",
            })
            print(f"SKIP (cap): {c['company']} | {c['role_title']}")
            continue

        # --- Step 5: Priority (posted < 24h = high) ---
        posted = datetime.fromisoformat(c["posted_at"].replace("Z", "+00:00"))
        age_hours = (datetime.now(timezone.utc) - posted).total_seconds() / 3600
        priority = "high" if age_hours < 24 else "normal"

        # --- Insert into applications ---
        cursor = db.execute("""
            INSERT INTO applications (
                posting_url, company, role_title, source_board, ats_platform,
                posted_at, posted_at_raw, discovered_at, industry, seniority,
                remote_type, salary_disclosed, salary_range, status,
                posting_fingerprint, priority, title_matched
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            c["posting_url"], c["company"], c["role_title"], c["source"], None,
            c["posted_at"], c["posted_at_raw"], now_iso, c["industry"], c["seniority"],
            c["remote_type"], c["salary_disclosed"], c["salary_range"], "discovered",
            fp, priority, c["title_matched"] if not is_borderline else f"{c['title_matched']} [BORDERLINE PASS]",
        ))
        app_id = cursor.lastrowid

        # --- Insert into posting_sources ---
        db.execute("""
            INSERT INTO posting_sources
                (application_id, posting_url, source_name, discovered_by, first_seen_at, is_canonical)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (app_id, c["posting_url"], c["source"], "job_1_boards", now_iso, 1))

        queued_count += 1
        log["queued"] += 1
        log["details"].append({
            "company": c["company"], "title": c["role_title"],
            "action": "queued", "priority": priority, "posted_at": c["posted_at"],
            "age_hours": round(age_hours, 1), "salary": c["salary_range"],
            "filter_reason": filter_reason, "fingerprint": fp,
            "borderline": is_borderline, "app_id": app_id,
        })
        print(f"QUEUED: {c['company']} | {c['role_title']} | priority={priority} "
              f"| age={age_hours:.1f}h | {c['salary_range']} | id={app_id}")

    conn.commit()

    # --- Step 7: Log cron execution ---
    finished_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    db.execute("""
        INSERT INTO cron_executions
            (job_label, job_name, started_at, finished_at, outcome, detail)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ("1", "discovery-scan", now_iso, finished_at, "ran",
          json.dumps({"queued": queued_count,
                      "sources_blocked": len(log["sources_blocked"]),
                      "sources_reachable": log["sources_reachable"]})))
    conn.commit()

    # Save run log to outbox
    outbox = os.path.join(os.path.dirname(__file__), "..", "..", "shared", ".outbox")
    os.makedirs(outbox, exist_ok=True)
    with open(os.path.join(outbox, "discovery-run-log.json"), "w") as f:
        json.dump(log, f, indent=2)

    conn.close()
    print(f"\n=== DONE: {queued_count} queued, {log['skipped_duplicates']} dups, "
          f"{log['skipped_non_match']} non-matches, {log['skipped_cap']} cap ===")
    print(json.dumps(log, indent=2))


if __name__ == "__main__":
    main()
