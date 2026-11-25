#!/usr/bin/env python3
"""
Analyze the saved LinkedIn HTML to find job data patterns.
The probe showed job URNs and timestamps exist, but extraction patterns missed titles/companies.
Search for the actual data structure in the HTML.
"""
import re

HTML_PATH = "C:/Users/rotim/AppData/Local/hermes/cache/browser-use/workspace/linkedin_raw.html"

with open(HTML_PATH, "r", encoding="utf-8") as f:
    html = f.read()

print(f"HTML length: {len(html)}")

# 1. Find all jobPosting URNs and their positions
urn_positions = [(m.start(), m.group(1)) for m in re.finditer(r'urn:li:jobPosting:(\d+)', html)]
print(f"\n1. JobPosting URNs: {len(urn_positions)}")
if urn_positions:
    print(f"   First URN at position {urn_positions[0][0]}: {urn_positions[0][1]}")
    print(f"   Last URN at position {urn_positions[-1][0]}: {urn_positions[-1][1]}")
    
    # Show context around the first URN
    pos = urn_positions[0][0]
    context = html[max(0, pos-200):pos+200]
    print(f"\n   Context around first URN:")
    print(f"   {context}")

# 2. Find the text around job data - search for "jobPostingEntity" or similar
patterns = [
    "jobPostingEntity",
    "jobPostingCache",
    "jobsJobResults",
    "jobResults",
    "searchResult",
    "entityResult",
    "jobCard",
    "job-posting",
    "linkedin:jobs",
]
for p in patterns:
    count = html.count(p)
    if count > 0:
        # Find first occurrence
        idx = html.find(p)
        snippet = html[max(0, idx-50):idx+100]
        snippet = re.sub(r'<[^>]+>', ' ', snippet)
        snippet = re.sub(r'\s+', ' ', snippet).strip()
        print(f"\n2. Pattern '{p}': {count} occurrences. Context: ...{snippet}...")

# 3. Look for what's near the URNs - LinkedIn often has data in a specific format
if urn_positions:
    pos = urn_positions[0][0]
    # Search backwards for nearby text
    nearby = html[max(0, pos-500):pos+500]
    # Look for jobTitle, company, location in the nearby text
    print("\n3. Searching for job metadata near URNs...")
    nearby_matches = re.findall(r'"(jobTitle|title|companyName|company|location|jobPostingUrl|url|postedAt|posted)"\s*:\s*"([^"]+)"', nearby)
    if nearby_matches:
        print(f"   Found {len(nearby_matches)} metadata fields near first URN: {nearby_matches}")
    
    # Also check if data is in a different format (e.g., single-quoted, or escaped)
    nearby_escaped = re.findall(r'\\"([^\\"]{3,80})\\"', nearby)
    if nearby_escaped:
        print(f"   Found {len(nearby_escaped)} escaped string values near first URN:")
        for v in nearby_escaped[:10]:
            print(f"     - {v}")

# 4. Try to find JSON data blocks
json_blocks = re.findall(r'\{[^{}]*"jobPostingId"[^{}]*\}', html)
print(f"\n4. JSON blocks with jobPostingId: {len(json_blocks)}")
if json_blocks:
    print(f"   First block: {json_blocks[0][:300]}")

# 5. Search for all occurrences of "jobTitle" (case-insensitive)
all_titles = re.findall(r'(?:jobTitle|job_title|title)\s*[:=]\s*[\'"]([^\'"]{5,100})[\'"]', html, re.IGNORECASE)
print(f"\n5. All title-like fields: {len(all_titles)} — first 10: {all_titles[:10]}")

# 6. Search for company-like data near URNs
if urn_positions:
    # Check a few URNs for surrounding text
    for i in [0, 1, 5, 10, 20]:
        if i < len(urn_positions):
            pos = urn_positions[i][0]
            nearby = html[max(0, pos-1000):pos+1000]
            # Look for text between specific delimiters
            text_only = re.sub(r'<[^>]+>', ' ', nearby)
            text_only = re.sub(r'\s+', ' ', text_only).strip()
            print(f"\n6. URN #{i} ({urn_positions[i][1]}) text context (1000 chars around):")
            print(f"   {text_only[:200]}...{text_only[-200:]}")

# 7. Check for remote_type or work_type
remote_matches = re.findall(r'(?:remoteType|workType|workLocationStyle)\s*[:=]\s*[\'"]([^\'"]+)[\'"]', html)
print(f"\n7. remoteType/workType fields: {len(remote_matches)} — {remote_matches[:5]}")

# 8. Search for salary data
salary_matches = re.findall(r'(?:salary|payRange|estimateAmount)\s*[:=]\s*[\'"]([^\'"]+)[\'"]', html, re.IGNORECASE)
print(f"8. Salary fields: {len(salary_matches)} — {salary_matches[:5]}")
