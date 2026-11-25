#!/usr/bin/env python3
"""Manual Bing search check — bypass daily cadence to see if there are any new PM jobs right now."""
import urllib.request, urllib.parse, re, html as html_mod, json
from datetime import datetime, timezone

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml',
    'Accept-Language': 'en-US,en;q=0.9',
}

TITLE_VARIANTS = [
    "Product Manager", "AI Product Manager", "AI Engineer", "Automation Engineer",
    "Associate Product Manager", "Junior Product Manager", "Workflow Engineer",
    "Product Owner", "Technical Product Manager", "Growth Product Manager",
    "AI/ML Product Manager",
]

DB_PATH = "shared/applications.db"
import sqlite3
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
known_urls = set(r[0].lower() for r in c.execute("SELECT posting_url FROM applications WHERE posting_url IS NOT NULL"))
known_urls.update(r[0].lower() for r in c.execute("SELECT posting_url FROM posting_sources WHERE posting_url IS NOT NULL"))
known_fps = set(r[0] for r in c.execute("SELECT posting_fingerprint FROM applications WHERE posting_fingerprint IS NOT NULL"))
conn.close()
print(f"Known URLs: {len(known_urls)}, Known fingerprints: {len(known_fps)}")

def fetch(url, timeout=15):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=timeout)
        raw = resp.read()
        if 'gzip' in resp.headers.get('Content-Encoding', ''):
            import gzip
            raw = gzip.decompress(raw)
        return raw.decode('utf-8', errors='replace'), resp.status
    except Exception as e:
        return str(e), 0

def title_matches(title):
    t = title.lower().strip()
    for v in TITLE_VARIANTS:
        if v.lower() in t:
            return v
    return None

def compute_fingerprint(company, title, location):
    def norm_title(title):
        t = title.lower().strip()
        patterns = [
            r'\s*\(.*\)', r'\s*-\s*contract', r'#\s*[ivx]+', r'\[\d+\]',
            r'(ii|iii|iv|v|vi)\s*$', r'^senior\s+', r'^lead\s+',
            r'^staff\s+', r'^principal\s+',
        ]
        for pat in patterns:
            t = re.sub(pat, '', t, flags=re.IGNORECASE)
        t = re.sub(r'[^a-z0-9\s]', ' ', t).strip()
        return re.sub(r'\s+', ' ', t).strip()
    def norm_loc(loc):
        l = loc.lower().strip()
        if any(w in l for w in ['remote', 'worldwide', 'global', 'anywhere']):
            return 'remote'
        elif 'united states' in l or 'us only' in l:
            return 'united states'
        l = re.sub(r'[^a-z0-9\s]', ' ', l).strip()
        return re.sub(r'\s+', ' ', l).strip()
    return f"{company.lower().strip()}|{norm_title(title)}|{norm_loc(location)}"

# ── 1. Bing search per ATS platform ──
platforms = {
    'greenhouse': 'site:greenhouse.io',
    'lever': 'site:jobs.lever.co',
    'ashby': 'site:ashbyhq.com',
    'workday': 'site:my.workday.com',
    'smartrecruiters': 'site:company.smartrecruiters.com',
    'icims': 'site:home.icims.com',
}

# Also try a generic Bing search
queries = [
    'remote product manager hiring',
    '"AI product manager" remote',
    'remote AI engineer hiring',
    'remote workflow engineer',
]

all_candidates = []
total_bing_results = 0

for pname, psite in platforms.items():
    pm_terms = ' OR '.join(f'"{t}"' for t in TITLE_VARIANTS)
    q = f'{psite} ({pm_terms}) remote'
    url = 'https://www.bing.com/search?q=' + urllib.parse.quote(q) + '&count=15'
    content, status = fetch(url)
    if status != 200:
        print(f"  [{pname}] Bing fetch failed: HTTP {status}")
        continue
    # Extract result links — try multiple patterns
    links = re.findall(r'<h2><a[^>]*href="(https?://[^"]+)"', content)
    links += re.findall(r'href="(https?://[^"]+)"', content)
    links = [html_mod.unescape(l) for l in links]
    # Filter for Bing redirect URLs or direct ATS URLs
    ats_links = []
    for l in links:
        # Check if it's an ATS domain
        low = l.lower()
        if any(k in low for k in ['greenhouse', 'lever', 'ashby', 'workday', 'smartrecruiters', 'icims']):
            if 'uddg=' in l:
                m = re.search(r'uddg=([^&]+)', l)
                if m:
                    ats_links.append(html_mod.unescape(m.group(1)))
            else:
                ats_links.append(l)
    ats_links = list(dict.fromkeys(ats_links))
    total_bing_results += len(ats_links)
    print(f"\n  [{pname}] Bing returned {len(ats_links)} ATS links")
    for link in ats_links[:5]:
        print(f"    {link[:120]}")
        # Try to fetch the job page
        page, pstatus = fetch(link, timeout=10)
        if pstatus != 200 or len(page) < 3000:
            print(f"    -> fetch failed or too small (HTTP {pstatus}, size={len(page)})")
            continue
        page_low = page.lower()
        if 'captcha' in page_low or 'challenge' in page_low:
            print(f"    -> blocked (captcha/challenge)")
            continue
        # Extract title
        title_match = re.search(r'["\']jobTitle["\']?\s*:\s*["\']([^"\']+)["\']', page)
        if not title_match:
            title_match = re.search(r'<title>(.*?)</title>', page, re.DOTALL)
        title = html_mod.unescape(title_match.group(1).strip()) if title_match else ''
        matched = title_matches(title)
        if matched:
            # Extract company
            co_match = re.search(r'["\']companyName["\']?\s*:\s*["\']([^"\']+)["\']', page)
            if not co_match:
                co_match = re.search(r'<title>.*?,\s*(.*?)</title>', page, re.DOTALL)
            company = html_mod.unescape(co_match.group(1).strip()) if co_match else 'unknown'
            fp = compute_fingerprint(company, title, 'Remote')
            if fp in known_fps or link.lower() in known_urls:
                print(f"    -> DUP: {company} | {title}")
            else:
                print(f"    *** NEW CANDIDATE: {company} | {title} | {link[:100]}")
                all_candidates.append({'company': company, 'title': title, 'url': link, 'location': 'Remote', 'source': f'Bing-{pname}', 'fp': fp})
        else:
            print(f"    -> no PM title match: {title[:60]}")

# ── 2. Generic Bing searches ──
print("\n=== Generic Bing searches ===")
for q in queries:
    url = 'https://www.bing.com/search?q=' + urllib.parse.quote(q) + '&count=15'
    content, status = fetch(url)
    if status != 200:
        print(f"  [{q}] Bing fetch failed: HTTP {status}")
        continue
    links = re.findall(r'<h2><a[^>]*href="(https?://[^"]+)"', content)
    links = [html_mod.unescape(l) for l in links]
    ats_links = [l for l in links if any(k in l.lower() for k in ['greenhouse', 'lever', 'ashby', 'workday', 'smartrecruiters', 'icims'])]
    print(f"  [{q}] {len(ats_links)} ATS links found")
    for link in ats_links[:5]:
        if link.lower() in known_urls:
            print(f"    DUP: {link[:100]}")
            continue
        page, pstatus = fetch(link, timeout=10)
        if pstatus != 200 or len(page) < 3000:
            print(f"    -> fetch failed (HTTP {pstatus}, size={len(page)})")
            continue
        if 'captcha' in page.lower() or 'challenge' in page.lower():
            print(f"    -> blocked (captcha)")
            continue
        title_match = re.search(r'<title>(.*?)</title>', page, re.DOTALL)
        title = html_mod.unescape(title_match.group(1).strip()) if title_match else ''
        matched = title_matches(title)
        if matched:
            co_match = re.search(r'<title>.*?,?\s*(.*?)</title>', page, re.DOTALL)
            company = html_mod.unescape(co_match.group(1).strip()) if co_match else 'unknown'
            fp = compute_fingerprint(company, title, 'Remote')
            if fp in known_fps or link.lower() in known_urls:
                print(f"    -> DUP: {company} | {title}")
            else:
                print(f"    *** NEW: {company} | {title} | {link[:100]}")
                all_candidates.append({'company': company, 'title': title, 'url': link, 'location': 'Remote', 'source': 'Bing-generic', 'fp': fp})

print(f"\n{'='*60}")
print(f"TOTAL BING RESULTS: {total_bing_results} ATS links")
print(f"NEW CANDIDATES: {len(all_candidates)}")
for c in all_candidates:
    print(f"  {c['company']} | {c['title']} | {c['url']}")
