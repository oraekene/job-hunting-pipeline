#!/usr/bin/env python
"""Normalize raw JD data into clean text for stages 2-9. Covers Ashby (__appData)
and Greenhouse (raw HTML text extraction)."""
import os, re, json, html as html_lib

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ART = os.path.join(BASE, "shared", "build_artifacts")
PY = "python3" if False else None  # noop

def strip_html(s):
    if not s:
        return ""
    s = html_lib.unescape(s)
    # remove style/script blocks
    s = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', s, flags=re.S|re.I)
    # replace block tags with newlines
    s = re.sub(r'</(p|div|li|h[1-6]|tr|br)>', '\n', s, flags=re.I)
    s = re.sub(r'<br\s*/?>', '\n', s, flags=re.I)
    # drop remaining tags
    s = re.sub(r'<[^>]+>', ' ', s)
    s = re.sub(r'[ \t]+', ' ', s)
    s = re.sub(r'\n\s*\n+', '\n', s)
    return s.strip()

def ashby_text(app_id):
    jp = os.path.join(ART, f"app_{app_id}", "_jd_parsed.json")
    if not os.path.exists(jp):
        return None
    d = json.load(open(jp, encoding="utf-8"))
    desc = strip_html(d.get("descriptionHtml",""))
    parts = []
    parts.append(f"COMPANY: {d.get('organizationName','')}".replace("organizationName","company"))
    # Ashby fields
    comp = d.get("organizationName") or d.get("company") or ""
    title = d.get("title","")
    loc = d.get("locationName","")
    et = d.get("employmentType","")
    tiers = d.get("compensationTiers",[])
    comp_str = " | ".join(t.get("tierSummary","") for t in tiers) if tiers else d.get("scrapableCompensationSalarySummary","")
    header = f"# {title}\n\n**Company:** {comp}\n**Location:** {loc} | **Type:** {et}\n**Compensation:** {comp_str}\n\n"
    return header + desc

def greenhouse_text(app_id):
    fp = os.path.join(ART, f"app_{app_id}", "_jd_raw.html")
    if not os.path.exists(fp):
        return None
    html = open(fp, encoding="utf-8").read()
    # Try JSON-LD jobPosting
    m = re.search(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.S|re.I)
    if m:
        try:
            data = json.loads(m.group(1))
            if isinstance(data, list):
                for o in data:
                    if isinstance(o, dict) and o.get("@type")=="JobPosting":
                        desc = strip_html(o.get("description",""))
                        title = o.get("title","")
                        return f"# {title}\n\n**Company:** {o.get('hiringOrganization','')}\n**Location:** {o.get('jobLocation',{}).get('address',{}).get('addressLocality','')}\n\n{desc}"
            elif isinstance(data, dict) and data.get("@type")=="JobPosting":
                desc = strip_html(data.get("description",""))
                return f"# {data.get('title','')}\n\n**Company:** {data.get('hiringOrganization','')}\n\n{desc}"
        except Exception as e:
            print(f"  gh ld+json parse error: {e}")
    # Fallback: greenhouse.io classic content
    # Look for the description div
    m2 = re.search(r'<div[^>]*id=["\']job-description["\'][^>]*>(.*?)</div>', html, re.S|re.I)
    if m2:
        return "# ezCater Job Posting\n\n" + strip_html(m2.group(1))
    # Last resort: just strip all visible text
    txt = strip_html(html)
    # trim navigation boilerplate
    return txt

if __name__ == "__main__":
    for app_id, kind in [(87,"ashby"),(88,"ashby"),(89,"greenhouse")]:
        if kind == "ashby":
            out = ashby_text(app_id)
        else:
            out = greenhouse_text(app_id)
        if not out:
            print(f"app {app_id}: NO content ({kind})")
            continue
        # save normalized
        out_path = os.path.join(ART, f"app_{app_id}", "_jd_normalized.txt")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"app {app_id}: normalized -> {len(out)} chars -> {out_path}")
        print("  HEAD:", out[:200].replace("\n"," | "))
        print("  TAIL:", out[-200:].replace("\n"," | "))
        print()
