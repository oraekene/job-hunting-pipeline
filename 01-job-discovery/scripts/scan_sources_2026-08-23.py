#!/usr/bin/env python3
"""Discovery source scan 2026-08-23 — fetch raw data from HTTP sources."""
import json, re, os, sys
from datetime import datetime, timezone

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scan_2026_08_23")
os.makedirs(OUT_DIR, exist_ok=True)
now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
print("now:", now_iso)

summary = {}

import urllib.request

def fetch(url, timeout=25, headers=None):
    h = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Accept": "*/*"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", errors="replace")

# ---------- 1. Remotive API ----------
try:
    rem_all = []
    for q in ["product%20manager", "AI%20product%20manager"]:
        st, body = fetch(f"https://remotive.com/api/remote-jobs?limit=60&search={q}")
        data = json.loads(body)
        jobs = data.get("jobs", [])
        rem_all.extend(jobs)
        print(f"remotive '{q}': HTTP {st}, {len(jobs)} jobs")
    seen = set(); rem_uniq = []
    for j in rem_all:
        if j["id"] not in seen:
            seen.add(j["id"]); rem_uniq.append(j)
    with open(os.path.join(OUT_DIR, "remotive.json"), "w") as f:
        json.dump(rem_uniq, f)
    summary["remotive"] = len(rem_uniq)
except Exception as e:
    print("REMOTIVE ERROR:", type(e).__name__, str(e)[:200])
    summary["remotive"] = f"ERROR {type(e).__name__}"

# ---------- 2. RemoteOK JSON ----------
try:
    st, body = fetch("https://remoteok.com/json", timeout=25,
                     headers={"User-Agent": "Mozilla/5.0 (compatible; JobDiscovery/1.0)"})
    data = json.loads(body)
    with open(os.path.join(OUT_DIR, "remoteok.json"), "w") as f:
        json.dump(data, f)
    print(f"remoteok: HTTP {st}, {max(0, len(data)-1)} jobs")
    summary["remoteok"] = max(0, len(data)-1)
except Exception as e:
    print("REMOTEOK ERROR:", type(e).__name__, str(e)[:200])
    summary["remoteok"] = f"BLOCKED/ERROR {type(e).__name__}"

# ---------- 3. Wellfound page ----------
try:
    st, body = fetch("https://wellfound.com/jobs", timeout=25)
    with open(os.path.join(OUT_DIR, "wellfound.html"), "w", encoding="utf-8") as f:
        f.write(body)
    n_urls = len(re.findall(r'href="(https://wellfound\.com/jobs/\d+[^"]*)"', body))
    print(f"wellfound: HTTP {st}, bytes={len(body)}, job-url matches={n_urls}")
    summary["wellfound"] = f"HTTP {st}, urls={n_urls}"
except Exception as e:
    print("WELLFOUND ERROR:", type(e).__name__, str(e)[:200])
    summary["wellfound"] = f"BLOCKED/ERROR {type(e).__name__}"

with open(os.path.join(OUT_DIR, "summary.json"), "w") as f:
    json.dump({"now": now_iso, **summary}, f, indent=2)
print("\nSUMMARY:", json.dumps(summary, indent=2))
