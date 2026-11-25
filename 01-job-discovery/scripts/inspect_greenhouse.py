#!/usr/bin/env python3
"""Inspect Greenhouse job page HTML structure for data extraction."""
import requests, re, json
from bs4 import BeautifulSoup

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
           'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}

# Test Greenhouse pages
urls = [
    ('Wikimedia', 'https://job-boards.greenhouse.io/wikimedia/jobs/8140060'),
    ('Pomelo Care', 'https://job-boards.greenhouse.io/pomelocare/jobs/6167736004'),
    ('Baton', 'https://job-boards.greenhouse.io/baton/jobs/5210863007'),
]

for name, url in urls:
    print(f"\n=== {name} ({url}) ===")
    r = requests.get(url, headers=HEADERS, timeout=15)
    print(f"HTTP {r.status_code}, size={len(r.text)}")
    soup = BeautifulSoup(r.text, 'lxml')
    
    # Check for JSON-LD
    ld_scripts = soup.find_all('script', type='application/ld+json')
    print(f"JSON-LD scripts: {len(ld_scripts)}")
    for s in ld_scripts[:3]:
        try:
            data = json.loads(s.string.strip().strip('[]').rstrip('}'))
            if isinstance(data, dict):
                print(f"  JSON-LD keys: {list(data.keys())[:10]}")
                for k in ['@type','title','datePosted','jobLocation','baseSalary','hiringOrganization','description','employmentType']:
                    if k in data:
                        v = json.dumps(data[k]) if not isinstance(data[k], str) else data[k]
                        print(f"    {k}: {v[:120]}")
        except Exception as e:
            print(f"    parse error: {e}")
    
    # Check meta tags
    meta_tags = {m.get('name',''): m.get('content','') for m in soup.find_all('meta', attrs={'name': True})}
    for key in ['keywords', 'description']:
        if key in meta_tags:
            print(f"  meta {key}: {meta_tags[key][:150]}")
    
    # Check for job title in h1/h2
    for tag in ['h1', 'h2', 'h3']:
        els = soup.find_all(tag)
        for el in els[:3]:
            txt = el.get_text(strip=True)
            if len(txt) > 5 and len(txt) < 200:
                print(f"  {tag}: {txt[:100]}")
    
    # Check for embedded JSON (window.GHW or similar)
    for script in soup.find_all('script'):
        content = script.string or ''
        if content and 'job' in content.lower()[:500] and len(content) > 200:
            # Look for company name, title, location in the script
            titles = re.findall(r'"?title"?\s*:\s*"([^"]+)"', content[:2000])
            companies = re.findall(r'"?company"?\s*:\s*"([^"]+)"', content[:2000])
            locations = re.findall(r'"?location"?\s*:\s*"([^"]+)"', content[:2000])
            dates = re.findall(r'"?(?:date_posted|datePosted|posted_at)"?\s*:\s*"([^"]+)"', content[:2000])
            if titles:
                print(f"  Script title: {titles[:3]}")
            if companies:
                print(f"  Script company: {companies[:3]}")
            if locations:
                print(f"  Script location: {locations[:3]}")
            if dates:
                print(f"  Script date: {dates[:3]}")
    
    # Check for specific Greenhouse data attributes
    job_title_div = soup.find(class_=re.compile(r'job-?title', re.I))
    job_location = soup.find(class_=re.compile(r'job-?location|location', re.I))
    if job_title_div:
        print(f"  job-title class: {job_title_div.get_text(strip=True)[:100]}")
    if job_location:
        print(f"  location class: {job_location.get_text(strip=True)[:100]}")
