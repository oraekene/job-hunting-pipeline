#!/usr/bin/env python
"""Extract embedded job-description JSON from Ashby/Greenhouse posting pages."""
import urllib.request, re, json, os, sys

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ART = os.path.join(BASE, "shared", "build_artifacts")

def fetch(url):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml',
    })
    return urllib.request.urlopen(req, timeout=25).read().decode('utf-8', 'replace')

def safe_name(c, r):
    s = re.sub(r'[^A-Za-z0-9]+', '_', c + '_' + r)
    return re.sub(r'_+', '_', s).strip('_')

def try_ashby(html):
    m = re.search(r'window\.__appData\s*=\s*(\{.*?\});\s*\n', html, re.S)
    if not m:
        return None, "no __appData"
    try:
        data = json.loads(m.group(1))
    except Exception as e:
        return None, f"json parse: {e}"
    # Walk to find the job posting block
    def walk(o, depth=0):
        if depth > 8:
            return None
        if isinstance(o, dict):
            if 'jobPosting' in o and isinstance(o['jobPosting'], dict):
                return o['jobPosting']
            if 'posting' in o and isinstance(o['posting'], dict):
                return o['posting']
            for v in o.values():
                r = walk(v, depth+1)
                if r:
                    return r
        elif isinstance(o, list):
            for v in o:
                r = walk(v, depth+1)
                if r:
                    return r
        return None
    return data, walk(data)

def try_greenhouse(html):
    # Greenhouse embeds in __NEXT_DATA__ or window.__INITIAL_STATE__ / gimme data
    m = re.search(r'__NEXT_DATA__[^>]*>(.*?)</script>', html, re.S)
    if m:
        try:
            data = json.loads(m.group(1))
        except Exception:
            data = None
        if data:
            return data
    m2 = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});', html, re.S)
    if m2:
        try:
            return json.loads(m2.group(1))
        except Exception:
            pass
    # fallback: look for a content_html / job body in inline script
    for pat in [r'"description"\s*:\s*"', r'"content"\s*:\s*"', r'jobDescriptionContent', r'gh-job-description']:
        if pat.strip('"') in html:
            return html  # raw marker hit
    return None

if __name__ == "__main__":
    jobs = {
        87: ("https://jobs.ashbyhq.com/turquoise-health/7a416ec3-eef0-41da-8afb-09644fb54e1b", "ashby"),
        88: ("https://jobs.ashbyhq.com/benepass/716b41c7-f3df-470a-bd7c-7f38d67d951a", "ashby"),
        89: ("https://boards.greenhouse.io/ezcaterinc/jobs/5207123007", "greenhouse"),
    }
    for app_id, (url, kind) in jobs.items():
        out_dir = os.path.join(ART, f"app_{app_id}")
        os.makedirs(out_dir, exist_ok=True)
        raw_path = os.path.join(out_dir, "_jd_raw.html")
        json_path = os.path.join(out_dir, "_jd_parsed.json")
        try:
            html = fetch(url)
            open(raw_path, "w", encoding="utf-8").write(html)
            print(f"app {app_id}: fetched {len(html)} bytes -> {raw_path}")
            if kind == "ashby":
                data, job = try_ashby(html)
                if job:
                    open(json_path, "w", encoding="utf-8").write(json.dumps(job, indent=2, default=str)[:200000])
                    print(f"app {app_id}: __appData job block extracted ({len(json.dumps(job, default=str))} chars)")
                    # print key fields
                    for k in ('title','name','description','responsibilities','requirements','qualifications','location','company','department'):
                        if k in job and job[k]:
                            v = job[k]
                            s = v if isinstance(v,str) else json.dumps(v)[:300]
                            print(f"  {k}: {s}")
                else:
                    print(f"app {app_id}: ashby parse note: {job}")
            else:
                data = try_greenhouse(html)
                if data:
                    open(json_path, "w", encoding="utf-8").write(json.dumps(data, indent=2, default=str)[:200000])
                    print(f"app {app_id}: greenhouse data extracted ({len(json.dumps(data, default=str))} chars)")
                else:
                    print(f"app {app_id}: greenhouse: no structured data found")
        except Exception as e:
            print(f"app {app_id}: ERROR {e!r}")
        print("-"*40)
