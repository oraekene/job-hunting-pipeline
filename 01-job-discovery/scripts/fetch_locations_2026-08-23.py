#!/usr/bin/env python3
"""Extract JSON-LD JobPosting location fields for candidates missing them."""
import urllib.request, ssl, re, json

ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=25, context=ctx) as r:
        return r.read().decode("utf-8", errors="replace")

for name, url in [
    ("finch", "https://jobs.lever.co/finch/6ecfd590-d27b-489f-8e24-e66868de4cbb"),
    ("arraylabs", "https://jobs.lever.co/arraylabs.io/1a7e9279-7576-4c4b-aa97-ec11554eaa3e"),
    ("elf", "https://jobs.lever.co/elfbeauty/e0b20ead-92f4-4bb0-be93-9a256d4da462"),
    ("stedi", "https://jobs.ashbyhq.com/stedi/65b38320-75df-4386-b5e5-25b411e7a6a4"),
]:
    html = fetch(url)
    print("=" * 8, name)
    found = False
    for m in re.finditer(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S):
        try:
            data = json.loads(m.group(1).strip())
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for it in items:
            if isinstance(it, dict) and it.get("@type") == "JobPosting":
                found = True
                print("   datePosted:", it.get("datePosted"))
                print("   validThrough:", it.get("validThrough"))
                loc = it.get("jobLocation")
                if isinstance(loc, list):
                    locs = [(l.get("address") or {}).get("addressLocality") or (l.get("address") or {}).get("addressRegion") or str(l) for l in loc]
                    print("   locations:", locs[:6])
                elif isinstance(loc, dict):
                    print("   location:", loc)
                ap = it.get("applicantLocationRequirements")
                if ap:
                    print("   applicantLocationRequirements:", ap if not isinstance(ap, list) else ap[:4])
                rt = it.get("jobLocationType")
                if rt:
                    print("   jobLocationType:", rt)
    if not found:
        print("    no JobPosting JSON-LD found")
