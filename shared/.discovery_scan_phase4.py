#!/usr/bin/env python
"""Phase 4: Try Wellfound API and broader Bing searches for PM roles."""

import requests, json, re, datetime
from bs4 import BeautifulSoup

SKILL_ROOT = "C:/Users/rotim/AppData/Local/hermes/skills/job-hunting"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}
BING_URL = 'https://www.bing.com/search'

# --- Try Wellfound API ---
print("=" * 60)
print("Wellfound API search for PM roles")
print("=" * 60)

# Wellfound likely has API endpoints
api_endpoints = [
    'https://wellfound.com/api/jobs',
    'https://wellfound.com/api/v1/jobs',
    'https://wellfound.com/api/search',
    'https://wellfound.com/api/v1/search/jobs',
]

for api_url in api_endpoints:
    try:
        # Try with different params
        r = requests.get(api_url, headers=HEADERS, timeout=10, params={'query': 'product manager', 'remote': True})
        print(f"  {api_url}: status={r.status_code}, len={len(r.text)}")
        if r.status_code == 200 and len(r.text) > 100:
            content_type = r.headers.get('content-type', '')
            print(f"    Content-Type: {content_type}")
            if 'json' in content_type:
                data = r.json()
                print(f"    JSON keys: {list(data.keys())[:5] if isinstance(data, dict) else f'array of {len(data)}'}")
    except Exception as e:
        print(f"  {api_url}: Error - {str(e)[:80]}")

# --- Try Wellfound with query params ---
print("\n--- Wellfound main page with PM filter ---")
for url in ['https://wellfound.com/jobs?query=product+manager', 'https://wellfound.com/jobs?keywords=product+manager']:
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        print(f"  {url}: status={r.status_code}, len={len(r.text)}")
        if r.status_code == 200 and len(r.text) > 5000:
            soup = BeautifulSoup(r.text, 'html.parser')
            job_links = soup.find_all('a', href=re.compile(r'/jobs/\d+'))
            pm_links = []
            for link in job_links:
                href = link.get('href', '')
                full_url = f"https://wellfound.com{href}" if href.startswith('/') else href
                text = link.get_text(strip=True).lower()
                if any(kw in text for kw in ['product manager', 'ai product', 'technical product', 'growth product',
                     'product owner', 'workflow engineer', 'ai engineer', 'automation engineer']):
                    pm_links.append((full_url, text))
            print(f"    Job links: {len(job_links)}, PM-related: {len(pm_links)}")
            for url, text in pm_links[:10]:
                print(f"    -> {text} @ {url}")
    except Exception as e:
        print(f"  {url}: Error - {str(e)[:80]}")

# --- Broader Bing search without site: filters ---
print("\n" + "=" * 60)
print("Broad Bing search for PM roles (no site: filter)")
print("=" * 60)

search_queries = [
    'hiring "AI Product Manager" remote job 2026',
    'hiring "Product Manager" remote job 2026',
    '"Product Manager" remote job Greenhouse',
    '"AI Engineer" remote job posting 2026',
    'remote AI Product Manager job site:greenhouse.io',
    'remote Product Manager job site:lever.co',
    'remote Technical Product Manager job site:ashby.io',
]

job_urls_found = set()
for query in search_queries:
    try:
        r = requests.get(BING_URL, params={'q': query, 'count': 10}, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            # Bing organic results
            results = soup.select('li.b_algo h2 a')
            for a in results:
                href = a.get('href', '')
                title = a.get_text(strip=True)[:100]
                if href and 'bing.com' not in href and not href.startswith('/search'):
                    # Skip known non-job domains
                    skip_domains = ['youtube.com', 'wikipedia.org', 'google.com', 'openai.com', 
                                  'chatgpt.com', 'perplexity.ai', 'deepai.org', 'gemini.google.com',
                                  'ai.google.com', 'meta.ai', 'goojara', 'fawanews', 'tuttosullegalline',
                                  'modernagriculture', 'passioneavicola', 'qualcherisposta', 'forumdiagraria']
                    if not any(d in href.lower() for d in skip_domains):
                        job_urls_found.add((href, title, query))
            if results:
                print(f"\n  Query: {query}")
                for href, title, _ in list(job_urls_found)[-10:]:
                    print(f"    -> {title} @ {href[:100]}")
    except Exception as e:
        print(f"  Query '{query}': Error - {str(e)[:60]}")

# Filter for PM-related results
print(f"\nTotal unique URLs from Bing: {len(job_urls_found)}")
pm_keywords = ['product manager', 'ai product', 'technical product', 'growth product', 'product owner',
               'workflow engineer', 'ai engineer', 'automation engineer', 'junior product', 'associate product',
               'ai/ml product', 'principal product', 'senior product']
pm_urls = [(url, title, query) for url, title, query in job_urls_found if any(kw in (title + url).lower() for kw in pm_keywords)]
print(f"PM-related URLs: {len(pm_urls)}")
for url, title, query in pm_urls[:10]:
    print(f"  [{query[:30]}...] {title[:80]} @ {url[:80]}")
