#!/usr/bin/env python3
"""Verify candidate postings: fetch page, extract JSON-LD datePosted / visible date, confirm alive."""
import json, re, os
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "scan_2026_08_23")

CANDIDATES = [
    {"company": "Stedi", "role_title": "Product Manager",
     "posting_url": "https://jobs.ashbyhq.com/stedi/65b38320-75df-4386-b5e5-25b411e7a6a4", "source_board": "Ashby"},
    {"company": "Teleperformance", "role_title": "AI Product Manager, Internal Transformations",
     "posting_url": "https://careersus-teleperformance.icims.com/jobs/85572/ai-product-manager%2C-internal-transformations/job", "source_board": "iCIMS"},
    {"company": "MCI", "role_title": "AI Product Manager",
     "posting_url": "https://careers-mci2.icims.com/jobs/50183/ai-product-manager/job", "source_board": "iCIMS"},
    {"company": "e.l.f. Beauty", "role_title": "Product Manager, Marketing Technology",
     "posting_url": "https://jobs.lever.co/elfbeauty/e0b20ead-92f4-4bb0-be93-9a256d4da462", "source_board": "Lever"},
    {"company": "Finch", "role_title": "Product Manager, Integrations (Core Product)",
     "posting_url": "https://jobs.lever.co/finch/6ecfd590-d27b-489f-8e24-e66868de4cbb", "source_board": "Lever"},
    {"company": "Array Labs", "role_title": "Technical Product Manager, 3D Geospatial Products",
     "posting_url": "https://jobs.lever.co/arraylabs.io/1a7e9279-7576-4c4b-aa97-ec11554eaa3e", "source_board": "Lever"},
    {"company": "Chime", "role_title": "Product Manager, Transaction Risk Decisioning",
     "posting_url": "https://boards.greenhouse.io/chime/jobs/8694087002", "source_board": "Greenhouse"},
    {"company": "Jeeves", "role_title": "Product Manager - Accounting",
     "posting_url": "https://jobs.lever.co/tryjeeves/15988e81-3e5a-475f-b401-16eb3f96cf1c", "source_board": "Lever"},
]

import urllib.request, ssl
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml"})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return r.status, r.read().decode("utf-8", errors="replace")

def extract_date(html):
    """Try JSON-LD datePosted first, then common visible-date patterns."""
    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try:
            data = json.loads(m.group(1).strip())
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for it in items:
            if isinstance(it, dict) and it.get("@type") == "JobPosting":
                dp = it.get("datePosted")
                if dp:
                    return f"json_ld:{dp}"
                break
    patterns = [
        r'"datePosted"\s*:\s*"([^"]+)"',
        r'(?:posted|Published)[^<]{0,30}(\w+ \d{1,2},? \d{4})',
        r'datetime="(\d{4}-\d{2}-\d{2})',
    ]
    for p in patterns:
        m = re.search(p, html, re.I)
        if m:
            return f"text:{m.group(1)}"
    return None

out = []
for c in CANDIDATES:
    rec = dict(c)
    try:
        st, html = fetch(c["posting_url"])
        rec["http"] = st
        rec["bytes"] = len(html)
        low = html.lower()
        dead = any(x in low for x in ["no longer accepting", "this job is no longer", "position has been filled", "page not found", "404 error", "job doesn't exist", "couldn't find the job"])
        rec["dead_signal"] = dead
        d = extract_date(html)
        rec["date_found"] = d
        if c["source_board"] == "Lever":
            t = re.search(r'<div class="section page-centered[^"]*">\s*<h2>([^<]+)</h2>', html)
            loc = re.search(r'class="sorting-tagline[^"]*"[^>]*>([^<]+)<', html)
            if loc: rec["location_text"] = loc.group(1).strip()
        if c["source_board"] == "Greenhouse":
            loc = re.search(r'class="location"[^>]*>([^<]+)<', html)
            if loc: rec["location_text"] = loc.group(1).strip()
            sal = re.search(r'\$\d{2,3}[,.]?\d*[kK]?[^\d]{0,10}\$\d{2,3}[,.]?\d*[kK]?', html)
        print(f"{st} | {c['company']:15s} | {c['role_title'][:45]:45s} | date={d} | dead={dead} | bytes={len(html)}")
    except Exception as e:
        rec["http"] = None
        rec["error"] = f"{type(e).__name__}: {str(e)[:120]}"
        print(f"ERR | {c['company']:15s} | {c['role_title'][:45]:45s} | {rec['error']}")
    out.append(rec)

with open(os.path.join(RAW, "verified_candidates.json"), "w") as f:
    json.dump(out, f, indent=2)
print("\nsaved verified_candidates.json")
