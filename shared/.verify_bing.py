import urllib.request, urllib.parse, re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
}

query = '"product manager" "AI" remote hiring 2026'
url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}&count=20"

req = urllib.request.Request(url, headers=HEADERS)
try:
    with urllib.request.urlopen(req, timeout=15) as r:
        status = r.status
        body = r.read().decode("utf-8", errors="replace")
    print(f"Status: {status}, Body length: {len(body)}")
    job_links = re.findall(r'href="(https?://(?!www\.bing\.com|go\.microsoft\.com|bing\.com|microsoft\.com)[^"]+)"', body)
    print(f"Raw href links found: {len(job_links)}")
    b_algo = body.count('b_algo')
    print(f"b_algo occurrences: {b_algo}")
    ats_patterns = ['greenhouse', 'lever.co', 'ashbyhq', 'workday', 'smartrecruit', 'jobs.lever']
    ats_count = 0
    for link in job_links[:30]:
        for pat in ats_patterns:
            if pat in link.lower():
                print(f"  ATS link: {link[:100]}")
                ats_count += 1
                break
    print(f"ATS links found: {ats_count}")
    idx = body.find('b_algo')
    if idx >= 0:
        print(f"HTML around b_algo: {body[idx:idx+800]}")
    else:
        idx2 = body.find('<li')
        if idx2 >= 0:
            print(f"HTML around first <li: {body[idx2:idx2+800]}")
        else:
            print(f"Body snippet: {body[:2000]}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
