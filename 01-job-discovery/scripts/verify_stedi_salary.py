#!/usr/bin/env python3
"""Verify the Stedi salary range against the live page."""
import urllib.request, ssl, re

ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
req = urllib.request.Request(
    "https://jobs.ashbyhq.com/stedi/65b38320-75df-4386-b5e5-25b411e7a6a4",
    headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=25, context=ctx) as r:
    html = r.read().decode("utf-8", errors="replace")

hits = re.findall(r"[^<>]{0,30}\$[\d,.]+[Kk]?[^<>]{0,60}", html)
for h in hits[:10]:
    print(repr(h.strip()[:110]))
if not hits:
    print("NO salary strings found on Stedi page")
