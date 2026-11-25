#!/usr/bin/env python3
"""Fetch Kindred Ashby job posting using urllib (stdlib)."""
import urllib.request, json, re, html as html_mod

url = 'https://jobs.ashbyhq.com/kindred/8868c144-1909-47f2-9c1c-e59a9e4ddce0'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}
req = urllib.request.Request(url, headers=headers)
try:
    resp = urllib.request.urlopen(req, timeout=30)
    html_text = resp.read().decode('utf-8', errors='replace')
    print(f'Status: {resp.status}, HTML len: {len(html_text)}')

    # Try JSON-LD
    ld_blocks = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html_text, re.DOTALL)
    for block in ld_blocks:
        cleaned = re.sub(r'[\x00-\x1f]', ' ', block.strip())
        try:
            data = json.loads(cleaned)
            if isinstance(data, dict) and data.get('@type') == 'JobPosting':
                desc = data.get('description', '')
                if desc:
                    clean = re.sub(r'<[^>]+>', ' ', desc)
                    clean = html_mod.unescape(clean)
                    clean = re.sub(r'\s+', ' ', clean).strip()
                    print(f'JSON-LD JobPosting found! desc_len={len(clean)}')
                    for k in ['title', 'datePosted', 'hiringOrganization']:
                        print(f'  {k}: {data.get(k, "N/A")}')
                    print('=== DESCRIPTION ===')
                    print(clean)
                    exit(0)
        except Exception as e:
            print(f'JSON-LD parse error: {e}')

    # Try embedded JSON
    for m in re.finditer(r'"description"\s*:\s*"(.*?)(?<!\\)",\s*(?:"compensationTiers"|"datePosted"|"hiringOrganization")', html_text, re.DOTALL):
        raw = m.group(1)
        desc = raw.replace('\\n', '\n').replace('<br/>', '\n').replace('<br>', '\n')
        clean = re.sub(r'<[^>]+>', ' ', desc)
        clean = html_mod.unescape(clean)
        clean = re.sub(r'\s+', ' ', clean).strip()
        if len(clean) > 200:
            print(f'Embedded JSON found! desc_len={len(clean)}')
            print('=== DESCRIPTION ===')
            print(clean)
            exit(0)

    # Fallback: body text
    body_match = re.search(r'<body[^>]*>(.*?)</body>', html_text, re.DOTALL | re.IGNORECASE)
    if body_match:
        body_text = re.sub(r'<[^>]+>', ' ', body_match.group(1))
        body_text = html_mod.unescape(body_text)
        body_text = re.sub(r'\s+', ' ', body_text).strip()
        print(f'BODY LEN: {len(body_text)}')
        for marker in ["Here's what you", "What you'll do", "Staff Product", "Kindred", "Responsibilities", "Qualifications"]:
            idx = body_text.find(marker)
            if idx > 0:
                print(f'Found "{marker}" at index {idx}')
                print('=== EXCERPT ===')
                print(body_text[max(0,idx-200):idx+8000])
                exit(0)
        print('=== FULL BODY (first 10000) ===')
        print(body_text[:10000])

    print('=== NO DESCRIPTION FOUND ===')
    print(f'Full HTML (first 5000 chars):')
    print(html_text[:5000])
except Exception as e:
    print(f'ERROR: {e}')
