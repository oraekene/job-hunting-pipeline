#!/usr/bin/env python3
"""Filter Remotive + RemoteOK raw data against target profile (cheap filter)."""
import json, re, os
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "scan_2026_08_23")
now = datetime.now(timezone.utc)

TITLE_VARIANTS = [
    "product manager", "ai product manager", "ai engineer", "automation engineer",
    "associate product manager", "junior product manager", "workflow engineer",
    "product owner", "technical product manager", "growth product manager",
    "ai/ml product manager",
]
SENIOR_REJECT = ["senior", "sr.", "sr ", "staff", "principal", "lead", "head of", "director", "vp ", "chief", "manager ii", "manager iii"]

def is_title_match(t):
    tl = (t or "").lower()
    # key-term substring approach (same as run_discovery.py)
    key_terms = ["product manager", "product owner", "ai product", "ai/ml product",
                 "technical product", "growth product", "associate product",
                 "junior product", "workflow engineer", "automation engineer", "ai engineer"]
    return any(kt in tl for kt in key_terms)

def is_senior_reject(t):
    tl = " " + (t or "").lower() + " "
    return any((" " + kw.strip()) in tl for kw in SENIOR_REJECT)

def hours_ago(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return (now - dt).total_seconds() / 3600.0
    except Exception:
        return None

results = {"remotive": [], "remoteok": []}

# ---- Remotive ----
with open(os.path.join(RAW, "remotive.json")) as f:
    rem = json.load(f)
for j in rem:
    title = j.get("title", "")
    pub = j.get("publication_date", "")  # ISO
    h = hours_ago(pub)
    cand = {
        "company": j.get("company_name", ""),
        "role_title": title,
        "posting_url": j.get("url", ""),
        "source_board": "Remotive",
        "ats_platform": "remotive",
        "posted_at": pub,
        "posted_at_raw": pub,
        "hours_ago": round(h, 1) if h is not None else None,
        "salary_range": j.get("salary", ""),
        "remote_type": "remote",
        "location": j.get("candidate_required_location", ""),
    }
    if not is_title_match(title):
        cand["_reject"] = "title"
    elif is_senior_reject(title):
        cand["_reject"] = "seniority"
    elif h is not None and h > 48:
        cand["_reject"] = f"stale ({round(h)}h)"
    else:
        cand["_reject"] = None
    results["remotive"].append(cand)

# ---- RemoteOK ----
with open(os.path.join(RAW, "remoteok.json")) as f:
    rok = json.load(f)
for j in rok[1:] if isinstance(rok, list) else []:
    title = j.get("position", "")
    epoch = j.get("epoch")
    h = ((now.timestamp() - epoch) / 3600.0) if epoch else None
    salary_min = j.get("salary_min") or 0
    salary_max = j.get("salary_max") or 0
    cand = {
        "company": j.get("company", ""),
        "role_title": title,
        "posting_url": ("https://remoteok.com" + j["url"]) if j.get("url", "").startswith("/") else j.get("url", ""),
        "source_board": "RemoteOK",
        "ats_platform": "remoteok",
        "posted_at": datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if epoch else None,
        "posted_at_raw": datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if epoch else "",
        "hours_ago": round(h, 1) if h is not None else None,
        "salary_range": (f"${salary_min:,} - ${salary_max:,}" if salary_min or salary_max else ""),
        "salary_min": salary_min,
        "remote_type": "remote",
        "location": j.get("location", ""),
    }
    if not is_title_match(title):
        cand["_reject"] = "title"
    elif is_senior_reject(title):
        cand["_reject"] = "seniority"
    elif h is not None and h > 48:
        cand["_reject"] = f"stale ({round(h)}h)"
    else:
        cand["_reject"] = None
    results["remoteok"].append(cand)

for src, items in results.items():
    keep = [c for c in items if c["_reject"] is None]
    print(f"\n=== {src}: {len(items)} total, {len(keep)} PASS ===")
    for c in keep:
        sal = c.get('salary_range') or '-'
        print(f"  KEEP [{c['hours_ago']}h] {c['company']} — {c['role_title']} | {sal}")
    rej = [c for c in items if c["_reject"]]
    print(f"  ({len(rej)} rejected)")
    for c in rej[:40]:
        print(f"    reject[{c['_reject']}]: {c['company']} — {c['role_title']}")

with open(os.path.join(RAW, "filtered_candidates.json"), "w") as f:
    json.dump(results, f, indent=2)
