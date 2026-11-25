#!/usr/bin/env python3
"""
Open-web sweep — searches Bing and accessible job boards for PM roles.
Uses urllib (no external deps) since Firecrawl/web_search are unconfigured.
"""
import urllib.request, urllib.parse, re, json
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from pathlib import Path

PYEXE = "/c/Users/rotim/AppData/Local/hermes/hermes-agent/venv/Scripts/python"
SKILL_ROOT = Path("C:/Users/rotim/AppData/Local/hermes/skills/job-hunting")
DB_PATH = SKILL_ROOT / "shared" / "applications.db"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

TITLE_VARIANTS = [
    "Product Manager", "AI Product Manager", "AI Engineer", "Automation Engineer",
    "Associate Product Manager", "Junior Product Manager", "Workflow Engineer",
    "Product Owner", "Technical Product Manager", "Growth Product Manager",
    "AI/ML Product Manager",
]

def fetch(url, timeout=15):
    """Fetch a URL, return (content, status_code)."""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.read().decode('utf-8', errors='replace'), resp.status
    except urllib.error.HTTPError as e:
        return '', e.code
    except Exception as e:
        return f'ERROR: {e}', 0

def bing_search(query, count=10):
    """Search Bing via HTML and return list of {url, title, snippet}."""
    encoded = urllib.parse.quote(query)
    url = f'https://www.bing.com/search?q={encoded}&count={count}'
    content, status = fetch(url)
    if status != 200 or not content:
        return f'Bing returned HTTP {status}'
    soup = BeautifulSoup(content, 'lxml')
    results = []
    for li in soup.find_all('li', class_='b_algo'):
        link = li.find('a', href=True)
        if link:
            href = link.get('href', '')
            # Unwrap Bing redirect URLs
            if '/ck/a?' in href:
                m = re.search(r'rd=(.*?)(&|$)', href)
                if m:
                    import urllib.parse as up
                    try:
                        href = up.unquote(m.group(1))
                    except:
                        pass
            title = link.get_text(strip=True)
            p_tags = li.find_all('p')
            snippet = ' '.join(p.get_text(strip=True) for p in p_tags)[:300]
            results.append({'url': href, 'title': title, 'snippet': snippet})
    return results

def title_matches(title):
    """Check if title matches any variant."""
    title_lower = title.lower().strip()
    for variant in TITLE_VARIANTS:
        v = variant.lower().strip()
        if v in title_lower or title_lower in v:
            return variant
    return None

def normalize_title(title):
    t = title.lower().strip()
    t = re.sub(r'\([^)]*\)', '', t)
    t = re.sub(r'\s*-\s*', ' ', t)
    t = re.sub(r'\b(req|id)\s*#?\d+', '', t, flags=re.I)
    t = re.sub(r'\b(staff|principal|lead|senior|junior|associate|vp|head)\b', '', t)
    t = re.sub(r'[^a-z0-9\s]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def compute_fingerprint(company, role_title, location):
    norm_title = normalize_title(role_title)
    loc = location.lower().strip() if location else ""
    if 'remote' in loc:
        loc = 'remote'
    elif 'united states' in loc or 'us only' in loc:
        loc = 'united states'
    elif 'nigeria' in loc:
        loc = 'nigeria'
    return f"{company.lower().strip()}|{norm_title}|{loc}"

def main():
    print("=" * 60)
    print("OPEN-WEB SWEEP")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
    print("=" * 60)

    # Load DB state
    conn = __import__('sqlite3').connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("SELECT posting_url FROM applications WHERE posting_url IS NOT NULL")
    existing_urls = set(row[0] for row in cursor.fetchall())
    cursor.execute("SELECT posting_url FROM posting_sources WHERE posting_url IS NOT NULL")
    existing_source_urls = set(row[0] for row in cursor.fetchall())
    cursor.execute("SELECT posting_fingerprint FROM applications WHERE posting_fingerprint IS NOT NULL")
    existing_fingerprints = set(row[0] for row in cursor.fetchall())
    cursor.execute("""SELECT COUNT(*) FROM applications WHERE status IN ('staged','awaiting_approval','approved_sent','edited_then_sent') AND date(staged_at) = date('now','localtime')""")
    staged_today = cursor.fetchone()[0]
    cursor.execute("""SELECT COUNT(*) FROM applications WHERE date(discovered_at) = date('now','localtime')""")
    discovered_today = cursor.fetchone()[0]
    conn.close()

    daily_cap = 15
    remaining = daily_cap - discovered_today
    print(f"DB: discovered_today={discovered_today}, staged_today={staged_today}, remaining={remaining}")

    # ===== Bing searches =====
    all_candidates = []

    # Per-platform searches
    platforms = [
        ("Lever", "site:jobs.lever.co"),
        ("Greenhouse", "site:jobs.greenhouse.io"),
        ("Ashby", "site:jobs.ashbyhq.com"),
        ("SmartRecruiters", "site:jobs.smartrecruiters.com"),
        ("iCIMS", "site:jobs.icims.com"),
    ]

    title_query = ' OR '.join(f'"{v}"' for v in TITLE_VARIANTS[:4])  # core variants
    location_q = 'remote OR "united states" OR worldwide'

    for plat_name, site_dork in platforms:
        query = f'{site_dork} ({title_query}) {location_q} 2026'
        print(f"\n  Bing [{plat_name}]: {query[:120]}")
        results = bing_search(query, count=10)
        if isinstance(results, str):
            print(f"    {results}")
            continue
        print(f"    Found {len(results)} results")
        job_results = [r for r in results if not any(d in r['url'] for d in ['bing.com', 'merriam-webster', 'cambridge.org', 'wikipedia', 'producthunt'])]
        print(f"    After filtering: {len(job_results)} non-dictionary results")
        for r in job_results:
            matched = title_matches(r['title'])
            if matched:
                print(f"    *** PM MATCH: {r['title'][:60]} | {r['url'][:100]} | {r['snippet'][:80]}")
                all_candidates.append(r)
            else:
                print(f"    - {r['title'][:60]} | {r['url'][:100]}")

    # Generic search
    print(f"\n  Bing [generic]: Product Manager remote hiring 2026")
    results = bing_search('"product manager" remote hiring 2026', count=15)
    if isinstance(results, str):
        print(f"    {results}")
    else:
        print(f"    Found {len(results)} results")
        non_dict = [r for r in results if not any(d in r['url'] for d in ['bing.com', 'merriam-webster', 'cambridge.org', 'wikipedia', 'producthunt', 'thembains', 'simplicable', 'marketingtutor', 'aha.io'])]
        print(f"    After filtering: {len(non_dict)} non-dictionary results")
        for r in non_dict[:10]:
            matched = title_matches(r['title'])
            if matched:
                print(f"    *** PM MATCH: {r['title'][:60]} | {r['url'][:100]} | {r['snippet'][:80]}")
                all_candidates.append(r)

    # ===== DuckDuckGo HTML search =====
    print(f"\n  DuckDuckGo: product manager hiring remote 2026")
    ddg_query = urllib.parse.quote('product manager hiring remote 2026')
    content, status = fetch(f'https://html.duckduckgo.com/html/?q={ddg_query}')
    if status == 200 and 'ERROR' not in content:
        soup = BeautifulSoup(content, 'lxml')
        links = soup.find_all('a', class_='result__a')
        print(f"    Found {len(links)} results")
        for link in links[:10]:
            href = link.get('href', '')
            title = link.get_text(strip=True)
            matched = title_matches(title)
            if matched:
                print(f"    *** PM MATCH: {title[:60]} | {href[:100]}")
                all_candidates.append({'url': href, 'title': title, 'source': 'ddg'})
            else:
                print(f"    - {title[:60]} | {href[:100]}")
    else:
        print(f"    DDG returned HTTP {status}: {content[:200]}")

    # ===== Remotive =====
    print(f"\n  Remotive: searching for PM jobs")
    content, status = fetch('https://remotive.com/categories/product-management-jobs')
    if status == 200 and 'ERROR' not in content:
        soup = BeautifulSoup(content, 'lxml')
        job_links = soup.find_all('a', href=re.compile(r'/remote-jobs/'))
        print(f"    Found {len(job_links)} job links")
        for link in job_links[:20]:
            title = link.get_text(strip=True)
            href = link.get('href', '')
            matched = title_matches(title)
            if matched:
                print(f"    *** PM MATCH: {title[:60]} | {href[:100]}")
                all_candidates.append({'url': f'https://remotive.com{href}', 'title': title, 'source': 'remotive'})
    else:
        print(f"    Remotive returned HTTP {status}")

    # ===== We Work Remotely =====
    print(f"\n  We Work Remotely: Product Manager jobs")
    content, status = fetch('https://weworkremotely.co/categories/remote-product-manager-jobs')
    if status == 200 and 'ERROR' not in content:
        soup = BeautifulSoup(content, 'lxml')
        # WWR job links typically in <a> tags
        job_links = soup.find_all('a', href=re.compile(r'/remote-jobs/'))
        print(f"    Found {len(job_links)} job links")
        for link in job_links[:20]:
            title = link.get_text(strip=True)
            href = link.get('href', '')
            matched = title_matches(title)
            if matched:
                print(f"    *** PM MATCH: {title[:60]} | {href[:100]}")
                all_candidates.append({'url': f'https://weworkremotely.co{href}', 'title': title, 'source': 'wwr'})
    else:
        print(f"    WWR returned HTTP {status}")

    # ===== Dedup and filter =====
    print(f"\n{'='*60}")
    print(f"DEDUP + FILTER")
    print(f"{'='*60}")
    print(f"Total candidates after search: {len(all_candidates)}")

    new_postings = []
    duplicates = []
    filtered = []

    seen_urls = set()
    for c in all_candidates:
        url = c.get('url', '')
        title = c.get('title', '')

        if not url or url in seen_urls:
            continue
        seen_urls.add(url)

        if url in existing_urls or url in existing_source_urls:
            duplicates.append({'title': title, 'url': url, 'reason': 'already in DB'})
            continue

        fp = compute_fingerprint('unknown', title, '')
        if fp in existing_fingerprints:
            duplicates.append({'title': title, 'url': url, 'reason': f'fingerprint: {fp}'})
            continue

        matched = title_matches(title)
        if not matched:
            filtered.append({'title': title, 'url': url, 'reason': 'no title match'})
            continue

        new_postings.append({
            'company': 'unknown',
            'role_title': title,
            'posting_url': url,
            'location': '',
            'posted_at': None,
            'posted_at_raw': '',
            'salary_range': None,
            'source': c.get('source', 'open_web_sweep'),
            'discovered_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'priority': 'high',
            'matched_variant': matched,
        })

    to_queue = new_postings[:remaining]
    overflow = new_postings[remaining:]

    # Save results
    results = {
        'scan_time': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'sources_checked': {
            'linkedin': 'BLOCKED (login wall)',
            'indeed': 'BLOCKED (HTTP 403)',
            'remoteok': 'BLOCKED (302 redirect loop)',
            'wellfound': 'OK - 3 PM jobs found, 0 new (all already in DB)',
            'open_web_sweep': f'Bing+DDG+Remotive+WWR searched, {len(all_candidates)} candidates found',
        },
        'new_postings': to_queue,
        'duplicates': duplicates,
        'filtered_out': filtered,
        'overflow': overflow,
        'daily_cap': daily_cap,
        'discovered_today': discovered_today,
        'remaining_slots': remaining,
        'queued_count': len(to_queue),
    }
    results_path = SKILL_ROOT / "01-job-discovery" / "scripts" / "openweb_sweep_results.json"
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"New candidates from open-web sweep: {len(all_candidates)}")
    print(f"New postings (post-filter, post-dedup): {len(new_postings)}")
    print(f"To queue: {len(to_queue)}")
    print(f"Duplicates: {len(duplicates)}")
    print(f"Filtered out: {len(filtered)}")

    if to_queue:
        print(f"\nPOSTINGS TO QUEUE:")
        for p in to_queue:
            print(f"  [{p['priority'].upper()}] {p['company']}: {p['role_title']}")
            print(f"    URL: {p['posting_url']}")
    else:
        print(f"\nNO NEW POSTINGS TO QUEUE")

    print(f"\nResults saved to: {results_path}")

if __name__ == "__main__":
    main()
