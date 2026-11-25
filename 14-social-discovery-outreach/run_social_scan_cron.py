#!/usr/bin/env python3
"""
CRON RUN — job-hunting-social-discovery-outreach: discovery half.
Scans configured social_listening sources (queries from
shared/discovery_queries.yaml), classifies each post by CTA type, and
routes per Part A of the skill.

Routes:
  apply_link (TRUE: external ATS/job-board link) -> applications + posting_sources
  dm_instructions      -> social_outreach record (drafted, status=drafted)
  email_instructions   -> social_outreach record (drafted, status=drafted)
  reply_instructions   -> social_outreach record (drafted, status=drafted)
  unclear              -> flagged in digest only

No sends. No Telegram pings. Per Rule 1, everything is staged.
"""
import json, re, html as html_mod, urllib.request, urllib.parse, os, sqlite3
from datetime import datetime, timezone
import yaml

SKILL_ROOT = r'C:\Users\rotim\AppData\Local\hermes\skills\job-hunting'
DB_PATH    = os.path.join(SKILL_ROOT, 'shared', 'applications.db')
QUERIES_FILE = os.path.join(SKILL_ROOT, 'shared', 'discovery_queries.yaml')
OUTPUT_FILE  = os.path.join(SKILL_ROOT, '14-social-discovery-outreach', 'references', 'scan_results.json')
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 (Hermes-JobHunt/1.0)')

def fetch(url, accept="application/json", timeout=20):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": accept, "Accept-Language": "en-US,en;q=0.9"})
    resp = urllib.request.urlopen(req, timeout=timeout)
    return resp.read().decode('utf-8', errors='replace')

def strip_html(text):
    # Extract URLs from href/src attributes BEFORE stripping tags,
    # so embedded links (e.g. "Apply HERE" with an href) are preserved
    # and available for the classifier's apply_link detection.
    urls = re.findall(r'href=["\']([^"\'>]+)["\']', text)
    # Strip tags, then append extracted URLs at the end
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html_mod.unescape(text)
    if urls:
        text = text + ' ' + ' '.join(urls)
    return re.sub(r'\s+', ' ', text).strip()

def classify_cta(title, body):
    combined = (title + " " + body).lower()
    # reply takes priority (public ask)
    if re.search(r'(comment|reply|drop|post)\s*(?:your|below|here)', combined):
        if not re.search(r'(hiring|job|opening|looking|need)', combined):
            return "unclear"
        return "reply_instructions"
    # email
    if re.search(r'(email\s*(?:me|to|at)|mailto:|send.*email|reach\s*out\s*to\s*[^\s]+)', combined):
        return "email_instructions"
    # email with address present (strong signal) — also match "contact" and "reach out"
    if re.search(r'[\w.+-]+@[\w.-]+\.\w+', combined) and re.search(r'email|cv|resume|send|contact|reach', combined):
        return "email_instructions"
    # dm
    if re.search(r'(dm\s*me|message\s*me|direct\s*message|slide\s*into\s*my\s*dm)', combined):
        # check if there's also an external apply link
        urls = re.findall(r'https?://[^\s\'\"\)]+', combined)
        apply_kw = ['greenhouse', 'lever', 'ashby', 'wellfound', 'jobs', 'careers', 'workable', 'angel', 'jobscore', 'icims', 'jazzhr']
        if any(any(d in u for d in apply_kw) for u in urls):
            return "apply_link"
        return "dm_instructions"
    # apply_link — requires actual external link to ATS/job board
    urls = re.findall(r'https?://[^\s\'\"\)]+', combined)
    apply_kw = ['greenhouse', 'lever', 'ashby', 'wellfound', 'jobs.', 'jobs/', 'careers.', 'careers/', 'workable', 'angel', 'jobscore', 'icims', 'jazzhr', 'apply.link', 'join.com', 'linkedin.com/jobs', '/jobs/']
    for u in urls:
        if any(d in u for d in apply_kw):
            return "apply_link"
    # hiring intent but no explicit CTA channel
    if re.search(r'\bhiring\b|we\s*\'?re\s*looking|need\s*someone|looking\s*for\s*a\s*(pm|product|engineer|developer)', combined):
        return "unclear"
    return "unclear"

def extract_cta_context(cta_type, combined):
    cl = (combined or "").lower()
    if cta_type == "dm_instructions":
        m = re.search(r'(dm\s*(?:me|us)|message\s*(?:me|us)\s*(?:direct|please)|direct\s*message)', cl)
        return m.group(1) if m else "DM requested"
    if cta_type == "email_instructions":
        m = re.search(r'(email\s*(?:me|to|at)|mailto:|reach\s*out\s*to\s*[\w.+-]+@[\w.]+)', cl)
        return m.group(1) if m else "Email requested"
    if cta_type == "reply_instructions":
        m = re.search(r'(comment|reply|drop|post)\s*(?:your|below|here)', cl)
        return m.group(1) if m else "Public reply requested"
    if cta_type == "apply_link":
        urls = re.findall(r'https?://[^\s\'\"\)]+', combined or "")
        return f"External apply link in post: {[u for u in urls if u][:1]}"
    return ""

def extract_emails(text):
    emails = re.findall(r'[\w.+-]+@[\w.-]+\.\w+', text)
    emails = [e for e in emails if not e.startswith('noreply') and not e.startswith('example')]
    return list(dict.fromkeys(emails))

def has_external_apply_link(body, title=""):
    urls = re.findall(r'https?://[^\s\'"]+', (title + " " + body).lower())
    apply_kw = ['greenhouse', 'lever', 'ashby', 'wellfound', 'jobs.', 'jobs/', 'careers.', 'careers/', 'workable', 'angel', 'jobscore', 'icims', 'jazzhr', 'apply.link', 'join.com', 'linkedin.com/jobs', '/jobs/']
    for u in urls:
        if any(d in u for d in apply_kw):
            return True, u
    return False, None

def draft_body(cta_type, title, body, cta_context, source_url):
    combined = (title + " " + body).lower()
    skill_kw = []
    if 'n8n' in combined or 'automation' in combined or 'ai' in combined:
        skill_kw = ['n8n', 'AI automation', 'AI agents', 'workflow automation']
    if 'product manager' in combined: skill_kw.append('product management')
    if 'telegram' in combined or 'bot' in combined: skill_kw.append('Telegram bot dev')
    if 'api' in combined: skill_kw.append('API integration')
    skills = ', '.join(skill_kw[:4]) if skill_kw else 'n8n + AI automation'

    hook_base = 'Your n8n community post about "%s" caught my attention.' % title[:60]

    if cta_type == "dm_instructions":
        return '\n'.join([
            hook_base,
            cta_context or 'I saw you are looking for help.',
            '',
            "I'm a Product Manager + AI Automation Engineer with hands-on experience building n8n/AI systems like the ones you described. At Savecoins (fintech P2P lending), I've shipped production AI-powered automation workflows using n8n and LLM integrations — including a Telegram trading signal bot (Python + n8n + LLM analysis) and an RSS-to-LinkedIn AI agent. My toolkit: %s." % skills,
            '',
            'Would love to see if I can help — happy to share examples of relevant n8n workflows.',
            '',
            '— Kenechukwu',
            'Product Manager & AI Automation Engineer | Savecoins',
        ])
    if cta_type == "email_instructions":
        emails = extract_emails(body)
        target = emails[0] if emails else ""
        sub = "n8n community post — %s" % title[:40]
        name_part = target.split('@')[0].title() if target else ""
        salutation = "Hi %s," % name_part if target else ""
        extra = (" Reaching out per your note to email %s." % target) if target else ""
        parts = [
            salutation,
            '',
            'Your n8n community post about "%s" matches my background.%s' % (title[:60], extra),
            '',
            "I'm a Product Manager + AI Automation Engineer at Savecoins (fintech P2P lending). I've built production AI-powered automation workflows using n8n — including a Telegram trading signal bot (Python + n8n + LLM), an RSS-to-LinkedIn AI agent, and AI agentic systems for workflow automation. I work daily with %s and full-stack automation pipelines." % skills,
            '',
            'Would welcome a quick conversation to see if I can help with what you have in mind.',
            '',
            'Best,',
            'Kenechukwu',
            'Product Manager & AI Automation Engineer | Savecoins',
        ]
        return ('\n'.join(parts), sub)
    if cta_type == "reply_instructions":
        return '\n'.join([
            hook_base + ' This aligns well with my expertise in %s.' % skills,
            '',
            "I'm a Product Manager + AI Automation Engineer at Savecoins (fintech P2P lending). I've built production n8n/AI automation systems including a Telegram trading signal bot (Python + n8n + LLM), an RSS-to-LinkedIn AI agent, and AI agentic workflows. Happy to share examples.",
            '',
            '— Kenechukwu',
        ])
    return 'Re: %s\n\nI\'m interested in this opportunity.\n\n— Kenechukwu' % title[:60]

# ─── MAIN ───────────────────────────────────────────────────────────
def main():
    now = datetime.now(timezone.utc)
    scan_ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    now_str = scan_ts
    print(f"[Social Discovery Scan] {scan_ts}")
    print("=" * 70)

    # 1. Load queries
    with open(QUERIES_FILE) as f:
        queries = yaml.safe_load(f) or []
    active = [q for q in queries if isinstance(q, dict) and q.get('status') == 'active']
    print(f"Active social_listening queries: {len(active)}")
    for q in active:
        print(f"  [{q.get('platform','?')}] {q['id']}")

    # 2. Get existing URLs from DB (dedup)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute('PRAGMA table_info(social_outreach)')
    social_cols = {r[1] for r in cur.fetchall()}
    cur.execute('PRAGMA table_info(applications)')
    app_cols = {r[1] for r in cur.fetchall()}
    print(f"\nsocial_outreach columns: {len(social_cols)}")
    print(f"applications columns: {len(app_cols)}")

    existing_urls = set()
    for table, col in [('applications', 'posting_url'), ('posting_sources', 'posting_url'), ('social_outreach', 'source_url')]:
        try:
            for r in cur.execute(f"SELECT {col} FROM {table} WHERE {col} IS NOT NULL"):
                if r[0]: existing_urls.add(r[0])
        except: pass
    print(f"Existing URLs in DB: {len(existing_urls)}")

    # 3. Scan n8n community via Discourse JSON API
    print("\n--- n8n community Discourse API search ---")
    n8n_queries = [
        'hiring product manager remote',
        'hiring AI engineer remote',
        'hiring automation engineer remote',
        'hiring workflow engineer remote',
        'looking for product manager remote',
        'need someone product manager remote',
        'hiring remote developer',
        'hiring remote engineer',
        'hiring n8n engineer',
        'hiring n8n automation',
        'hiring AI automation',
        'product manager remote',
        'DM me product manager',
        'message me product manager',
    ]
    n8n_posts = {}  # dedupe by url
    for q in n8n_queries:
        url = f'https://community.n8n.io/search.json?q={urllib.parse.quote(q)}&per_page=8'
        try:
            raw = fetch(url, accept='application/json')
            data = json.loads(raw)
            topics = data.get('topics', [])
            for t in topics:
                tid = t.get('id')
                slug = t.get('slug', '')
                post_url = f'https://community.n8n.io/t/{slug}'
                if post_url not in n8n_posts:
                    n8n_posts[post_url] = {
                        'id': tid, 'title': t.get('title', ''), 'slug': slug,
                        'source_platform': 'n8n_community', 'search_query': q,
                    }
            print(f"  query '{q}': {len(topics)} topics")
        except Exception as e:
            print(f"  query '{q}': ERROR - {str(e)[:80]}")

    # 4. Fetch full content for each post
    print(f"\n  Fetching full content for {len(n8n_posts)} topics...")
    fetched = 0
    for post_url, p in list(n8n_posts.items()):
        topic_url = f"https://community.n8n.io/t/{p['slug']}.json"
        try:
            raw = fetch(topic_url)
            data = json.loads(raw)
            posts = data.get('post_stream', {}).get('posts', [])
            if posts:
                first = posts[0]
                cooked = first.get('cooked', '')
                p['body'] = strip_html(cooked)[:5000]
                p['author'] = first.get('username', '')
                p['created_at'] = data.get('created_at', p.get('created_at', ''))
                fetched += 1
            else:
                p['body'] = ''
                p['created_at'] = p.get('created_at', '')
        except Exception as e:
            p['body'] = f'FETCH_ERROR: {str(e)[:80]}'
            p['created_at'] = p.get('created_at', '')
    print(f"  Fetched: {fetched}, skipped/failed: {len(n8n_posts) - fetched}")

    # 5. Also try Reddit/X via Bing (document that it's blocked)
    print("\n--- Bing search for Reddit/X (secondary — expected blocked) ---")
    bing_attempted = False
    try:
        bing_q = 'hiring product manager remote site:reddit.com r/forhire'
        url = f'https://www.bing.com/search?q={urllib.parse.quote(bing_q)}&count=10'
        raw = fetch(url, accept='text/html', timeout=15)
        blocks = re.findall(r'<li class="b_algo">', raw)
        if not blocks:
            print("  Bing: 0 results (interstitial/bot-detection page)")
            bing_attempted = True
        else:
            print(f"  Bing: {len(blocks)} results found (unexpected — parsing)")
            bing_attempted = True
    except Exception as e:
        print(f"  Bing: BLOCKED - {type(e).__name__}: {str(e)[:80]}")
        bing_attempted = True

    # 6. Deduplicate against DB, filter
    unique_posts = []
    for post_url, p in n8n_posts.items():
        if post_url in existing_urls:
            continue
        title = p.get('title', '')
        body = p.get('body', '')
        # Skip FOR HIRE posts
        tl = title.lower()
        if '[for hire]' in tl or 'for hire:' in tl or 'for-hire' in tl:
            continue
        if not body or 'FETCH_ERROR' in body:
            continue
        unique_posts.append({
            'source_platform': 'n8n_community',
            'post_url': post_url,
            'title': title,
            'body': body[:2000],
            'author': p.get('author', ''),
            'created_at': p.get('created_at', ''),
            'search_query': p.get('search_query', ''),
        })

    print(f"\nUnique NEW n8n posts (not in DB): {len(unique_posts)}")

    # 7. Classify
    classified = {'apply_link': [], 'dm_instructions': [], 'email_instructions': [],
                  'reply_instructions': [], 'unclear': []}
    for p in unique_posts:
        cta = classify_cta(p['title'], p['body'])
        p['cta_type'] = cta
        p['cta_context'] = extract_cta_context(cta, (p['title'] + " " + p['body']))
        classified[cta].append(p)
        print(f"  [{cta:>18}] {p['title'][:55]} | {p['post_url'][:80]}")

    # 8. Route
    print("\n" + "=" * 70)
    print("ROUTING")
    print("=" * 70)

    routed_app_ids = []
    routed_outreach_ids = []
    unclear_posts = []
    apply_link_recheck = []

    # ── apply_link ──
    print(f"\n[apply_link: {len(classified['apply_link'])}]")
    for p in classified['apply_link']:
        has_ext, ext_url = has_external_apply_link(p['body'], p['title'])
        if not has_ext:
            apply_link_recheck.append(p)
            print(f"  RECHECK (no external link): {p['title'][:50]}")
            continue
        # True apply link → feed into standard discovery queue
        today_queued = cur.execute(
            "SELECT COUNT(*) FROM applications WHERE status='discovered' AND date(discovered_at) = date('now')"
        ).fetchone()[0]
        if today_queued >= 15:
            print(f"  SKIP (daily cap): {p['title'][:50]}")
            continue
        try:
            cur.execute("""
                INSERT INTO applications
                (posting_url, company, role_title, source_board,
                 discovered_at, priority, status, remote_type, salary_disclosed, salary_range)
                VALUES (?, 'n8n Community', ?, 'n8n_community', ?, 'normal', 'discovered', 'remote', 0, NULL)
            """, (p['post_url'], p['title'][:200], now_str))
            app_id = cur.lastrowid
            cur.execute("""
                INSERT INTO posting_sources (application_id, posting_url, source_name, discovered_by, is_canonical)
                VALUES (?, ?, 'n8n_community', 'social_discovery_scan', 1)
            """, (app_id, p['post_url']))
            conn.commit()
            routed_app_ids.append(app_id)
            print(f"  QUEUED app #{app_id}: {p['title'][:50]}")
        except Exception as e:
            print(f"  INSERT FAILED: {e}")

    # ── dm_instructions ──
    print(f"\n[dm_instructions: {len(classified['dm_instructions'])}]")
    for p in classified['dm_instructions']:
        body_draft = draft_body('dm_instructions', p['title'], p['body'], p['cta_context'], p['post_url'])
        cur.execute("""
            INSERT INTO social_outreach
            (trigger_type, source_platform, source_url, source_cta_type, source_cta_context,
             contact_platform, contact_handle, contact_display_name, contact_profile_url,
             contact_role_guess, contact_company, contact_relationship, send_tier, send_method,
             matrix_checked_at, channel, body_draft, personalization_hooks, char_count,
             platform_char_limit, risk_gate_pass_count, risk_gate_fail_count,
             fidelity_mode_at_draft, status, created_at)
            VALUES ('social_listening_post', 'n8n_community', ?, 'dm_instructions', ?,
                    'n8n_community', NULL, 'OP (post author)', NULL,
                    'hiring_manager_or_decision_maker', NULL, 'stranger', 2, 'manual_cued',
                    ?, 'dm', ?, ?, ?, 20000, 0, 0, 'strict', 'drafted', ?)
        """, (p['post_url'], p['cta_context'] or 'DM requested',
             now_str, body_draft,
             json.dumps([p['cta_context'] or 'DM requested', p['title'][:60]]),
             len(body_draft), now_str))
        conn.commit()
        oid = cur.lastrowid
        routed_outreach_ids.append(oid)
        print(f"  DRAFTED outreach #{oid}: {p['title'][:50]} (DM, tier 2)")

    # ── email_instructions ──
    print(f"\n[email_instructions: {len(classified['email_instructions'])}]")
    for p in classified['email_instructions']:
        emails = extract_emails(p['body'])
        target_email = emails[0] if emails else ""
        body_draft, subject = draft_body('email_instructions', p['title'], p['body'], p['cta_context'], p['post_url'])
        cur.execute("""
            INSERT INTO social_outreach
            (trigger_type, source_platform, source_url, source_cta_type, source_cta_context,
             contact_platform, contact_handle, contact_display_name, contact_profile_url,
             contact_role_guess, contact_company, contact_relationship, send_tier, send_method,
             matrix_checked_at, channel, subject, body_draft, personalization_hooks, char_count,
             platform_char_limit, risk_gate_pass_count, risk_gate_fail_count,
             fidelity_mode_at_draft, status, created_at)
            VALUES ('social_listening_post', 'n8n_community', ?, 'email_instructions', ?,
                    'email', ?, 'OP (post author)', NULL,
                    'hiring_manager_or_decision_maker', NULL, 'stranger', 1, 'cold_email',
                    ?, 'email', ?, ?, ?, ?, NULL, 0, 0, 'strict', 'drafted', ?)
        """, (p['post_url'], p['cta_context'] or 'Email requested',
             target_email, now_str, subject, body_draft,
             json.dumps([p['cta_context'] or 'Email requested', target_email or 'no email', p['title'][:60]]),
             len(body_draft), now_str))
        conn.commit()
        oid = cur.lastrowid
        routed_outreach_ids.append(oid)
        print(f"  DRAFTED outreach #{oid}: {p['title'][:50]} (email, tier 1, to={target_email})")

    # ── reply_instructions ──
    print(f"\n[reply_instructions: {len(classified['reply_instructions'])}]")
    for p in classified['reply_instructions']:
        body_draft = draft_body('reply_instructions', p['title'], p['body'], p['cta_context'], p['post_url'])
        # n8n community reply = Tier 2 (manual_cued, per matrix)
        cur.execute("""
            INSERT INTO social_outreach
            (trigger_type, source_platform, source_url, source_cta_type, source_cta_context,
             contact_platform, contact_handle, contact_display_name, contact_profile_url,
             contact_role_guess, contact_company, contact_relationship, send_tier, send_method,
             matrix_checked_at, channel, body_draft, personalization_hooks, char_count,
             platform_char_limit, risk_gate_pass_count, risk_gate_fail_count,
             fidelity_mode_at_draft, status, created_at)
            VALUES ('social_listening_post', 'n8n_community', ?, 'reply_instructions', ?,
                    'n8n_community', NULL, 'OP (post author)', NULL,
                    'hiring_manager_or_decision_maker', NULL, 'stranger', 2, 'manual_cued',
                    ?, 'reply', ?, ?, ?, 20000, 0, 0, 'strict', 'drafted', ?)
        """, (p['post_url'], p['cta_context'] or 'Public reply requested',
             now_str, body_draft,
             json.dumps([p['cta_context'] or 'Public reply requested', p['title'][:60]]),
             len(body_draft), now_str))
        conn.commit()
        oid = cur.lastrowid
        routed_outreach_ids.append(oid)
        print(f"  DRAFTED outreach #{oid}: {p['title'][:50]} (reply, tier 2)")

    # ── unclear ──
    print(f"\n[unclear: {len(classified['unclear'])}]")
    for p in classified['unclear']:
        unclear_posts.append(p)
        print(f"  FLAGGED: {p['title'][:50]} | {p['post_url'][:80]}")

    conn.close()

    # 9. Save scan_results.json
    results = {
        "scan_at": scan_ts,
        "sources_tried": ["n8n_community_discourse_api", "bing_reddit_x"],
        "sources_blocked": {"bing_reddit_x": "interstitial/bot-detection page, 0 results"},
        "total_posts_found": len(unique_posts),
        "classified_counts": {k: len(v) for k, v in classified.items()},
        "routed": {
            "apply_link_to_discovery_queue": len(routed_app_ids),
            "apply_link_recheck": len(apply_link_recheck),
            "outreach_drafts_created": len(routed_outreach_ids),
            "outreach_ids": routed_outreach_ids,
            "app_ids": routed_app_ids,
            "unclear_flagged_in_digest": len(unclear_posts),
        },
    }
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {OUTPUT_FILE}")

    # ─── Final summary ───
    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)
    print(f"  Sources: n8n_community (16 queries) + Bing/Reddit/X (blocked)")
    print(f"  New posts found (not in DB): {len(unique_posts)}")
    print(f"  apply_link: {len(classified['apply_link'])} → queued {len(routed_app_ids)} to discovery queue, {len(apply_link_recheck)} recheck")
    print(f"  dm_instructions: {len(classified['dm_instructions'])} → {sum(1 for p in classified['dm_instructions'])} drafts staged")
    print(f"  email_instructions: {len(classified['email_instructions'])} → drafts staged")
    print(f"  reply_instructions: {len(classified['reply_instructions'])} → drafts staged")
    print(f"  unclear: {len(classified['unclear'])} → flagged in digest")
    print(f"  Total outreach drafts staged: {len(routed_outreach_ids)}")
    print(f"  Total apply_link queued: {len(routed_app_ids)}")
    print(f"  No sends performed. All records at status='drafted' (awaiting approval ping).")

if __name__ == '__main__':
    main()
