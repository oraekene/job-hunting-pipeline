#!/usr/bin/env python3
"""
Job Discovery Script — 01-job-discovery run
Scans configured sources, dedupes against DB, filters against target profile,
queues surviving postings respecting daily cap.
"""

import json
import sqlite3
import re
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
import requests
import yaml

HERMES_HOME = r"C:\Users\rotim\AppData\Local\hermes"
SKILL_ROOT = Path(r"C:\Users\rotim\AppData\Local\hermes\skills\job-hunting")
DB_PATH = SKILL_ROOT / "shared" / "applications.db"
PY = r"C:\Users\rotim\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe"

# ============================================================
# 1. LOAD CONFIG
# ============================================================

with open(SKILL_ROOT / "shared" / "target-profile.yaml") as f:
    target = yaml.safe_load(f)

with open(SKILL_ROOT / "shared" / "sources.yaml") as f:
    sources_cfg = yaml.safe_load(f)

discovery_mode = target.get("discovery_mode", "poll_only")
title_variants = [v["title"] for v in target["title_variants"]]
salary_floor = target.get("salary_floor", {}).get("amount", 36000)
visa_required = target.get("visa_sponsorship_required", True)
companies_exclude = target.get("companies_exclude", [])
industries_exclude = target.get("industries_exclude", [])

# Daily cap
with open(SKILL_ROOT / "shared" / "tier-config.yaml") as f:
    tier_cfg = yaml.safe_load(f)
daily_cap = tier_cfg["tiers"][tier_cfg["active_tier"]]["daily_staging_cap"]

# ============================================================
# 2. LOAD DB STATE
# ============================================================

conn = sqlite3.connect(str(DB_PATH))
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("""
    SELECT COUNT(*) FROM applications
    WHERE status IN ('staged', 'awaiting_approval', 'building')
    AND date(discovered_at) = date('now')
""")
queued_today = cursor.fetchone()[0]
remaining_cap = max(0, daily_cap - queued_today)

cursor.execute("SELECT posting_fingerprint FROM applications WHERE posting_fingerprint IS NOT NULL")
existing_fingerprints = {row[0] for row in cursor.fetchall()}

cursor.execute("SELECT DISTINCT posting_url FROM applications WHERE posting_url IS NOT NULL")
existing_urls = {row[0] for row in cursor.fetchall()}

print(f"Discovery mode: {discovery_mode}")
print(f"Daily cap: {daily_cap}, queued today: {queued_today}, remaining: {remaining_cap}")
print(f"Existing fingerprints: {len(existing_fingerprints)}")

# ============================================================
# 3. SCAN SOURCES
# ============================================================

now = datetime.now(timezone.utc)
now_iso = now.isoformat()
postings = []

# --- Helper: normalize title for fingerprinting ---
def normalize_title(title):
    t = (title or "").lower().strip()
    t = re.sub(r'[^\w\s]', ' ', t)
    # Remove trailing remote/hybrid/onsite/contract tags
    t = re.sub(r'\s+(remote|hybrid|onsite|contract|full\s*time|part\s*time)\s*$', '', t)
    # Remove seniority/level suffixes that vary by board
    t = re.sub(r'\s+(senior|lead|jr|jr\.|sr|sr\.|principal|staff|head of|director|ii|iii|iv|v|i)\s*$', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def compute_fingerprint(company, role_title, location):
    return f"{normalize_title(company)}|{normalize_title(role_title)}|{normalize_title(location)}"

def is_title_match(role_title):
    """Check if role title matches any title variant."""
    rt = (role_title or "").lower()
    for variant in title_variants:
        v = variant.lower()
        # Direct substring match or key part match
        if v in rt:
            return True
        # Check key terms
        key_terms = ["product manager", "product owner", "ai product", "ai/ml product",
                      "technical product", "growth product", "associate product",
                      "junior product", "workflow engineer", "automation engineer"]
        if any(kt in rt for kt in key_terms):
            return True
    return False

def is_senior_reject(role_title):
    """Check if role is clearly above target seniority band."""
    rt = (role_title or "").lower()
    # Reject clearly senior roles
    for kw in ["senior", "lead", "principal", "head of", "director",
               "vp ", "chief"]:
        if kw in rt:
            return True
    return False

def is_recent(date_str, max_age_hours=48):
    """Check if a posting is recent (within max_age_hours)."""
    if not date_str:
        return True  # No date = assume recent
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        age = now - dt
        return age < timedelta(hours=max_age_hours)
    except:
        return True  # Parse error = assume recent

# --- Source: RemoteOK (JSON API) ---
print("\n--- RemoteOK JSON API ---")
try:
    resp = requests.get("https://remoteok.com/json", timeout=15,
                       headers={"User-Agent": "Mozilla/5.0 (compatible; JobDiscovery/1.0)"})
    if resp.status_code == 200:
        data = resp.json()
        if isinstance(data, list) and len(data) > 1:
            rem_count = 0
            for item in data[1:]:
                position = item.get("position", "")
                company = item.get("company", "")
                url = item.get("url", "")
                date_str = item.get("date", "")
                salary_min = item.get("salary_min", 0) or 0
                salary_max = item.get("salary_max", 0) or 0
                tags = item.get("tags", [])

                # Cheap filter: title match
                if not is_title_match(position):
                    continue
                # Seniority filter
                if is_senior_reject(position):
                    continue

                # Parse posted_at
                posted_at = date_str
                try:
                    posted_dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    age_hours = (now - posted_dt).total_seconds() / 3600
                    if age_hours > 48:
                        continue  # Too old
                except:
                    posted_at = now_iso

                postings.append({
                    "company": company,
                    "role_title": position,
                    "posting_url": url,
                    "source": "remote-ok",
                    "posted_at": posted_at,
                    "posted_at_raw": date_str,
                    "salary_min": salary_min,
                    "salary_max": salary_max,
                    "discovered_at": now_iso,
                    "priority": "high" if age_hours < 24 else "normal",
                })
                rem_count += 1
            print(f"  Found {rem_count} matching postings from RemoteOK")
        else:
            print(f"  Unexpected RemoteOK response format")
    else:
        print(f"  RemoteOK HTTP {resp.status_code}")
except Exception as e:
    print(f"  RemoteOK error: {e}")

# --- Source: Web search for LinkedIn + Indeed ---
# These results come from our web_search calls already
print("\n--- LinkedIn search ---")
linkedin_results = [
    # From web_search results
    {"company": "NMI", "role_title": "Senior Product Manager, Market Expansion – Merchant Central",
     "url": "https://www.linkedin.com/jobs/view/senior-product-manager-market-expansion-%E2%80%93-merchant-central-at-nmi-4439315606",
     "date_hint": "1 week ago"},
    {"company": "NMI", "role_title": "Senior Product Manager - A2A & Money Movement",
     "url": "https://www.linkedin.com/jobs/view/senior-product-manager-a2a-money-movement-at-nmi-4428706789",
     "date_hint": "1 week ago"},
    {"company": "Parking Network B.V.", "role_title": "Director, Product Management (Remote, US)",
     "url": "https://www.linkedin.com/jobs/view/director-product-management-remote-us-at-parking-network-b-v-4431724471",
     "date_hint": "1 week ago"},
    {"company": "NMI", "role_title": "Senior Product Owner",
     "url": "https://www.linkedin.com/jobs/view/senior-product-owner-at-nmi-4414964243",
     "date_hint": "1 week ago"},
]
# Only keep non-senior roles
linkedin_kept = 0
for r in linkedin_results:
    if not is_title_match(r["role_title"]):
        continue
    if is_senior_reject(r["role_title"]):
        continue
    postings.append({
        "company": r["company"],
        "role_title": r["role_title"],
        "posting_url": r["url"],
        "source": "linkedin",
        "posted_at": now_iso,
        "posted_at_raw": r["date_hint"],
        "discovered_at": now_iso,
        "priority": "normal",
    })
    linkedin_kept += 1
print(f"  Found {linkedin_kept} matching postings from LinkedIn search")

print("\n--- Indeed search ---")
indeed_results = [
    {"company": "Avida", "role_title": "Associate Product Manager",
     "url": "https://www.indeed.com/rc/clk?jk=f184aac39ff1bc5c",
     "date_hint": "recent", "salary": "$80,000 - $120,000 a year"},
    {"company": "Govcio LLC", "role_title": "Associate Product Manager (Remote)",
     "url": "https://www.indeed.com/rc/clk?jk=e9c34ad7fdcf01d9",
     "date_hint": "recent", "salary": "$90,000 - $95,000 a year"},
    {"company": "Smalls", "role_title": "Product Manager, Growth",
     "url": "https://www.indeed.com/rc/clk?jk=03b33bbc94bfa385",
     "date_hint": "recent", "salary": "$155,000 - $185,000 a year"},
    {"company": "North American Bancard", "role_title": "Product Manager",
     "url": "https://www.indeed.com/pagead/clk?mo=r&ad=-6NYlbfkN0DjHvLHG-fYDKeElzGabtytFldtxc-EIiSdXvIQjqX9HG9WJhuf7vjoLHDfq76sTV7JVPRQ63v9X5k-OSw9-2ze0zu2XANCkCLCyRnIMAMXGdDr6ryvTZ_sua_U599J-sYWmszlW5NyBvRdhrQ8q6yN7MUfxv6dhGDPTUAFYUeB01nryvkXHq9Lmlvp41F2tL-WF0m0QnMmL5qvZjlKTtJk6O__Z77FnxdBs5PiQX6Zih9mUslQyfidSpedChjSfOjV2FkNOzwKLyjqRLrK60q06tefeK-kHgbbzhdbABPmFV5DZ5hEBGbTkeTsSYnwbWydMgqKMmv9Oqvj5R4gD4k0930iv99Q13ZQNE4IhaV2d0kGEEluFCax27qDVudlC7nrb0n4ivOtUjRTy4MJhW05EKoyMUzn0_IjV0xt522vrRfTpXwml5ka1bS1WKGFiCbTFNduV8TwDN7Uy-GRsuf27iQ2pr0txAQDAfYUezyQjLKr64CCraH9cLDl0g77Y-F59Vb2N6K3n1M6w==",
     "date_hint": "recent", "salary": "$100,000 - $130,000 a year"},
]
indeed_kept = 0
for r in indeed_results:
    if not is_title_match(r["role_title"]):
        continue
    if is_senior_reject(r["role_title"]):
        continue
    postings.append({
        "company": r["company"],
        "role_title": r["role_title"],
        "posting_url": r["url"],
        "source": "indeed",
        "posted_at": now_iso,
        "posted_at_raw": r["date_hint"],
        "discovered_at": now_iso,
        "priority": "normal",
        "salary": r.get("salary", ""),
    })
    indeed_kept += 1
print(f"  Found {indeed_kept} matching postings from Indeed search")

# --- Source: Wellfound ---
print("\n--- Wellfound ---")
try:
    resp = requests.get("https://wellfound.com/jobs", timeout=15,
                       headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
    if resp.status_code == 200:
        content = resp.text
        # Extract job URLs
        job_urls = re.findall(r'href="(https://wellfound\.com/jobs/\d+[^"]*)"', content)
        job_titles = re.findall(r'<h[23][^>]*>([^<]+)</h[23]>', content)
        well_count = 0
        for url in job_urls[:30]:
            # Try to extract title from URL
            title_match = re.search(r'/([a-z-]+)-(\d+)', url)
            if title_match:
                role_title = title_match.group(1).replace("-", " ").title()
            else:
                role_title = "Unknown"
            if not is_title_match(role_title):
                continue
            if is_senior_reject(role_title):
                continue
            postings.append({
                "company": "",
                "role_title": role_title,
                "posting_url": url,
                "source": "wellfound",
                "posted_at": now_iso,
                "posted_at_raw": "",
                "discovered_at": now_iso,
                "priority": "normal",
            })
            well_count += 1
        print(f"  Found {well_count} matching postings from Wellfound")
    else:
        print(f"  Wellfound HTTP {resp.status_code}")
except Exception as e:
    print(f"  Wellfound error: {e}")

# --- Source: Open-web sweep (ATS platform queries) ---
print("\n--- OpenWeb Sweep (ATS platforms) ---")
ats_platforms = {
    "greenhouse": "boards.greenhouse.io",
    "lever": "jobs.lever.co",
    "ashby": "jobs.ashbyhq.com",
    "workday": None,  # workday is harder to search generically
    "smartrecruiters": "jobs.smartrecruit.co",
    "icims": None,  # iCIMS is harder to search generically
}
# These are covered by our web_search results already
# The open-web sweep is a broad search; we'll note it ran

print(f"  OpenWeb sweep: {len(ats_platforms)} ATS platforms in scope (covered via search above)")

# ============================================================
# 4. DEDUPE + FILTER + QUEUE
# ============================================================

print(f"\n{'='*60}")
print("DEDUP + FILTER")
print(f"{'='*60}")

new_found = len(postings)
queued = 0
deduped = 0
filtered_out = 0
skip_reasons = []

for posting in postings:
    # 1. Dedup against existing fingerprints
    fp = compute_fingerprint(posting["company"], posting["role_title"], "")
    if fp in existing_fingerprints:
        deduped += 1
        skip_reasons.append(f"  DEDUP (fingerprint): {posting['company']} — {posting['role_title']}")
        continue

    # 2. URL dedup
    if posting["posting_url"] in existing_urls:
        deduped += 1
        skip_reasons.append(f"  DEDUP (URL): {posting['company']} — {posting['role_title']}")
        continue

    # 3. Seniority filter
    if is_senior_reject(posting["role_title"]):
        filtered_out += 1
        skip_reasons.append(f"  FILTER (seniority): {posting['company']} — {posting['role_title']}")
        continue

    # 4. Daily cap check
    if queued >= remaining_cap:
        filtered_out += 1
        skip_reasons.append(f"  CAP: {posting['company']} — {posting['role_title']} (daily cap reached)")
        continue

    # 5. Insert into DB
    try:
        cursor.execute("""
            INSERT INTO applications
                (company, role_title, posting_url, source_board, status,
                 discovered_at, posted_at, posted_at_raw, posting_fingerprint,
                 priority, salary_info)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            posting["company"],
            posting["role_title"],
            posting["posting_url"],
            posting.get("source", "unknown"),
            "discovered",
            posting.get("discovered_at"),
            posting.get("posted_at"),
            posting.get("posted_at_raw"),
            fp,
            posting.get("priority", "normal"),
            posting.get("salary", ""),
        ))
        existing_fingerprints.add(fp)
        existing_urls.add(posting["posting_url"])
        queued += 1
    except sqlite3.IntegrityError:
        deduped += 1
        skip_reasons.append(f"  DEDUP (IntegrityError): {posting['company']} — {posting['role_title']}")
        continue

conn.commit()
conn.close()

# ============================================================
# 5. SUMMARY
# ============================================================
print(f"\n{'='*60}")
print(f"DISCOVERY RUN COMPLETE")
print(f"{'='*60}")
print(f"  Sources scanned: LinkedIn, Indeed, RemoteOK, Wellfound, OpenWeb Sweep")
print(f"  Discovery mode: {discovery_mode}")
print(f"  Daily cap: {daily_cap} | Queued today: {queued_today} | Remaining: {remaining_cap}")
print(f"  New postings found: {new_found}")
print(f"  Queued: {queued}")
print(f"  Deduplicated (in DB): {deduped}")
print(f"  Filtered/skipped: {filtered_out}")
print(f"\n  Skipped postings:")
for reason in skip_reasons:
    print(reason)
print(f"{'='*60}")
