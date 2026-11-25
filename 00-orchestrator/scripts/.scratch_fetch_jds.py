#!/usr/bin/env python3
"""One-off: fetch 3 job posting HTML pages + extract visible text."""
import urllib.request, urllib.error, ssl, re, sys, os

URLS = {
 84: "https://jobs.lever.co/kpler/c7103421-ccbe-43b4-b23d-752e8c8a3a9c",
 85: "https://www.workingnomads.com/jobs/product-manager-ai-synack",
 86: "https://jobs.ashbyhq.com/kindred/8868c144-1909-47f2-9c1c-e59a9e4ddce0",
}
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# write raw html + extracted text to a scratch dir
OUT = "00-orchestrator/scripts/.scratch_jd_fetch"
os.makedirs(OUT, exist_ok=True)

for app_id, url in URLS.items():
    print(f"=== app {app_id}: {url} ===", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    try:
        with urllib.request.urlopen(req, timeout=25, context=ctx) as r:
            raw = r.read()
            print(f"  HTTP {r.status} | {len(raw)} bytes | final: {r.geturl()}", flush=True)
            with open(os.path.join(OUT, f"app_{app_id}_raw.html"), "wb") as f:
                f.write(raw)
            text = raw.decode("utf-8", "replace")
            text_nc = re.sub(r'<script.*?</script>', ' ', text, flags=re.S | re.I)
            text_nc = re.sub(r'<style.*?</style>', ' ', text_nc, flags=re.S | re.I)
            text_nc = re.sub(r'<[^>]+>', ' ', text_nc)
            text_nc = re.sub(r'\s+', ' ', text_nc).strip()
            with open(os.path.join(OUT, f"app_{app_id}_text.txt"), "w", encoding="utf-8") as f:
                f.write(text_nc)
            print(f"  visible chars: {len(text_nc)}", flush=True)
            print("  --- snippet ---", flush=True)
            print(text_nc[:1500], flush=True)
    except urllib.error.HTTPError as e:
        print(f"  HTTPError {e.code}: {e.reason}", flush=True)
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}", flush=True)
    print(flush=True)
