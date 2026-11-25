#!/usr/bin/env python
import json, urllib.request

req = urllib.request.Request('https://remotive.com/api/remote-jobs',
    headers={'User-Agent': 'Mozilla/5.0'})
resp = urllib.request.urlopen(req, timeout=15)
data = json.loads(resp.read().decode())
jobs = data.get('jobs', [])
print(f"Total jobs from Remotive API: {len(jobs)}")

pm_titles = ['product manager', 'ai product manager', 'ai engineer',
             'automation engineer', 'associate product manager', 'junior product manager',
             'workflow engineer', 'product owner', 'technical product manager',
             'growth product manager', 'ai/ml product manager']

for j in jobs:
    title = j.get('title', '')
    if any(v in title.lower() for v in pm_titles):
        print(f"Title: {title}")
        print(f"  Company: {j.get('company_name','')}")
        print(f"  Salary: {repr(j.get('salary',''))}")
        print(f"  URL: {j.get('url','')}")
        print(f"  Location: {j.get('candidate_required_location','')}")
        print(f"  Date posted: {j.get('date_posted_at','')}")
        print(f"  Epoch: {j.get('epoch','')}")
        print(f"  All keys: {list(j.keys())}")
        print("---")
