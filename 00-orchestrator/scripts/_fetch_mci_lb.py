#!/usr/bin/env python3
"""Fetch MCI (iCIMS) and Lead Bank (Wellfound) job posting content."""
import urllib.request, ssl, re, json

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
            return resp.read().decode('utf-8', errors='replace'), resp.status
    except urllib.error.HTTPError as e:
        return f'HTTP_ERROR_{e.code}: {e.reason}', e.code
    except Exception as e:
        return f'ERROR: {type(e).__name__}: {e}', 0

def extract_text(html):
    """Extract readable text from HTML."""
    if not html or html.startswith('HTTP_ERROR') or html.startswith('ERROR'):
        return html, 0
    # Try JSON-LD first
    ld_scripts = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE)
    ld_data = None
    for ld in ld_scripts:
        try:
            data = json.loads(ld.strip())
            if '@type' in data and ('JobPosting' in str(data.get('@type', '')) or 'job' in str(data.get('@type','')).lower()):
                ld_data = data
                break
        except:
            pass
    # Extract body text
    body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
    body = body_match.group(1) if body_match else html
    text = re.sub(r'<[^>]+>', '\n', body)
    text = re.sub(r'\n\s*\n', '\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    lines = [l.strip() for l in text.split('\n') if l.strip() and len(l.strip()) > 1]
    clean = '\n'.join(lines)
    return clean, ld_data

# Fetch MCI (iCIMS) - app 92
print("=== App 92: MCI (iCIMS) ===")
mci_html, mci_status = fetch('https://careers-mci2.icims.com/jobs/50183/ai-product-manager/job')
print(f"Status: {mci_status}, HTML length: {len(mci_html) if isinstance(mci_html, str) else 'N/A'}")
if not mci_html.startswith('HTTP_ERROR') and not mci_html.startswith('ERROR'):
    mci_text, mci_ld = extract_text(mci_html)
    print(f"Text length: {len(mci_text)}")
    print(f"JSON-LD: {'found' if mci_ld else 'none'}")
    if mci_ld:
        print(f"JD keys: {list(mci_ld.keys())}")
        for k in ['title', 'description', 'hiringOrganization', 'jobLocation', 'datePosted', 'qualifications']:
            v = mci_ld.get(k, '')
            if v:
                print(f"  {k}: {str(v)[:300]}")
    if mci_text and len(mci_text) > 200:
        print(f"\nText (first 3000):")
        print(mci_text[:3000])
    # Save raw HTML
    with open('00-orchestrator/scripts/_mci_92_raw.txt', 'w', encoding='utf-8') as f:
        f.write(mci_html)
    print(f"\nSaved to _mci_92_raw.txt")
else:
    print(mci_html)

print("\n" + "="*60 + "\n")

# Fetch Lead Bank (Wellfound) - app 94
print("=== App 94: Lead Bank (Wellfound) ===")
lb_html, lb_status = fetch('https://wellfound.com/jobs/4678061-principal-product-manager')
print(f"Status: {lb_status}, HTML length: {len(lb_html) if isinstance(lb_html, str) else 'N/A'}")
if not lb_html.startswith('HTTP_ERROR') and not lb_html.startswith('ERROR'):
    lb_text, lb_ld = extract_text(lb_html)
    print(f"Text length: {len(lb_text)}")
    print(f"JSON-LD: {'found' if lb_ld else 'none'}")
    if lb_ld:
        print(f"JD keys: {list(lb_ld.keys())}")
        for k in ['title', 'description', 'hiringOrganization', 'jobLocation', 'datePosted', 'qualifications']:
            v = lb_ld.get(k, '')
            if v:
                print(f"  {k}: {str(v)[:300]}")
    if lb_text and len(lb_text) > 200:
        print(f"\nText (first 3000):")
        print(lb_text[:3000])
    with open('00-orchestrator/scripts/_lb_94_raw.txt', 'w', encoding='utf-8') as f:
        f.write(lb_html)
    print(f"\nSaved to _lb_94_raw.txt")
else:
    print(lb_html)
