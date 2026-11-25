#!/usr/bin/env python
"""Fetch Wellfound job pages and extract structured fields via JSON-LD + DOM text."""
import json, sys, urllib.request, re

URLS = [
    "https://wellfound.com/jobs/4735289-product-manager-reactors",
    "https://www.wellfound.com/jobs/4735289-product-manager-reactors",
    "https://wellfound.com/jobs/4735287-product-manager-ii",
    "https://wellfound.com/jobs/4644462-technical-product-lead",
    "https://wellfound.com/jobs/4618116-junior-product-manager",
    "https://wellfound.com/jobs/4735152-head-of-fraud-product",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
}

def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        return f"FETCH_ERROR: {e}"

def extract(html):
    # JSON-LD JobPosting
    scripts = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL)
    json_ld = None
    for s in scripts:
        try:
            d = json.loads(s.strip())
            if isinstance(d, list):
                for x in d:
                    if isinstance(x, dict) and x.get("@type") == "JobPosting":
                        json_ld = x
                        break
            elif isinstance(d, dict) and d.get("@type") == "JobPosting":
                json_ld = d
            if json_ld:
                break
        except Exception:
            pass

    # Strip HTML tags for text fallback
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text).strip()

    return {
        "json_ld": json_ld,
        "text_preview": text[:5000],
        "html_len": len(html),
        "has_json_ld": json_ld is not None,
    }

results = {}
for url in URLS:
    # Try primary url, fall back to www
    html = fetch(url)
    if html.startswith("FETCH_ERROR"):
        results[url] = {"status": "fetch_failed", "error": html}
        print(f"FAILED: {url} -> {html}")
    else:
        data = extract(html)
        results[url] = data
        print(f"OK: {url} (html_len={len(html)}, json_ld={data['has_json_ld']})")
        if data["json_ld"]:
            print(f"  JSON-LD keys: {list(data['json_ld'].keys())}")
            print(f"  title: {data['json_ld'].get('title', 'N/A')}")
            print(f"  company: {data['json_ld'].get('hiringOrganization', 'N/A')}")
            print(f"  posted: {data['json_ld'].get('datePosted', 'N/A')}")
            print(f"  apply: {data['json_ld'].get('applyLink', data['json_ld'].get('url', 'N/A'))}")
            print(f"  location: {data['json_ld'].get('jobLocation', 'N/A')}")
        if not data["json_ld"]:
            # Try to find key fields in text
            for keyword in ["Salary", "Company", "Location", "Remote", "Posted", "Apply"]:
                idx = data["text_preview"].find(keyword)
                if idx >= 0:
                    snippet = data["text_preview"][max(0, idx-20):idx+120].strip()
                    print(f"  text has '{keyword}': ...{snippet}...")

print("\n=== DETAILED JSON-LD ===")
for url, data in results.items():
    if isinstance(data, dict) and data.get("json_ld"):
        print(f"\n--- {url} ---")
        print(json.dumps(data["json_ld"], indent=2, default=str)[:2000])
