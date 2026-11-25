#!/usr/bin/env python3
"""Test Reddit JSON API access for the subreddits targeted by social scan queries."""
import urllib.request, urllib.parse, json, time

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 (Hermes-JobHunt-SocialScan/1.0)"

subreddits = ["forhire", "jobbit", "techjobs", "remotework", "AIProductManagers", "AIJobs", "productmanagement"]
for sub in subreddits:
    url = f"https://www.reddit.com/r/{sub}/new/.json?limit=25"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read().decode("utf-8", "replace"))
        posts = data["data"]["children"]
        print(f"\n=== r/{sub} === {len(posts)} posts")
        for p in posts[:5]:
            t = p["data"]["title"]
            s = p["data"].get("selftext", "")[:120]
            print(f"  - {t[:90]}")
            if s:
                print(f"    body: {s}")
    except Exception as e:
        print(f"\n=== r/{sub} === ERROR: {e}")
    time.sleep(1)

# Also try Reddit search endpoint
print("\n\n=== REDDIT SEARCH: hiring + product manager ===")
for q in ["hiring product manager", "hiring AI product manager", "need product manager", "we're hiring product manager"]:
    url = f"https://www.reddit.com/search/.json?q={urllib.parse.quote(q)}&limit=10&sort=new"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read().decode("utf-8", "replace"))
        posts = data["data"]["children"]
        print(f"\n  query: {q} -> {len(posts)} results")
        for p in posts[:3]:
            print(f"  - {p['data']['title'][:90]}")
    except Exception as e:
        print(f"\n  query: {q} -> ERROR: {e}")
    time.sleep(2)
