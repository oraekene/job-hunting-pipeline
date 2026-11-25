#!/usr/bin/env python3
"""Extract job listings from Remotive's product category page."""
import urllib.request, json, re, sqlite3, datetime, html as html_module

DB_PATH = "C:/Users/rotim/AppData/Local/hermes/skills/job-hunting/shared/applications.db"
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

# --- Load DB state for dedup ---
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
existing_urls = set(r[0] for r in cur.execute("SELECT DISTINCT posting_url FROM applications WHERE posting_url IS NOT NULL"))
existing_fps = set(r[0] for r in cur.execute("SELECT posting_fingerprint FROM applications WHERE posting_fingerprint IS NOT NULL"))
source_urls = set(r[0] for r in cur.execute("SELECT DISTINCT posting_url FROM posting_sources WHERE posting_url IS NOT NULL"))
all_known = existing_urls | source_urls
today_queued = cur.execute("SELECT COUNT(*) FROM applications WHERE status='discovered' AND date(discovered_at) = date('now')").fetchone()[0]
conn.close()
print(f"DB: {len(existing_urls)} app URLs, {len(existing_fps)} fingerprints, {len(all_known)} known URLs, {today_queued} queued today")

# --- Title matching ---
PM_KEYWORDS = [
    "product manager", "ai product", "technical product", "growth product",
    "associate product", "junior product", "product owner", "ai engineer",
    "automation engineer", "workflow engineer", "ml engineer", "machine learning engineer",
]
def title_matches(title):
    if not title:
        return False
    tl = title.lower().strip()
    return any(kw in tl for kw in PM_KEYWORDS)

def normalize_title(title):
    t = (title or "").lower().strip()
    t = re.sub(r'\s*#\d+\s*$', '', t)
    t = re.sub(r'\s*\(\s*[IVX]+\s*\)\s*$', '', t)
    t = re.sub(r'\s*\(\s*(senior|junior|lead|principal|staff|mid|entry|associate)\s*\)\s*$', '', t)
    t = re.sub(r'\s*\(\s*(remote|contract|freelance|temp)\s*\)\s*$', '', t)
    t = re.sub(r'[^\w\s]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def compute_fingerprint(company, role_title, location):
    c = (company or "").lower().strip()
    t = normalize_title(role_title)
    l = re.sub(r'\s+', ' ', (location or "").lower().strip())
    return f"{c}|{t}|{l}"

# --- Fetch Remotive product jobs page ---
url = "https://remotive.com/remote-jobs/product"
req = urllib.request.Request(url, headers=HEADERS)
resp = urllib.request.urlopen(req, timeout=20)
html = resp.read().decode('utf-8', errors='replace')
print(f"\nRemotive product page: HTTP {resp.status}, {len(html)} chars")

# Extract job links
job_links = re.findall(r'href="(/remote-jobs/[^"]+)"', html)
unique_jobs = list(dict.fromkeys(job_links))  # dedupe, preserve order
print(f"Job links found: {len(unique_jobs)}")

# Try to extract job data from embedded JSON
# Look for script tags with JSON data
json_data = None
for script in re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL):
    if 'publication_date' in script or 'job_title' in script or '"title"' in script:
        # Try to find a JSON object
        json_match = re.search(r'\{.*\}', script, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
                if isinstance(data, list) and len(data) > 5:
                    json_data = data
                    break
            except:
                pass

# Also try to find job data in the page's data attributes
# Remotive cards typically have: data-test="job-card", data-company, data-title, etc.
cards = re.findall(r'data-test="job-card"[^>]*>(.*?)</div>\s*</div>', html, re.DOTALL | re.IGNORECASE)
print(f"Job cards with data-test: {len(cards)}")

# Alternative: look for the job listing structure
# Remotive uses <a> tags with href="/remote-jobs/..." containing job info
# Let's extract company, title, and date from each job card
job_data = []
for link in unique_jobs:
    full_url = f"https://remotive.com{link}"
    # Skip if already known
    if full_url in all_known:
        continue

    # Try to extract title from URL slug
    parts = link.strip('/').split('/')
    slug = parts[-1] if parts else ''
    # Convert slug to title (replace - with space, etc.)
    title_from_slug = slug.replace('-', ' ').title()

    if not title_matches(slug) and not title_matches(title_from_slug):
        continue

    # Try to find company and date from the HTML context near this link
    # Search for the link in the HTML and extract surrounding content
    link_pattern = re.escape(link)
    match = re.search(link_pattern, html)
    if match:
        # Get surrounding context (500 chars before and after)
        start = max(0, match.start() - 500)
        end = min(len(html), match.end() + 500)
        context = html[start:end]

        # Extract company name - look for company patterns
        company = "Unknown"
        # Try to find company name in the context
        company_match = re.search(r'data-company="([^"]+)"', context)
        if company_match:
            company = company_match.group(1)
        else:
            # Try to find company from the surrounding text
            # Remotive typically has: <span class="company_name">Company Name</span>
            company_match = re.search(r'company[^"]*"[^>]*>([^<]+)', context, re.IGNORECASE)
            if company_match:
                company = company_match.group(1).strip()
            else:
                company_match = re.search(r'>([^<]+)</a>', context)
                # This is too generic, let's try another approach
                # Look for data attributes near the link
                company_match = re.search(r'data-company="([^"]+)"', html[max(0,match.start()-1000):match.end()+100])
                if company_match:
                    company = company_match.group(1)

        # Extract date
        date_match = re.search(r'data-date="([^"]+)"', context)
        date_text = date_match.group(1) if date_match else ""
        # Also try to find publication date
        if not date_text:
            date_match = re.search(r'publication_date["\s:=]+("[^"]+"|\d{4}-\d{2}-\d{2})', context)
            if date_match:
                date_text = date_match.group(1).strip('"')
            else:
                date_match = re.search(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', context)
                if date_match:
                    date_text = date_match.group(1)

    job_data.append({
        "url": full_url,
        "title": title_from_slug,
        "company": company,
        "date_raw": date_text,
        "slug": slug,
    })

# Print matching jobs
print(f"\n=== Jobs matching PM/AI keywords ({len(job_data)} found) ===")
for j in job_data:
    print(f"  {j['title']} | {j['company']} | {j['url'][:70]} | date={j['date_raw']}")

# Now, let's try to fetch individual job pages for the matching ones
now = datetime.datetime.now(datetime.timezone.utc)
recent_cutoff = now - datetime.timedelta(hours=24)
week_cutoff = now - datetime.timedelta(days=7)

candidates = []
skipped_dup_url = 0
skipped_dup_fp = 0

for j in job_data:
    full_url = j["url"]
    if full_url in all_known:
        skipped_dup_url += 1
        continue

    # Try to fetch the job page for full details
    print(f"\n  Fetching: {full_url[:80]}")
    try:
        req2 = urllib.request.Request(full_url, headers=HEADERS)
        resp2 = urllib.request.urlopen(req2, timeout=15)
        job_html = resp2.read().decode('utf-8', errors='replace')

        # Extract title from page
        title = j["title"]
        title_match = re.search(r'<title>(.*?)</title>', job_html, re.DOTALL)
        if title_match:
            page_title = title_match.group(1).strip()
            # Use page title if it's more descriptive
            if len(page_title) > len(title):
                title = page_title

        # Extract company
        company = j["company"]
        # Try JSON-LD
        ld_scripts = re.findall(r'<script type="application/ld\+json">(.*?)</script>', job_html, re.DOTALL)
        for ld in ld_scripts:
            try:
                data = json.loads(ld)
                if isinstance(data, dict):
                    if data.get("@type") == "JobPosting":
                        company = data.get("hiringOrganization", {}).get("name", company) if isinstance(data.get("hiringOrganization"), dict) else company
                        title = data.get("title", title)
                        date_raw = data.get("datePosted", j["date_raw"])
                        salary = data.get("baseSalary", "")
                        # Extract location
                        loc = data.get("jobLocation", {})
                        if isinstance(loc, dict):
                            addr = loc.get("address", {})
                            if isinstance(addr, dict):
                                location = ", ".join([p for p in [addr.get("addressLocality",""), addr.get("addressRegion",""), addr.get("addressCountry","")] if p]) or "remote"
                            else:
                                location = "remote"
                        else:
                            location = "remote"
                        break
            except:
                continue

        # If title doesn't match, skip
        if not title_matches(title):
            continue

        # Compute fingerprint
        location = "remote"  # Default for Remotive
        fp = compute_fingerprint(company, title, location)
        if fp in existing_fps:
            skipped_dup_fp += 1
            print(f"    SKIP (dup fingerprint): {fp}")
            continue

        # Parse posted date
        posted_at = None
        posted_raw = j["date_raw"] or ""
        if "publication_date" in job_html:
            # Look for publication date in JSON
            pub_match = re.search(r'"publication_date"\s*:\s*"([^"]+)"', job_html)
            if pub_match:
                posted_raw = pub_match.group(1)
        if posted_raw:
            try:
                posted_at = datetime.datetime.fromisoformat(posted_raw.replace("Z", "+00:00"))
                if posted_at.tzinfo is None:
                    posted_at = posted_at.replace(tzinfo=datetime.timezone.utc)
            except:
                pass

        priority = "high" if (posted_at and posted_at > recent_cutoff) or not posted_at else "normal"
        if posted_at and posted_at < week_cutoff:
            print(f"    SKIP (old): {title} | posted {posted_at}")
            continue

        candidates.append({
            "posting_url": full_url,
            "company": company or "Unknown",
            "role_title": title,
            "location": location,
            "posted_at": posted_at.strftime("%Y-%m-%dT%H:%M:%SZ") if posted_at else None,
            "posted_at_raw": posted_raw,
            "salary_disclosed": False,
            "salary_range": None,
            "source_board": "Remotive",
            "remote_type": "remote",
            "discovered_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "priority": priority,
            "posting_fingerprint": fp,
        })
        print(f"    MATCH: {company} | {title} | priority={priority}")
    except Exception as e:
        print(f"    Error fetching: {e}")
        continue

# Intra-run dedup
seen_fp = set()
unique_candidates = []
for p in candidates:
    if p["posting_fingerprint"] not in seen_fp:
        seen_fp.add(p["posting_fingerprint"])
        unique_candidates.append(p)

print(f"\n=== SUMMARY ===")
print(f"Jobs matching titles: {len(job_data)}")
print(f"Candidates (after DB dedup): {len(candidates)}")
print(f"Unique candidates (intra-run dedup): {len(unique_candidates)}")
print(f"Skipped dup URL: {skipped_dup_url}, Skipped dup FP: {skipped_dup_fp}")
for p in unique_candidates:
    print(f"  CANDIDATE: {p['company']} | {p['role_title']} | {p['posting_url']}")
