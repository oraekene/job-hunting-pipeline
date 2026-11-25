#!/usr/bin/env python3
"""
Scan Wellfound (AngelList) job listings page for new postings.
Wellfound is a JavaScript SPA — check for embedded JSON data in the HTML.
"""
import requests
import re
import json
from datetime import datetime, timezone

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

def fetch_wellfound():
    """Fetch Wellfound jobs page and look for embedded job data."""
    url = "https://wellfound.com/jobs"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
        print(f"Status: {resp.status_code}")
        print(f"Final URL: {resp.url}")
        print(f"Content length: {len(resp.text)}")
        
        # Look for __NEXT_DATA__ (Next.js SSR data)
        next_data_match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', resp.text, re.DOTALL)
        if next_data_match:
            print("Found __NEXT_DATA__ (Next.js data)")
            try:
                data = json.loads(next_data_match.group(1))
                print(f"Next data keys: {list(data.keys()) if isinstance(data, dict) else 'not dict'}")
                # Look for jobs in the data
                data_str = json.dumps(data)
                print(f"Next data length: {len(data_str)}")
                # Search for job-related content
                if 'job' in data_str.lower():
                    print("Contains job-related content")
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")
        
        # Look for any JSON-LD data
        jsonld_matches = re.findall(r'<script type="application/ld\+json">(.*?)</script>', resp.text, re.DOTALL)
        print(f"\nFound {len(jsonld_matches)} JSON-LD blocks")
        for i, m in enumerate(jsonld_matches[:3]):
            try:
                data = json.loads(m.strip())
                print(f"  JSON-LD #{i}: type={data.get('@type', 'unknown')}, keys={list(data.keys())[:10]}")
            except:
                print(f"  JSON-LD #{i}: parse error")
        
        # Check if page has login/sign-in wall
        login_indicators = ['sign in', 'log in', 'linkedin', 'google', 'angel', 'email', 'password']
        body_text = resp.text.lower()
        # Count how many login indicators appear
        found_indicators = [w for w in login_indicators if w in body_text]
        print(f"\nLogin indicators found: {found_indicators[:10]}")
        
        # Look for job listing elements
        job_patterns = [
            (r'jobTitle["\']?\s*[:=]\s*["\']([^"\']+)', 'jobTitle'),
            (r'"title"[^"]*"([^"]+)"', 'title field'),
            (r'roleName["\']?\s*[:=]\s*["\']([^"\']+)', 'roleName'),
            (r'data-job-id=["\']([^"\']+)', 'data-job-id'),
            (r'job_id["\']?\s*[:=]\s*["\']([^"\']+)', 'job_id'),
        ]
        for pattern, name in job_patterns:
            matches = re.findall(pattern, resp.text, re.IGNORECASE)
            if matches:
                print(f"  Pattern '{name}': found {len(matches)} matches — first 5: {matches[:5]}")
        
        # Try the API endpoint
        api_url = "https://wellfound.com/api/jobs"
        try:
            api_resp = requests.get(api_url, headers=HEADERS, timeout=15)
            print(f"\nAPI /api/jobs status: {api_resp.status_code}, length: {len(api_resp.text)}")
            if api_resp.status_code == 200:
                print(f"API content preview: {api_resp.text[:500]}")
        except Exception as e:
            print(f"\nAPI /api/jobs failed: {e}")

        # Also try fetching the body text for inspection
        print(f"\nBody text preview (first 2000 chars):")
        # Strip HTML tags for readability
        text = re.sub(r'<[^>]+>', ' ', resp.text)
        text = re.sub(r'\s+', ' ', text)
        print(text[:2000])
        
    except Exception as e:
        print(f"Error fetching Wellfound: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fetch_wellfound()
