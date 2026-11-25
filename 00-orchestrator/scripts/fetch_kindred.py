#!/usr/bin/env python3
"""Try multiple strategies to fetch the Kindred Ashby job posting."""
import requests, re, json

URL = "https://jobs.ashbyhq.com/kindred/8868c144-1909-47f2-9c1c-e59a9e4ddce0"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-CH-UA': '"Not_A Brand";v="8", "Chromium";v="120"',
    'Sec-CH-UA-Mobile': '?0',
    'Sec-CH-UA-Platform': '"Windows"',
}

# Strategy 1: Direct fetch with full headers
try:
    resp = requests.get(URL, headers=HEADERS, timeout=30, allow_redirects=True)
    html = resp.text
    print(f"Direct fetch: status={resp.status_code}, len={len(html)}")
    
    # Check for JSON-LD
    ld_blocks = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL)
    for block in ld_blocks:
        cleaned = re.sub(r'[\x00-\x1f]', ' ', block.strip())
        try:
            data = json.loads(cleaned)
            if isinstance(data, dict) and data.get('@type') == 'JobPosting':
                desc = data.get('description', '')
                if desc:
                    print(f"JSON-LD JobPosting found! desc_len={len(desc)}")
                    clean = re.sub(r'<[^>]+>', ' ', desc)
                    import html as html_mod
                    clean = html_mod.unescape(clean)
                    clean = re.sub(r'\s+', ' ', clean).strip()
                    print("=== DESCRIPTION ===")
                    print(clean)
                    exit(0)
        except Exception as e:
            print(f"JSON-LD parse error: {e}")
    
    # If no JSON-LD, check for any description text in the HTML
    if 'Staff Product Manager' in html or 'staff product' in html.lower():
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text).strip()
        idx = text.lower().find('staff')
        if idx > 0:
            print("Found 'staff' in page text:")
            print(text[max(0,idx-200):idx+5000])
            exit(0)
    
    print("No JSON-LD or description text found in direct fetch")
except Exception as e:
    print(f"Direct fetch error: {e}")

# Strategy 2: Try Ashby org page to find the job
try:
    resp = requests.get("https://jobs.ashbyhq.com/kindred", headers=HEADERS, timeout=30)
    html = resp.text
    print(f"\nOrg page: status={resp.status_code}, len={len(html)}")
    ld_blocks = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL)
    for block in ld_blocks:
        cleaned = re.sub(r'[\x00-\x1f]', ' ', block.strip())
        try:
            data = json.loads(cleaned)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get('@type') == 'JobPosting':
                        title = item.get('title', '')
                        if 'staff' in title.lower() or 'product' in title.lower():
                            print(f"Found JobPosting: {title}")
                            desc = re.sub(r'<[^>]+>', ' ', item.get('description', ''))
                            import html as html_mod
                            desc = html_mod.unescape(desc)
                            print(f"=== DESCRIPTION ({len(desc)} chars) ===")
                            print(desc[:6000])
                            exit(0)
        except Exception as e:
            print(f"Org page JSON-LD error: {e}")
    # Also try to find the job URL in the page
    for m in re.finditer(r'href="(/kindred/[a-f0-9-]+)"', html):
        print(f"Found job link: {m.group(1)}")
except Exception as e:
    print(f"Org page error: {e}")

# Strategy 3: Try Wayback Machine CDX API
try:
    cdx_url = "https://web.archive.org/cdx/search/cdx"
    params = {"url": "jobs.ashbyhq.com/kindred/8868c144-1909-47f2-9c1c-e59a9e4ddce0", "matchType": "exact", "limit": "5", "from": "20260801", "to": "20260912"}
    resp = requests.get(cdx_url, params=params, headers=HEADERS, timeout=20)
    print(f"\nWayback CDX: status={resp.status_code}")
    print(f"CDX response: {resp.text[:500]}")
    if resp.text.strip():
        lines = resp.text.strip().split('\n')
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 2:
                ts, url = parts[0], parts[1]
                archive_url = f"https://web.archive.org/web/{ts}/{url}"
                print(f"Trying archive: {archive_url}")
                resp2 = requests.get(archive_url, headers=HEADERS, timeout=30)
                html2 = resp2.text
                print(f"Archive fetch: status={resp2.status_code}, len={len(html2)}")
                ld = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html2, re.DOTALL)
                for block in ld:
                    cleaned = re.sub(r'[\x00-\x1f]', ' ', block.strip())
                    try:
                        data = json.loads(cleaned)
                        if isinstance(data, dict) and data.get('@type') == 'JobPosting':
                            desc = re.sub(r'<[^>]+>', ' ', data.get('description', ''))
                            import html as html_mod
                            desc = html_mod.unescape(desc)
                            print(f"=== ARCHIVE DESCRIPTION ({len(desc)} chars) ===")
                            print(desc[:6000])
                            exit(0)
                    except:
                        pass
except Exception as e:
    print(f"Wayback CDX error: {e}")

print("\nALL STRATEGIES FAILED - could not fetch Kindred posting")
