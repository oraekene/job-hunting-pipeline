"""Discovery source fetch 2026-08-24 - pull raw data from HTTP sources (remotive, remoteok, wellfound)."""
import json, re, os, urllib.request, ssl
from datetime import datetime, timezone

OUT_DIR = r"C:/Users/rotim/AppData/Local/hermes/skills/job-hunting/01-job-discovery/scripts/scan_2026_08_24"
os.makedirs(OUT_DIR, exist_ok=True)
now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
print("now:", now_iso)
summary = {}

def fetch(url, timeout=25, headers=None):
    h = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Accept": "*/*"}
    if headers: h.update(headers)
    req = urllib.request.Request(url, headers=h)
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
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
    json.dump(rem_uniq, open(os.path.join(OUT_DIR, "remotive.json"), "w"))
    summary["remotive"] = len(rem_uniq)
except Exception as e:
    print("REMOTIVE ERROR:", type(e).__name__, str(e)[:200])
    summary["remotive"] = f"ERROR {type(e).__name__}"

# ---------- 2. RemoteOK JSON ----------
try:
    st, body = fetch("https://remoteok.com/json", timeout=25,
                     headers={"User-Agent": "Mozilla/5.0 (compatible; JobDiscovery/1.0)"})
    data = json.loads(body)
    json.dump(data, open(os.path.join(OUT_DIR, "remoteok.json"), "w"))
    n = max(0, len(data)-1)
    print(f"remoteok: HTTP {st}, {n} jobs")
    summary["remoteok"] = n
except Exception as e:
    print("REMOTEOK ERROR:", type(e).__name__, str(e)[:200])
    summary["remoteok"] = f"BLOCKED/ERROR {type(e).__name__}"

# ---------- 3. Wellfound page ----------
try:
    st, body = fetch("https://wellfound.com/jobs", timeout=25)
    open(os.path.join(OUT_DIR, "wellfound.html"), "w", encoding="utf-8").write(body)
    # try JSON-LD JobPosting extraction
    ld_blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', body, re.S)
    postings = []
    for blk in ld_blocks:
        try:
            d = json.loads(blk.strip())
            items = d if isinstance(d, list) else [d]
            for it in items:
                if isinstance(it, dict) and it.get("@type") == "JobPosting":
                    postings.append(it)
        except Exception:
            pass
    n_urls = len(re.findall(r'href="(https://wellfound\.com/jobs/\d+[^"]*)"', body))
    json.dump(postings, open(os.path.join(OUT_DIR, "wellfound_ld.json"), "w"))
    print(f"wellfound: HTTP {st}, bytes={len(body)}, job-url matches={n_urls}, jsonld postings={len(postings)}")
    summary["wellfound"] = f"HTTP {st}, urls={n_urls}, ld={len(postings)}"
except Exception as e:
    print("WELLFOUND ERROR:", type(e).__name__, str(e)[:200])
    summary["wellfound"] = f"BLOCKED/ERROR {type(e).__name__}"

json.dump({"now": now_iso, **summary}, open(os.path.join(OUT_DIR, "summary.json"), "w"), indent=2)
print("\nSUMMARY:", json.dumps(summary, indent=2))
