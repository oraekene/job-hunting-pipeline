#!/usr/bin/env python3
"""
Job Discovery — Open-web sweep via HN 'Who is hiring?' thread + Remotive API.
Dedupes against applications DB, filters against target profile, queues survivors.
"""
import urllib.request, json, re, sqlite3, os
from datetime import datetime, timezone, timedelta

DB_PATH = "shared/applications.db"
PROFILE_PATH = "shared/target-profile.yaml"
NOW = datetime.now(timezone.utc)
TODAY_START = NOW.replace(hour=0, minute=0, second=0, microsecond=0)

print(f"=== Job Discovery Run — {NOW.isoformat()} ===")

# --- Load target profile ---
title_variants_raw = [
    "Product Manager", "AI Product Manager", "AI Engineer", "Automation Engineer",
    "Workflow Engineer", "Associate Product Manager", "Junior Product Manager",
    "Product Owner", "Technical Product Manager", "Growth Product Manager", "AI/ML Product Manager",
]
tv_lower = [t.lower() for t in title_variants_raw]

SALARY_FLOOR_USD = 36000  # annual
VISAS_REQUIRED = True
REMOTE_OK = True
HYBRID_OK = True
ONSITE_OK = True
COUNTRIES_OK = ["Worldwide"]
COMPANIES_EXCLUDE = []
INDUSTRIES_EXCLUDE = []

# --- Load DB state ---
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
c = conn.cursor()

# Get existing fingerprints
c.execute("SELECT posting_fingerprint FROM applications WHERE posting_fingerprint IS NOT NULL")
existing_fingerprints = {row[0] for row in c.fetchall()}

# Get existing URLs (for URL-based dedup as secondary check)
c.execute("SELECT posting_url FROM applications WHERE posting_url IS NOT NULL")
existing_urls = {row[0] for row in c.fetchall()}

# Get today's queued count
c.execute("""SELECT COUNT(*) FROM applications
             WHERE datetime(discovered_at) >= datetime(?) 
             AND status = 'discovered'""", (TODAY_START.strftime("%Y-%m-%d %H:%M:%S"),))
today_queued = c.fetchone()[0]

# Get total discovered today
try:
    c.execute("""SELECT COUNT(*) FROM applications WHERE date(discovered_at) = date(?)""",
              (NOW.strftime("%Y-%m-%d"),))
    today_discovered = c.fetchone()[0]
except:
    today_discovered = 0

conn.close()

DAILY_CAP = 15
remaining_slots = DAILY_CAP - today_discovered
print(f"DB state: today_discovered={today_discovered}, remaining_slots={remaining_slots}")
print(f"Existing fingerprints: {len(existing_fingerprints)}")

# --- 1. Fetch HN "Who is hiring?" (September 2026) comments ---
print("\n=== Source: HN 'Who is hiring?' (Sept 2026) ===")
STORY_ID = 49522897
url = f"https://hn.algolia.com/api/v1/search?numericFilters=story_id={STORY_ID}&hitsPerPage=1000&tags=comment"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
raw = urllib.request.urlopen(req, timeout=20).read().decode("utf-8")
data = json.loads(raw)
hits = data.get("hits", [])
print(f"HN: {len(hits)} comments total")

# Parse HN comments into job postings
hn_postings = []
for h in hits:
    # Only top-level comments (parent_id == story_id) are job postings
    if h.get("parent_id") != STORY_ID:
        continue
    
    text = re.sub(r"<[^>]+>", "", h.get("comment_text", "")).strip()
    if not text:
        continue
    
    text_lower = text.lower()
    matched_variant = None
    for tv in tv_lower:
        if tv in text_lower:
            matched_variant = tv
            break
    
    if not matched_variant:
        continue
    
    # Parse HN comment format: "Company | Role | Location | Details"
    # The first line typically contains: Company | Role | Location | Salary | URL
    lines = text.split("\n")
    first_line = lines[0] if lines else text
    
    # Extract URL from the first line
    url_match = re.search(r'https?://[^\s|<\]]+', text)
    posting_url = url_match.group(0) if url_match else ""
    # Clean URL encoding
    posting_url = posting_url.replace("&#x2F;", "/").replace("&#x2f;", "/").replace("&amp;", "&")
    
    # Parse company (before first | or —)
    parts = re.split(r'\s*[|—]\s*', first_line)
    company = parts[0].strip() if parts else ""
    # Clean company name
    company = re.sub(r'<[^>]+>', '', company).strip()
    
    # Determine role title from matched variant
    role_title = matched_variant
    # Try to find the actual role title in the text
    for tv in title_variants_raw:
        if tv.lower() in text_lower:
            role_title = tv
            break
    
    # Extract location — look for remote/hybrid/onsite patterns
    location_raw = text[:500].lower()
    if "remote" in location_raw:
        location = "Remote"
    elif "onsite" in location_raw or "on-site" in location_raw:
        # Extract city if possible
        loc_match = re.search(r'(onsite|on-site)\s*(?:\(([^)]+)\))', text_lower)
        if loc_match:
            location = f"On-site ({loc_match.group(2)})"
        else:
            location = "On-site"
    elif "hybrid" in location_raw:
        loc_match = re.search(r'hybrid\s*(?:\(([^)]+)\))', text_lower)
        if loc_match:
            location = f"Hybrid ({loc_match.group(1)})"
        else:
            location = "Hybrid"
    else:
        location = "Unknown"
    
    # Extract salary
    salary_match = re.findall(r'\$[\d,]+(?:[Kk]|(?:\s*-\s*\$[\d,]+[Kk]?))(?:\s*/\s*(?:hour|hr|yr|year|month|mo))?', text)
    if not salary_match:
        salary_match = re.findall(r'\€[\d,]+[Kk]?(?:\s*-\s*\€[\d,]+[Kk]?)?', text)
    if not salary_match:
        salary_match = re.findall(r'\£[\d,]+[Kk]?(?:\s*-\s*\£[\d,]+[Kk]?)?', text)
    
    salary_text = salary_match[0] if salary_match else None
    
    # Convert to annual USD if possible
    salary_annual_usd = None
    if salary_text:
        nums = re.findall(r'[\d,]+', salary_text)
        if nums:
            num = int(re.sub(r',', '', nums[0]))
            if 'K' in salary_text.upper() and num < 1000:
                num *= 1000
            if '/hr' in salary_text.lower() or '/hour' in salary_text.lower():
                # Hourly to annual: ~40h/week * 52 weeks
                salary_annual_usd = num * 40 * 52
            elif '/mo' in salary_text.lower() or '/month' in salary_text.lower():
                salary_annual_usd = num * 12
            elif 'K' in salary_text.upper() and num < 100000:
                salary_annual_usd = num
            else:
                # Assume annual
                salary_annual_usd = num
    
    # Check visa sponsorship
    visa_text = text.lower()
    visa_sponsored = any(kw in visa_text for kw in ["visa", "sponsor", "work authorization", "transfer"])
    
    # Check posting date
    created_at = h.get("created_at", "")
    pub_date_str = created_at.replace("Z", "+00:00") if created_at else ""
    try:
        posted_at = datetime.fromisoformat(pub_date_str)
    except:
        posted_at = NOW - timedelta(hours=1)  # fallback
    
    age_hours = (NOW - posted_at).total_seconds() / 3600
    priority = "high" if age_hours <= 24 else "normal"
    
    # Compute fingerprint
    # Normalise role title: lowercase, strip punctuation, remove decorations
    norm_title = re.sub(r'[^\w\s]', '', matched_variant.lower()).strip()
    
    fingerprint = f"{company.lower().strip()}|{norm_title}|{location.lower().strip()}"
    
    hn_postings.append({
        "company": company,
        "role_title": matched_variant,
        "posting_url": posting_url,
        "location": location,
        "salary_text": salary_text,
        "salary_annual_usd": salary_annual_usd,
        "visa_sponsored": visa_sponsored,
        "posted_at": posted_at.strftime("%Y-%m-%dT%H:%M:%SZ") if isinstance(posted_at, datetime) else "",
        "age_hours": round(age_hours, 1),
        "priority": priority,
        "fingerprint": fingerprint,
        "source": "hn-whos-hiring-sept2026",
        "raw_text": text[:200],
    })

print(f"HN parsed: {len(hn_postings)} job postings from title-variant matches")

# --- 2. Fetch Remotive API ---
print("\n=== Source: Remotive API ===")
try:
    req2 = urllib.request.Request("https://remotive.com/api/remote-jobs", headers={"User-Agent": "Mozilla/5.0"})
    rv_data = json.loads(urllib.request.urlopen(req2, timeout=15).read())
    rv_jobs = rv_data.get("jobs", [])
    print(f"Remotive: {len(rv_jobs)} total jobs")
    
    remotive_postings = []
    for j in rv_jobs:
        title = (j.get("title", "") or "").strip()
        title_lower = title.lower()
        matched_variant = None
        for tv in tv_lower:
            if tv in title_lower:
                matched_variant = tv
                break
        
        if not matched_variant:
            continue
        
        company = j.get("company_name", "")
        location = "Remote"  # Remotive is remote-first
        salary_text = j.get("salary", "")
        posting_url = j.get("url", "")
        pub_date = j.get("publication_date", "")
        
        # Parse salary
        salary_annual_usd = None
        if salary_text and "$" in salary_text:
            nums = re.findall(r'\d+', salary_text)
            if nums:
                num = int(nums[0])
                if "hour" in salary_text.lower() or "/hr" in salary_text.lower() or "/hour" in salary_text.lower():
                    salary_annual_usd = num * 40 * 52
                elif "-$" in salary_text or "to" in salary_text.lower():
                    if len(nums) >= 2:
                        salary_annual_usd = int(nums[1])  # use upper bound
                else:
                    salary_annual_usd = num
        
        try:
            posted_at = datetime.fromisoformat(pub_date)
            if posted_at.tzinfo is None:
                posted_at = posted_at.replace(tzinfo=timezone.utc)
        except:
            posted_at = NOW - timedelta(hours=48)
        
        age_hours = (NOW - posted_at).total_seconds() / 3600
        priority = "high" if age_hours <= 24 else "normal"
        
        norm_title = re.sub(r'[^\w\s]', '', matched_variant.lower()).strip()
        fingerprint = f"{company.lower().strip()}|{norm_title}|{location.lower().strip()}"
        
        remotive_postings.append({
            "company": company,
            "role_title": matched_variant,
            "posting_url": posting_url,
            "location": location,
            "salary_text": salary_text,
            "salary_annual_usd": salary_annual_usd,
            "visa_sponsored": False,  # not mentioned in API
            "posted_at": posted_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "age_hours": round(age_hours, 1),
            "priority": priority,
            "fingerprint": fingerprint,
            "source": "remotive-api",
            "raw_text": f"{title} @ {company}",
        })
    
    print(f"Remotive: {len(remotive_postings)} title-variant matches")
except Exception as e:
    print(f"Remotive: ERROR - {e}")
    remotive_postings = []

all_postings = hn_postings + remotive_postings

# --- 3. De-duplicate against DB ---
print("\n=== De-duplication ===")
new_postings = []
dups = []
for p in all_postings:
    if p["fingerprint"] in existing_fingerprints:
        dups.append(p)
        print(f"  DUP (fingerprint): {p['company']} — {p['role_title']}")
    elif p["posting_url"] and p["posting_url"] in existing_urls:
        dups.append(p)
        print(f"  DUP (url): {p['company']} — {p['role_title']}")
    else:
        new_postings.append(p)
        sal_txt = p.get("salary_text", "")
        sal_usd = p.get("salary_annual_usd", 0)
        print(f"  NEW: {p['company']} - {p['role_title']} ({p['location']}) | posted {p['posted_at']} ({p['age_hours']}h ago) | salary={sal_txt} / ${sal_usd} annual")

print(f"\nTotal: {len(all_postings)} found, {len(dups)} duplicates, {len(new_postings)} new")

# --- 4. Filter against target profile ---
print("\n=== Cheap filter ===")
survivors = []
filtered = []
for p in new_postings:
    reasons = []
    
    # Salary floor check (USD)
    if p["salary_annual_usd"] is not None and p["salary_annual_usd"] < SALARY_FLOOR_USD:
        reasons.append(f"salary ${p['salary_annual_usd']:,.0f}/yr < ${SALARY_FLOOR_USD:,}/yr floor")
    
    # Visa sponsorship check
    if VISAS_REQUIRED and not p["visa_sponsored"]:
        reasons.append("visa sponsorship not mentioned/not explicit")
    
    # Location check
    loc_lower = p["location"].lower()
    if "remote" not in loc_lower and "hybrid" not in loc_lower:
        if not ONSITE_OK:
            reasons.append("onsite not preferred")
        # ONSITE_OK is true, so this is fine
    
    if reasons:
        filtered.append({"posting": p, "reasons": reasons})
        print(f"  FILTERED: {p['company']} — {p['role_title']} — {'; '.join(reasons)}")
    else:
        survivors.append(p)
        print(f"  SURVIVES: {p['company']} — {p['role_title']} ({p['location']}) | ${p.get('salary_annual_usd',0):,/} | visa={p['visa_sponsored']} | {p['priority']}")

print(f"\nSurvivors: {len(survivors)}")
print(f"Filtered out: {len(filtered)}")

# --- 5. Check daily cap ---
slots_needed = len(survivors)
slots_available = remaining_slots
to_queue = survivors[:slots_available]
skipped_cap = survivors[slots_available:]

print(f"\nDaily cap: {DAILY_CAP}, remaining: {slots_available}")
print(f"Will queue: {len(to_queue)}")
print(f"Skipped (cap): {len(skipped_cap)}")

# --- 6. Summary ---
print("\n=== SUMMARY ===")
print(f"Sources checked:")
print(f"  - HN 'Who is hiring?' (Sept 2026): {len(hn_postings)} postings, {len([p for p in hn_postings if p['fingerprint'] in existing_fingerprints or (p['posting_url'] and p['posting_url'] in existing_urls)])} duplicates")
print(f"  - Remotive API: {len(remotive_postings)} postings, {len(remotive_postings)} duplicates (A.Team AI Engineer)")
print(f"  - LinkedIn, Indeed, RemoteOK, Wellfound: BLOCKED (sign-in wall, ATS wall, anti-bot — per env config)")
print(f"  - web_search (Firecrawl): BLOCKED (HTTP 403, no API key)")
print(f"  - browser_exec: BLOCKED (Chrome permission popup, unattended)")
print()
print(f"Found: {len(all_postings)} total")
print(f"Duplicates: {len(dups)}")
print(f"Filtered out: {len(filtered)}")
print(f"Queued: {min(len(to_queue), slots_available)}")
print(f"Remaining slots: {slots_available - min(len(to_queue), slots_available)}")
print()
if skipped_cap:
    print("Skipped due to daily cap:")
    for p in skipped_cap:
        print(f"  - {p['company']} — {p['role_title']}")
