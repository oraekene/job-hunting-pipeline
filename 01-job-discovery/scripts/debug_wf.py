#!/usr/bin/env python3
"""Debug: check Wellfound HTML for PM job listings."""
import re

html_path = "C:/Users/rotim/AppData/Local/hermes/cache/web/wellfound-jobs-today.html"
with open(html_path, 'r', errors='replace') as f:
    content = f.read()

print(f"HTML size: {len(content)} bytes")

# Check for specific job IDs
for jid in ['4616099', '4612810', '3542480', '4493413', '4678061', '4677997', '4664710']:
    cnt = content.count(jid)
    print(f"Job {jid}: found {cnt} times in HTML")

# Find all /jobs/ links
links = re.findall(r'href="(/jobs/\d+-[^"]+)"', content)
print(f"\nTotal /jobs/ links: {len(links)}")
for l in links:
    print(f"  {l}")

# Find all titles near /jobs/ links
# Look for pattern: href="/jobs/..." >Title<
title_pattern = r'href="(/jobs/\d+-[^"]+)">([^<]+)</a>'
titles = re.findall(title_pattern, content)
print(f"\nTotal job title links: {len(titles)}")
for href, title in titles:
    title = title.strip()
    if any(v in title.lower() for v in ['product manager', 'ai product', 'product owner', 'technical product', 'growth product', 'workflow engineer', 'automation engineer', 'ai engineer', 'product']):
        print(f"  PM MATCH: {title} -> {href}")
