#!/usr/bin/env python3
"""Test different search engines and direct board access."""
import re
from urllib.parse import quote
import urllib.request
import urllib.error

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html", "Accept-Language": "en-US,en;q=0.9"})
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.read().decode("utf-8", errors="replace"), resp.getcode(), None
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if hasattr(e, 'read') else None
        return body, e.code, str(e)
    except Exception as e:
        return None, None, str(e)

# Test 1: Google search
print("=== Google search ===")
q = quote("Product Manager remote job site:greenhouse.io")
html, code, err = fetch("https://www.google.com/search?q=" + q + "&num=10")
print(f"Status: {code}, len: {len(html) if html else 0}, err: {err}")
if html:
    links = re.findall(r'<a href="/url\?q=([^"]+)', html)
    print(f"Google /url links: {len(links)}")
    for l in links[:10]:
        print(f"  {l[:120]}")
    if not links:
        links2 = re.findall(r'<a[^>]+href="(https?://[^"]+)"', html)
        print(f"Google direct hrefs: {len(links2)}")
        for l in links2[:10]:
            print(f"  {l[:120]}")

# Test 2: Bing with site:boards.greenhouse.io
print("\n=== Bing site:boards.greenhouse.io ===")
q = quote('"Product Manager" site:boards.greenhouse.io remote')
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

# Test 3: Direct Wellfound
print("\n=== Wellfound direct ===")
html, code, err = fetch("https://wellfound.com/jobs")
print(f"Status: {code}, len: {len(html) if html else 0}, err: {err}")
if html and len(html) > 100:
    # Look for job links
    links = re.findall(r'href="(/jobs/\d+[^"]*)"', html)
    print(f"Wellfound job links: {len(links)}")
    for l in links[:5]:
        print(f"  {l[:120]}")
    # Also try finding JSON data
    if '"companyName"' in html or '"roleName"' in html:
        print("  Found job data in page!")

# Test 4: Direct AngelList
print("\n=== AngelList direct ===")
html, code, err = fetch("https://angel.co/jobs")
print(f"Status: {code}, len: {len(html) if html else 0}, err: {err}")

# Test 5: Direct Greenhouse - a known company career page
print("\n=== Greenhouse direct (example: stripe) ===")
html, code, err = fetch("https://boards.greenhouse.io/stripe")
print(f"Status: {code}, len: {len(html) if html else 0}, err: {err}")
if html:
    # Look for job links
    links = re.findall(r'href="/stripe/jobs/[^"]*"', html)
    print(f"  Greenhouse job links: {len(links)}")
    for l in links[:10]:
        print(f"  {l}")
