#!/usr/bin/env python3
"""Fetch full bodies of hiring posts to verify CTA instructions."""
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

test_slugs = [
    'hiring-n8n-consultant',
    'hiring-n8n-experts-for-ongoing-collaboration-remote',
    'hiring-n8n-ai-automation-developer-remote',
    'hiring-applied-ai-engineer-n8n',
    'hiring-n8n-automation-expert-with-data-science-background',
    'looking-for-n8n-experts-for-ongoing',
    'hiring-n8n-whatsapp-automation-developer-chat-mitra',
    'hiring-n8n-and-whatsapp-automation-developer',
]

for slug in test_slugs:
    url = f'https://community.n8n.io/t/{slug}.json'
    try:
        raw = fetch(url)
        data = json.loads(raw)
        posts = data.get('post_stream', {}).get('posts', [])
        if posts:
            body = strip_html(posts[0].get('cooked', ''))
            title = data.get('title', '')
            print(f'=== {title} ===')
            print(f'FULL BODY ({len(body)} chars):\n{body}\n')
            # Search for any email/contact/DM/reach-out patterns
            em = re.findall(r'[\w.+-]+@[\w.-]+\.\w+', body)
            # Filter out common non-personal emails
            em = [e for e in em if not e.startswith('noreply') and not e.startswith('example')]
            print(f'Emails found: {em}')
            for pat in ['dm', 'message me', 'email', 'reach out', 'contact', 'ping', 'get in touch', 'hit me up', 'apply', 'send']:
                idx = body.lower().find(pat)
                if idx >= 0:
                    ctx = body[max(0,idx-20):idx+60]
                    print(f'  "{pat}" at pos {idx}: ...{ctx}...')
            print()
    except Exception as e:
        print(f'Slug {slug}: ERROR - {str(e)[:80]}')
