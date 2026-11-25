#!/usr/bin/env python3
"""Quick: Parse Remotive HTML for PM job links."""
import urllib.request, re, json
from datetime import datetime, timezone

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

TITLE_VARIANTS = [
    "product manager", "ai product manager", "ai engineer",
    "automation engineer", "associate product manager", "junior product manager",
    "workflow engineer", "product owner", "technical product manager",
    "growth product manager", "ai/ml product manager",
]

def title_matches(title):
    tl = title.lower().strip()
    return any(v in tl for v in TITLE_VARIANTS)

# Fetch Remotive all jobs page
req = urllib.request.Request('https://remotive.com/remote-jobs', headers=HEADERS)
resp = urllib.request.urlopen(req, timeout=15)
html = resp.read().decode('utf-8', errors='replace')
print(f"Remotive HTML: {len(html)} chars")

# Remotive job cards - look for links and titles
# Job links pattern: href="/remote-jobs/company-title"
job_links = re.findall(r'href="(/remote-jobs/[a-z0-9-]+)"', html)
job_links = list(dict.fromkeys(job_links))
print(f"Unique job link paths: {len(job_links)}")

pm_found = []
for path in job_links:
    full_url = f'https://remotive.com{path}'
    # Extract title from path
    slug = path.replace('/remote-jobs/', '')
    title_guess = re.sub(r'^\d+-', '', slug).replace('-', ' ').title()
    if title_matches(title_guess):
        pm_found.append((title_guess, full_url))

print(f"\nPM matches from paths: {len(pm_found)}")
for t, u in pm_found:
    print(f"  {t} | {u}")

# Also look for job cards with JSON-LD data
# Remotive might embed job data in JSON-LD or script tags
scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
for s in scripts:
    if 'job' in s.lower() or 'position' in s.lower():
        # Look for JSON-LD or structured data
        ld_match = re.search(r'\{[^{}]*"job"[^{}]*\}', s)
        if ld_match:
            print(f"  Found job data in script tag")

# Print all paths for context
print(f"\nAll {len(job_links)} job paths:")
for p in job_links:
    print(f"  {p}")
