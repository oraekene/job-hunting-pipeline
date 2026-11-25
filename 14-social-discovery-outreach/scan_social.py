#!/usr/bin/env python3
"""
Social discovery scan — properly parses Bing HTML results to find
hiring-style posts on Reddit, X/Twitter, and other platforms.
Then fetches individual posts for CTA classification.
"""
import json, re, html as html_mod, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 (Hermes-JobHunt/1.0)"
SKILL_ROOT = r'C:\Users\rotim\AppData\Local\hermes\skills\job-hunting'
CACHE_DIR = r'C:\Users\rotim\AppData\Local\hermes\cache\web'

def fetch(url, accept="text/html"):
    headers = {"User-Agent": UA, "Accept": accept, "Accept-Language": "en-US,en;q=0.9"}
    req = urllib.request.Request(url, headers=headers)
    resp = urllib.request.urlopen(req, timeout=20)
    return resp.read().decode('utf-8', errors='replace')

def search_bing_proper(q, count=20):
    """Search Bing and properly extract result URLs and snippets."""
    url = f"https://www.bing.com/search?q={urllib.parse.quote(q)}&count={count}"
    html = fetch(url)
    
    results = []
    # Bing organic results are in <li class="b_algo"> blocks
    algo_blocks = re.findall(r'<li class="b_algo">(.*?)</li>', html, re.DOTALL)
    
    for block in algo_blocks:
        # Extract link — first <a href="...">
        link_match = re.search(r'<a[^>]*href="(https?://[^"]+)"', block)
        link = link_match.group(1) if link_match else ''
        
        # Extract cite (displayed URL)
        cite_match = re.search(r'<cite[^>]*>(.*?)</cite>', block, re.DOTALL)
        cite = re.sub(r'<[^>]+>', '', cite_match.group(1)).strip() if cite_match else ''
        cite = html_mod.unescape(cite)
        
        # Extract title
        title_match = re.search(r'<a[^>]*>(.*?)</a>', block, re.DOTALL)
        title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip() if title_match else '(no title)'
        title = html_mod.unescape(title)
        
        # Extract snippet
        snippet_match = re.search(r'<p[^>]*>(.*?)</p>', block, re.DOTALL)
        snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip() if snippet_match else ''
        snippet = html_mod.unescape(snippet)
        
        # Use cite URL if link is a bing redirect
        if 'bing.com' in link and cite:
            link = cite
        
        if link and not link.startswith('https://r.bing.com') and not link.startswith('https://th.bing.com'):
            results.append({"url": link, "title": title, "snippet": snippet})
    
    return results, html

def classify_cta(title, snippet, page_text=""):
    """Classify a post's CTA type."""
    combined = (title + " " + snippet + " " + page_text).lower()
    
    # apply_link: links to job board, ATS, or careers page
    apply_domains = ['greenhouse.io', 'lever.co', 'jobs.lever', 'workable.com',
                     'greenhouse.com', 'jobs.ashby', 'ashbyhq.com', 'jobscore.com',
                     'boards.greenhouse', 'hiring.'],
    apply_patterns = [
        r'greenhouse\.io', r'lever\.co', r'workable\.com', r'ashby\.com',
        r'careers\.', r'/jobs/', r'/careers/', r'jobscore', r'brassring',
        r'icims\.com', r'smartrecruiters\.com', r'jazzhr'
    ]
    has_apply_link = any(re.search(p, combined) for p in apply_patterns)
    
    # reply_instructions
    reply_patterns = [
        r'comment\s*(?:your|below|here|with)',
        r'reply\s*(?:below|here|with|your)',
        r'drop\s*(?:your|below)\s*(?:your|link|portfolio|github|resume)',
        r'post\s*(?:your|below)\s*(?:link|portfolio|github|resume)',
    ]
    has_reply = any(re.search(p, combined) for p in reply_patterns)
    
    # email_instructions
    email_patterns = [
        r'\bemail\s*(?:me|to|at)\b',
        r'mailto:',
        r'send\s*(?:your|my|their)\s*(?:resume|cv|email|portfolio)\s*(?:to|at)',
        r'reach\s*out\s*to\s*[\w.]+@[\w.]+',
    ]
    has_email = any(re.search(p, combined) for p in email_patterns)
    
    # dm_instructions
    dm_patterns = [
        r'\bdm\s*(?:me|us)\b',
        r'message\s*(?:me|us)\s*(?:directly|please|for|on)',
        r'direct\s*message',
        r'send\s*(?:me|us)\s*a\s*(?:dm|message|direct)',
        r'slide\s*into\s*(?:my|your|their)\s*dm',
    ]
    has_dm = any(re.search(p, combined) for p in dm_patterns)
    
    # Classification
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
    
    # Hiring intent without explicit CTA
    hiring_patterns = [
        r'\bhiring\b', r'\bwe\s*\'?re\s*looking\s+for\b',
        r'\bneed\s+someone\b', r'\blooking\s+for\s+a\b.*(?:pm|product)',
        r'\bjob\s*opening\b', r'\bwe\s+are\s+hiring\b',
        r'\brole\b.*open', r'\bposition\b.*open'
    ]
    has_hiring = any(re.search(p, combined) for p in hiring_patterns)
    
    if has_hiring:
        return "dm_instructions" if has_dm else "unclear"
    return "unclear"

# === Search queries (from discovery_queries.yaml + profile) ===
# These mirror the configured social_listening queries
search_queries = [
    # Reddit PM hiring with DM
    '"hiring" "product manager" remote "DM me"',
    '"hiring" "AI engineer" "DM me" remote',
    '"hiring" "automation engineer" remote "message me"',
    # Forhire subreddits
    'site:reddit.com r/forhire "product manager" "hiring" remote',
    'site:reddit.com r/forhire "AI engineer" "hiring"',
    'site:reddit.com r/jobbit "product manager" remote',
    'site:reddit.com r/techjobs "hiring" "product manager"',
    # AI subreddits
    'site:reddit.com r/AIProductManagers "hiring"',
    'site:reddit.com r/AIJobs "product manager" "hiring"',
    # Broad hiring + need someone
    '"hiring" "product manager" "automation" remote',
    '"need someone" "product manager" remote',
    '"looking for" "AI engineer" remote',
    # X/Twitter
    'site:x.com "hiring" "product manager" "DM"',
    'site:twitter.com "hiring" "AI engineer" remote',
    'site:x.com "hiring" "product manager" remote',
    # n8n community
    'site:community.n8n.io "hiring" "automation"',
    # Generic (catches posts without explicit platform)
    '"hiring" "product manager" remote "apply"',
]

now = datetime.now(timezone.utc)
print(f"Social discovery scan started at {now.strftime('%Y-%m-%dT%H:%M:%SZ')}")
print("=" * 70)

# === Phase 1: Bing web search ===
print("\n--- Phase 1: Bing web search ---")
bing_results = []
searched_urls = set()

for q in search_queries:
    try:
        results, html = search_bing_proper(q, count=10)
        print(f"  '{q[:55]}': {len(results)} results")
        for r in results:
            url = r["url"]
            # Filter for relevant platforms
            is_reddit = "reddit.com" in url.lower() and "/r/" in url.lower() and ("/comments/" in url or "/s/" in url)
            is_x = ("x.com" in url.lower() or "twitter.com" in url.lower()) and "/status/" in url.lower()
            is_n8n = "community.n8n.io" in url.lower()
            
            if (is_reddit or is_x or is_n8n) and url not in searched_urls:
                searched_urls.add(url)
                platform = "reddit" if is_reddit else ("x" if is_x else "n8n_community")
                bing_results.append({"query": q, "platform": platform, **r})
    except Exception as e:
        print(f"  '{q[:55]}': ERROR — {str(e)[:80]}")

print(f"\nTotal unique social candidate URLs from Bing: {len(bing_results)}")
for r in bing_results:
    print(f"  [{r['platform']}] {r['title'][:70]}")
    print(f"    {r['url'][:120]}")
    print(f"    {r['snippet'][:120]}")
    print()

# === Phase 2: Also try Reddit-specific search queries via Bing ===
print("--- Phase 2: Reddit-specific searches via Bing ---")
reddit_specific = [
    'site:reddit.com r/forhire "product manager" "hiring" remote 2026',
    'site:reddit.com r/forhire "AI engineer" "hiring" remote',
    'site:reddit.com r/forhire "automation engineer" hiring',
    'site:reddit.com r/AIJobs "hiring" "product manager"',
    'site:reddit.com r/AIProductManagers "hiring"',
    'site:reddit.com r/product_management "hiring" remote',
    'site:reddit.com "hiring" "product manager" "DM me"',
    'site:reddit.com "hiring" "AI engineer" "DM me"',
    'site:reddit.com "looking for" "product manager" remote',
    'site:reddit.com "need someone" "AI product manager"',
]

for q in reddit_specific:
    try:
        results, html = search_bing_proper(q, count=10)
        print(f"  '{q[:55]}': {len(results)} results")
        for r in results:
            url = r["url"]
            is_reddit_post = "reddit.com" in url.lower() and "/comments/" in url.lower()
            if is_reddit_post and url not in searched_urls:
                searched_urls.add(url)
                bing_results.append({"query": q, "platform": "reddit", **r})
                print(f"    NEW: {r['title'][:70]}")
                print(f"      {url[:120]}")
    except Exception as e:
        print(f"  '{q[:55]}': ERROR — {str(e)[:60]}")

# === Phase 3: Fetch individual posts for content ===
print(f"\n--- Phase 3: Fetching {len(bing_results)} candidate posts ---")
classified_posts = []

for r in bing_results:
    url = r["url"]
    platform = r["platform"]
    
    # Try to fetch the post content
    post_text = r.get("snippet", "") + " " + r.get("title", "")
    
    # For Reddit posts, try to get the actual content
    if platform == "reddit":
        try:
            # Try old.reddit.com for the post (simpler HTML)
            post_url = url.replace("www.reddit.com", "old.reddit.com")
            html = fetch(post_url, accept="text/html;q=0.9,*/*;q=0.8")
            
            # Extract title
            title_match = re.search(r'<title>(.*?)</title>', html)
            post_title = html_mod.unescape(title_match.group(1).strip()) if title_match else r.get("title", "")
            
            # Extract post body (selftext)
            body_match = re.search(r'<div class="md">(.*?)</div>\s*<div', html, re.DOTALL)
            if not body_match:
                body_match = re.search(r'<div class="md">(.*?)</div>\s*<div[^>]*>', html, re.DOTALL)
            
            post_body = ""
            if body_match:
                post_body = re.sub(r'<[^>]+>', '', body_match.group(1)).strip()
                post_body = html_mod.unescape(post_body)
            
            post_text = post_title + " " + post_body + " " + r.get("snippet", "")
            
            # Extract links in the post
            links_in_post = re.findall(r'href="(https?://[^"]+)"', html)
            
        except Exception as e:
            post_title = r.get("title", "")
            post_body = ""
            print(f"    [FETCH ERROR] {url[:80]}: {str(e)[:60]}")
    
    elif platform == "x":
        post_title = r.get("title", "")
        post_body = r.get("snippet", "")
    
    else:
        post_title = r.get("title", "")
        post_body = r.get("snippet", "")
    
    # Classify
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
        urls_in_text = re.findall(r'https?://[^\s]+', combined_lower)
        cta_context = f"Apply link found" if urls_in_text else "Apply link in post"
    
    classified_posts.append({
        "source_platform": platform,
        "source_url": url,
        "title": post_title,
        "body": post_body[:500] if post_body else "",
        "cta_type": cta_type,
        "cta_context": cta_context,
        "search_query": r.get("query", ""),
    })
    
    print(f"  [{cta_type.upper()}] {platform} | {post_title[:60]}")
    print(f"    URL: {url[:100]}")
    if post_body:
        print(f"    Body: {post_body[:120]}")
    print()

# === Summary ===
print("=" * 70)
print("CLASSIFICATION SUMMARY")
print("=" * 70)
counts = {}
for p in classified_posts:
    counts[p["cta_type"]] = counts.get(p["cta_type"], 0) + 1
for cta, count in sorted(counts.items()):
    print(f"  {cta}: {count}")

# === Save results ===
results = {
    "scan_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    "total_candidates_searched": len(searched_urls),
    "total_posts_examined": len(classified_posts),
    "classified": counts,
    "posts": classified_posts,
}
out_path = f"{CACHE_DIR}/social_discovery_results.json"
with open(out_path, 'w') as f:
    json.dump(results, f, indent=2)
print(f"\nResults saved to {out_path}")
