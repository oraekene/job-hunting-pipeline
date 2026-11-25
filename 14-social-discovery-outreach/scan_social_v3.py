#!/usr/bin/env python3
"""Social listening scan v3 - reads discovery_queries.yaml, searches platforms,
classifies posts by CTA type, and routes per Part A rules.
Uses Bing search via web_search tool results, and n8n community API directly.
"""
import json, re, html as html_mod, urllib.request, urllib.parse, os, sqlite3
from datetime import datetime, timezone

SKILL_ROOT = r'C:\Users\rotim\AppData\Local\hermes\skills\job-hunting'
DB_PATH = os.path.join(SKILL_ROOT, 'shared', 'applications.db')
OUTBOX_DIR = os.path.join(SKILL_ROOT, 'shared', '.outbox')
QUERIES_FILE = os.path.join(SKILL_ROOT, 'shared', 'discovery_queries.yaml')
OUTPUT_FILE = os.path.join(SKILL_ROOT, '14-social-discovery-outreach', 'references', 'scan_results.json')

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 (Hermes-JobHunt/1.0)')

def fetch(url, accept='application/json', timeout=20):
    headers = {"User-Agent": UA, "Accept": accept, "Accept-Language": "en-US,en;q=0.9"}
    req = urllib.request.Request(url, headers=headers)
    resp = urllib.request.urlopen(req, timeout=timeout)
    return resp.read().decode('utf-8', errors='replace')

def load_queries():
    import yaml
    with open(QUERIES_FILE, 'r') as f:
        data = yaml.safe_load(f)
    if not data:
        return []
    return [q for q in data if q.get('status') == 'active']

def search_bing(q, count=15):
    url = f"https://www.bing.com/search?q={urllib.parse.quote(q)}&count={count}"
    try:
        html = fetch(url, accept='text/html')
        results = []
        # Try multiple patterns for Bing results
        for block in re.findall(r'<li class="b_algo">(.*?)</li>', html, re.DOTALL):
            link_m = re.search(r'<a[^>]*href="(https?://[^"]+)"', block)
            title_m = re.search(r'<a[^>]*>(.*?)</a>', block, re.DOTALL)
            snippet_m = re.search(r'<p[^>]*>(.*?)</p>', block, re.DOTALL)
            cite_m = re.search(r'<cite[^>]*>(.*?)</cite>', block, re.DOTALL)
            link = link_m.group(1) if link_m else ''
            title = html_mod.unescape(re.sub(r'<[^>]+>', '', title_m.group(1)).strip()) if title_m else ''
            snippet = html_mod.unescape(re.sub(r'<[^>]+>', '', snippet_m.group(1)).strip()) if snippet_m else ''
            cite = html_mod.unescape(re.sub(r'<[^>]+>', '', cite_m.group(1)).strip()) if cite_m else ''
            if 'bing.com' in link and cite:
                link = cite
            if link and not link.startswith('https://r.bing.com') and not link.startswith('https://th.bing.com'):
                results.append({"url": link, "title": title, "snippet": snippet})
        if not results:
            # Fallback: find all external links
            for link in re.findall(r'https?://(?:www\.)?reddit\.com[^\s"<>]+', html) + \
                      re.findall(r'https?://(?:www\.)?(?:x|twitter)\.com/[^\s"<>]+', html) + \
                      re.findall(r'https?://community\.n8n\.io[^\s"<>]+', html):
                if link not in [r['url'] for r in results]:
                    results.append({"url": link, "title": "", "snippet": ""})
        return results, html
    except Exception as e:
        return [], f"ERROR: {e}"

def search_n8n_api():
    """Search n8n community via Discourse JSON API."""
    queries = [
        '"hiring" "product manager"',
        '"hiring" "AI engineer"',
        '"hiring" "automation engineer"',
        '"looking for" "product manager" remote',
        '"need someone" "AI automation"',
        '"we are hiring" remote',
    ]
    all_posts = {}
    for q in queries:
        url = f'https://community.n8n.io/search.json?q={urllib.parse.quote(q)}&per_page=8'
        try:
            raw = fetch(url)
            data = json.loads(raw)
            topics = data.get('topics', [])
            for t in topics:
                tid = t.get('id')
                if tid and tid not in all_posts:
                    all_posts[tid] = {
                        'id': tid,
                        'title': t.get('title', ''),
                        'slug': t.get('slug', ''),
                        'source_platform': 'n8n_community',
                        'search_query': q,
                    }
        except Exception as e:
            print(f"  n8n query '{q}': ERROR - {str(e)[:80]}")
    # Fetch full content for each
    for p in all_posts.values():
        url = f"https://community.n8n.io/t/{p['slug']}.json"
        try:
            raw = fetch(url)
            data = json.loads(raw)
            posts = data.get('post_stream', {}).get('posts', [])
            if posts:
                cooked = posts[0].get('cooked', '')
                text = strip_html(cooked)
                p['body'] = text[:2000]
                p['author'] = posts[0].get('username', '')
                p['post_url'] = f"https://community.n8n.io/t/{p['slug']}"
        except Exception as e:
            p['body'] = f'FETCH_ERROR: {str(e)[:80]}'
            p['post_url'] = f"https://community.n8n.io/t/{p['slug']}"
    return list(all_posts.values())

def strip_html(text):
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html_mod.unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def classify_cta(title, body, page_text=""):
    combined = (title + " " + body + " " + page_text).lower()

    apply_patterns = [
        r'greenhouse\.io', r'lever\.co', r'jobs\.lever', r'workable\.com',
        r'ashby\.com', r'ashbyhq\.com', r'careers\.', r'/jobs/', r'/careers/',
        r'jobscore', r'brassring', r'icims\.com', r'smartrecruiters\.com',
        r'jazzhr', r'wellfound\.com', r'angel\.co', r'greenhouse\.com',
        r'jobboard', r'apply\son', r'apply now', r'apply here',
        r'apply\s+click', r'hiring.*page', r'full.*posting',
        r'job posting', r'job description', r'apply\.link',
    ]
    has_apply_link = any(re.search(p, combined) for p in apply_patterns)

    reply_patterns = [
        r'comment\s*(?:your|below|here|with)',
        r'reply\s*(?:below|here|with|your)',
        r'drop\s*(?:your|below)\s*(?:link|portfolio|github|resume)',
        r'post\s*(?:your|below)\s*(?:link|portfolio|github|resume)',
    ]
    has_reply = any(re.search(p, combined) for p in reply_patterns)

    email_patterns = [
        r'\bemail\s*(?:me|to|at)\b', r'mailto:',
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
        r'send\s*me\s*a\s*message',
    ]
    has_dm = any(re.search(p, combined) for p in dm_patterns)

    if has_reply: return "reply_instructions"
    if has_email: return "email_instructions"
    if has_dm:
        if has_apply_link: return "apply_link"
        return "dm_instructions"
    if has_apply_link: return "apply_link"

    hiring_patterns = [
        r'\bhiring\b', r'\bwe\s*\'?re\s*looking\s+for\b',
        r'\bneed\s+someone\b', r'\blooking\s+for\s+a\b',
        r'\bjob\s*opening\b', r'\bwe\s+are\s+hiring\b',
        r'\brole\b.*open', r'\bposition\b.*open',
        r'\[hiring\]', r'\[hiring',
    ]
    has_hiring = any(re.search(p, combined) for p in hiring_patterns)
    if has_hiring:
        return "dm_instructions" if has_dm else "unclear"
    return "unclear"

def extract_cta_context(cta_type, combined_text):
    cl = (combined_text or "").lower()
    if cta_type == "dm_instructions":
        m = re.search(r'(dm\s*(?:me|us)|message\s*(?:me|us)\s*(?:directly|please)|direct\s*message|send\s+me\s+a\s+message)', cl)
        return m.group(1) if m else "DM requested"
    elif cta_type == "email_instructions":
        m = re.search(r'(email\s*(?:me|to|at)|mailto:|send.*email)', cl)
        return m.group(1) if m else "Email requested"
    elif cta_type == "reply_instructions":
        m = re.search(r'(comment|reply|drop|post)\s*(?:your|below|here)', cl)
        return m.group(1) if m else "Public reply requested"
    elif cta_type == "apply_link":
        urls = re.findall(r'https?://[^\s]+', combined_text or "")
        apply_urls = [u for u in urls if any(d in u for d in
            ['greenhouse', 'lever', 'ashby', 'wellfound', 'jobs', 'careers', 'workable'])]
        if apply_urls: return f"Apply link found: {apply_urls[0]}"
        return "Apply link referenced in post"
    return ""

def get_existing_urls():
    """Get all URLs already in the pipeline (applications + posting_sources + social_outreach)."""
    seen = set()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("SELECT posting_url FROM applications")
        for r in c.fetchall(): seen.add(r[0])
        c.execute("SELECT posting_url FROM posting_sources")
        for r in c.fetchall(): seen.add(r[0])
        c.execute("SELECT source_url FROM social_outreach")
        for r in c.fetchall(): seen.add(r[0])
    except: pass
    conn.close()
    return seen

def extract_reddit_post(url):
    try:
        post_url = url.replace('www.reddit.com', 'old.reddit.com').replace('reddit.com', 'old.reddit.com')
        html_content = fetch(post_url, accept='text/html;q=0.9,*/*;q=0.8')
        title_match = re.search(r'<title>(.*?)</title>', html_content)
        post_title = html_mod.unescape(title_match.group(1).strip()) if title_match else ''
        # Try to extract body from old.reddit
        body_match = re.search(r'<div class="md">(.*?)</div>\s*</div>', html_content, re.DOTALL)
        if not body_match:
            body_match = re.search(r'<div class="md">(.*?)</div>\s*<div', html_content, re.DOTALL)
        post_body = ""
        if body_match:
            post_body = re.sub(r'<[^>]+>', '', body_match.group(1)).strip()
            post_body = html_mod.unescape(post_body)
        links_in_post = re.findall(r'href="(https?://[^"]+)"', html_content)
        apply_links = [l for l in links_in_post if any(p in l for p in
            ['greenhouse', 'lever', 'ashby', 'wellfound', 'jobs', 'careers', 'workable', 'angel'])]
        return post_title, post_body, apply_links
    except Exception as e:
        return '', '', []

def main():
    now = datetime.now(timezone.utc)
    scan_ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"Social discovery scan started at {scan_ts}")
    print("=" * 70)

    queries = load_queries()
    print(f"Loaded {len(queries)} active social_listening queries from discovery_queries.yaml")
    for q in queries:
        print(f"  [{q.get('platform','?')}] {q['id']}: {q.get('query_text','')[:80]}...")

    existing_urls = get_existing_urls()
    print(f"\nExisting URLs in pipeline DB: {len(existing_urls)}")

    bing_results = []
    seen_bing_urls = set()

    print("\n--- Phase 1: Bing web search for social platform posts ---")
    for q in queries:
        query_text = q['query_text']
        platform = q.get('platform', '')
        print(f"\n  Query [{q['id']}]: {query_text[:80]}...")
        results, html_or_err = search_bing(query_text, count=15)
        print(f"  Bing returned {len(results)} results")
        for r in results:
            url = r["url"]
            if url in seen_bing_urls: continue
            # Filter for relevant platforms
            is_reddit = "reddit.com" in url.lower() and "/comments/" in url.lower()
            is_x = ("x.com" in url.lower() or "twitter.com" in url.lower()) and "/status/" in url.lower()
            is_n8n = "community.n8n.io" in url.lower()
            if not (is_reddit or is_x or is_n8n): continue
            seen_bing_urls.add(url)
            bing_results.append({"query": query_text, "query_id": q['id'], "platform": platform, **r})

    print(f"\nTotal unique social candidate URLs from Bing: {len(bing_results)}")

    print("\n--- Phase 2: n8n community API search ---")
    n8n_posts = search_n8n_api()
    print(f"  n8n API returned {len(n8n_posts)} unique topics")

    # Combine all candidates
    all_posts = []
    for r in bing_results:
        url = r["url"]
        if url in existing_urls: continue
        pt = "reddit" if "reddit" in url else ("x" if "twitter" in url or "x.com" in url else "n8n_community")
        title, body, apply_links = r.get("title",""), r.get("snippet",""), []
        if pt == "reddit":
            title, body, apply_links = extract_reddit_post(url)
            if not title: title = r.get("title", "")
            if not body: body = r.get("snippet", "")
        post_text = (title + " " + body).strip()
        if not post_text: continue
        all_posts.append({
            "source_platform": pt, "source_url": url, "title": title,
            "body": body[:500] if body else "", "cta_type": "",
            "search_query": r.get("query",""), "query_id": r.get("query_id",""),
        })

    for p in n8n_posts:
        url = p.get("post_url", "")
        if url in existing_urls: continue
        all_posts.append({
            "source_platform": "n8n_community", "source_url": url,
            "title": p.get("title",""), "body": p.get("body",""),
            "cta_type": "", "search_query": p.get("search_query",""),
        })

    # Deduplicate by URL
    seen_urls = set()
    unique_posts = []
    for p in all_posts:
        if p["source_url"] in seen_urls: continue
        seen_urls.add(p["source_url"])
        unique_posts.append(p)

    print(f"\nTotal unique new posts to classify: {len(unique_posts)}")

    # Classify
    classified = {"apply_link": [], "dm_instructions": [], "email_instructions": [],
                  "reply_instructions": [], "unclear": []}
    for p in unique_posts:
        cta = classify_cta(p["title"], p.get("body",""))
        ctx = extract_cta_context(cta, p["title"] + " " + p.get("body",""))
        p["cta_type"] = cta
        p["cta_context"] = ctx
        if cta in classified: classified[cta].append(p)
        print(f"  [{cta.upper()}] {p['source_platform']} | {p['title'][:60]}")
        print(f"    URL: {p['source_url'][:120]}")

    # Summary
    print("\n" + "=" * 70)
    print("CLASSIFICATION SUMMARY")
    print("=" * 70)
    for cta, posts in classified.items():
        print(f"  {cta}: {len(posts)}")
    total = sum(len(v) for v in classified.values())
    print(f"\n  Total new posts found: {len(unique_posts)}")
    print(f"  Total classified: {total}")

    # Save results
    results = {
        "scan_at": scan_ts,
        "total_posts_found": len(unique_posts),
        "classified": {k: len(v) for k, v in classified.items()},
        "posts": classified,
        "queries_scanned": [q['id'] for q in queries],
    }
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {OUTPUT_FILE}")

if __name__ == '__main__':
    main()
