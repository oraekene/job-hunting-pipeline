#!/usr/bin/env python3
"""Extract JSON-LD JobPosting data from remaining accessible ATS pages."""
import requests, re, json
from bs4 import BeautifulSoup

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
           'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}

urls = [
    ('Snowflake 1', 'https://careers.snowflake.com/us/en/job/SNCOUSA253CD7A2E69453EB8B604BE3E91B6C2EXTERNALENUS'),
    ('Snowflake 2', 'https://careers.snowflake.com/us/en/job/SNCOUS7EFCFE1247594E538A308EA79EAB418EEXTERNALENUS'),
    ('Snowflake 3', 'https://careers.snowflake.com/us/en/job/SNCOUSCACA807AEC05482C8E7B6F31EE3E081BEXTERNALENUS'),
    ('Deel SwingVision', 'https://jobs.deel.com/swingvision/job-details/cb631dcb-1a80-4678-ab29-0ec2853c5ee4/overview'),
    ('Deel SwingVision 2', 'https://jobs.deel.com/swingvision/job-details/c2cc0f23-3e59-4c03-849e-d53e7567a3fd/overview'),
    ('Langfuse Ashby', 'https://jobs.ashbyhq.com/langfuse'),
    ('Checkly Ashby', 'https://jobs.ashbyhq.com/checkly?utm_source=hn'),
    ('Vistulo PO', 'https://ats.vistulo.com/roles/49e20bfe-7453-4ffa-bfe8-8b2799ea3c86/murex-ba-2026-07/hn/'),
    ('SearchAtlas', 'https://careers.searchatlas.com/jobs/599248-product-engineer-pm'),
]

PM_TITLES = ['product manager', 'ai product manager', 'ai engineer', 'automation engineer',
             'associate product manager', 'junior product manager', 'workflow engineer',
             'product owner', 'technical product manager', 'growth product manager',
             'ai/ml product manager', 'head of product', 'product engineer (pm)']

for label, url in urls:
    print(f"\n=== {label} ({url[:70]}) ===")
    try:
        r = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        print(f"HTTP {r.status_code}, final={r.url[:90]}, size={len(r.text)}")
        
        # Extract ALL JSON-LD scripts
        for m in re.finditer(r'<script[^>]*type=["\']?application/ld\+json["\']?[^>]*>(.*?)</script>', r.text, re.DOTALL):
            raw = m.group(1).strip()
            try:
                data = json.loads(raw)
            except:
                try:
                    data = json.loads('[' + raw + ']')
                except:
                    continue
            
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict):
                    atype = item.get('@type', '')
                    if atype in ('JobPosting', ['JobPosting', 'Article'], 'Article', ['Article', 'Product'], ['Article','BroadcastService'], ['Article','Product']):
                        title = item.get('title', item.get('name', ''))
                        company = item.get('hiringOrganization', item.get('publisher', item.get('publisher', {}).get('name', '') if isinstance(item.get('publisher'), dict) else ''))
                        if isinstance(company, dict): company = company.get('name', '')
                        loc = item.get('jobLocation', item.get('jobLocationType', ''))
                        location_str = ''
                        if isinstance(loc, dict):
                            addr = loc.get('address', '')
                            if isinstance(addr, dict): location_str = addr.get('addressLocality', addr.get('addressCountry', ''))
                            elif isinstance(addr, str): location_str = addr
                        elif isinstance(loc, list):
                            location_str = str(loc[0])[:80] if loc else ''
                        elif isinstance(loc, str): location_str = loc
                        date_posted = item.get('datePosted', '')
                        salary = item.get('baseSalary', '')
                        if isinstance(salary, dict): salary = f"${salary.get('value',{}).get('minValue','')}-${salary.get('value',{}).get('maxValue','')}"
                        print(f"  @type={atype} title='{title[:70]}' company='{company[:40]}' loc='{location_str[:40]}' datePosted={date_posted} salary='{str(salary)[:50]}'")
                        # Check PM match
                        tl = title.lower()
                        for vt in PM_TITLES:
                            if vt in tl:
                                print(f"  ** PM MATCH: '{vt}' found in title **")
                                break
    except Exception as e:
        print(f"  ERROR: {str(e)[:80]}")
