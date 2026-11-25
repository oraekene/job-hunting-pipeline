#!/usr/bin/env python
"""Check all RemoteOK API titles for PM matches."""
import json, urllib.request

TITLE_VARIANTS = [
    "product manager", "ai product manager", "ai engineer",
    "automation engineer", "associate product manager", "junior product manager",
    "workflow engineer", "product owner", "technical product manager",
    "growth product manager", "ai/ml product manager"
]

def title_matches_variant(title):
    tl = title.lower()
    for variant in TITLE_VARIANTS:
        if variant in tl:
            return True, variant
    return False, None

req = urllib.request.Request('https://remoteok.com/api',
    headers={'User-Agent': 'Mozilla/5.0'})
resp = urllib.request.urlopen(req, timeout=15)
jobs = json.loads(resp.read().decode())
if isinstance(jobs, dict):
    jobs = jobs.get('jobs', jobs.get('data', []))

print(f"Total RemoteOK jobs: {len(jobs)}")
print("\nAll titles containing PM keywords:")
for j in jobs:
    title = j.get('title', '')
    matched, variant = title_matches_variant(title)
    if matched:
        company = j.get('company', '')
        url = j.get('url', '')
        loc = j.get('location', '')
        sal = j.get('salary', '')
        epoch = j.get('epoch', 0)
        print(f"  [+] {company}: {title} (matched: {variant})")
        print(f"      URL: {url}")
        print(f"      Loc: {loc}")
        print(f"      Sal: {sal}")
        print(f"      Epoch: {epoch}")
        print()

print("\n=== ALL titles (for manual review) ===")
for i, j in enumerate(jobs):
    print(f"  {i}: {j.get('title','')}")
