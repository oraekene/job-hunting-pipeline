import urllib.request, urllib.parse, re
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
}

queries = [
    '"product manager" "AI" remote hiring 2026',
    'site:boards.greenhouse.io "product manager" remote',
    '"AI product manager" remote remote OK 2026 hiring',
]

for query in queries:
    url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}&count=20"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        body = r.read().decode("utf-8", errors="replace")
    soup = BeautifulSoup(body, "html.parser")
    
    print(f"\n=== Query: {query[:60]} ===")
    print(f"Body length: {len(body)}")
    
    # Method 1: li.b_algo h2 a (what the script uses)
    results1 = soup.select("li.b_algo h2 a")
    print(f"  Method 1 (li.b_algo h2 a): {len(results1)} results")
    for a in results1[:5]:
        print(f"    href={a.get('href','')[:80]} | text={a.get_text(strip=True)[:60]}")
    
    # Method 2: li.b_algo a
    results2 = soup.select("li.b_algo a")
    print(f"  Method 2 (li.b_algo a): {len(results2)} results")
    
    # Method 3: all href links
    all_links = re.findall(r'href="([^"]+)"', body)
    external = [l for l in all_links if l.startswith('http') and 'bing.com' not in l and 'microsoft.com' not in l and 'go.microsoft' not in l]
    print(f"  External HTTP links: {len(external)}")
    for l in external[:10]:
        print(f"    {l[:100]}")
