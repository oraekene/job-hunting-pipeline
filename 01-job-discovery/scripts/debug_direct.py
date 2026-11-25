#!/usr/bin/env python3
"""
Test direct access to job boards and ATS career pages.
"""
import re, json
from urllib.parse import quote
import urllib.request
import urllib.error

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml", "Accept-Language": "en-US,en;q=0.9"})
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.read().decode("utf-8", errors="replace"), resp.getcode(), None
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if hasattr(e, 'read') else None
        return body, e.code, str(e)
    except Exception as e:
        return None, None, str(e)

# Test 1: Wellfound with search query params
print("=== Wellfound search: Product Manager ===")
html, code, err = fetch("https://wellfound.com/jobs?q=Product%20Manager&remote=true")
print(f"Status: {code}, len: {len(html) if html else 0}")
if html:
    # Look for job card links
    links = re.findall(r'href="(/jobs/\d+[^"]*)"', html)
    print(f"Job links: {len(links)}")
    for l in links[:15]:
        print(f"  {l[:120]}")
    # Look for role titles in JSON/script data
    roles = re.findall(r'"roleName"\s*:\s*"([^"]+)"', html)
    companies = re.findall(r'"companyName"\s*:\s*"([^"]+)"', html)
    print(f"Role names found in JSON: {len(roles)}")
    for i, r in enumerate(roles[:10]):
        comp = companies[i] if i < len(companies) else "?"
        print(f"  {r} at {comp}")

# Test 2: LinkedIn Jobs (we know it's blocked, but let's confirm)
print("\n=== LinkedIn Jobs ===")
html, code, err = fetch("https://www.linkedin.com/jobs/search/?keywords=Product+Manager&location=Remote")
print(f"Status: {code}, len: {len(html) if html else 0}, err: {err}")

# Test 3: Greenhouse direct - try Stripe jobs listing page
print("\n=== Greenhouse: Stripe ===")
html, code, err = fetch("https://boards.greenhouse.io/stripe")
print(f"Status: {code}, len: {len(html) if html else 0}")
if html:
    # Greenhouse uses JSON in a script tag or API endpoints
    # Look for the jobs API endpoint
    api_links = re.findall(r'/(stripe|[^/]+)/jobs/(\d+)', html)
    print(f"  Job API refs: {len(api_links)}")
    # Check for __NEXT_DATA__ or similar
    if "__NEXT_DATA__" in html:
        print("  Found __NEXT_DATA__")
    # Look for job title text
    titles = re.findall(r'"title":"([^"]+)"', html)[:10]
    print(f"  JSON titles: {titles}")
    # Try to find job links in different formats
    job_links = re.findall(r'href="[^"]*job[^"]*"', html, re.IGNORECASE)
    print(f"  Job hrefs: {len(job_links)}")
    for l in job_links[:5]:
        print(f"    {l[:120]}")

# Test 4: Lever direct - try a known company
print("\n=== Lever: Example company ===")
# Lever job pages are at jobs.lever.co/{company}/{job-id}
# Let's try Wellfound-style: jobs.lever.co/api/public/postings
html, code, err = fetch("https://jobs.lever.co/")
print(f"Status: {code}, len: {len(html) if html else 0}")

# Test 5: Try Lever's API endpoint for a known company
print("\n=== Lever API: some-company ===")
html, code, err = fetch("https://api.lever.co/v0/postings/some-company/public?mode=list")
print(f"Status: {code}, len: {len(html) if html else 0}")

# Test 6: Bing search with different phrasing
print("\n=== Bing: 'remote product manager job' (no site: restriction) ===")
q = quote("remote product manager job")
html, code, err = fetch("https://www.bing.com/search?q=" + q + "&count=15")
print(f"Status: {code}, len: {len(html) if html else 0}")
if html:
    h2 = re.findall(r'<h2[^>]*>(.*?)</h2>', html, re.DOTALL)
    cites = re.findall(r'<cite[^>]*>(.*?)</cite>', html, re.DOTALL)
    print(f"h2: {len(h2)}, cites: {len(cites)}")
    for h in h2[:5]:
        t = re.sub(r'<[^>]+>', '', h).strip()
        print(f"  title: {t[:100]}")
    for c in cites[:5]:
        t = re.sub(r'<[^>]+>', '', c).strip()
        print(f"  url: {t[:120]}")
