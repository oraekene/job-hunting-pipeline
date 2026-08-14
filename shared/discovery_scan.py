#!/usr/bin/env python3
"""
Job discovery scanner - scans RemoteOK and extracts relevant postings
"""
import json
import re
from datetime import datetime, timezone

# Read the RemoteOK JSON cache file
cache_file = '/c/Users/rotim/AppData/Local/hermes/cache/web/remoteok.com-c064fd7833.md'

with open(cache_file, 'r') as f:
    content = f.read()

# Extract JSON from the markdown code block
lines = content.strip().split('\n')
json_str = '\n'.join(lines[1:-1])  # Remove ```json and ```

# Parse the JSON
jobs = json.loads(json_str)

# Title variants to match (from target-profile.yaml)
title_variants = [
    'Product Manager', 'AI Product Manager', 'AI Engineer', 'Automation Engineer',
    'Workflow Engineer', 'Associate Product Manager', 'Junior Product Manager',
    'Product Owner', 'Technical Product Manager', 'Growth Product Manager', 'AI/ML Product Manager'
]

# Locations allowed (from target-profile.yaml - Worldwide/remote-ok)
allowed_locations = ['Worldwide', 'remote', 'Remote']

# Filter jobs that match our title variants
matching_jobs = []
for job in jobs:
    if isinstance(job, dict):
        position = job.get('position', '')
        company = job.get('company', '')
        location = job.get('location', '')
        epoch = job.get('epoch', 0)
        apply_url = job.get('apply_url', job.get('url', ''))
        
        # Check if position matches any title variant
        position_lower = position.lower()
        for variant in title_variants:
            variant_lower = variant.lower()
            # Match if variant contains position keywords or position contains variant keywords
            if variant_lower in position_lower or position_lower in variant_lower:
                # Check location - Worldwide or remote is allowed
                location_allowed = any(loc.lower() in location.lower() for loc in allowed_locations) if location else True
                
                # Convert epoch to ISO date
                if epoch:
                    posted_date = datetime.fromtimestamp(epoch, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
                else:
                    posted_date = job.get('date', datetime.now(tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
                
                matching_jobs.append({
                    'company': company,
                    'role_title': position,
                    'posting_url': apply_url,
                    'location': location,
                    'posted_at': posted_date,
                    'source': 'remoteok'
                })
                break

print(f"Found {len(matching_jobs)} matching job postings from RemoteOK")
for job in matching_jobs[:10]:
    print(f"  - {job['company']}: {job['role_title']} ({job['posted_at']})")
    print(f"    URL: {job['posting_url']}")