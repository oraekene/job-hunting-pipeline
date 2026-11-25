#!/usr/bin/env python3
"""
Fetch Wellfound jobs with proper decompression. Also try LinkedIn, Indeed, RemoteOK to confirm block status.
"""
import requests
import re
import json

# Use gzip/deflate only (no brotli) to avoid decompression issues
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",  # NO brotli
    "Connection": "keep-alive",
}

def try_fetch(url, label):
    """Fetch a URL and report status + whether it's behind a login wall."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
        body = resp.text if resp.text else ""
        print(f"\n{'='*60}")
        print(f"{label}: {url}")
        print(f"Status: {resp.status_code}")
        print(f"Final URL: {resp.url}")
        print(f"Content length: {len(resp.text) if resp.text else 'N/A'}")
        print(f"Content-Type: {resp.headers.get('Content-Type', 'N/A')}")
        
        # Check for login wall indicators
        body_lower = body.lower()[:2000]
        login_words = ['sign in', 'log in', 'login', 'password', 'by continuing', 
                       'create account', 'register', 'cookie', 'gdpr', 'consent']
        found_login = [w for w in login_words if w in body_lower]
        
        # Check for error/blocked indicators
        blocked_words = ['403', 'forbidden', 'access denied', 'blocked', 'captcha', 'cloudflare',
                         'security check', 'rate limit', 'too many requests']
        found_blocked = [w for w in blocked_words if w in body_lower]
        
        # Look for job content
        job_words = ['job', 'position', 'hiring', 'career', 'product', 'manager', 'engineer']
        found_jobs = [w for w in job_words if w in body_lower]
        
        print(f"Login indicators: {found_login[:5]}")
        print(f"Blocked indicators: {found_blocked[:5]}")
        print(f"Job-related words: {found_jobs[:10]}")
        
        # Print body preview (text only, no binary)
        text = re.sub(r'<[^>]+>', ' ', body)
        text = re.sub(r'\s+', ' ', text).strip()
        preview = text[:1500] if len(text) > 0 else "(empty or binary)"
        print(f"Body preview: {preview}")
        
        return resp
    except Exception as e:
        print(f"\n{'='*60}")
        print(f"{label}: {url}")
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    # Wellfound
    try_fetch("https://wellfound.com/jobs", "Wellfound")
    
    # LinkedIn
    try_fetch("https://www.linkedin.com/jobs/search/?keywords=Product+Manager&f_TPR=r86400&f_WT=1%2C2%2C3&sortBy=DD", "LinkedIn")
    
    # Indeed
    try_fetch("https://www.indeed.com/worldwide/implement?q=Product+Manager&sort=date", "Indeed")
    
    # RemoteOK
    try_fetch("https://remoteok.com/remote-product-manager-jobs", "RemoteOK")
