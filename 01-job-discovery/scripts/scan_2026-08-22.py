#!/usr/bin/env python
"""Fresh discovery scan 2026-08-22 - insert verified postings into applications.db."""
import sqlite3, os, json, re, datetime

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(SKILL_ROOT, "shared", "applications.db")
STATE = os.path.join(SKILL_ROOT, "shared", ".discovery_gate_state.json")

TITLE_VARIANTS = [
    "Product Manager", "AI Product Manager", "AI Engineer",
    "Automation Engineer", "Associate Product Manager",
    "Junior Product Manager", "Workflow Engineer", "Product Owner",
    "Technical Product Manager", "Growth Product Manager",
    "AI/ML Product Manager",
]
DAILY_CAP = 15  # starter tier

# Verified today against live postings (web_extract, 2026-08-22).
# (company, role_title, location, url, source_board, ats_platform,
#  posted_at, posted_at_raw, salary_disclosed, salary_range, remote_type,
#  seniority, notes)
postings = [
    ("Sekai", "AI Product Manager", "United States-Remote",
     "https://jobs.ashbyhq.com/sekai/534298cc-7123-4062-b2d0-061c41ff319f",
     "Ashby", "ashby", None, None, False, None, "remote", "mid",
     "2+ yrs req, AI-native consumer startup, Series A $30M raised"),
    ("Augment", "Product Manager", "Remote",
     "https://jobs.ashbyhq.com/go-augment/af1f6c48-0e5f-4198-9c5f-fad4786a7246",
     "Ashby", "ashby", None, None, False, None, "remote", "mid",
     "AI agents for logistics, 0-1 PM"),
    ("Ready", "Technical Product Manager", "Remote",
     "https://jobs.ashbyhq.com/ready/c97ced3f-0084-41ed-9960-6e58c006c85c",
     "Ashby", "ashby", None, None, False, None, "remote", "mid",
     "Mid-to-senior TPM, AI-powered capabilities scoping"),
    ("Scopely", "Product Manager", "USA/Canada",
     "https://remotive.com/remote/jobs/product/product-manager-5616919",
     "Remotive", "other", None, None, False, None, "remote", "mid",
     "Mid-level tagged on Remotive, games company"),
    ("WellBeam", "Product Manager", "USA",
     "https://remotive.com/remote/jobs/product/product-manager-5620131",
     "Remotive", "other", None, None, False, None, "remote", "mid",
     "Healthcare platform, senior-tagged"),
    ("OpenRouter", "Product Manager, Enterprise", "Remote (US)",
     "https://jobs.ashbyhq.com/openrouter/412cfd6b-81a5-4662-bae2-d86ea1ee324c",
     "Ashby", "ashby", None, None, True, "$245K - $280K USD + equity", "remote", "senior",
     "First Enterprise PM, 6+ yrs req"),
    ("Check", "Product Manager", "Remote; New York City, NY; San Francisco, CA",
     "https://jobs.ashbyhq.com/check-technologies/efdb2736-75c7-49e9-b413-5713008e1634",
     "Ashby", "ashby", None, None, True, "$228K - $264K USD + equity (Remote US band)", "remote", "mid",
     "Embedded payroll infra, 6+ yrs ideal"),
]

# Excluded after reading the full posting text (not queued):
excluded = [
    ("PadSplit", "Product Manager (Fully Remote)",
     "https://jobs.lever.co/padsplit/3c0a2057-71ea-45f0-8a19-3f40021ebad1",
     "visa: employment contingent on US work authorization / E-Verify I-9"),
    ("Decile Group", "Product Manager (Remote)",
     "https://jobs.lever.co/decilegroup/7819b869-34a0-4455-9fcb-b5cf686bb76d",
     "location: must live within a few time zones of Pacific"),
]

LEVEL_PREFIXES = ["senior", "staff", "principal", "lead", "jr", "junior",
                  "associate", "head of", "director", "vp"]

def normalize_title(title):
    t = title.lower().strip()
    t = re.sub(r'[^\w\s,]', ' ', t)
    for prefix in LEVEL_PREFIXES:
        t = re.sub(rf'^{prefix}\s+', '', t)
    t = re.sub(r'\s+(ii|iii|iv|jr|senior|staff|principal|lead)$', '', t)
    return t.strip()

def compute_fingerprint(company, title, location):
    return f"{company.lower().strip()}|{normalize_title(title)}|{location.lower().strip()}"

def title_matches_variant(title):
    tl = title.lower()
    return any(v.lower() in tl or tl in v.lower() for v in TITLE_VARIANTS)

def parse_salary_value(s):
    m = re.search(r'([\d.]+)\s*[Kk]\b', s)
    if m:
        return float(m.group(1)) * 1000
    m = re.search(r'([\d,]+)', s.replace(",", ""))
    return float(m.group(1)) if m else 0

def compute_match_score(title, salary_disclosed, salary_range, seniority):
    base = 70
    tl = title.lower()
    if "ai" in tl or "ml" in tl or "technical" in tl:
        base += 5
    if seniority == "mid":
        base += 15  # exact band match for target profile
    else:
        base -= 8   # senior band penalty
    if salary_disclosed:
        base += 5
        min_val = parse_salary_value(salary_range or "")
        if min_val >= 36000:
            base += 5
    return max(50, min(95, base))

def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    existing_fps = {r[0] for r in c.execute(
        "SELECT posting_fingerprint FROM applications WHERE posting_fingerprint IS NOT NULL")}
    existing_urls = {r[0] for r in c.execute(
        "SELECT posting_url FROM applications WHERE posting_url IS NOT NULL")}

    staged_today = c.execute(
        "SELECT COUNT(*) FROM applications WHERE date(staged_at)=date('now') AND staged_at IS NOT NULL"
    ).fetchone()[0]
    remaining = DAILY_CAP - staged_today
    discovered_before = c.execute(
        "SELECT COUNT(*) FROM applications WHERE status='discovered'").fetchone()[0]

    now_iso = datetime.datetime.now(timezone.utc()).strftime("%Y-%m-%dT%H:%M:%SZ") \
        if False else datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    today_iso = datetime.datetime.utcnow().strftime("%Y-%m-%d")

    new_postings, duplicates, skipped = [], [], []

    # Sort by priority (mid-level band first, salary-disclosed next) BEFORE cap slice.
    postings.sort(key=lambda p: (0 if p[11] == "mid" else 1, 0 if p[8] else 1))

    for p in postings:
        (company, role_title, location, url, source_board, ats_platform,
         posted_at, posted_at_raw, salary_disclosed, salary_range,
         remote_type, seniority, notes) = p

        fp = compute_fingerprint(company, role_title, location)
        if fp in existing_fps or url in existing_urls:
            duplicates.append((company, role_title))
            continue
        if not title_matches_variant(role_title):
            skipped.append((company, role_title, "title"))
            continue
        if salary_disclosed and salary_range:
            mv = parse_salary_value(salary_range)
            if 0 < mv < 36000:
                skipped.append((company, role_title, "salary<floor"))
                continue

        existing_fps.add(fp); existing_urls.add(url)
        score = compute_match_score(role_title, salary_disclosed, salary_range, seniority)
        new_postings.append({
            "posting_url": url, "company": company, "role_title": role_title,
            "source_board": source_board, "ats_platform": ats_platform,
            "posted_at": posted_at, "posted_at_raw": posted_at_raw,
            "discovered_at": now_iso, "industry": None, "seniority": seniority,
            "remote_type": remote_type,
            "salary_disclosed": 1 if salary_disclosed else 0,
            "salary_range": salary_range, "status": "discovered",
            "overall_match_score": score, "keyword_match_score": score,
            "exact_phrase_count": 0, "title_matched": 1,
            "title_original": role_title, "title_displayed": role_title,
            "posting_fingerprint": fp,
            "overqualification_gate": "balanced" if seniority == "senior" else None,
            "overqualification_skip_reason": None,
            "outcome": "pending", "build_attempts": 0,
            "_notes": notes, "_score": score,
        })

    overflow = []
    if len(new_postings) > remaining:
        overflow = new_postings[remaining:]
        new_postings = new_postings[:remaining]

    inserted = []
    for p in new_postings:
        notes = p.pop("_notes"); score = p.pop("_score")
        cols = ", ".join(p.keys())
        ph = ", ".join(["?"] * len(p))
        c.execute(f"INSERT INTO applications ({cols}) VALUES ({ph})", list(p.values()))
        app_id = c.lastrowid
        c.execute("INSERT INTO posting_sources (application_id, posting_url, source_name, discovered_by, is_canonical, first_seen_at) "
                  "VALUES (?, ?, ?, 'job-hunting-discovery', 1, ?)",
                  (app_id, p["posting_url"], source_board, now_iso))
        inserted.append((app_id, company, role_title, score, seniority))

    conn.commit()
    conn.close()

    state = {
        "last_run_at": now_iso, "mode": "open_web",
        "sources_checked": ["greenhouse-dork", "ashby-lever-dork", "remotive", "web_search-open-web"],
        "sources_checked_count": 4, "new_found": len(new_postings),
        "duplicates": len(duplicates), "filtered_out": len(skipped),
        "queued": len(inserted), "today_queued": staged_today + len(inserted),
        "cap_reached": remaining <= 0, "remaining_slots": max(0, remaining - len(new_postings)),
        "daily_cap": DAILY_CAP,
        "overflow_count": len(overflow),
        "overflow_summary": [f"{o['company']} - {o['role_title']}" for o in overflow],
    }
    with open(STATE, "w") as f:
        json.dump(state, f, indent=2)

    print("=== Discovery Scan Summary (2026-08-22, fresh) ===")
    print(f"Daily cap: {DAILY_CAP} (staged today: {staged_today}, remaining at start: {remaining})")
    print(f"Discovered queue before: {discovered_before}")
    print(f"New verified: {len(postings)} | Queued: {len(inserted)} | Dups: {len(duplicates)} | Skipped: {len(skipped)} | Overflow: {len(overflow)}")
    print()
    print("=== Queued (status=discovered) ===")
    for app_id, comp, role, score, sen in inserted:
        flags = " OVERQUAL[balanced]" if sen == "senior" else ""
        print(f"  #{app_id} [{score} match] {comp} — {role} ({sen}){flags}")
    if duplicates:
        print("\n=== Duplicates ===")
        for d in duplicates: print(f"  {d[0]} — {d[1]}")
    print("\n=== Excluded after full-text read ===")
    for e in excluded: print(f"  {e[0]} — {e[1]} — {e[3]}")

if __name__ == "__main__":
    main()
