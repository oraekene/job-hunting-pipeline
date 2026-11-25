#!/usr/bin/env python3
"""
Social discovery scan for job-hunting-social-discovery-outreach.
Reads configured queries from shared/discovery_queries.yaml,
searches Bing for hiring-style posts on Reddit/X/n8n, fetches
individual posts, classifies each by CTA type, and writes results
to a JSON file for downstream handling.
"""
import json, re, html as html_mod, urllib.request, urllib.parse
from datetime import datetime, timezone

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 (Hermes-JobHunt/1.0)"
SKILL_ROOT = r'C:\Users\rotim\AppData\Local\hermes\skills\job-hunting'
QUERIES_FILE = SKILL_ROOT + r'\shared\discovery_queries.yaml'
OUTPUT_FILE = SKILL_ROOT + r'\14-social-discovery-outreach\references\scan_results.json'

def fetch(url, accept="text/html"):
    headers = {"User-Agent": UA, "Accept": accept, "Accept-Language": "en-US,en;q=0.9"}
    req = urllib.request.Request(url, headers=headers)
    resp = urllib.request.urlopen(req, timeout=20)
    return resp.read().decode('utf-8', errors='replace')

def search_bing(q, count=10):
    """Search Bing and properly extract result URLs and snippets."""
    url = f"https://www.bing.com/search?q={urllib.parse.quote(q)}&count={count}"
    try:
        html_content = fetch(url)
        results = []
        algo_blocks = re.findall(r'<li class="b_algo">(.*?)</li>', html_content, re.DOTALL)
        for block in algo_blocks:
            link_match = re.search(r'<a[^>]*href="(https?://[^"]+)"', block)
            link = link_match.group(1) if link_match else ''
            cite_match = re.search(r'<cite[^>]*>(.*?)</cite>', block, re.DOTALL)
            cite = re.sub(r'<[^>]+>', '', cite_match.group(1)).strip() if cite_match else ''
            cite = html_mod.unescape(cite)
            title_match = re.search(r'<a[^>]*>(.*?)</a>', block, re.DOTALL)
            title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip() if title_match else '(no title)'
            title = html_mod.unescape(title)
            snippet_match = re.search(r'<p[^>]*>(.*?)</p>', block, re.DOTALL)
            snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip() if snippet_match else ''
            snippet = html_mod.unescape(snippet)
            if 'bing.com' in link and cite:
                link = cite
            if link and not link.startswith('https://r.bing.com') and not link.startswith('https://th.bing.com'):
                results.append({"url": link, "title": title, "snippet": snippet})
        return results, html_content
    except Exception as e:
        return [], f"ERROR: {e}"

def classify_cta(title, snippet, page_text=""):
    """Classify a post's CTA type per cold-dm-email-schema.md."""
    combined = (title + " " + snippet + " " + page_text).lower()

    apply_patterns = [
        r'greenhouse\.io', r'lever\.co', r'workable\.com', r'ashby\.com',
        r'careers\.', r'/jobs/', r'/careers/', r'jobscore', r'brassring',
        r'icims\.com', r'smartrecruiters\.com', r'jazzhr',
        r'wellfound\.com', r'angel\.co', r'greenhouse\.com', r'jobs\.lever',
    ]
    has_apply_link = any(re.search(p, combined) for p in apply_patterns)

    reply_patterns = [
        r'comment\s*(?:your|below|here|with)',
        r'reply\s*(?:below|here|with|your)',
        r'drop\s*(?:your|below)\s*(?:link|portfolio|github|resume)',
        r'post\s*(?:your|below)\s*(?:link|portfolio|github|resume)',
        r'comment.*below',
    ]
    has_reply = any(re.search(p, combined) for p in reply_patterns)

    email_patterns = [
        r'\bemail\s*(?:me|to|at)\b',
        r'mailto:',
        r'send\s*(?:your|my|their)\s*(?:resume|cv|email|portfolio)\s*(?:to|at)',
        r'reach\s*out\s*to\s*[\w.]+@[w.]+',
    ]
    has_email = any(re.search(p, combined) for p in email_patterns)

    dm_patterns = [
        r'\bdm\s*(?:me|us)\b',
        r'message\s*(?:me|us)\s*(?:directly|please|for|on)',
        r'direct\s*message',
        r'send\s*(?:me|us)\s*a\s*(?:dm|message|direct)',
        r'slide\s*into\s*(?:my|your|their)\s*dm',
    ]
    has_dm = any(re.search(p, combined) for p in dm_patterns)

    if has_reply:
        return "reply_instructions"
    if has_email:
        return "email_instructions"
    if has_dm:
        if has_apply_link:
            return "apply_link"  # prefer apply_link if both
        return "dm_instructions"
    if has_apply_link:
        return "apply_link"

    hiring_patterns = [
        r'\bhiring\b', r'\bwe\s*\'?re\s*looking\s+for\b',
        r'\bneed\s+someone\b', r'\blooking\s+for\s+a\b.*(?:pm|product)',
        r'\bjob\s*opening\b', r'\bwe\s+are\s+hiring\b',
        r'\brole\b.*open', r'\bposition\b.*open',
    ]
    has_hiring = any(re.search(p, combined) for p in hiring_patterns)
    if has_hiring:
        return "dm_instructions" if has_dm else "unclear"
    return "unclear"

def parse_yaml_queries(filepath):
    """Parse discovery_queries.yaml using pyyaml."""
    import yaml
    with open(filepath, 'r') as f:
        data = yaml.safe_load(f)
    if not data:
        return []
    return [q for q in data if q.get('status') == 'active']

def extract_reddit_post(url):
    """Fetch a Reddit post and extract title + body."""
    try:
        post_url = url.replace('www.reddit.com', 'old.reddit.com')
        html_content = fetch(post_url, accept="text/html;q=0.9,*/*;q=0.8")
        
        title_match = re.search(r'<title>(.*?)</title>', html_content)
        post_title = html_mod.unescape(title_match.group(1).strip()) if title_match else ''
        
        body_match = re.search(r'<div class="md">(.*?)</div>\s*<div', html_content, re.DOTALL)
        if not body_match:
            body_match = re.search(r'<div class="md">(.*?)</div>\s*<div[^>]*>', html_content, re.DOTALL)
        
        post_body = ""
        if body_match:
            post_body = re.sub(r'<[^>]+>', '', body_match.group(1)).strip()
            post_body = html_mod.unescape(post_body)
        
        links_in_post = re.findall(r'href="(https?://[^"]+)"', html_content)
        apply_links = []
        for link in links_in_post:
            if any(p in link for p in ['greenhouse', 'lever', 'ashby', 'workable', 'careers', 'wellfound', 'jobs']):
                apply_links.append(link)
        
        return post_title, post_body, apply_links, html_content
    except Exception as e:
        return '', '', [], ''

def extract_x_post(url):
    """Fetch an X/Twitter post - usually blocked, try Bing snippet."""
    return '', '', []

def extract_n8n_post(url):
    """Fetch an n8n community post."""
    try:
        html_content = fetch(url)
        title_match = re.search(r'<title>(.*?)</title>', html_content)
        post_title = html_mod.unescape(title_match.group(1).strip()) if title_match else ''
        return post_title, '', [], html_content
    except:
        return '', '', []

# === Main scan ===
now = datetime.now(timezone.utc)
print(f"Social discovery scan started at {now.strftime('%Y-%m-%dT%H:%M:%SZ')}")
print("=" * 70)

# Load configured queries from discovery_queries.yaml
queries = parse_yaml_queries(QUERIES_FILE)
print(f"\nLoaded {len(queries)} active social_listening queries from discovery_queries.yaml")
for q in queries:
    print(f"  [{q.get('platform', '?')}] {q['id']}: {q.get('query_text', '')[:80]}...")

# Run each query
all_posts = []
seen_urls = set()

for q in queries:
    query_text = q['query_text']
    platform = q.get('platform', '')
    print(f"\n--- Scanning: {q['id']} ({platform}) ---")
    results, html_or_err = search_bing(query_text, count=10)
    print(f"  Bing returned {len(results)} results")
    
    for r in results:
        url = r["url"]
        if url in seen_urls:
            continue
        
        # Filter for relevant platforms
        is_reddit = "reddit.com" in url.lower() and "/comments/" in url.lower()
        is_x = ("x.com" in url.lower() or "twitter.com" in url.lower()) and "/status/" in url.lower()
        is_n8n = "community.n8n.io" in url.lower()
        
        if not (is_reddit or is_x or is_n8n):
            continue
        
        seen_urls.add(url)
        
        # Determine platform
        if is_reddit:
            pt = "reddit"
            post_title, post_body, apply_links, _ = extract_reddit_post(url)
        elif is_x:
            pt = "x"
            post_title, post_body, apply_links = extract_x_post(url)
        elif is_n8n:
            pt = "n8n_community"
            post_title, post_body, apply_links = extract_n8n_post(url)
        else:
            pt = "unknown"
            post_title, post_body, apply_links = r.get("title", ""), r.get("snippet", ""), []
        
        # If we couldn't fetch the post, use Bing snippet
        if not post_title:
            post_title = r.get("title", "(no title)")
        if not post_body:
            post_body = r.get("snippet", "")
        
        post_text = post_title + " " + post_body
        cta_type = classify_cta(post_title, post_body)
        
        # Extract CTA context
        combined_lower = (post_title + " " + post_body).lower()
        cta_context = ""
        if cta_type == "dm_instructions":
            m = re.search(r'(dm\s*(?:me|us)|message\s*(?:me|us)\s*(?:directly|please)|direct\s*message)', combined_lower)
            cta_context = m.group(1) if m else "DM requested"
        elif cta_type == "email_instructions":
            m = re.search(r'(email\s*(?:me|to)|mailto:|send.*email)', combined_lower)
            cta_context = m.group(1) if m else "Email requested"
        elif cta_type == "reply_instructions":
            m = re.search(r'(comment|reply|drop|post)\s*(?:your|below|here)', combined_lower)
            cta_context = m.group(1) if m else "Public reply requested"
        elif cta_type == "apply_link":
            if apply_links:
                cta_context = f"Apply link found: {apply_links[0]}"
            else:
                cta_context = "Apply link in post"
        
        post_record = {
            "source_platform": pt,
            "source_url": url,
            "title": post_title,
            "body": post_body[:500] if post_body else "",
            "cta_type": cta_type,
            "cta_context": cta_context,
            "search_query": query_text,
            "query_id": q['id'],
            "apply_links": apply_links[:3],
        }
        all_posts.append(post_record)
        
        print(f"  [{cta_type.upper()}] {pt} | {post_title[:60]}")
        print(f"    URL: {url[:100]}")
        if post_body:
            print(f"    Body: {post_body[:120]}")
        print()

# === Summary ===
print("=" * 70)
print("CLASSIFICATION SUMMARY")
print("=" * 70)
counts = {}
for p in all_posts:
    counts[p["cta_type"]] = counts.get(p["cta_type"], 0) + 1
for cta in sorted(counts.keys()):
    print(f"  {cta}: {counts[cta]}")
print(f"\nTotal posts found: {len(all_posts)}")

results = {
    "scan_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "queries_scanned": [q['id'] for q in queries],
    "total_posts_found": len(all_posts),
    "classified": counts,
    "posts": all_posts,
}
with open(OUTPUT_FILE, 'w') as f:
    json.dump(results, f, indent=2)
print(f"\nResults saved to {OUTPUT_FILE}")
