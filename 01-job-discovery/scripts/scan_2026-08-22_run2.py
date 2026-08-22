#!/usr/bin/env python
"""Discovery scan run 2, 2026-08-22 (~15:00 UTC) - insert verified postings into applications.db.

All 8 postings verified live against their source pages this run (web_extract / API fetch).
Excluded during verification (NOT queued):
  - Conversica Senior PM (Lever)          -> 404, posting gone
  - Vendavo Senior PM Remote (Lever)      -> 404, posting gone
  - SupplyHouse TPM Platform (Greenhouse) -> must live in one of 16 listed US states
  - Acorns Senior PM Family (Ashby)       -> E-Verify / US work-authorization signal (visa blocker)
  - Clipboard Product Manager (YC)        -> "US citizen/visa only" (visa blocker)
  - Datadog Senior PM Agent Integrations  -> requires office 3 days/week (hybrid blocker)
  - Pencil Senior PM EMEA (Ashby)         -> Europe-labeled role
  - HubSpot Senior PM Events Data Platform-> job URL redirects to careers index; could not verify
"""
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

# Verified live this run (company, role_title, location, url, source_board, ats_platform,
#  posted_at, posted_at_raw, salary_disclosed, salary_range, remote_type,
#  seniority, notes)
postings = [
    ("Kraken", "Product Manager - CRM", "USA",
     "https://www.workingnomads.com/jobs/product-manager-crm-kraken-1801481",
     "WorkingNomads", "other",
     "2026-08-19", "Posted 3 days ago (aggregator listing)", True, "$96k-$192k per year",
     "remote", "mid",
     "Crypto exchange B2B org; CRM/sales-tools PM; aggregator relays original Payward posting"),
    ("Lendbuzz", "Product Manager (Payments)", "Remote / Remote (East Coast Timezone)",
     "https://jobs.lever.co/lendbuzz/e22d4d36-d9fe-4337-8616-91fc480524a8",
     "Lever", "lever", None, None, True, "$140,000 - $160,000 a year",
     "remote", "mid",
     "Auto-finance fintech; payments infra PM; ET timezone preference stated"),
    ("Kpler", "Product Manager", "Greece",
     "https://jobs.lever.co/kpler/c7103421-ccbe-43b4-b23d-752e8c8a3a9c",
     "Lever", "lever", None, None, False, None,
     "remote", "mid",
     "Maritime data & compliance SaaS; Risk & Compliance platform; posted as Greece (Remote); 3 yrs B2B SaaS"),
    ("Synack", "Product Manager, AI", "USA",
     "https://www.workingnomads.com/jobs/product-manager-ai-synack",
     "WorkingNomads", "other",
     "2026-08-18", "Posted 4 days ago (aggregator listing)", True, "$150k-$190k per year",
     "remote", "senior",
     "Owns Sara AI product suite (PTaaS security platform); aggregator relays original posting"),
    ("Kindred", "Staff Product Manager", "Remote - US",
     "https://jobs.ashbyhq.com/kindred/8868c144-1909-47f2-9c1c-e59a9e4ddce0",
     "Ashby", "ashby", None, None, True, "$200K - $245K + equity",
     "remote", "senior",
     "Home-swap marketplace; growth/supply-side staff PM"),
    ("Benepass", "Lead Product Manager", "U.S Remote",
     "https://jobs.ashbyhq.com/benepass/716b41c7-f3df-470a-bd7c-7f38d67d951a",
     "Ashby", "ashby", None, None, False, None,
     "remote", "senior",
     "Benefits fintech ($75M raised); owns a strategic product area end to end"),
    ("Turquoise Health", "Senior/Staff Product Manager, Contracts", "Remote",
     "https://jobs.ashbyhq.com/turquoise-health/7a416ec3-eef0-41da-8afb-09644fb54e1b",
     "Ashby", "ashby", None, None, True, "$185K - $245K + equity",
     "remote", "senior",
     "Healthcare price transparency; Contracts platform; needs back-office healthcare domain interest"),
    ("ezCater", "Senior Product Manager, Post Order Experience (Remote)", "Remote",
     "https://boards.greenhouse.io/ezcaterinc/jobs/5207123007",
     "Greenhouse", "greenhouse", None, None, False, None,
     "remote", "senior",
     "Workplace food marketplace; post-order retention/self-service surface"),
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

    discovered_today = c.execute(
        "SELECT COUNT(*) FROM applications WHERE date(discovered_at)=date('now') AND discovered_at IS NOT NULL"
    ).fetchone()[0]
    remaining = DAILY_CAP - discovered_today

    now_iso = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

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

    # Overflow captured even when remaining == 0 (pitfall #3).
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
                  (app_id, p["posting_url"], p["source_board"], now_iso))
        inserted.append((app_id, p["company"], p["role_title"], score, seniority))
        print(f"  INSERTED #{app_id}: {p['company']} | {p['role_title']} | score {score}")

    conn.commit()
    conn.close()

    state = {
        "last_run_at": now_iso, "mode": "open_web",
        "sources_checked": ["remotive-api", "ashby-dork", "lever-dork", "greenhouse-dork", "web_search-open-web"],
        "sources_checked_count": 5, "new_found": len(new_postings),
        "duplicates": len(duplicates), "filtered_out": len(skipped),
        "queued": len(inserted), "today_queued": discovered_today + len(inserted),
        "cap_reached": remaining <= 0, "remaining_slots": max(0, remaining - len(new_postings)),
        "daily_cap": DAILY_CAP,
        "overflow_count": len(overflow),
        "overflow_summary": [f"{o['company']} - {o['role_title']}" for o in overflow],
    }
    with open(STATE, "w") as f:
        json.dump(state, f, indent=2)
    print(json.dumps(state, indent=2))

if __name__ == "__main__":
    main()
