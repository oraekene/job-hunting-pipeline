#!/usr/bin/env python
"""Fetch a job posting URL and extract readable text."""
import sys, re, json, urllib.request

def fetch(url, timeout=25):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    })
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.status, resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        return None, str(e)

def extract_text(html):
    """Extract readable text from HTML."""
    # Remove script/style tags
    html_clean = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.DOTALL)
    # Extract JSON-LD if present
    ld_scripts = re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html_clean, re.DOTALL)
    ld_data = []
    for ld in ld_scripts:
        try:
            ld_data.append(json.loads(ld.strip().rstrip(';') if ld.rstrip().endswith(';') else ld.strip()))
        except:
            pass
    # Extract text
    text = re.sub(r'<[^>]+>', '\n', html_clean)
    text = re.sub(r'\n\s*\n', '\n', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&quot;', '"', text)
    text = re.sub(r'&#39;', "'", text)
    text = re.sub(r'&#x2[fF];', '/', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&#x[0-9A-Fa-f]+;', '', text)
    lines = [l.strip() for l in text.split('\n') if l.strip() and len(l.strip()) > 1]
    return '\n'.join(lines), ld_data

if __name__ == '__main__':
    url = sys.argv[1] if len(sys.argv) > 1 else None
    if not url:
        print("Usage: python fetch_jd.py <url>")
        sys.exit(1)
    status, content = fetch(url)
    if status != 200:
        print(f"ERROR: status={status}, error={content}")
        sys.exit(1)
    text, ld_data = extract_text(content)
    print(f"STATUS: {status}")
    print(f"LENGTH: {len(content)}")
    print(f"JSON-LD blocks: {len(ld_data)}")
    for i, ld in enumerate(ld_data):
        print(f"\n=== JSON-LD block {i} ===")
        print(json.dumps(ld, indent=2)[:3000])
    print(f"\n=== TEXT (first 5000 chars) ===")
    print(text[:5000])
