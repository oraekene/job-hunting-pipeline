#!/usr/bin/env python3
"""Fetch HN 'Who is hiring' (Sept 2026) comments via Algolia and extract job postings."""
import urllib.request, json, re
from datetime import datetime, timezone

# 1. Try Algolia API with = operator for exact story match
url = "https://hn.algolia.com/api/v1/search?tags=comment&numericFilters=story_id=49522897&hitsPerPage=500"
print(f"Algolia URL: {url}")
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
try:
    raw = urllib.request.urlopen(req, timeout=15).read().decode("utf-8")
    data = json.loads(raw)
    hits = data.get("hits", [])
    print(f"Algolia returned {len(hits)} comments for story 49522897")
except Exception as e:
    print(f"Algolia error: {e}")
    hits = []

# 2. If that fails, try Firebase API for just the first 15 top-level comments
if not hits:
    print("\nFalling back to Firebase API (15 comments)...")
    story_url = "https://hacker-news.firebaseio.com/v0/item/49522897.json"
    req2 = urllib.request.Request(story_url, headers={"User-Agent": "Mozilla/5.0"})
    story = json.loads(urllib.request.urlopen(req2, timeout=15).read())
    kids = story.get("kids", [])
    hits = []
    for kid_id in kids[:15]:
        try:
            c_url = f"https://hacker-news.firebaseio.com/v0/item/{kid_id}.json"
            creq = urllib.request.Request(c_url, headers={"User-Agent": "Mozilla/5.0"})
            c = json.loads(urllib.request.urlopen(creq, timeout=10).read())
            if c and "text" in c:
                hits.append({"text": c.get("text",""), "created_at": c.get("created_at", datetime.now().isoformat())})
        except:
            pass

# 3. Parse comments for job postings
title_variants = [
    "product manager", "ai product manager", "ai engineer",
    "automation engineer", "workflow engineer", "associate product manager",
    "junior product manager", "product owner", "technical product manager",
    "growth product manager", "ai/ml product manager",
]

comments = []
for h in hits:
    text = h.get("text", "")
    text_clean = re.sub(r"<[^>]+>", "", text).strip()
    if not text_clean or text_clean.startswith("[deleted]"):
        continue
    comments.append({"text": text_clean, "data": h})

print(f"\nUsable comments: {len(comments)}")

matched = []
for c in comments:
    text_lower = c["text"].lower()
    for tv in title_variants:
        if tv in text_lower:
            matched.append({"text": c["text"], "variant": tv})
            break

print(f"Comments matching title variants: {len(matched)}")
print()
for m in matched[:20]:
    print(f"  [matched: {m['variant']}]")
    print(f"    {m['text'][:600]}")
    print()
