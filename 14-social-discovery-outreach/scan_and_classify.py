#!/usr/bin/env python3
"""
Social discovery scan for job-hunting-social-discovery-outreach.
Searches the n8n community (the accessible social source), fetches full
post content, classifies each by CTA type, and routes posts according to
the skill's Part A rules:
  - apply_link    -> standard discovery queue (outbox / applications table)
  - dm_instructions / email_instructions -> draft outreach record in DB
  - unclear       -> digest only
Also tries Reddit/X via Bing as a secondary source, though both are
known to be blocked/redirected.
"""
import urllib.request, json, urllib.parse, re, html as html_mod, os, sqlite3
from datetime import datetime, timezone

SKILL_ROOT = r'C:\Users\rotim\AppData\Local\hermes\skills\job-hunting'
DB_PATH = os.path.join(SKILL_ROOT, 'shared', 'applications.db')
OUTBOX_DIR = os.path.join(SKILL_ROOT, 'shared', '.outbox')

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 (Hermes-JobHunt/1.0)')


def fetch(url, accept="application/json"):
    headers = {"User-Agent": UA, "Accept": accept, "Accept-Language": "en-US,en;q=0.9"}
    req = urllib.request.Request(url, headers=headers)
    resp = urllib.request.urlopen(req, timeout=20)
    return resp.read().decode('utf-8', errors='replace')


def strip_html(text):
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html_mod.unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def classify_cta(title, body, page_text=""):
    """Classify a post's CTA type per cold-dm-email-schema.md."""
    combined = (title + " " + body + " " + page_text).lower()

    # apply_link: links to job board, ATS, or careers page
    apply_patterns = [
        r'greenhouse\.io', r'lever\.co', r'jobs\.lever', r'workable\.com',
        r'ashby\.com', r'ashbyhq\.com', r'careers\.', r'/jobs/', r'/careers/',
        r'jobscore', r'brassring', r'icims\.com', r'smartrecruiters\.com',
        r'jazzhr', r'wellfound\.com', r'angel\.co', r'greenhouse\.com',
        r'jobboard', r'apply\son', r'apply now', r'apply here',
        r'apply\sclick', r'hiring.*page', r'full.*posting',
        r'job posting', r'job description',
    ]
    has_apply_link = any(re.search(p, combined) for p in apply_patterns)

    # reply_instructions
    reply_patterns = [
        r'comment\s*(?:your|below|here|with)',
        r'reply\s*(?:below|here|with|your)',
        r'drop\s*(?:your|below)\s*(?:link|portfolio|github|resume)',
        r'post\s*(?:your|below)\s*(?:link|portfolio|github|resume)',
    ]
    has_reply = any(re.search(p, combined) for p in reply_patterns)

    # email_instructions
    email_patterns = [
        r'\bemail\s*(?:me|to|at)\b',
        r'mailto:',
        r'send\s*(?:your|my|their)\s*(?:resume|cv|email|portfolio)\s*(?:to|at)',
        r'reach\s*out\s*to\s*[\w.]+@[w.]+',
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

    # Classification (order matters per SKILL.md)
    if has_reply:
        return "reply_instructions"
    if has_email:
        return "email_instructions"
    if has_dm:
        if has_apply_link:
            return "apply_link"
        return "dm_instructions"
    if has_apply_link:
        return "apply_link"

    # Hiring intent without explicit CTA
    hiring_patterns = [
        r'\bhiring\b', r'\bwe\s*\'?re\s*looking\s+for\b',
        r'\bneed\s+someone\b', r'\blooking\s+for\s+a\b',
        r'\bjob\s*opening\b', r'\bwe\s+are\s+hiring\b',
        r'\brole\b.*open', r'\bposition\b.*open',
        r'\[hiring\]', r'\[hiring', r'we\'?re hiring',
    ]
    has_hiring = any(re.search(p, combined) for p in hiring_patterns)

    if has_hiring:
        return "dm_instructions" if has_dm else "unclear"
    return "unclear"


def extract_cta_context(cta_type, combined_text):
    """Extract the specific CTA phrase from the post text."""
    combined_lower = combined_text.lower()
    if cta_type == "dm_instructions":
        m = re.search(r'(dm\s*(?:me|us)|message\s*(?:me|us)\s*(?:directly|please)|direct\s*message)', combined_lower)
        return m.group(1) if m else "DM requested"
    elif cta_type == "email_instructions":
        m = re.search(r'(email\s*(?:me|to|at)|mailto:|send.*email)', combined_lower)
        return m.group(1) if m else "Email requested"
    elif cta_type == "reply_instructions":
        m = re.search(r'(comment|reply|drop|post)\s*(?:your|below|here)', combined_lower)
        return m.group(1) if m else "Public reply requested"
    elif cta_type == "apply_link":
        urls_in_text = re.findall(r'https?://[^\s]+', combined_text)
        apply_urls = [u for u in urls_in_text if any(d in u for d in
            ['greenhouse', 'lever', 'ashby', 'wellfound', 'jobs', 'careers', 'workable'])]
        if apply_urls:
            return f"Apply link found: {apply_urls[0]}"
        return "Apply link referenced in post"
    return ""


def search_n8n_community():
    """Search the n8n community forum for hiring-style posts."""
    queries = [
        'hiring product manager',
        'hiring AI engineer',
        'hiring automation engineer',
        'looking for product manager remote',
        'need someone product manager remote',
        'hiring remote engineer AI',
        'hiring remote developer',
        'hiring remote engineer',
        'product manager remote',
        'DM me product manager',
        'message me product manager',
    ]
    all_posts = {}
    for q in queries:
        url = f'https://community.n8n.io/search.json?q={urllib.parse.quote(q)}'
        try:
            raw = fetch(url, accept='application/json')
            data = json.loads(raw)
            topics = data.get('topics', [])
            for t in topics[:8]:
                tid = t.get('id')
                if tid and tid not in all_posts:
                    all_posts[tid] = {
                        'id': tid,
                        'title': t.get('title', ''),
                        'slug': t.get('slug', ''),
                        'posts_count': t.get('posts_count', 0),
                        'like_count': t.get('like_count', 0),
                        'search_query': q,
                        'source_platform': 'n8n_community',
                    }
        except Exception as e:
            print(f"  n8n query '{q}': ERROR - {str(e)[:80]}")
    return list(all_posts.values())


def fetch_n8n_post_info(post):
    """Fetch full content of a single n8n community post."""
    url = f'https://community.n8n.io/t/{post["slug"]}.json'
    try:
        raw = fetch(url, accept='application/json')
        data = json.loads(raw)
        post_stream = data.get('post_stream', {}).get('posts', [])
        if post_stream:
            first_post = post_stream[0]
            cooked = first_post.get('cooked', '')
            text = strip_html(cooked)
            post['body'] = text[:2000]
            post['author'] = first_post.get('username', '')
            post['post_url'] = f'https://community.n8n.io/t/{post["slug"]}'
            return True
    except Exception as e:
        post['body'] = f'FETCH_ERROR: {str(e)[:80]}'
        post['post_url'] = f'https://community.n8n.io/t/{post["slug"]}'
    return False


def search_bing_for_social():
    """Try Bing search for Reddit/X posts as a secondary source."""
    queries = [
        'hiring product manager remote site:reddit.com',
        'hiring AI engineer remote site:reddit.com',
        'looking for product manager remote site:reddit.com',
    ]
    found = []
    for q in queries:
        url = f'https://www.bing.com/search?q={urllib.parse.quote(q)}&count=10'
        try:
            html_content = fetch(url, accept='text/html,application/xhtml+xml')
            blocks = re.findall(r'<li class="b_algo">(.*?)</li>', html_content, re.DOTALL)
            for b in blocks:
                link_m = re.search(r'<a[^>]*href="(https?://[^"]+)"', b)
                title_m = re.search(r'<a[^>]*>(.*?)</a>', b, re.DOTALL)
                if link_m:
                    link = link_m.group(1)
                    title = strip_html(title_m.group(1)) if title_m else ''
                    is_reddit = 'reddit.com' in link.lower() and '/comments/' in link.lower()
                    if is_reddit:
                        found.append({'url': link, 'title': title, 'source_platform': 'reddit'})
        except Exception as e:
            print(f"  Bing query '{q}': ERROR - {str(e)[:80]}")
    return found


def deduplicate_by_url(posts):
    """Remove exact duplicate URLs."""
    seen = set()
    unique = []
    for p in posts:
        url = p.get('post_url', p.get('source_url', ''))
        if url and url not in seen:
            seen.add(url)
            unique.append(p)
    return unique


def main():
    now = datetime.now(timezone.utc)
    print(f"Social discovery scan started at {now.strftime('%Y-%m-%dT%H:%M:%SZ')}")
    print("=" * 70)

    # === Phase 1: n8n community search ===
    print("\n--- Phase 1: n8n community search ---")
    n8n_posts = search_n8n_community()
    print(f"  Found {len(n8n_posts)} unique topics")

    # Fetch full content for each
    print(f"\n  Fetching full content for {len(n8n_posts)} posts...")
    fetched = 0
    for p in n8n_posts:
        if fetch_n8n_post_info(p):
            fetched += 1
    print(f"  Successfully fetched: {fetched}")

    # === Phase 2: Bing search for Reddit/X (secondary) ===
    print("\n--- Phase 2: Bing search for Reddit/X (secondary) ---")
    bing_posts = search_bing_for_social()
    print(f"  Bing found {len(bing_posts)} Reddit/X posts")

    # === Phase 3: Classify all posts ===
    print("\n" + "=" * 70)
    print("CLASSIFICATION")
    print("=" * 70)

    all_posts = deduplicate_by_url(n8n_posts + bing_posts)

    classified = {
        'apply_link': [],
        'dm_instructions': [],
        'email_instructions': [],
        'reply_instructions': [],
        'unclear': [],
    }

    for p in all_posts:
        title = p.get('title', '')
        body = p.get('body', '')
        combined = title + " " + body
        cta_type = classify_cta(title, body)
        cta_context = extract_cta_context(cta_type, combined)

        # Skip [FOR HIRE] posts (people offering services, not hiring)
        title_lower = title.lower()
        if '[for hire]' in title_lower or 'for hire:' in title_lower or 'for-hire' in title_lower:
            # These are people OFFERING to be hired, not hiring.
            # Still classify but flag as "for_hire" in digest
            p['cta_type'] = 'for_hire'
            p['cta_context'] = cta_context
            print(f"\n  [FOR HIRE] {title[:60]}")
            print(f"    Platform: {p.get('source_platform', '?')} | URL: {p.get('post_url', p.get('source_url', ''))[:100]}")
            continue

        p['cta_type'] = cta_type
        p['cta_context'] = cta_context
        classified[cta_type].append(p)

        print(f"\n  [{cta_type.upper()}] {p.get('source_platform', '?')} | {title[:60]}")
        print(f"    URL: {p.get('post_url', p.get('source_url', ''))[:120]}")
        if body:
            print(f"    Body: {body[:150]}")
        print(f"    CTA context: {cta_context}")

    # === Summary ===
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for cta_type, posts in classified.items():
        print(f"  {cta_type}: {len(posts)}")
    total = sum(len(p) for p in classified.values())
    for_hire_count = len([p for p in all_posts if p.get('cta_type') == 'for_hire'])
    print(f"  for_hire (offering, not hiring): {for_hire_count}")
    print(f"\n  Total posts found: {len(all_posts)}")
    print(f"  Total classified (hiring): {total}")

    # Save results
    results = {
        "scan_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_posts_found": len(all_posts),
        "classified": {k: len(v) for k, v in classified.items()},
        "for_hire_count": for_hire_count,
        "classified_posts": classified,
        "all_posts": all_posts,
    }
    out_path = os.path.join(SKILL_ROOT, '14-social-discovery-outreach', 'references', 'scan_results.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {out_path}")


if __name__ == '__main__':
    main()
