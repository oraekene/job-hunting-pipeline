#!/usr/bin/env python3
"""Check Wellfound.com accessibility."""
import urllib.request, re

urls = ['https://wellfound.com/jobs', 'https://wellfound.com/jobs/product-manager']
for url in urls:
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        resp = urllib.request.urlopen(req, timeout=20)
        html = resp.read().decode('utf-8', errors='replace')
        status = resp.status
        body_lower = html.lower()
        print(f"{url}: HTTP {status}, {len(html)} chars")
        if 'captcha' in body_lower or 'challenge' in body_lower:
            print("  BLOCKED: Anti-bot challenge")
        elif len(html) < 2000:
            print("  BLOCKED: Response too small")
        else:
            links = re.findall(r'href="(/jobs/\d+[^\"]+)"', html)
            print(f"  Job links found: {len(links)}")
            for l in links[:5]:
                print(f"    {l}")
    except Exception as e:
        print(f"{url}: ERROR — {e}")

# Also check cached file
import os
cache_path = r'C:\Users\rotim\AppData\Local\hermes\skills\job-hunting\wellfound_pm_search.html'
if os.path.exists(cache_path):
    stat = os.stat(cache_path)
    import datetime
    mtime = datetime.datetime.fromtimestamp(stat.st_mtime, tz=datetime.timezone.utc)
    print(f"\nCache file found: {cache_path}")
    print(f"  Size: {stat.st_size} bytes, Modified: {mtime.isoformat()}")
    with open(cache_path, 'r', encoding='utf-8') as f:
        html = f.read()
    links = re.findall(r'href="(/jobs/\d+-[^\"]+)"', html)
    print(f"  Job links in cache: {len(links)}")
    for l in links[:10]:
        print(f"    {l}")
else:
    print(f"\nCache file not found: {cache_path}")
