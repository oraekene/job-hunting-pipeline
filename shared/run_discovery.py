#!/usr/bin/env python3
"""Discovery scan for job-hunting pipeline.

Scans configured sources for new postings matching Kenechukwu's target profile,
dedupes against the applications DB, cheap-filters, and queues survivors
respecting the daily cap. Delivers a short digest.

Sources attempted (in order):
  1. Remotive API          — reliable (per env config)
  2. HN "Who is Hiring"    — reliable (per env config)
  3. Wellfound             — try (likely blocked)
  4. Bing open-web sweep   — reliable (per env config)

Blocked sources (noted, not retried):
  - LinkedIn     — sign-in wall (anti-bot)
  - Indeed       — sign-in wall / ATS wall
  - RemoteOK     — anti-bot / redirect

Discovery mode: open_web (poll_only sources + open-web sweep on daily cadence)
"""
import json
import os
import re
import sqlite3
import datetime
import urllib.request
import urllib.parse

import yaml
from bs4 import BeautifulSoup

SKILL_ROOT = r"C:/Users/rotim/AppData/Local/hermes/skills/job-hunting"
DB_PATH = os.path.join(SKILL_ROOT, "shared", "applications.db")
TARGET_PATH = os.path.join(SKILL_ROOT, "shared", "target-profile.yaml")
GATE_STATE_PATH = os.path.join(SKILL_ROOT, "shared", ".discovery_gate_state.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# ─── Load target profile ──────────────────────────────────────────
with open(TARGET_PATH) as f:
    target = yaml.safe_load(f)

title_variants = [tv["title"] for tv in target.get("title_variants", [])]
salary_floor = target.get("salary_floor", {"amount": 36000, "currency": "USD", "period": "year"})
companies_exclude = target.get("companies_exclude", [])
seniority_band = target.get("seniority_band", "mid")
discovery_mode = target.get("discovery_mode", "poll_only")
visa_required = target.get("visa_sponsorship_required", True)

now = datetime.datetime.now(datetime.timezone.utc)
recent_cutoff = now - datetime.timedelta(hours=24)
week_cutoff = now - datetime.timedelta(days=7)

# ─── Title matching ───────────────────────────────────────────────
PM_KEYWORDS = [
    "product manager", "ai product manager", "technical product manager",
    "growth product manager", "associate product manager", "junior product manager",
    "product owner", "ai engineer", "automation engineer",
    "workflow engineer", "ai/ml product manager", "machine learning product manager",
    "head of product", "lead product manager", "staff product manager",
    "principal product manager",  # "product manager" is substring of all PM variants
]

def title_matches(title):
    if not title:
        return False
    tl = title.lower().strip()
    for kw in PM_KEYWORDS:
        if kw in tl:
            return True
    return False


# ─── Fingerprint normalization ────────────────────────────────────
def normalize_title(title):
    """Normalize a job title for fingerprinting.

    Matches the style used by existing DB fingerprints:
    - lowercase
    - strip trailing req IDs (e.g. #123), roman-numeral suffixes, level/party suffixes
    - replace non-word/non-space chars with spaces (keeps commas as spaces per existing data)
    - collapse whitespace
    - strip
    """
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


# ─── Salary filter ────────────────────────────────────────────────
def passes_salary(salary_text, floor):
    """Return True if salary is acceptable or not disclosed (can't reject)."""
    if not salary_text:
        return True
    text = str(salary_text).lower()
    amounts = []
    for m in re.finditer(r'(\d[\d,]*\.?\d*)', text):
        try:
            v = float(m.group(1).replace(",", ""))
            if 1000 < v < 10000000:
                amounts.append(v)
        except:
            pass
    if amounts:
        mx = max(amounts)
        fa = floor.get("amount", 0)
        if mx >= fa:
            return True
        if "month" in text and mx * 12 >= fa:
            return True
        if mx < fa * 0.3:
            return False
    return True


# ─── Posted date parsing ──────────────────────────────────────────
def extract_posted(posted_str):
    if not posted_str:
        return None, ""
    ps = str(posted_str).strip()
    # ISO format
    try:
        dt = datetime.datetime.fromisoformat(ps)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt, ps
    except:
        pass
    for fmt in ["%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S",
                "%B %d, %Y", "%b %d, %Y", "%Y-%m-%d %H:%M:%S"]:
        try:
            dt = datetime.datetime.strptime(ps, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return dt, ps
        except:
            pass
    # Relative text
    t = ps.lower().strip()
    n = now
    if "today" in t or "just now" in t or "0 day" in t:
        return n, ps
    if "yesterday" in t:
        return n - datetime.timedelta(days=1), ps
    m = re.match(r'(\d+)\s+hour', t)
    if m:
        return n - datetime.timedelta(hours=int(m.group(1))), ps
    m = re.match(r'(\d+)\s+day', t)
    if m:
        return n - datetime.timedelta(days=int(m.group(1))), ps
    return None, ps


# ─── HTTP helper ──────────────────────────────────────────────────
def fetch_url(url, timeout=20):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", errors="replace")


# ─── Load DB state ────────────────────────────────────────────────
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
existing_fingerprints = set(r[0] for r in cur.execute("SELECT posting_fingerprint FROM applications WHERE posting_fingerprint IS NOT NULL"))
existing_urls = set(r[0] for r in cur.execute("SELECT DISTINCT posting_url FROM applications WHERE posting_url IS NOT NULL"))
existing_source_urls = set(r[0] for r in cur.execute("SELECT DISTINCT posting_url FROM posting_sources WHERE posting_url IS NOT NULL"))
all_known_urls = existing_urls | existing_source_urls
today_queued = cur.execute("SELECT COUNT(*) FROM applications WHERE status='discovered' AND date(discovered_at) = date('now')").fetchone()[0]
conn.close()

print(f"DB loaded: {len(existing_fingerprints)} fingerprints, {len(all_known_urls)} known URLs, {today_queued} queued today")
daily_cap = 15
remaining = daily_cap - today_queued
print(f"Daily cap: {daily_cap}, remaining: {remaining}")
print(f"Discovery mode: {discovery_mode}")
print(f"Title variants: {title_variants}")

# ─── Results collection ───────────────────────────────────────────
candidates = []
skipped = []
sources_checked = []
sources_blocked = []

# ──────────────────────────────────────────────────────────────────
# 1. LinkedIn (BLOCKED)
# ──────────────────────────────────────────────────────────────────
sources_blocked.append({"linkedin-global": "BLOCKED — sign-in wall / anti-bot (per env config)"})

# ──────────────────────────────────────────────────────────────────
# 2. Indeed (BLOCKED)
# ──────────────────────────────────────────────────────────────────
sources_blocked.append({"indeed-global": "BLOCKED — sign-in wall / ATS wall (per env config)"})

# ──────────────────────────────────────────────────────────────────
# 3. RemoteOK (BLOCKED)
# ──────────────────────────────────────────────────────────────────
sources_blocked.append({"remote-ok": "BLOCKED — anti-bot/redirect (per env config)"})

# ──────────────────────────────────────────────────────────────────
# 4. Wellfound — try, likely blocked
# ──────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("4. Wellfound")
print("=" * 60)
try:
    st, body = fetch_url("https://wellfound.com/jobs", timeout=15)
    print(f"  Wellfound: HTTP {st}, body={len(body)} chars")
    if st == 200:
        job_urls = list(set(re.findall(r'href="(https://wellfound\.com/jobs/\d+[^"])*', body)))
        if len(job_urls) > 0:
            print(f"  Job links found: {len(job_urls)}")
            sources_checked.append("wellfound")
            for jurl in job_urls[:15]:
                if jurl in all_known_urls:
                    continue
                try:
                    st2, jhtml = fetch_url(jurl, timeout=15)
                    if st2 != 200:
                        continue
                    soup2 = BeautifulSoup(jhtml, "html.parser")
                    ld_scripts = soup2.find_all("script", type="application/ld+json")
                    for script in ld_scripts:
                        try:
                            data = json.loads(script.string)
                            if isinstance(data, list):
                                data = data[0]
                            if isinstance(data, dict) and data.get("@type") == "JobPosting":
                                title = data.get("title", "")
                                ho = data.get("hiringOrganization", "")
                                company = ho.get("name", "") if isinstance(ho, dict) else str(ho) if ho else ""
                                loc_data = data.get("jobLocation", {})
                                if isinstance(loc_data, list) and loc_data:
                                    loc_data = loc_data[0]
                                location = "remote"
                                if isinstance(loc_data, dict):
                                    addr = loc_data.get("address", {})
                                    if isinstance(addr, dict):
                                        parts = [addr.get("addressLocality", ""), addr.get("addressRegion", ""), addr.get("addressCountry", "")]
                                        location = ", ".join(p for p in parts if p) or "remote"
                                posted_raw = data.get("datePosted", "")
                                salary_obj = data.get("baseSalary", {})
                                salary_text = ""
                                if isinstance(salary_obj, dict):
                                    val = salary_obj.get("value", {})
                                    if isinstance(val, dict):
                                        salary_text = f"{salary_obj.get('currency', 'USD')} {val.get('minValue', '')} - {val.get('maxValue', '')} {val.get('unitText', '')}"
                                    elif isinstance(val, str):
                                        salary_text = val
                                elif isinstance(salary_obj, str):
                                    salary_text = salary_obj
                                if title_matches(title):
                                    fp = compute_fingerprint(company, title, location)
                                    if fp in existing_fingerprints:
                                        skipped.append(f"DUPLICATE FP: {fp}")
                                    elif jurl in all_known_urls:
                                        skipped.append(f"DUPLICATE URL: {jurl}")
                                    elif not passes_salary(salary_text, salary_floor):
                                        skipped.append(f"SALARY: {company} | {title} | {salary_text}")
                                    else:
                                        posted_at, posted_raw_str = extract_posted(posted_raw)
                                        priority = "high" if (posted_at and posted_at > recent_cutoff) or not posted_at else "normal"
                                        if posted_at and posted_at < week_cutoff:
                                            skipped.append(f"OLD: {company} | {title} | posted {posted_at}")
                                        else:
                                            candidates.append({
                                                "posting_url": jurl, "company": company or "Unknown",
                                                "role_title": title, "location": location or "remote",
                                                "posted_at": posted_at.strftime("%Y-%m-%dT%H:%M:%SZ") if posted_at else None,
                                                "posted_at_raw": posted_raw_str or "",
                                                "salary_disclosed": bool(salary_text), "salary_range": salary_text or None,
                                                "source_board": "Wellfound", "remote_type": "remote",
                                                "discovered_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                                "priority": priority, "posting_fingerprint": fp,
                                            })
                                            print(f"  MATCH: {company} | {title} | priority={priority}")
                                    break
                        except:
                            continue
                except:
                    continue
        else:
            sources_blocked.append({"wellfound": "BLOCKED — HTTP 200 but no job links extracted (JS-rendered or anti-bot)"})
    else:
        sources_blocked.append({"wellfound": f"BLOCKED — HTTP {st}"})
except Exception as e:
    sources_blocked.append({"wellfound": f"BLOCKED/ERROR: {type(e).__name__}: {str(e)[:150]}"})
    print(f"  Wellfound error: {e}")

# ──────────────────────────────────────────────────────────────────
# 5. Remotive API
# ──────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("5. Remotive API")
print("=" * 60)
try:
    search_terms = ["product-manager", "ai-product-manager", "ai-engineer",
                    "automation-engineer", "workflow-engineer", "product-owner",
                    "technical-product-manager", "growth-product-manager",
                    "junior-product-manager", "associate-product-manager",
                    "staff-product-manager", "principal-product-manager"]
    seen_urls = set()
    for term in search_terms:
        encoded = urllib.parse.quote(term)
        url = f"https://remotive.com/api/remote-jobs?limit=100&search={encoded}"
        try:
            st, body = fetch_url(url, timeout=10)
            if st == 200:
                data = json.loads(body)
                jobs = data.get("jobs", [])
                for j in jobs:
                    title = j.get("title", "")
                    if not title_matches(title):
                        continue
                    company = j.get("company_name", "").strip()
                    jurl = j.get("url", "")
                    if jurl in seen_urls:
                        continue
                    seen_urls.add(jurl)
                    posted_raw = j.get("publication_date", "") or j.get("date_posted", "")
                    salary_text = j.get("salary", "")
                    location = "Remote"
                    if jurl in all_known_urls:
                        skipped.append(f"DUPLICATE URL (Remotive): {jurl[:80]}")
                        continue
                    fp = compute_fingerprint(company, title, location)
                    if fp in existing_fingerprints:
                        skipped.append(f"DUPLICATE FP (Remotive): {fp}")
                        continue
                    if not passes_salary(salary_text, salary_floor):
                        skipped.append(f"SALARY (Remotive): {company} | {title} | {salary_text}")
                        continue
                    if company and any(c.lower() in company.lower() for c in companies_exclude):
                        skipped.append(f"COMPANY EXCLUDED (Remotive): {company}")
                        continue
                    posted_at, posted_raw_str = extract_posted(posted_raw)
                    priority = "high" if (posted_at and posted_at > recent_cutoff) or not posted_at else "normal"
                    if posted_at and posted_at < week_cutoff:
                        skipped.append(f"OLD (Remotive): {company} | {title} | posted {posted_at}")
                        continue
                    candidates.append({
                        "posting_url": jurl, "company": company or "Unknown",
                        "role_title": title, "location": location,
                        "posted_at": posted_at.strftime("%Y-%m-%dT%H:%M:%SZ") if posted_at else None,
                        "posted_at_raw": posted_raw_str or "",
                        "salary_disclosed": bool(salary_text), "salary_range": salary_text or None,
                        "source_board": "Remotive", "remote_type": "remote",
                        "discovered_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "priority": priority, "posting_fingerprint": fp,
                    })
                    print(f"  MATCH: {company} | {title} | priority={priority}")
            else:
                print(f"  Remotive '{term}': HTTP {st}")
        except Exception as e:
            print(f"  Remotive '{term}' error: {type(e).__name__}: {str(e)[:80]}")
    sources_checked.append("remotive-api")
except Exception as e:
    sources_blocked.append({"remotive-api": f"BLOCKED/ERROR: {type(e).__name__}: {str(e)[:150]}"})
    print(f"  Remotive error: {e}")

# ──────────────────────────────────────────────────────────────────
# 6. HN "Who is Hiring" via Algolia API
# ──────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("6. HN 'Who is Hiring' via Algolia")
print("=" * 60)
try:
    params = {
        "query": "Ask HN: Who is hiring?",
        "restrictSearchableAttributes": "title",
        "tags": "story",
        "hitsPerPage": 5,
        "numericFilters": f"created_at_i>{int((now - datetime.timedelta(days=30)).timestamp())}",
    }
    url = "https://hn.algolia.com/api/v1/search?" + urllib.parse.urlencode(params)
    st, body = fetch_url(url, timeout=15)
    if st == 200:
        data = json.loads(body)
        hits = data.get("hits", [])
        print(f"  Found {len(hits)} 'who is hiring' stories (recent)")
        for hit in hits:
            obj_id = hit.get("objectID", "")
            hn_url = f"https://news.ycombinator.com/item?id={obj_id}"
            print(f"  Story: {hit.get('title','')} (id={obj_id}, created={hit.get('created_at','')})")
            try:
                st2, html = fetch_url(hn_url, timeout=15)
                if st2 == 200:
                    # Extract text and find hiring comments
                    all_text = re.sub(r"<[^>]+>", "\n", html)
                    all_text = re.sub(r"&#x2014;|&mdash;|&ndash;|&#8212;", "—", all_text)
                    lines = all_text.split("\n")
                    for line in lines:
                        line = line.strip()
                        if len(line) < 20:
                            continue
                        ll = line.lower()
                        if not any(kw in ll for kw in PM_KEYWORDS):
                            continue
                        # Skip if it's a header/navigation line
                        if any(skip in ll for skip in ["who's hiring", "who is hiring", "monthly", "thread", "discussion", "guidelines"]):
                            continue
                        # Try to parse HN hiring format: Company | Role | Location | ...
                        parts = [p.strip() for p in line.split("|")]
                        if len(parts) < 2:
                            continue
                        company = ""
                        role = ""
                        job_url = ""
                        for part in parts[:6]:
                            part_lower = part.lower()
                            if title_matches(part):
                                if not role:
                                    role = part
                            elif len(part) > 2 and len(part) < 60 and not any(
                                kw in part_lower for kw in ["remote", "hiring", "contract", "full-time", "part-time",
                                    "visa", "salary", "compensation", "$", "http", "us", "canada",
                                    "worldwide", "onsite", "hybrid", "equity", "stock", "pto",
                                    "benefits", "w-2", "1099", "today", "yesterday",
                                    "day ago", "week ago", "month", "year", "usd", "eur", "gbp", "ngn"]
                            ) and not re.search(r"[\d\$]", part_lower) and re.search(r"[a-z]", part_lower):
                                if not company:
                                    company = part
                        url_match = re.search(r"((?:https?://|www\.)[^\s|]+)", line)
                        job_url = url_match.group(1) if url_match else hn_url
                        if role and title_matches(role) and company:
                            fp = compute_fingerprint(company, role, "remote")
                            if fp in existing_fingerprints:
                                skipped.append(f"DUPLICATE FP (HN): {fp}")
                                continue
                            if job_url in all_known_urls:
                                skipped.append(f"DUPLICATE URL (HN): {job_url[:80]}")
                                continue
                            candidates.append({
                                "posting_url": job_url, "company": company,
                                "role_title": role, "location": "remote",
                                "posted_at": None, "posted_at_raw": "",
                                "salary_disclosed": False, "salary_range": None,
                                "source_board": "Hacker News (Who is Hiring)", "remote_type": "remote",
                                "discovered_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                "priority": "high", "posting_fingerprint": fp,
                            })
                            print(f"    -> MATCH: {company} | {role} | url={job_url[:60]}")
            except Exception as e:
                print(f"    Thread fetch error: {e}")
        sources_checked.append("hnrss-who-is-hiring")
    else:
        sources_blocked.append({"hnrss-who-is-hiring": f"BLOCKED — HTTP {st}"})
except Exception as e:
    sources_blocked.append({"hnrss-who-is-hiring": f"BLOCKED/ERROR: {type(e).__name__}: {str(e)[:150]}"})
    print(f"  HN error: {e}")

# ──────────────────────────────────────────────────────────────────
# 7. Bing Open-Web Sweep (ATS platforms)
# ──────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("7. Bing Open-Web Sweep (ATS platforms)")
print("=" * 60)

ATS_QUERIES = [
    'site:boards.greenhouse.io "product manager" remote',
    'site:jobs.lever.co "product manager" remote',
    'site:jobs.ashbyhq.com "product manager" remote',
    'site:careers.workday.com "product manager" remote',
    'site:jobs.smartrecruit.co "product manager" remote',
    '"product manager" "AI" remote remote OK 2026 hiring',
    '"AI product manager" remote remote OK 2026 hiring',
    '"AI engineer" remote remote OK 2026 hiring',
    '"automation engineer" remote remote OK 2026 hiring',
    '"technical product manager" remote remote OK 2026 hiring',
]

bing_sources_checked = []
for query in ATS_QUERIES:
    try:
        encoded = urllib.parse.quote(query)
        bing_url = f"https://www.bing.com/search?q={encoded}&count=20"
        st, html = fetch_url(bing_url, timeout=15)
        if st != 200 or len(html) < 500:
            sources_blocked.append({f"open_web_bing_{query[:30]}": f"BLOCKED — HTTP {st}, body={len(html)}"})
            continue
        soup = BeautifulSoup(html, "html.parser")
        result_urls = []
        for li in soup.select("li.b_algo"):
            a = li.select_one("h2 a") or li.select_one("a")
            href = a.get("href", "") if a else ""
            if href and href.startswith("http") and "bing.com" not in href and "microsoft.com" not in href:
                result_urls.append((href, a.get_text(strip=True)[:100] if a else ""))
        # Fallback: extract from all <a> tags
        if not result_urls:
            for a in soup.find_all("a", href=True):
                href = a.get("href")
                if href and href.startswith("http") and "bing.com" not in href and "microsoft.com" not in href:
                    result_urls.append((href, a.get_text(strip=True)[:100]))
        # Deduplicate
        seen_links = set()
        unique_urls = []
        for url, title_text in result_urls:
            if url not in seen_links:
                seen_links.add(url)
                unique_urls.append((url, title_text))
        print(f"  Bing '{query[:50]}': HTTP {st}, {len(unique_urls)} results")
        for job_url, title_text in unique_urls[:15]:
            if job_url in all_known_urls:
                continue
            try:
                st2, job_html = fetch_url(job_url, timeout=15)
                if st2 != 200:
                    continue
                soup2 = BeautifulSoup(job_html, "html.parser")
                ld_scripts = soup2.find_all("script", type="application/ld+json")
                for script in ld_scripts:
                    try:
                        data = json.loads(script.string)
                        if isinstance(data, list):
                            data = data[0]
                        if isinstance(data, dict) and data.get("@type") == "JobPosting":
                            title = data.get("title", "")
                            ho = data.get("hiringOrganization", "")
                            company = ho.get("name", "") if isinstance(ho, dict) else str(ho) if ho else ""
                            loc_data = data.get("jobLocation", {})
                            if isinstance(loc_data, list) and loc_data:
                                loc_data = loc_data[0]
                            location = "remote"
                            if isinstance(loc_data, dict):
                                addr = loc_data.get("address", {})
                                if isinstance(addr, dict):
                                    parts_l = [addr.get("addressLocality", ""), addr.get("addressRegion", ""), addr.get("addressCountry", "")]
                                    location = ", ".join(p for p in parts_l if p) or "remote"
                            posted_raw = data.get("datePosted", "")
                            salary_obj = data.get("baseSalary", {})
                            salary_text = ""
                            if isinstance(salary_obj, dict):
                                val = salary_obj.get("value", {})
                                if isinstance(val, dict):
                                    salary_text = f"{salary_obj.get('currency','USD')} {val.get('minValue','')} - {val.get('maxValue','')} {val.get('unitText','')}"
                                elif isinstance(val, str):
                                    salary_text = val
                            elif isinstance(salary_obj, str):
                                salary_text = salary_obj
                            if title_matches(title):
                                fp = compute_fingerprint(company, title, location)
                                if fp in existing_fingerprints:
                                    skipped.append(f"DUPLICATE FP (Bing): {fp}")
                                elif job_url in all_known_urls:
                                    skipped.append(f"DUPLICATE URL (Bing): {job_url[:80]}")
                                elif not passes_salary(salary_text, salary_floor):
                                    skipped.append(f"SALARY (Bing): {company} | {title} | {salary_text}")
                                elif company and any(c.lower() in company.lower() for c in companies_exclude):
                                    skipped.append(f"COMPANY EXCLUDED (Bing): {company}")
                                else:
                                    posted_at, posted_raw_str = extract_posted(posted_raw)
                                    priority = "high" if (posted_at and posted_at > recent_cutoff) or not posted_at else "normal"
                                    if posted_at and posted_at < week_cutoff:
                                        skipped.append(f"OLD (Bing): {company} | {title} | posted {posted_at}")
                                    else:
                                        candidates.append({
                                            "posting_url": job_url, "company": company or "Unknown",
                                            "role_title": title, "location": location or "remote",
                                            "posted_at": posted_at.strftime("%Y-%m-%dT%H:%M:%SZ") if posted_at else None,
                                            "posted_at_raw": posted_raw_str or "",
                                            "salary_disclosed": bool(salary_text), "salary_range": salary_text or None,
                                            "source_board": "Bing-OpenWeb", "remote_type": "remote" if "remote" in (location or "").lower() else "onsite",
                                            "discovered_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                            "priority": priority, "posting_fingerprint": fp,
                                            "ats_platform": title_text,
                                        })
                                        print(f"  BING MATCH: {company} | {title} | priority={priority}")
                                break
                    except:
                        continue
            except:
                continue
        bing_sources_checked.append(f"open_web_bing_{query[:30]}")
    except Exception as e:
        sources_blocked.append({f"open_web_bing_{query[:30]}": f"BLOCKED/ERROR: {type(e).__name__}: {str(e)[:100]}"})

sources_checked.extend(bing_sources_checked)

# ──────────────────────────────────────────────────────────────────
# 8. Intra-run dedup, daily cap, insert
# ──────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("DEDUP + DAILY CAP")
print("=" * 60)

seen_fp = set()
unique = []
for p in candidates:
    if p["posting_fingerprint"] not in seen_fp:
        seen_fp.add(p["posting_fingerprint"])
        unique.append(p)
    else:
        print(f"  Intra-run dup: {p['company']} | {p['role_title']}")
        skipped.append(f"INTRA-RUN DUP: {p['company']} | {p['role_title']}")

to_queue = unique[:max(0, remaining)]
overflow = unique[max(0, remaining):]

print(f"Total candidates: {len(candidates)}")
print(f"After intra-run dedup: {len(unique)}")
print(f"Daily cap: {daily_cap}, today_queued: {today_queued}, remaining: {remaining}")
print(f"To queue: {len(to_queue)}, overflow (cap): {len(overflow)}")

# Insert into DB
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
inserted = 0
for p in to_queue:
    try:
        cur.execute("""
            INSERT INTO applications
            (posting_url, company, role_title, source_board, posted_at, posted_at_raw,
             discovered_at, priority, posting_fingerprint, remote_type, salary_disclosed,
             salary_range, status, last_failure_stage, ats_platform)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'discovered', NULL, ?)
        """, (p["posting_url"], p["company"], p["role_title"], p["source_board"],
              p.get("posted_at"),
              p.get("posted_at_raw", ""), p["discovered_at"], p["priority"],
              p["posting_fingerprint"], p["remote_type"], p["salary_disclosed"],
              p.get("salary_range"), p.get("ats_platform", None)))
        app_id = cur.lastrowid
        cur.execute("""
            INSERT INTO posting_sources (application_id, posting_url, source_name, discovered_by, is_canonical)
            VALUES (?, ?, ?, 'job_1_boards', 1)
        """, (app_id, p["posting_url"], p["source_board"]))
        conn.commit()
        inserted += 1
        print(f"  INSERTED #{app_id}: {p['company']} | {p['role_title']} | {p['source_board']} | priority={p['priority']}")
    except Exception as e:
        conn.rollback()
        print(f"  INSERT FAILED: {p.get('company', '?')} | {p.get('role_title', '?')} | {e}")
conn.close()

# Update gate state
try:
    with open(GATE_STATE_PATH) as f:
        gate = json.load(f)
except:
    gate = {"sources_checked": [], "sources_blocked": [], "daily_cap": 15, "duplicates": 0, "filtered_out": 0}

gate["sources_checked"] = list(set(gate.get("sources_checked", []) + sources_checked))
existing_blocked_keys = set()
for b in gate.get("sources_blocked", []):
    for k in b:
        existing_blocked_keys.add(k)
for b in sources_blocked:
    for k in b:
        if k not in existing_blocked_keys:
            gate["sources_blocked"].append(b)
            existing_blocked_keys.add(k)

now_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")
gate["last_run_at"] = now_str
gate["new_found"] = len(to_queue)
gate["queued"] = len(to_queue)
gate["duplicates"] = gate.get("duplicates", 0) + len([s for s in skipped if "DUP" in s])
gate["filtered_out"] = len([s for s in skipped if "DUP" not in s])
gate["today_queued"] = today_queued + len(to_queue)
gate["remaining_slots"] = daily_cap - gate["today_queued"]
gate["cap_reached"] = gate["remaining_slots"] <= 0
gate["daily_cap"] = daily_cap
if "hnrss" in str(sources_checked) or "remotive" in str(sources_checked):
    gate["open_web_sweep_last_run"] = now_str

with open(GATE_STATE_PATH, "w") as f:
    json.dump(gate, f, indent=2, default=str)

# ──────────────────────────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"DISCOVERY COMPLETE")
print(f"{'='*60}")
print(f"Sources checked: {sources_checked}")
print(f"Sources blocked: {[list(b.keys())[0] for b in sources_blocked]}")
print(f"Total candidates found: {len(candidates)}")
print(f"Unique candidates: {len(unique)}")
print(f"Inserted into DB: {inserted}")
print(f"Overflow (cap): {len(overflow)}")
print(f"Skipped/duplicates: {len(skipped)}")
print(f"Remaining slots: {gate['remaining_slots']}")

# Write output
summary = {
    "timestamp": now_str,
    "sources_checked": sources_checked,
    "sources_blocked": sources_blocked,
    "total_found_raw": len(candidates),
    "total_unique": len(unique),
    "duplicates": len([s for s in skipped if "DUP" in s]),
    "filtered_out": len([s for s in skipped if "DUP" not in s]),
    "queued": inserted,
    "overflow": len(overflow),
    "remaining_slots": gate["remaining_slots"],
    "daily_cap": daily_cap,
    "today_queued": today_queued + inserted,
    "high_priority": len([p for p in candidates if p.get("priority") == "high"]),
    "normal_priority": len([p for p in candidates if p.get("priority") == "normal"]),
    "all_candidates": candidates[:20],
}
with open(os.path.join(SKILL_ROOT, "shared", ".discovery_run_output.json"), "w") as f:
    json.dump(summary, f, indent=2, default=str)
