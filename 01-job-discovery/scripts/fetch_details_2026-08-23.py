#!/usr/bin/env python3
"""Fetch location + salary details for candidates missing them."""
import urllib.request, ssl, re

ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=25, context=ctx) as r:
        return r.read().decode("utf-8", errors="replace")

for name, url in [
    ("finch", "https://jobs.lever.co/finch/6ecfd590-d27b-489f-8e24-e66868de4cbb"),
    ("arraylabs", "https://jobs.lever.co/arraylabs.io/1a7e9279-7576-4c4b-aa97-ec11554eaa3e"),
    ("chime", "https://boards.greenhouse.io/chime/jobs/8694087002"),
    ("elf", "https://jobs.lever.co/elfbeauty/e0b20ead-92f4-4bb0-be93-9a256d4da462"),
]:
    html = fetch(url)
    print("=" * 8, name)
    for pat in [
        r'class="sorting-tagline[^"]*"[^>]*>([^<]{3,80})<',
        r'workplaceType["\':\s]+([A-Za-z ]{3,30})',
        r'class="location"[^>]*>([^<]{3,80})<',
        r"<title>([^<]{5,120})</title>",
    ]:
        ms = re.findall(pat, html)
        if ms:
            print("   ", list(dict.fromkeys([m.strip() for m in ms]))[:4])
    sal = re.findall(r"\$[\d,.]+\s*[Kk]?\s*[-\u2013\u2014]\s*\$[\d,.]+\s*[Kk]?[^<]{0,40}", html)[:3]
    print("    salary:", sal if sal else "none")
