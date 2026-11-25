#!/usr/bin/env python
"""Inspect HN page structure to find comment elements."""
import requests, re
from bs4 import BeautifulSoup

url = 'https://news.ycombinator.com/item?id=49522897'
r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
soup = BeautifulSoup(r.text, 'html.parser')

print(f"Page length: {len(r.text)}")
print(f"Title: {soup.title.string if soup.title else 'N/A'}")

# Search for 'product manager' in the text
text_content = soup.get_text()
print(f"'product manager' count: {text_content.lower().count('product manager')}")

# Find elements containing 'product manager'
for match in soup.find_all(string=re.compile('product manager', re.I)):
    parent = match.parent
    print(f"  Parent: tag={parent.name}, class={parent.get('class', [])}, string_starts={str(match)[:50]}")

# Check various comment structures
for selector, label in [
    ('span.commtext', 'span.commtext'),
    ('td.comment', 'td.comment'),
    ('div.ind', 'div.ind'),
    ('.comment', '.comment'),
    ('p', '<p> tags'),
    ('td.default', 'td.default'),
    ('table', 'tables'),
]:
    elems = soup.select(selector)
    print(f"  {label}: {len(elems)}")

# Look for tr with class 'athing' (HN comment rows)
athing = soup.find_all('tr', class_='athing')
print(f"  tr.athing: {len(athing)}")

# Search for 'hiring' text
hiring_matches = text_content.lower().count('hiring')
print(f"'hiring' count: {hiring_matches}")

# Look at the full HTML around a PM mention
idx = r.text.lower().find('product manager')
if idx >= 0:
    snippet = r.text[max(0, idx-500):idx+500]
    print(f"\nHTML around 'product manager' (first occurrence):")
    print(snippet[:1000])
