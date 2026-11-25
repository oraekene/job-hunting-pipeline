import urllib.request, json, urllib.parse, re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

pm_keywords = ["product manager", "ai product manager", "technical product manager",
               "growth product manager", "associate product manager", "junior product manager",
               "product owner", "ai engineer", "automation engineer", "workflow engineer",
               "ai/ml product manager"]

# Check if Remotive returns different results for different search terms
terms = ["product-manager", "product-owner", "workflow-engineer", "automation-engineer",
         "technical-product-manager", "growth-product-manager", "junior-product-manager",
         "associate-product-manager"]

all_jobs = {}
for term in terms:
    url = f"https://remotive.com/api/remote-jobs?limit=100&search={urllib.parse.quote(term)}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8", errors="replace"))
        jobs = data.get("jobs", [])
        for j in jobs:
            job_id = j.get("id")
            if job_id not in all_jobs:
                all_jobs[job_id] = j
        pm_matches = [j for j in jobs if any(kw in j.get("title","").lower() for kw in pm_keywords)]
        print(f"  {term}: {len(jobs)} jobs, {len(pm_matches)} PM matches")
        for m in pm_matches:
            print(f"    -> {m.get('company_name','')} | {m.get('title','')} | id={m.get('id')}")
    except Exception as e:
        print(f"  {term}: ERROR {type(e).__name__}: {e}")

print(f"\nTotal unique jobs across all terms: {len(all_jobs)}")
# Check for any PM matches not seen before
new_pm = []
for job_id, j in all_jobs.items():
    title = j.get("title", "").lower()
    if any(kw in title for kw in pm_keywords):
        new_pm.append(j)
print(f"Total unique PM matches: {len(new_pm)}")
for j in new_pm:
    print(f"  {j.get('company_name','')} | {j.get('title','')} | {j.get('url','')[:70]} | salary={j.get('salary','N/A')}")
