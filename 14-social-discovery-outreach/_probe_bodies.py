#!/usr/bin/env python3
"""Probe n8n hiring posts for CTAs the classifier might have missed."""
import urllib.request, json, re, html as html_mod

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 (Hermes-JobHunt/1.0)'

def fetch(url, accept='application/json'):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': accept, 'Accept-Language': 'en-US,en;q=0.9'})
    resp = urllib.request.urlopen(req, timeout=20)
    return resp.read().decode('utf-8', errors='replace')

def strip_html(text):
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html_mod.unescape(text)
    return re.sub(r'\s+', ' ', text).strip()

# Posts that were classified as "unclear" but clearly hiring
test_slugs = [
    'hiring-n8n-experts-for-ongoing-collaboration-remote',
    'hiring-n8n-ai-automation-developer-remote',
    'were-hiring-n8n-automation-developer',
    'hiring-applied-ai-engineer-n8n',
    'hiring-senior-engineer-automation-ai-systems-n8n',
    'hiring-an-automation-engineer-in-karachi',
    'hiring-n8n-consultant',
    'hiring-n8n-ai-automation-specialist-mexico-based-remote',
    'hiring-n8n-automation-expert-to-build-ai-agent-workflows',
    'hiring-n8n-consultant',
]

for slug in test_slugs:
    url = f'https://community.n8n.io/t/{slug}.json'
    try:
        raw = fetch(url)
        data = json.loads(raw)
        posts = data.get('post_stream', {}).get('posts', [])
        if posts:
            body = strip_html(posts[0].get('cooked', ''))[:800]
            title = data.get('title', '')
            combined = (title + ' ' + body).lower()
            # Extended DM patterns
            has_dm = bool(re.search(r'(dm\s*(?:me|us)|message\s*(?:me|us)|direct\s*message|slide\s*into.*dm|pm\s*me|private\s*message|reach\s*out)', combined))
            has_email = bool(re.search(r'(email\s*(?:me|to|at)|mailto:|send.*email|reach\s*out\s*to\s*[\w.+-]+@)', combined))
            all_urls = re.findall(r'https?://[^\s\'"]+', combined)
            emails = re.findall(r'[\w.+-]+@[\w.-]+\.\w+', body)
            print(f'TITLE: {title}')
            print(f'  has_dm={has_dm}, has_email={has_email}')
            print(f'  urls={all_urls[:5]}')
            print(f'  emails={emails}')
            print(f'  BODY: {body[:400]}')
            print()
    except Exception as e:
        print(f'Slug {slug}: ERROR - {str(e)[:80]}')
