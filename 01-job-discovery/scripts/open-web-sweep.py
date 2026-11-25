#!/usr/bin/env python
"""Open-web sweep via Bing platform-dork queries. Returns candidate job URLs."""
import urllib.request, json, re, urllib.parse, datetime

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml',
}

TITLE_VARIANTS = [
    "Product Manager", "AI Product Manager", "Technical Product Manager",
    "Junior Product Manager", "Associate Product Manager",
    "Growth Product Manager", "AI/ML Product Manager",
    "AI Engineer", "Automation Engineer",
    "Workflow Engineer", "Product Owner",
]

ATS_PLATFORMS = [
    ("Greenhouse", "site:boards.greenhouse.com"),
    ("Lever", "site:jobs.lever.co"),
    ("Ashby", "site:careers.ashbyhq.com"),
    ("SmartRecruiters", "site:careers.smartrecruiters.com"),
    ("Workday", "site:myworkdayjobs.com"),
    ("iCIMS", "site:jobs.icims.com"),
]

TITLES_QUERY = ' OR '.join(f'"{t}"' for t in TITLE_VARIANTS)
GENERIC_QUERY = f'"Product Manager" "AI Engineer" remote "hiring" 2026'

def bing_search(q):
    url = f'https://www.bing.com/search?q={urllib.parse.quote(q)}'
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        html = urllib.request.urlopen(req, timeout=30).read().decode('utf-8', 'replace')
        return html
    except Exception as e:
        return f'FETCH_ERROR: {e}'

def extract_links(html):
    """Extract organic Bing result links."""
    links = []
    for m in re.finditer(r'href="(https?://[^"]+)"', html):
        url = m.group(1)
        if url.startswith('http') and 'bing.com' not in url and 'microsoft.com' not in url:
            links.append(url)
    return links

results = {}
for plat_name, plat_site in ATS_PLATFORMS:
    q = f'{plat_site} {TITLES_QUERY} remote'
    html = bing_search(q)
    if html.startswith('FETCH_ERROR'):
        results[plat_name] = {'status': 'error', 'error': html}
        print(f"=== {plat_name}: ERROR {html} ===")
        continue
    # Try to extract b_algon links
    b_algo = re.findall(r'<li class="b_algo".*?</li>', html, re.DOTALL)
    links = []
    for li in b_algo[:10]:
        m = re.search(r'href="(https?://[^"]+)"', li)
        if m:
            links.append(m.group(1))
    if not links:
        links = extract_links(html)[:12]
    # Filter to job-related URLs
    job_links = [l for l in links if re.search(r'job|career|position|role', l, re.I)]
    results[plat_name] = {'count': len(job_links), 'urls': job_links[:12]}
    print(f"=== {plat_name}: {len(job_links)} job URLs ===")
    for u in job_links[:8]:
        print(f"  {u[:120]}")
    print()

# Generic search
html = bing_search(GENERIC_QUERY)
if html.startswith('FETCH_ERROR'):
    results['generic'] = {'status': 'error', 'error': html}
    print(f"=== generic: ERROR {html} ===")
else:
    links = extract_links(html)[:15]
    job_links = [l for l in links if re.search(r'job|career|position|role', l, re.I)]
    results['generic'] = {'count': len(job_links), 'urls': job_links[:15]}
    print(f"=== generic: {len(job_links)} job URLs ===")
    for u in job_links[:10]:
        print(f"  {u[:120]}")

print("\n=== SUMMARY ===")
total = 0
for name, data in results.items():
    if data.get('status') == 'error':
        print(f"  {name}: ERROR")
    else:
        total += data['count']
        print(f"  {name}: {data['count']} URLs")
print(f"  TOTAL candidate URLs: {total}")

# Save to shared/.outbox for the orchestrator to pick up
import os
os.makedirs('shared/.outbox', exist_ok=True)
with open('shared/.outbox/open-web-sweep-candidates.json', 'w') as f:
    json.dump(results, f, indent=2)
print("Saved to shared/.outbox/open-web-sweep-candidates.json")
