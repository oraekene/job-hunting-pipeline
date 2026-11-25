#!/usr/bin/env python3
"""
Deep extraction from LinkedIn and RemoteOK — both returned 200 with content.
Look for actual job listing data in the HTML.
"""
import requests
import re
import json
from urllib.parse import urljoin

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

def extract_linkedin_jobs():
    """Try to extract job data from LinkedIn search results."""
    url = "https://www.linkedin.com/jobs/search/?keywords=Product+Manager+AI+Engineer+Automation+Workflow&locations=Worldwide&f_TPR=r86400&f_WT=1%2C2%2C3&sortBy=DD"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
        print(f"LinkedIn status: {resp.status_code}, length: {len(resp.text)}")
        
        # Check if we got actual job data or a login/challenge page
        # Look for the "4,000+ Product Manager jobs" text which indicates results loaded
        if "jobs in" in resp.text.lower() and "product manager" in resp.text.lower():
            print("LinkedIn: appears to have loaded job search results page")
            
            # Try to find job cards - LinkedIn uses various selectors
            # Look for job title patterns in the HTML
            job_patterns = [
                r'"title"\s*:\s*"([^"]+)"',
                r'"jobTitle"\s*:\s*"([^"]+)"',
                r'data-job-id=["\']([^"\']+)',
                r'"companyName"\s*:\s*"([^"]+)"',
                r'"jobPostingUrl"\s*:\s*"([^"]+)"',
                r'"jobPostingId"\s*:\s*"([^"]+)"',
            ]
            for pattern, name in [(p, n) for p, n in job_patterns]:
                matches = re.findall(pattern, resp.text)
                if matches:
                    print(f"  LinkedIn pattern '{name}': {len(matches)} matches — first 5: {matches[:5]}")
            
            # Try to find the JSON data embedded in the page (LinkedIn uses __NEXT_DATA__ or similar)
            # LinkedIn sometimes embeds data in script tags
            script_data = re.findall(r'<script[^>]*>(.*?)</script>', resp.text, re.DOTALL)
            print(f"  LinkedIn: found {len(script_data)} script tags")
            
            # Check for job card divs
            job_cards = re.findall(r'job-card|jobCard|jobs-job-card', resp.text)
            print(f"  LinkedIn: found {len(job_cards)} job card references")
            
            # Check for the specific job listing structure
            # LinkedIn typically has elements like:
            # <a href="/jobs/view/12345" ...>Job Title</a>
            job_links = re.findall(r'href="(/jobs/view/\d+[^"]*)"', resp.text)
            print(f"  LinkedIn: found {len(job_links)} job links — first 5: {job_links[:5]}")
            
            # Check if there's a sign-in wall by looking for specific patterns
            if 'sign in to view' in resp.text.lower() or 'create account' in resp.text.lower():
                print("  LinkedIn: WARNING - sign in wall detected")
            
        else:
            print("LinkedIn: page loaded but no job content detected — likely a challenge/landing page")
            # Print more of the body for debugging
            text = re.sub(r'<[^>]+>', ' ', resp.text)
            text = re.sub(r'\s+', ' ', text).strip()
            print(f"  Body preview: {text[:500]}")
            
    except Exception as e:
        print(f"LinkedIn error: {e}")

def extract_remoteok_jobs():
    """Try to extract job data from RemoteOK."""
    url = "https://remoteok.com/remote-product-manager-jobs"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
        print(f"\n{'='*60}")
        print(f"RemoteOK status: {resp.status_code}, length: {len(resp.text)}")
        
        # RemoteOK has a known structure with job cards
        # Each job is typically in a <tr> or <div> with class "job"
        
        # Look for job rows
        job_rows = re.findall(r'class="job[^"]*"', resp.text)
        print(f"  RemoteOK: found {len(job_rows)} job-row class references")
        
        # Look for job title links
        # RemoteOK typically has: <a class="job-title" href="/jobs/..." title="Job Title">
        job_titles = re.findall(r'<a[^>]*class="job-title"[^>]*>([^<]+)', resp.text, re.IGNORECASE)
        print(f"  RemoteOK: found {len(job_titles)} job-title links — first 10: {job_titles[:10]}")
        
        # Try alternative patterns
        title_pattern = re.findall(r'data-id="(\d+)"[^>]*>([^<]+)', resp.text)
        print(f"  RemoteOK: found {len(title_pattern)} data-id title matches")
        
        # Look for company names
        companies = re.findall(r'data-company="([^"]+)"', resp.text)
        print(f"  RemoteOK: found {len(companies)} company data attributes — first 10: {companies[:10]}")
        
        # Look for job links (RemoteOK uses /remote-[category]-jobs for the listing page
        # and /companies/[company]/jobs/[id] for individual jobs
        job_links = re.findall(r'href="(/[^"]*job[^"]*)"', resp.text, re.IGNORECASE)
        print(f"  RemoteOK: found {len(job_links)} job links — first 10: {job_links[:10]}")
        
        # Check for JSON data in script tags
        json_scripts = re.findall(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', resp.text, re.DOTALL)
        print(f"  RemoteOK: found {len(json_scripts)} JSON script tags")
        for i, js in enumerate(json_scripts[:3]):
            print(f"  JSON script {i}: {js[:300]}")
            
        # Also look for the all jobs data structure
        # RemoteOK often embeds data in window.location or __NEXT_DATA__
        next_data = re.search(r'<script id="__NEXT_DATA__".*?>(.*?)</script>', resp.text, re.DOTALL)
        if next_data:
            print(f"  RemoteOK: found __NEXT_DATA__ ({len(next_data.group(1))} chars)")
        else:
            print(f"  RemoteOK: no __NEXT_DATA__ found")
            
        # Print body preview for debugging
        text = re.sub(r'<[^>]+>', ' ', resp.text)
        text = re.sub(r'\s+', ' ', text).strip()
        print(f"\n  RemoteOK body preview: {text[:1000]}")
        
    except Exception as e:
        print(f"RemoteOK error: {e}")

if __name__ == "__main__":
    extract_linkedin_jobs()
    extract_remoteok_jobs()
