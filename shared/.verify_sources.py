import urllib.request, json, urllib.parse, re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

# 1. Check Remotive API
print("=== Remotive API Check ===")
url = f"https://remotive.com/api/remote-jobs?limit=100&search={urllib.parse.quote('product-manager')}"
req = urllib.request.Request(url, headers=HEADERS)
try:
    with urllib.request.urlopen(req, timeout=15) as r:
        body = r.read().decode("utf-8", errors="replace")
    data = json.loads(body)
    jobs = data.get("jobs", [])
    print(f"HTTP 200, found {len(jobs)} jobs")
    for j in jobs[:5]:
        title = j.get("title", "")
        company = j.get("company_name", "")
        url_j = j.get("url", "")
        print(f"  {company} | {title} | {url_j[:60]}")
    # Check if any match PM keywords
    pm_keywords = ["product manager", "ai product manager", "technical product manager",
                   "growth product manager", "associate product manager", "junior product manager",
                   "product owner", "ai engineer", "automation engineer", "workflow engineer",
                   "ai/ml product manager"]
    matches = [j for j in jobs if any(kw in j.get("title","").lower() for kw in pm_keywords)]
    print(f"PM keyword matches: {len(matches)}")
    for m in matches[:5]:
        print(f"  MATCH: {m.get('company_name','')} | {m.get('title','')} | {m.get('url','')[:60]}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")

# 2. Check Wellfound
print("\n=== Wellfound Check ===")
url = "https://wellfound.com/jobs"
req = urllib.request.Request(url, headers=HEADERS)
try:
    with urllib.request.urlopen(req, timeout=15) as r:
        body = r.read().decode("utf-8", errors="replace")
    print(f"HTTP 200, body={len(body)} chars")
    job_urls = list(set(re.findall(r'href="(https://wellfound\.com/jobs/\d+[^\"]*)"', body)))
    print(f"Job links found: {len(job_urls)}")
    for ju in job_urls[:5]:
        print(f"  {ju[:80]}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")

# 3. Check Remotive for AI Engineer also
print("\n=== Remotive AI Engineer Check ===")
url2 = f"https://remotive.com/api/remote-jobs?limit=100&search={urllib.parse.quote('ai-engineer')}"
req2 = urllib.request.Request(url2, headers=HEADERS)
try:
    with urllib.request.urlopen(req2, timeout=15) as r:
        body2 = r.read().decode("utf-8", errors="replace")
    data2 = json.loads(body2)
    jobs2 = data2.get("jobs", [])
    print(f"HTTP 200, found {len(jobs2)} jobs")
    for j in jobs2[:5]:
        print(f"  {j.get('company_name','')} | {j.get('title','')}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
