#!/usr/bin/env python3
"""Examine X/Twitter and n8n HTML to find the right extraction patterns."""
import urllib.request, re, json
from html import unescape
from pathlib import Path

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={
        'User-Agent': UA,
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml',
    })
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        return f'ERROR: {e}'

# Examine X/Twitter search HTML
print("=== X/Twitter search HTML analysis ===")
x_url = 'https://x.com/search?q=' + urllib.parse.quote('hiring product manager DM remote 2026')
x_html = fetch(x_url, timeout=20)
print(f'HTML length: {len(x_html)}')
if not x_html.startswith('ERROR'):
    # Look for common tweet markers
    for pattern_name, pattern in [
        ('tweet text divs', r'<div[^>]*data-testid="tweetText"[^>]*>(.*?)</div>'),
        ('tweet-text class', r'class="tweet-text[^"]*"[^>]*>(.*?)</div>'),
        ('og:title', r'<meta property="og:title" content="([^"]*)"'),
        ('og:description', r'<meta property="og:description" content="([^"]*)"'),
        ('hiring mentions', r'hiring'),
        ('JSON-LD scripts', r'<script type="application/ld\+json">(.*?)</script>'),
    ]:
        matches = re.findall(pattern, x_html, re.DOTALL | re.IGNORECASE)
        print(f'  {pattern_name}: {len(matches)} matches')
        if matches:
            for m in matches[:3]:
                clean = re.sub(r'<[^>]+>', '', m).strip()[:200]
                print(f'    {clean}')
    
    # Check what X actually shows - look for redirect/login page
    if 'login' in x_html.lower() or 'sign up' in x_html.lower() or 'sign in' in x_html.lower():
        print('  -> X shows login/signup wall (content blocked)')
    
    # Look for any hiring-related text
    hiring_matches = re.findall(r'.{0,50}[Hh]iring.{0,100}', x_html[:100000])
    print(f'\n  Hiring context snippets (first 100KB): {len(hiring_matches)}')
    for m in hiring_matches[:5]:
        clean = re.sub(r'<[^>]+>', '', m).strip()
        print(f'    {clean[:150]}')

# Examine n8n community HTML
print("\n=== n8n community HTML analysis ===")
n8n_url = 'https://community.n8n.io/search?q=hiring'
n8n_html = fetch(n8n_url, timeout=20)
print(f'HTML length: {len(n8n_html)}')
if not n8n_html.startswith('ERROR'):
    # Look for topic/post patterns
    for pattern_name, pattern in [
        ('topic links', r'href="(/t/[a-zA-Z0-9\-]+/[0-9]+)"'),
        ('title meta', r'<meta property="og:title" content="([^"]*)"'),
        ('topic titles', r'title="([^"]{5,120})"'),
        ('hiring mentions', r'.{0,50}[Hh]iring.{0,100}'),
    ]:
        matches = re.findall(pattern, n8n_html, re.DOTALL | re.IGNORECASE)
        print(f'  {pattern_name}: {len(matches)} matches')
