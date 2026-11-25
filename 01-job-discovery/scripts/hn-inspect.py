#!/usr/bin/env python3
import urllib.request, re
url = "https://news.ycombinator.com/item?id=49522897&sort=new"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64)'})
with urllib.request.urlopen(req, timeout=20) as resp:
    content = resp.read().decode('utf-8', errors='replace')

# Find the first commtext block and dump surrounding HTML
idx = content.find('commtext')
if idx >= 0:
    # Go back to find the start of the comment row
    start = max(0, idx - 2000)
    print("=== HTML around first commtext (2000 chars before) ===")
    print(content[start:idx+500])
    print("\n=== === ===")

# Look for timestamp patterns
print("\n=== Searching for date patterns ===")
# Try various timestamp formats
patterns = [
    (r'title="(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})"', "ISO title attr"),
    (r'streaming_since|<time[^>]+datetime="([^"]+)"', "time tag"),
    (r'(\d{2}/\d{2}/\d{2})', "slash dates"),
    (r'class="[^"]*time[^"]*"[^>]*>([^<]+)', "time class"),
    (r'itemprop="datePublished"[^>]*content="([^"]+)"', "itemprop datePublished"),
    (r'data-timestamp="(\d+)"', "data-timestamp"),
]
for pat, desc in patterns:
    matches = re.findall(pat, content, re.IGNORECASE)
    print(f"  {desc}: {len(matches)} matches, sample: {matches[:3]}")

# Try to find the structure of a single comment block
# Look for <tr class="athing comtr" 
print("\n=== Comment row patterns ===")
for pat in ['class="athing comtr', 'class="athing', '<article', '<div class="comment', 'data-comment']:
    count = content.count(pat)
    print(f"  '{pat}': {count} occurrences")

# Dump raw HTML around 2nd comment
idx2 = content.find('commtext', idx + 1)
if idx2 >= 0:
    print(f"\n=== HTML around 2nd commtext ===")
    print(content[idx2-1500:idx2+300])
