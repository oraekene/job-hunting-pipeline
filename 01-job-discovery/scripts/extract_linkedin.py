#!/usr/bin/env python3
"""
Extract job postings from LinkedIn search results page.
LinkedIn returned 200 with 285KB of content containing job cards.
Also try the Remotive API as an alternative source since RemoteOK
is a JS-SPA and needs a different approach.
"""
import requests
import re
import json

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

def extract_linkedin_jobs():
    """Extract job postings from LinkedIn search results."""
    url = "https://www.linkedin.com/jobs/search/?keywords=Product+Manager+AI+Engineer+Automation+Workflow+Technical+Product+Owner&locations=Worldwide&f_TPR=r86400&f_WT=1%2C2%2C3&sortBy=DD"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
        print(f"LinkedIn status: {resp.status_code}, length: {len(resp.text)}")
        
        # Save full response for analysis
        with open("C:/Users/rotim/AppData/Local/hermes/cache/browser-use/workspace/linkedin_raw.html", "w", encoding="utf-8") as f:
            f.write(resp.text)
        print(f"Saved raw HTML to cache")
        
        # Look for job data in various formats LinkedIn uses
        # Pattern 1: Job links in the form /jobs/view/{id}
        job_links = re.findall(r'href="(https?://(?:www\.)?linkedin\.com/jobs/view/(\d+)[^"]*)"', resp.text)
        print(f"\nJob view links found: {len(job_links)}")
        for link, job_id in job_links[:15]:
            print(f"  ID={job_id}: {link}")
        
        # Pattern 2: Look for job data in script tags (LinkedIn often embeds JSON)
        scripts = re.findall(r'<script[^>]*>(.*?)</script>', resp.text, re.DOTALL)
        print(f"\nScript tags found: {len(scripts)}")
        
        # Look for job titles in the page text
        # LinkedIn often has data like: "jobTitle":"Product Manager at Company"
        title_matches = re.findall(r'"jobTitle"\s*:\s*"([^"]{5,100})"', resp.text)
        print(f"\njobTitle fields: {len(title_matches)} — first 10: {title_matches[:10]}")
        
        # Look for company names
        company_matches = re.findall(r'"companyName"\s*:\s*"([^"]{2,80})"', resp.text)
        print(f"companyName fields: {len(company_matches)} — first 10: {company_matches[:10]}")
        
        # Look for job posting entity URN
        urn_matches = re.findall(r'urn:li:jobPosting:(\d+)', resp.text)
        print(f"jobPosting URNs: {len(urn_matches)} — first 10: {urn_matches[:10]}")
        
        # Look for location data
        location_matches = re.findall(r'"location"\s*:\s*"([^"]{2,80})"', resp.text)
        print(f"location fields: {len(location_matches)} — first 10: {location_matches[:10]}")
        
        # Look for posted date (relative text like "2 hours ago", "1 day ago")
        time_patterns = re.findall(r'(\d+\s*(?:hour|day|week|month)s?\s*ago)', resp.text, re.IGNORECASE)
        print(f"Posted-time references: {len(time_patterns)} — first 10: {time_patterns[:10]}")
        
        # Also try to find job cards by their structure
        # LinkedIn uses: <li class="..."><a href="/jobs/view/..."><h3>Job Title</h3></a></li>
        card_pattern = re.findall(r'class="[^"]*job-card[^"]*"[^>]*>(.*?)</a>', resp.text, re.DOTALL)
        print(f"Job card elements: {len(card_pattern)}")
        
        # Try entity card links
        entity_links = re.findall(r'<a\s+(?:[^>]*\s+)?href="(/jobs/view/\d+[^"]*)"[^>]*>(.*?)</a>', resp.text, re.DOTALL)
        print(f"Entity links (/jobs/view/): {len(entity_links)}")
        for href, content in entity_links[:10]:
            # Extract text from content
            text = re.sub(r'<[^>]+>', ' ', content)
            text = re.sub(r'\s+', ' ', text).strip()
            print(f"  {href}: {text[:100]}")

    except Exception as e:
        print(f"LinkedIn error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    extract_linkedin_jobs()
