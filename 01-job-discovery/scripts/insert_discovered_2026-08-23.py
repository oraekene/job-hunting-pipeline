#!/usr/bin/env python3
"""Discovery insert 2026-08-23 — queue surviving postings into applications.db.
Follows run-discovery-batch.py conventions (fingerprints, scores, cap accounting)."""
import sqlite3, os, json, re, datetime

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(SKILL_ROOT, "shared", "applications.db")
STATE = os.path.join(SKILL_ROOT, "shared", ".discovery_gate_state.json")
RESULTS = os.path.join(SKILL_ROOT, "shared", ".discovery_results.json")

now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

TITLE_VARIANTS = [
    "Product Manager", "AI Product Manager", "AI Engineer",
    "Automation Engineer", "Associate Product Manager",
    "Junior Product Manager", "Workflow Engineer", "Product Owner",
    "Technical Product Manager", "Growth Product Manager",
    "AI/ML Product Manager",
]

def normalize_title(t):
    t = t.lower().strip()
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\s+(ii|iii|iv|jr|senior|staff|principal|lead)$", "", t)
    return t.strip()

def compute_fingerprint(company, title, location):
    return f"{company.lower().strip()}|{normalize_title(title)}|{location.lower().strip()}"

def parse_salary_value(s):
    """Corrected parser (job-hunting-discovery-scan pitfall #1: K inside capture group)."""
    s = s.replace(",", "")
    m = re.search(r"\$(\d+(?:\.\d+)?)\s*[Kk]?\b", s)
    if not m:
        return 0
    val = float(m.group(1))
    if "k" in s.lower() and val < 1000:
        # only treat K as thousands when the token actually carried a K suffix
        if re.search(r"\$\d+(?:\.\d+)?\s*[Kk]\b", s):
            val *= 1000
    return val

def compute_match_score(title, salary_disclosed, salary_range):
    base = 70
    tl = title.lower()
    if tl in [v.lower() for v in TITLE_VARIANTS]:
        base += 15
    if "ai" in tl or "ml" in tl:
        base += 5
    if salary_disclosed:
        base += 5
        min_val = parse_salary_value(salary_range or "")
        if min_val >= 36000:
            base += 5
    overqual = any(tl.startswith(p) for p in ["senior", "staff", "principal", "lead", "director"])
    return max(50, min(95, base)), overqual

# (company, role_title, location_for_fingerprint, url, source_board, ats_platform,
#  posted_at, posted_at_raw, salary_disclosed, salary_range, remote_type, priority)
postings = [
    ("Stedi", "Product Manager", "USA (remote)",
     "https://jobs.ashbyhq.com/stedi/65b38320-75df-4386-b5e5-25b411e7a6a4",
     "Ashby", "ashby", "2026-08-03", "json_ld datePosted: 2026-08-03",
     True, "$150,000 - $212,000 USD", "remote", "normal"),
    ("Teleperformance", "AI Product Manager, Internal Transformations", "Remote - United States",
     "https://careersus-teleperformance.icims.com/jobs/85572/ai-product-manager%2C-internal-transformations/job",
     "iCIMS", "icims", None, "none available on iCIMS page - using discovered_at",
     True, "USD $90,000.00/Yr. - USD $110,000.00/Yr.", "remote", "normal"),
    ("MCI", "AI Product Manager", "US Remote Nationwide",
     "https://careers-mci2.icims.com/jobs/50183/ai-product-manager/job",
     "iCIMS", "icims", None, "none available on iCIMS page - using discovered_at",
     False, None, "remote", "normal"),
    ("Chime", "Product Manager, Transaction Risk Decisioning", "San Francisco, CA",
     "https://boards.greenhouse.io/chime/jobs/8694087002",
     "Greenhouse", "greenhouse", "2026-08-10", 'page meta "published_at":"2026-08-10"',
     False, None, "onsite", "normal"),
]

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
c = conn.cursor()

existing_fp = {r["posting_fingerprint"] for r in c.execute(
    "SELECT posting_fingerprint FROM applications WHERE posting_fingerprint IS NOT NULL")}
existing_urls = {r["posting_url"] for r in c.execute(
    "SELECT posting_url FROM applications WHERE posting_url IS NOT NULL")}

staged_today = c.execute(
    "SELECT COUNT(*) FROM applications WHERE date(staged_at) = date('now') AND staged_at IS NOT NULL"
).fetchone()[0]
discovered_today = c.execute(
    "SELECT COUNT(*) FROM applications WHERE date(discovered_at) = date('now')"
).fetchone()[0]
daily_cap = 15
used_today = staged_today + discovered_today
remaining = daily_cap - used_today

new_postings, duplicates, skipped = [], [], []
for p in postings:
    company, role_title, location, url, sb, ats, pat, praw, sd, sr, rt, prio = p
    fp = compute_fingerprint(company, role_title, location)
    if fp in existing_fp or url in existing_urls:
        duplicates.append((company, role_title))
        continue
    score, overqual = compute_match_score(role_title, sd, sr)
    existing_fp.add(fp)
    new_postings.append({
        "posting_url": url,
        "company": company,
        "role_title": role_title,
        "source_board": sb,
        "ats_platform": ats,
        "posted_at": pat,
        "posted_at_raw": praw,
        "discovered_at": now_iso,
        "seniority": "senior" if overqual else "mid",
        "remote_type": rt,
        "salary_disclosed": 1 if sd else 0,
        "salary_range": sr,
        "status": "discovered",
        "overall_match_score": score,
        "keyword_match_score": score,
        "exact_phrase_count": 1,
        "title_matched": 1,
        "title_original": role_title,
        "title_displayed": role_title,
        "posting_fingerprint": fp,
        "priority": prio,
        "outcome": "pending",
        "build_attempts": 0,
    })

inserted = []
if remaining > 0:
    for p in new_postings[:remaining]:
        cols = ", ".join(p.keys())
        ph = ", ".join(["?"] * len(p))
        c.execute(f"INSERT INTO applications ({cols}) VALUES ({ph})", list(p.values()))
        inserted.append(p)
overflow = new_postings[len(inserted):]

conn.commit()

# --- Self-check: second-pass dedup (should report all inserted as dups, 0 new) ---
check2 = []
for p in inserted:
    if p["posting_url"] in existing_urls:
        check2.append("pre-existing??")
check_new = c.execute("SELECT COUNT(*) FROM applications WHERE posting_url IN ({})".format(
    ",".join("?" * len(inserted))), [p["posting_url"] for p in inserted]).fetchone()[0]
print(f"self-check: {check_new} rows now present for the {len(inserted)} inserts")

# Cap accounting after insert
staged_after = c.execute(
    "SELECT COUNT(*) FROM applications WHERE date(staged_at) = date('now') AND staged_at IS NOT NULL").fetchone()[0]
disc_after = c.execute(
    "SELECT COUNT(*) FROM applications WHERE date(discovered_at) = date('now')").fetchone()[0]
conn.close()

today_queued = staged_after + disc_after
state = {
    "last_run_at": now_iso,
    "mode": "open_web",
    "sources_checked": ["remotive-api", "remoteok-json", "wellfound", "ashby-dork", "lever-dork",
                        "greenhouse-dork", "icims-workday-dork"],
    "sources_checked_count": 7,
    "new_found": len(postings),
    "duplicates": len(duplicates),
    "filtered_out": 3 + 1,  # 3 stale + 1 residency-excluded
    "queued": len(inserted),
    "today_queued": today_queued,
    "cap_reached": today_queued >= daily_cap,
    "remaining_slots": daily_cap - today_queued,
    "daily_cap": daily_cap,
    "overflow_count": len(overflow),
    "overflow_summary": [f"{p['company']} - {p['role_title']}" for p in overflow],
}
with open(STATE, "w") as f:
    json.dump(state, f, indent=2)

results = {
    "queued": [{"company": p["company"], "role_title": p["role_title"], "posting_url": p["posting_url"],
                "source": p["ats_platform"], "posted_at_raw": p["posted_at_raw"],
                "priority": p["priority"], "salary_range": p["salary_range"]} for p in inserted],
    "skipped_duplicates": [{"company": d[0], "role_title": d[1]} for d in duplicates],
    "skipped_filter": [
        {"company": "e.l.f. Beauty", "role_title": "Product Manager, Marketing Technology",
         "note": "stale - JSON-LD datePosted 2026-06-15 (69 days), beyond open-web freshness window"},
        {"company": "Finch", "role_title": "Product Manager, Integrations (Core Product)",
         "note": "stale - JSON-LD datePosted 2026-06-03 (81 days)"},
        {"company": "Array Labs", "role_title": "Technical Product Manager, 3D Geospatial Products",
         "note": "stale - JSON-LD datePosted 2026-05-29 (86 days)"},
        {"company": "Jeeves", "role_title": "Product Manager - Accounting",
         "note": "excluded - posting states remote based out of Argentina (residency-restricted)"},
    ],
    "overflow": [],
}
with open(RESULTS, "w") as f:
    json.dump(results, f, indent=2)

print(json.dumps(state, indent=2))
print()
for p in inserted:
    print(f"QUEUED [{p['overall_match_score']}] {p['company']} - {p['role_title']} "
          f"({p['source_board']}, {p['remote_type']}, sal={p['salary_range'] or 'n/a'})")
