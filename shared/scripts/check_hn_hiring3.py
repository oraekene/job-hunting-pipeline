#!/usr/bin/env python3
"""Fetch HN 'Who is hiring' (Sept 2026) comments and extract job postings."""
import urllib.request, json, re
from datetime import datetime, timezone

STORY_ID = 49522897
url = "https://hn.algolia.com/api/v1/search?tags=comment&numericFilters=story_id=49522897&hitsPerPage=1000"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
raw = urllib.request.urlopen(req, timeout=20).read().decode("utf-8")
data = json.loads(raw)
hits = data.get("hits", [])

print(f"Total comments on story {STORY_ID}: {len(hits)}")

# Title variants to match
title_variants = [
    "product manager", "ai product manager", "ai engineer",
    "automation engineer", "workflow engineer", "associate product manager",
    "junior product manager", "product owner", "technical product manager",
    "growth product manager", "ai/ml product manager",
]

# Separate top-level comments (job postings) from replies
toplevel = [h for h in hits if h.get("parent_id") == STORY_ID]
replies = [h for h in hits if h.get("parent_id") != STORY_ID]
print(f"Top-level comments (job postings): {len(toplevel)}")
print(f"Replies: {len(replies)}")

# Check top-level comments for title variants
matched_toplevel = []
for h in toplevel:
    text = re.sub(r"<[^>]+>", "", h.get("comment_text", "")).strip()
    if not text:
        continue
    text_lower = text.lower()
    for tv in title_variants:
        if tv in text_lower:
            matched_toplevel.append({"text": text, "variant": tv, "author": h.get("author","?"), "created_at": h.get("created_at","?"), "id": h.get("objectID","?")})
            break

# Also check ALL comments (including replies) for title variants — some job postings
# might be in replies (e.g., "We're hiring a Product Manager at FooCorp")
matched_all = []
for h in hits:
    text = re.sub(r"<[^>]+>", "", h.get("comment_text", "")).strip()
    if not text:
        continue
    text_lower = text.lower()
    for tv in title_variants:
        if tv in text_lower:
            matched_all.append({"text": text, "variant": tv, "author": h.get("author","?"), "created_at": h.get("created_at","?"), "id": h.get("objectID","?")})
            break

print(f"\nTop-level comments matching title variants: {len(matched_toplevel)}")
print(f"All comments matching title variants: {len(matched_all)}")

print("\n=== Top-level matches ===")
seen_ids = set()
for m in matched_toplevel[:25]:
    print(f"  [{m['created_at']}] by {m['author']} (matched: {m['variant']}) id={m['id']}")
    print(f"    {m['text'][:600]}")
    print()

print("\n=== All-comment matches (not in top-level) ===")
toplevel_ids = {m["id"] for m in matched_toplevel}
for m in matched_all:
    if m["id"] not in toplevel_ids and m["id"] not in seen_ids:
        seen_ids.add(m["id"])
        print(f"  [{m['created_at']}] by {m['author']} (matched: {m['variant']}) id={m['id']}")
        print(f"    {m['text'][:600]}")
        print()
        if len(seen_ids) > 20:
            break
