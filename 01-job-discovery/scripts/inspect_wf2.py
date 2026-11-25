#!/usr/bin/env python3
"""Deep inspect wellfound HTML structure — find company/location in card."""
import re
from bs4 import BeautifulSoup

html = open('wellfound_pm_search.html', 'r', errors='replace').read()
soup = BeautifulSoup(html, 'lxml')

# Find the first job link and show full surrounding HTML
a = soup.find('a', href=re.compile(r'^/jobs/\d+'))
if a:
    # Go up several parents to find the card
    parent = a
    for i in range(8):
        parent = parent.parent
        if parent.name:
            html_str = str(parent)[:5000]
            # Look for company name patterns
            if '<!-- -->' in str(parent) or re.search(r'>(?:Remote|USA|UK|EMEA|Europe|Worldwide|Nigeria|Canada|Onsite)', html_str, re.I):
                print(f"Parent level {i}: {parent.name} class={parent.get('class','')}")
                print(html_str[:2000])
                print('---')

# Alternative: search for PM-related job links specifically
pm_links = []
for a in soup.find_all('a', href=re.compile(r'^/jobs/\d+')):
    title = a.get_text(strip=True).lower()
    if 'product' in title and 'manager' in title:
        pm_links.append(a)

print(f'\nPM-related links found: {len(pm_links)}')
for a in pm_links[:5]:
    title = a.get_text(strip=True)
    href = a.get('href', '')
    full_url = f'https://wellfound.com{href}'
    # Get the full card by going up to a reasonable parent
    card = a.find_parent('div')
    # Try to extract company and location from the broader context
    # Look for patterns in the card text
    card_text = card.get_text(' | ', strip=True) if card else ''
    print(f'Title: {title[:60]}')
    print(f'URL: {full_url}')
    print(f'Card text: {card_text[:200]}')
    print()
