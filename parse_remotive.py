#!/usr/bin/env python3
"""Parse Remotive.com jobs page for PM-matching roles."""
import urllib.request, re, html as html_mod, json

TITLE_VARIANTS = [
    "product manager", "ai product manager", "ai engineer",
    "automation engineer", "associate product manager", "junior product manager",
    "workflow engineer", "product owner", "technical product manager",
    "growth product manager", "ai/ml product manager"
]

def title_matches_variant(title):
    tl = title.lower()
    return any(v in tl for v in TITLE_VARIANTS)

# Fetch Remotive.com jobs page
try:
    req = urllib.request.Request(
        'https://remotive.com/jobs',
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    )
    resp = urllib.request.urlopen(req, timeout=20)
    html_text = resp.read().decode('utf-8', errors='replace')
    print(f"Remotive web: HTTP {resp.status}, {len(html_text)} chars")

    # Find all job listing links — Remotive uses /remote-jobs/... format
    job_links = re.findall(r'href="(/remote-jobs/[a-z0-9-]+)"', html_text, re.IGNORECASE)
    # Deduplicate while preserving order
    seen = set()
    unique_links = []
    for l in job_links:
        if l not in seen and not l.endswith('/jobs') and 'category' not in l and 'page' not in l:
            seen.add(l)
            unique_links.append(l)
    print(f"Unique job links: {len(unique_links)}")
    for l in unique_links[:5]:
        print(f"  {l}")

    # Also try to extract from the full page — look for job title containers
    # Remotive jobs are in <h2> or <h3> tags with job titles
    titles = re.findall(r'<(?:h[1-6])[^>]*class="[^"]*job[^"]*"[^>]*>(.*?)</h', html_text, re.DOTALL | re.IGNORECASE)
    if not titles:
        # Try different patterns
        titles = re.findall(r'<a[^>]*href="/remote-jobs/[a-z0-9-]+[^"]*"[^>]*>(.*?)</a>', html_text, re.DOTALL | re.IGNORECASE)
    
    pm_jobs = []
    # Also look for the pattern: a tag with job link AND title text
    link_title_pattern = re.findall(r'<a[^>]*href="(/remote-jobs/[a-z0-9-]+)"[^>]*>(.*?)</a>', html_text, re.DOTALL | re.IGNORECASE)
    
    for url_path, title_html in link_title_pattern:
        # Clean title
        title = re.sub(r'<[^>]+>', '', title_html).strip()
        title = html_mod.unescape(title)
        if title and title_matches_variant(title):
            pm_jobs.append({
                'company': '',  # will extract from page
                'title': title,
                'url': 'https://remotive.com' + url_path,
                'location': 'Remote',
                'salary': '',
                'posted_at_raw': None,
                'source_board': 'Remotive',
                'ats_platform': 'remotive',
            })
    
    print(f"\nPM title matches from Remotive page: {len(pm_jobs)}")
    for j in pm_jobs[:10]:
        print(f"  {j['title']} | {j['url']}")

    with open('remotive_web_matches.json', 'w') as f:
        json.dump(pm_jobs, f, indent=2)
    print("Saved to remotive_web_matches.json")
except Exception as e:
    print(f"Remotive web ERROR: {e}")
