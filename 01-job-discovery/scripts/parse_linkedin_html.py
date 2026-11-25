#!/usr/bin/env python3
"""
Extract all job postings from saved LinkedIn HTML.
Each job card has: URN/id, title, company, location, posted time, work type.
"""
import re
import json
from datetime import datetime, timezone

HTML_PATH = "C:/Users/rotim/AppData/Local/hermes/cache/browser-use/workspace/linkedin_raw.html"

with open(HTML_PATH, "r", encoding="utf-8") as f:
    html = f.read()

print(f"HTML length: {len(html)}")

# Find all job card divs with data-entity-urn
# Pattern: <div class="base-card..." data-entity-urn="urn:li:jobPosting:ID"
job_card_pattern = r'data-entity-urn="urn:li:jobPosting:(\d+)"[^>]*>(.*?)</div>\s*</div>\s*</div>\s*</a>'

# More robust: find each job card by its URN, then extract the enclosing div
# Let's find all URN positions and extract the card content
urn_positions = [(m.start(), m.group(1)) for m in re.finditer(r'urn:li:jobPosting:(\d+)', html)]
print(f"Found {len(urn_positions)} job cards\n")

jobs = []
for i, (pos, job_id) in enumerate(urn_positions):
    # Get a chunk of HTML around this URN (each card is ~2000 chars)
    start = max(0, pos - 20)
    end = min(len(html), pos + 3000)
    
    # Find the start of the div containing this URN
    # Look backwards for the opening div
    card_start = html.rfind('<div class="base-card', 0, start)
    if card_start == -1:
        card_start = pos - 100  # fallback
    
    # Find the end of the card (the closing div structure)
    # Look for the next URN or end marker
    if i + 1 < len(urn_positions):
        next_pos = urn_positions[i + 1][0]
        card_end = min(len(html), next_pos)
    else:
        card_end = end
    
    card_html = html[card_start:card_end]
    
    # Extract job title - look in h3 or a tag with class containing 'job'
    title = None
    # Try: <h3[^>]*>([^<]+)</h3>
    title_matches = re.findall(r'<h3[^>]*>([^<]+(?:\s+[^<\s]+)*)</h3>', card_html)
    if title_matches:
        title = title_matches[0].strip()
    
    # Try: data-control-id attribute with title
    if not title:
        title_matches = re.findall(r'aria-label="([^"]+(?:Product|Manager|Engineer|Owner|Workflow|Automation)[^"]*)"', card_html)
        if title_matches:
            title = title_matches[0].strip()
    
    # Try: alt text of image (LinkedIn uses this for job titles sometimes)
    if not title:
        alt_matches = re.findall(r'alt="([^"]+(?:Product|Manager|Engineer|Owner|Workflow|Automation|AI)[^"]*)"', card_html)
        if alt_matches:
            title = alt_matches[0].strip()
    
    # Try: text in <a> tags
    if not title:
        # Look for the job title in the link text
        link_texts = re.findall(r'<a[^>]*>(.*?)</a>', card_html, re.DOTALL)
        for lt in link_texts:
            lt_clean = re.sub(r'<[^>]+>', ' ', lt)
            lt_clean = re.sub(r'\s+', ' ', lt_clean).strip()
            if len(lt_clean) > 10 and ('Product' in lt_clean or 'Manager' in lt_clean or 'Engineer' in lt_clean or 'AI' in lt_clean or 'Workflow' in lt_clean or 'Owner' in lt_clean):
                title = lt_clean[:100]
                break
    
    # Extract company name
    company = None
    # Pattern: /company/{slug} in trk URL
    company_matches = re.findall(r'/company/([a-zA-Z0-9_-]+)[^"]*trk=public_jobs_jserp', card_html)
    if company_matches:
        company = company_matches[0].replace('-', ' ').title()
    
    # Try: text after "Company" or in a specific div
    if not company:
        company_matches = re.findall(r'company/([^/"\s]+)', card_html)
        if company_matches:
            company = company_matches[0].replace('-', ' ').title()
    
    # Extract location
    location = None
    # Location usually appears after company name, before posted time
    # Pattern: company_name">Location</a> or similar
    loc_matches = re.findall(r'>([A-Za-z][A-Za-z\s,]+(?:[A-Z]{2}|\b(?:Remote|Worldwide|United States)))\s*<', card_html)
    if loc_matches:
        location = loc_matches[0].strip()
    
    # Try: text near the posted time
    if not location:
        # Look for city/state pattern
        loc_matches = re.findall(r'([A-Za-z]+\s*,\s*[A-Z]{2})', card_html)
        if loc_matches:
            location = loc_matches[-1].strip()
    
    # Extract posted time (relative text)
    posted_raw = None
    time_matches = re.findall(r'(\d+\s*(?:minute|hour|day|week|month|year)s?\s*ago|Just\s+now|Today)', card_html, re.IGNORECASE)
    if time_matches:
        posted_raw = time_matches[0].strip()
    
    # Extract work type (Remote/Hybrid/On-site)
    work_type = None
    if 'Remote' in card_html or 'remote' in card_html.lower():
        work_type = 'remote'
    elif 'Hybrid' in card_html or 'hybrid' in card_html.lower():
        work_type = 'hybrid'
    
    # Extract job URL
    job_url = f"https://www.linkedin.com/jobs/view/{job_id}/"
    
    # Check for "Be an early applicant" badge
    early_applicant = "Be an early applicant" in card_html
    
    jobs.append({
        "id": job_id,
        "title": title,
        "company": company,
        "location": location,
        "posted_raw": posted_raw,
        "work_type": work_type,
        "job_url": job_url,
        "early_applicant": early_applicant,
        "source": "linkedin-global",
    })

# Print extracted jobs
print(f"\nExtracted {len(jobs)} jobs:\n")
for job in jobs:
    print(f"  ID: {job['id']}")
    print(f"  Title: {job['title']}")
    print(f"  Company: {job['company']}")
    print(f"  Location: {job['location']}")
    print(f"  Posted: {job['posted_raw']}")
    print(f"  Work type: {job['work_type']}")
    print(f"  Early applicant: {job['early_applicant']}")
    print(f"  URL: {job['job_url']}")
    print()

# Summary stats
valid_jobs = [j for j in jobs if j['title'] and j['company']]
print(f"\nJobs with title+company: {len(valid_jobs)} / {len(jobs)}")

# Save to JSON
with open("C:/Users/rotim/AppData/Local/hermes/cache/browser-use/workspace/linkedin_jobs.json", "w") as f:
    json.dump(jobs, f, indent=2)
print(f"\nSaved to linkedin_jobs.json")
