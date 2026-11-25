#!/usr/bin/env python3
"""Inspect wellfound HTML structure for company/location extraction."""
import re, sys
from bs4 import BeautifulSoup

html = open('wellfound_pm_search.html', 'r', errors='replace').read()
soup = BeautifulSoup(html, 'lxml')
job_links = soup.find_all('a', href=re.compile(r'^/jobs/\d+'))
print(f'Job links in saved PM search: {len(job_links)}')
for a in job_links[:5]:
    href = a.get('href', '')
    title = a.get_text(strip=True)
    full_url = f'https://wellfound.com{href}'
    nearby = a.find_parent('div')
    nearby_html = str(nearby)[:3000] if nearby else ''
    company_match = re.search(r'>([^<]+)<!-- -->\s*•\s*<', nearby_html)
    loc_match = re.search(r'>(Remote|On-site|Onsite|USA|UK|EMEA|Europe|Worldwide|Nigeria|Canada)[^<]*<', nearby_html, re.I)
    print(f'Title: {title[:70]}')
    print(f'Company: {company_match.group(1).strip() if company_match else "NOT FOUND"}')
    print(f'Location: {loc_match.group(0).strip() if loc_match else "NOT FOUND"}')
    print(f'URL: {full_url}')
    print(f'Nearby snippet: {nearby_html[:600]}')
    print()
