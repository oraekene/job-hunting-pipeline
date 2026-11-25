#!/usr/bin/env python3
"""Fetch MCI (iCIMS) job posting content."""
import urllib.request, ssl, re

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

url = 'https://careers-mci2.icims.com/jobs/50183/ai-product-manager/job'
req = urllib.request.Request(url, headers={
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
})
with urllib.request.urlopen(req, timeout=25, context=ctx) as resp:
    html = resp.read().decode('utf-8', errors='replace')

print(f"Total HTML length: {len(html)}")

# Check for JSON-LD
ld_scripts = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE)
print(f"JSON-LD scripts found: {len(ld_scripts)}")
for i, ld in enumerate(ld_scripts):
    print(f"\n--- LD[{i}] ---")
    print(ld[:2000])
    try:
        import json
        data = json.loads(ld.strip())
        print("PARSED KEYS:", list(data.keys()))
    except:
        pass

# Check for embedded JSON data (iCIMS often has data in script tags)
json_matches = re.findall(r'iCMS_Json.*?(\{.*?\})', html, re.DOTALL | re.IGNORECASE)
print(f"\niCMS_Json matches: {len(json_matches)}")
for i, m in enumerate(json_matches):
    print(f"  JSON[{i}] (first 500): {m[:500]}")

# Look for job description content in the HTML
# iCIMS typically renders via JS, check for any text content
text = re.sub(r'<[^>]+>', '\n', html)
text = re.sub(r'\n\s*\n', '\n', text)
text = re.sub(r'[ \t]+', ' ', text)
lines = [l.strip() for l in text.split('\n') if l.strip() and len(l.strip()) > 2]
clean = '\n'.join(lines)
print(f"\nBody text length: {len(clean)}")
if len(clean) > 200:
    print(f"\nBody text (first 3000):")
    print(clean[:3000])
    print(f"\n... (skipping middle) ...")
    print(f"Body text (last 2000):")
    print(clean[-2000:])

# Save to file
with open('00-orchestrator/scripts/_mci_92_raw.txt', 'w', encoding='utf-8') as f:
    f.write(html)
print(f"\nHTML saved to _mci_92_raw.txt")
