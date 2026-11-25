#!/usr/bin/env python3
"""Inspect HN Algolia comment structure."""
import urllib.request, json

url = "https://hn.algolia.com/api/v1/search?tags=comment&numericFilters=story_id=49522897&hitsPerPage=3"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
raw = urllib.request.urlopen(req, timeout=15).read().decode("utf-8")
data = json.loads(raw)
hits = data.get("hits", [])

print(f"Number of hits: {len(hits)}")
if hits:
    print(f"\nKeys in first hit: {list(hits[0].keys())}")
    print(f"\nFirst hit (truncated):")
    print(json.dumps({k: (v[:200] if isinstance(v, str) else v) for k, v in hits[0].items()}, indent=2))
