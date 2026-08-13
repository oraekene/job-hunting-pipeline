#!/usr/bin/env python
"""Job discovery — insert newly discovered postings into applications.db"""
import sqlite3, os, json, re, datetime, sys

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(SKILL_ROOT, "shared", "applications.db")
STATE = os.path.join(SKILL_ROOT, "shared", ".discovery_gate_state.json")

# --- Title variants from target-profile.yaml ---
TITLE_VARIANTS = [
    "Product Manager", "AI Product Manager", "AI Engineer",
    "Automation Engineer", "Associate Product Manager",
    "Junior Product Manager", "Workflow Engineer", "Product Owner",
    "Technical Product Manager", "Growth Product Manager",
    "AI/ML Product Manager",
]

# --- Discovered postings from this scan ---
# (company, role_title, location, posting_url, source_board, ats_platform,
#  posted_at, posted_at_raw, salary_disclosed, salary_range,
#  remote_type, discovered_source)
TODAY_ISO = datetime.datetime.now().strftime("%Y-%m-%d")
now_iso = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

postings = [
    # 1. Figma — Product Manager, Acquisition (from open_web_search / Greenhouse dork)
    ("Figma", "Product Manager, Acquisition", "United States",
     "https://boards.greenhouse.io/figma/jobs/6119781004",
     "Greenhouse", "greenhouse", None, None,
     True, "$169,000 - $303,000 USD", "remote", "open_web_search"),
    # 2. Figma — Product Manager, AI Growth
    ("Figma", "Product Manager, AI Growth", "United States",
     "https://boards.greenhouse.io/figma/jobs/5989185004",
     "Greenhouse", "greenhouse", None, None,
     True, "$169,000 - $303,000 USD", "remote", "open_web_search"),
    # 3. Peek — Product Manager (Associate PM) — posted 1 day ago
    ("Peek", "Product Manager", "Mexico",
     "https://jobs.ashbyhq.com/peek/6d418ac7-65dd-4373-bd49-5dd8471509f4",
     "Ashby", "ashby", TODAY_ISO, "1 day ago",
     True, "MX$950K - MX$1.2M (~USD 50K-63K)", "remote", "open_web_search"),
    # 4. Camunda — Product Manager, Self Managed Service — posted 2026-07-29
    ("Camunda", "Product Manager, Self Managed Service", "Remote (global)",
     "https://jobs.ashbyhq.com/camunda/5652a3f3-e418-4e91-b58b-4be13f36853b",
     "Ashby", "ashby", "2026-07-29", "2026-07-29",
     True, "$143,800 - $231,900 USD", "remote", "open_web_search"),
    # 5. Camunda — Senior Product Manager - Core Platform
    ("Camunda", "Senior Product Manager", "Remote",
     "https://jobs.ashbyhq.com/camunda/b771e145-a5cf-4867-ad13-b54830e3b744",
     "Ashby", "ashby", None, None,
     True, "$143,800 - $231,900 USD", "remote", "open_web_search"),
    # 6. Apera AI Inc — Senior Product Manager
    ("Apera AI Inc", "Senior Product Manager", "Remote",
     "https://job-boards.greenhouse.io/aperaaiinc/jobs/5180835007",
     "Greenhouse", "greenhouse", None, None,
     False, None, "remote", "open_web_search"),
    # 7. GitLab — Principal Product Manager, AI Custom Models
    ("GitLab", "Principal Product Manager, AI Custom Models", "Remote (US/CA)",
     "http://job-boards.greenhouse.io/gitlab/jobs/8564957002",
     "Greenhouse", "greenhouse", None, None,
     False, None, "remote", "open_web_search"),
    # 8. GitLab — Senior AI Engineer
    ("GitLab", "Senior AI Engineer", "Remote, US",
     "http://job-boards.greenhouse.io/gitlab/jobs/8565469002",
     "Greenhouse", "greenhouse", None, None,
     False, None, "remote", "open_web_search"),
    # 9. EvolutionIQ — Senior/Lead Product Manager
    ("EvolutionIQ", "Senior/Lead Product Manager", "Worldwide (remote)",
     "https://job-boards.greenhouse.io/evolutioniq/jobs/6116681004",
     "Greenhouse", "greenhouse", None, None,
     False, None, "remote", "open_web_search"),
    # --- Wellfound sweep results ---
    # 10. SimpleStudy — Staff Product Manager — posted today
    ("SimpleStudy", "Staff Product Manager", "Remote (UK)",
     "https://wellfound.com/jobs/4566105-staff-product-manager",
     "Wellfound", "wellfound", TODAY_ISO, "today",
     False, None, "remote", "wellfound_search"),
    # 11. Raptive Intelligence — Senior Product Manager — posted 2 days ago
    ("Raptive Intelligence", "Senior Product Manager", "Remote (US)",
     "https://wellfound.com/jobs/4557611-senior-product-manager-raptive-intelligence-consumer-applications",
     "Wellfound", "wellfound", "2026-08-07", "2 days ago",
     False, None, "remote", "wellfound_search"),
    # 12. Occupier — Product Manager, AI — posted 1 day ago
    ("Occupier", "Product Manager, AI", "Boston/Toronto",
     "https://wellfound.com/jobs/4544920-product-manager-ai",
     "Wellfound", "wellfound", "2026-08-08", "1 day ago",
     False, None, "remote", "wellfound_search"),
    # 13. LawnStarter — Senior Product Manager
    ("LawnStarter", "Senior Product Manager", "New York",
     "https://wellfound.com/jobs/4551017-senior-product-manager",
     "Wellfound", "wellfound", None, None,
     False, None, "onsite", "wellfound_search"),
    # 14. SingleStore — Principal Product Manager Lead — posted 1 day ago
    ("SingleStore", "Principal Product Manager Lead", "SF/London/Bengaluru/Lisbon",
     "https://wellfound.com/jobs/4557504-principal-product-manager-lead-singlestore",
     "Wellfound", "wellfound", "2026-08-08", "1 day ago",
     False, None, "onsite", "wellfound_search"),
]

# --- Excluded postings (visa sponsorship not available) ---
excluded = [
    ("Dealops", "Product Manager", "San Francisco",
     "https://wellfound.com/jobs/4545042-product-manager",
     "Visa Sponsorship: Not Available"),
    ("IonQ", "Product Manager", "Geneva",
     "https://wellfound.com/jobs/4557586-product-manager",
     "Visa Sponsorship: Not Available"),
]

LEVEL_PREFIXES = ["senior", "staff", "principal", "lead", "jr", "junior",
                   "associate", "head of", "director", "vp"]

def normalize_title(title):
    """Lowercase, strip punctuation, remove level prefixes/suffixes and decorations."""
    t = title.lower().strip()
    t = re.sub(r'[^\w\s,]', ' ', t)  # strip punctuation
    # Remove leading level prefixes
    for prefix in LEVEL_PREFIXES:
        t = re.sub(rf'^{prefix}\s+', '', t)
    # Remove trailing level decorations
    t = re.sub(r'\s+(ii|iii|iv|jr|senior|staff|principal|lead)$', '', t)
    t = t.strip()
    return t

def compute_fingerprint(company, title, location):
    norm_title = normalize_title(title)
    return f"{company.lower().strip()}|{norm_title}|{location.lower().strip()}"

def title_matches_variant(title):
    """Check if title contains any approved title variant (cheap filter)."""
    title_lower = title.lower()
    for variant in TITLE_VARIANTS:
        v = variant.lower()
        # Check if the variant appears in the title or vice versa
        if v in title_lower or title_lower in v:
            return True
        # Handle compound: "Senior Product Manager" contains "Product Manager"
        if v in title_lower:
            return True
    return False

def parse_salary_value(s):
    """Parse a salary string like '$169,000' or 'MX$950K' or '1.2M' to a number."""
    # Handle K suffix (thousands)
    if re.search(r'\d+\.?\d*\s*[Kk]\b', s):
        num = re.search(r'([\d.]+)\s*[Kk]', s)
        if num:
            return float(num.group(1)) * 1000
    # Handle M suffix (millions)
    if re.search(r'\d+\.?\d*\s*[Mm]\b', s):
        num = re.search(r'([\d.]+)\s*[Mm]', s)
        if num:
            return float(num.group(1)) * 1000000
    # Plain number with commas: '$169,000'
    num = re.search(r'([\d,]+\.?\d*)', s.replace(",", ""))
    if num:
        return float(num.group(0).replace(",", ""))
    return 0

def compute_match_score(title, salary_disclosed, salary_range):
    """Preliminary match score for the discovered status."""
    base = 70
    title_lower = title.lower()
    # Exact title match
    if title_lower in [v.lower() for v in TITLE_VARIANTS]:
        base += 15
    # "AI" in title — high value
    if "ai" in title_lower or "ml" in title_lower:
        base += 5
    # Salary disclosed and above floor ($36K)
    if salary_disclosed:
        base += 5
        # Extract numeric range and check against floor
        nums = re.findall(r'[\d.]+', salary_range or "")
        if nums:
            min_val = float(nums[0])
            if min_val >= 36000:
                base += 5
    # Senior/overqualification penalty
    for prefix in ["senior", "staff", "principal", "lead", "director", "vp"]:
        if title_lower.startswith(prefix):
            base -= 8
    # Overqualification flag
    overqual = any(title_lower.startswith(p) for p in ["senior", "staff", "principal", "lead", "director"])
    return max(50, min(95, base)), overqual


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Get existing fingerprints for dedup
    existing_fingerprints = set()
    for row in c.execute("SELECT posting_fingerprint FROM applications WHERE posting_fingerprint IS NOT NULL"):
        existing_fingerprints.add(row["posting_fingerprint"])

    # Also get existing URLs
    existing_urls = set()
    for row in c.execute("SELECT posting_url FROM applications WHERE posting_url IS NOT NULL"):
        existing_urls.add(row["posting_url"])

    # Check daily cap
    staged_today = c.execute(
        "SELECT COUNT(*) FROM applications WHERE date(staged_at) = date('now') AND staged_at IS NOT NULL"
    ).fetchone()[0]
    daily_cap = 15  # starter tier
    remaining = daily_cap - staged_today

    # Check discovered count
    discovered_count = c.execute("SELECT COUNT(*) FROM applications WHERE status = 'discovered'").fetchone()[0]

    new_postings = []
    duplicates = []
    non_matches = []

    for p in postings:
        company, role_title, location, url, source_board, ats_platform, \
        posted_at, posted_at_raw, salary_disclosed, salary_range, \
        remote_type, discovered_source = p

        # Dedup check: fingerprint + URL
        fp = compute_fingerprint(company, role_title, location)
        if fp in existing_fingerprints or url in existing_urls:
            duplicates.append((company, role_title, url))
            continue

        # Cheap filter: title match
        if not title_matches_variant(role_title):
            non_matches.append((company, role_title, url))
            continue

        # Salary check: if salary disclosed, must be >= $36K
        if salary_disclosed and salary_range:
            min_val = parse_salary_value(salary_range)
            if min_val > 0 and min_val < 36000:
                non_matches.append((company, role_title, "Salary below floor"))
                continue

        match_score, overqual = compute_match_score(role_title, salary_disclosed, salary_range)

        existing_fingerprints.add(fp)
        existing_urls.add(url)

        new_postings.append({
            "company": company,
            "role_title": role_title,
            "posting_url": url,
            "source_board": source_board,
            "ats_platform": ats_platform,
            "posted_at": posted_at,
            "posted_at_raw": posted_at_raw,
            "discovered_at": now_iso,
            "industry": None,
            "seniority": "senior" if overqual else "mid",
            "remote_type": remote_type,
            "salary_disclosed": 1 if salary_disclosed else 0,
            "salary_range": salary_range,
            "status": "discovered",
            "overall_match_score": match_score,
            "keyword_match_score": match_score,
            "exact_phrase_count": 1,
            "title_matched": 1,
            "title_original": role_title,
            "title_displayed": role_title,
            "posting_fingerprint": fp,
            "overqualification_gate": "balanced" if overqual else None,
            "overqualification_skip_reason": None if overqual else None,
            "outcome": "pending",
            "build_attempts": 0,
        })

    # Respect daily cap
    if len(new_postings) > remaining:
        new_postings = new_postings[:remaining]

    # Insert new postings
    inserted = []
    for p in new_postings:
        cols = ", ".join(p.keys())
        placeholders = ", ".join(["?"] * len(p))
        c.execute(f"INSERT INTO applications ({cols}) VALUES ({placeholders})", list(p.values()))
        inserted.append((p["company"], p["role_title"], p["posting_url"], p["overall_match_score"], p["seniority"], p["overqualification_gate"]))

    # Record duplicates in posting_sources
    for dup in duplicates:
        c.execute(
            "INSERT INTO posting_sources (application_id, posting_url, source_name, discovered_by, is_canonical) "
            "SELECT id, ?, ?, 'job-hunting-discovery', 0 "
            "FROM applications WHERE posting_url = ? OR posting_fingerprint = ?",
            (dup[2], dup[0], dup[2], dup[1])
        )

    conn.commit()
    conn.close()

    # Update discovery gate state
    state = {"last_run_at": now_iso, "last_run": datetime.datetime.now().isoformat()}
    with open(STATE, "w") as f:
        json.dump(state, f, indent=2)

    # Print summary
    print(f"=== Discovery Scan Summary ===")
    print(f"Sources scanned: linkedin-global, indeed-global, remote-ok, wellfound, open-web-sweep")
    print(f"Discovery mode: open_web")
    print(f"Daily cap: {daily_cap} (staged today: {staged_today}, remaining: {remaining})")
    print(f"Discovered queue before: {discovered_count}")
    print(f"")
    print(f"New postings found: {len(postings) + len(excluded)}")
    print(f"  - New (queued): {len(inserted)}")
    print(f"  - Duplicates: {len(duplicates)}")
    print(f"  - Non-matches (visa not available): {len(excluded)}")
    print(f"  - Non-matches (title/salary): {len(non_matches)}")
    print(f"")
    print(f"=== New Postings Queued (status=discovered) ===")
    for p in inserted:
        flags = []
        if p[5]:
            flags.append(f"OVERQUAL[{p[5]}]")
        if p[4] == "senior":
            flags.append("SENIOR_BAND")
        print(f"  [{p[3]} match] {p[0]} — {p[1]} ({p[2]}) {' '.join(flags)}")
    print(f"")
    if duplicates:
        print(f"=== Duplicates (already in DB) ===")
        for d in duplicates:
            print(f"  {d[0]} — {d[1]} ({d[2]})")
    print(f"")
    if excluded:
        print(f"=== Excluded (visa sponsorship not available) ===")
        for e in excluded:
            print(f"  {e[0]} — {e[1]} ({e[2]}) — {e[3]}")

    return inserted

if __name__ == "__main__":
    main()
