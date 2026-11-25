#!/usr/bin/env python3
"""Fetch HN 'Who is hiring' (Sept 2026) comments and extract job postings."""
import urllib.request, json, re, time
from datetime import datetime, timezone

STORY_ID = 49522897

# 1. Get the story to get top-level comment IDs (kids)
story_url = f"https://hacker-news.firebaseio.com/v0/item/{STORY_ID}.json"
req = urllib.request.Request(story_url, headers={"User-Agent": "Mozilla/5.0"})
story = json.loads(urllib.request.urlopen(req, timeout=15).read())
kids = story.get("kids", [])
print(f"Story: {story.get('title','?')}")
print(f"Descendants: {story.get('descendants',0)}")
print(f"Top-level comments (kids): {len(kids)}")

# 2. Fetch top-level comments
comments = []
for kid_id in kids[:80]:  # fetch up to 80 top-level comments
    try:
        url = f"https://hacker-news.firebaseio.com/v0/item/{kid_id}.json"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        c = json.loads(urllib.request.urlopen(req, timeout=10).read())
        if c and "text" in c:
            text = re.sub(r"<[^>]+>", "", c.get("text","")).strip()
            if text and not text.startswith("[deleted]"):
                comments.append({
                    "id": c.get("id"),
                    "by": c.get("by","?"),
                    "text": text,
                    "created_utc": c.get("time", 0),
                })
        time.sleep(0.02)  # rate limit
    except Exception as e:
        print(f"  Error fetching comment {kid_id}: {e}")

print(f"\nFetched {len(comments)} top-level comments with text")

# 3. Filter for title variants
title_variants = [
    "product manager", "ai product manager", "ai engineer",
    "automation engineer", "workflow engineer", "associate product manager",
    "junior product manager", "product owner", "technical product manager",
    "growth product manager", "ai/ml product manager",
]

matched = []
for c in comments:
    text_lower = c["text"].lower()
    for tv in title_variants:
        if tv in text_lower:
            matched.append({"comment": c, "matched_variant": tv})
            break

# Also look for general "hiring" posts
hiring_comments = [c for c in comments if "hiring" in c["text"].lower() or "we're hiring" in c["text"].lower()]

print(f"\nComments matching title variants: {len(matched)}")
print(f"Comments mentioning 'hiring': {len(hiring_comments)}")

# Print matched comments (first 30)
print("\n=== Title-variant matches ===")
for i, m in enumerate(matched[:30]):
    c = m["comment"]
    ts = datetime.fromtimestamp(c["created_utc"], tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if c["created_utc"] else "?"
    print(f"  [{ts}] by {c['by']} (matched: {m['matched_variant']})")
    print(f"    {c['text'][:500]}")
    print()

# Print hiring comments that are NOT title matches (might have "hiring" in non-job context)
print("\n=== Other hiring mentions (non-title-match) ===")
for c in hiring_comments[:15]:
    if c not in [m["comment"] for m in matched]:
        ts = datetime.fromtimestamp(c["created_utc"], tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if c["created_utc"] else "?"
        print(f"  [{ts}] by {c['by']}")
        print(f"    {c['text'][:300]}")
        print()
