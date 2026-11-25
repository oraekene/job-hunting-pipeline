#!/usr/bin/env python
"""Try multiple approaches to fetch Ashby job posting."""
import json, re, urllib.request, urllib.parse, ssl

url = "https://jobs.ashbyhq.com/turquoise-health/7a416ec3-eef0-41da-8afb-09644fb54e1b"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

# Fetch raw HTML
req = urllib.request.Request(url, headers=headers)
resp = urllib.request.urlopen(req, timeout=25, context=ctx)
html = resp.read().decode('utf-8', errors='replace')

print(f"HTML length: {len(html)}")

# Look for script tags with JSON data (Ashby embeds __NEXT_DATA__ or similar)
# Look for any JSON blobs
scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
print(f"\nFound {len(scripts)} script tags")

# Check for __NEXT_DATA__
next_data = re.search(r'__NEXT_DATA__["\s:=]+(.*?)</script>', html, re.DOTALL)
if not next_data:
    next_data = re.search(r'id=["\']__NEXT_DATA__["\s:=]+(.*?)</script>', html, re.DOTALL)

# Look for any large JSON blobs
for i, s in enumerate(scripts):
    s_stripped = s.strip()
    if len(s_stripped) > 200 and ('{' in s_stripped or '[' in s_stripped):
        print(f"\n--- Script {i} (len={len(s_stripped)}) ---")
        print(s_stripped[:3000])

# Also try the Ashby GraphQL API
# Ashby sites typically expose a public API at api.ashbyhq.com
print("\n\n=== Trying GraphQL API ===")
# The job ID is likely a UUID used in the Ashby API
job_id = "7a416ec3-eef0-41da-8afb-09644fb54e1b"
company_slug = "turquoise-health"

# Try the Ashby public GraphQL endpoint
api_url = "https://api.ashbyhq.com/graphql"
query = """
query {
  jobPosting(id: "%s") {
    id
    name
    locationName
    teamName
    departmentName
    description
    responsibilities
    requirements
    qualifications
    compensation
    url
    postedAt
    employmentType
    customJobPostingLink
    department {
      name
    }
    location {
      name
    }
    company {
      name
    }
  }
}
""" % job_id

body = json.dumps({"query": query}).encode('utf-8')
api_req = urllib.request.Request(api_url, headers={
    **headers,
    'Content-Type': 'application/json',
}, data=body)

try:
    api_resp = urllib.request.urlopen(api_req, timeout=25, context=ctx)
    api_data = json.loads(api_resp.read().decode('utf-8', errors='replace'))
    print(json.dumps(api_data, indent=2)[:5000])
except Exception as e:
    print(f"GraphQL API error: {e}")

# Try fetching the page itself with the job ID in the URL path
print("\n\n=== Trying Ashby public job API ===")
api_url2 = f"https://api.ashbyhq.com/public/job-posting/{job_id}"
try:
    api_req2 = urllib.request.Request(api_url2, headers=headers)
    api_resp2 = urllib.request.urlopen(api_req2, timeout=25, context=ctx)
    api_data2 = json.loads(api_resp2.read().decode('utf-8', errors='replace'))
    print(json.dumps(api_data2, indent=2)[:5000])
except Exception as e:
    print(f"Public API error: {e}")
