#!/usr/bin/env python3
"""HN hiring-thread scanner — finds NEW PM-relevant comments since last run."""
import urllib.request, re, html
from datetime import datetime, timezone, timedelta

THREAD_ID = "49522897"
# Previous run scraped Sep 16. Look for comments dated Sep 16+ (i.e. since the
# last run). Using Sep 16 18:00 UTC as cutoff to avoid re-finding same-day items.
CUTOFF = datetime(2026, 9, 16, 18, 0, tzinfo=timezone.utc)

url = f"https://news.ycombinator.com/item?id={THREAD_ID}&sort=new"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64)'})
with urllib.request.urlopen(req, timeout=20) as resp:
    content = resp.read().decode('utf-8', errors='replace')

print(f"Page size: {len(content)} chars")

# Extract ALL timestamps (ISO format from title= attribute)
ts_pattern = r'<span class="age" title="(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})"'
timestamps = re.findall(ts_pattern, content)
print(f"Found {len(timestamps)} timestamps")

all_ts = []
for ts_str in timestamps:
    try:
        dt = datetime.fromisoformat(ts_str)
        all_ts.append(dt)
    except:
        pass
all_ts.sort(reverse=True)
if all_ts:
    print(f"Newest comment: {all_ts[0].isoformat()}")
    print(f"Oldest comment: {all_ts[-1].isoformat()}")

recent_ts = [d for d in all_ts if d >= CUTOFF]
print(f"Comments since {CUTOFF.isoformat()}: {len(recent_ts)}")

# Extract comment text blocks — HN uses <div class="commtext c00"> ... </div>
# Each commtext div's preceding age span has the timestamp.
# Strategy: split content into comment chunks by the comhead span, which
# contains BOTH the timestamp (in the age span title) and precedes commtext.
chunks = content.split('class="athing comtr"')
print(f"Split into {len(chunks)-1} comment chunks")

pm_kw = re.compile(
    r'product manager|ai pm|ai product|machine.?learn.*product|'
    r'research.*scientist|ml engineer|workflow engineer|'
    r'automation engineer|technical pm|growth product|'
    r'product owner|ai/ml product',
    re.IGNORECASE
)

new_matches = []
for chunk in chunks[1:]:  # skip the header
    # Extract timestamp from this chunk
    ts_match = re.search(r'<span class="age" title="(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})"', chunk)
    if not ts_match:
        continue
    try:
        dt = datetime.fromisoformat(ts_match.group(1))
    except:
        continue
    if dt < CUTOFF:
        continue
    # Extract commtext
    ct_match = re.search(r'class="commtext[^"]*">(.*?)</div>\s*<div class="reply"', chunk, re.DOTALL)
    if not ct_match:
        ct_match = re.search(r'class="commtext[^"]*"[^>]*>(.*?)</div>', chunk, re.DOTALL)
    if not ct_match:
        continue
    raw = ct_match.group(1)
    text = re.sub(r'<[^>]+>', ' ', raw)
    text = html.unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    if pm_kw.search(text) and len(text) > 20:
        new_matches.append((dt, text[:400]))

print(f"\n=== NEW PM-relevant comments since {CUTOFF.isoformat()} ===")
if new_matches:
    for dt, text in new_matches:
        print(f"[{dt.strftime('%m-%d %H:%M UTC')}] {text}")
else:
    print("None found — either no new comments since Sep 16, or none PM-relevant.")
    # Show all recent comments (Sep 16+) regardless of keyword, for visibility
    print("\n=== ALL comments since cutoff (for visibility) ===")
    all_recent = []
    for chunk in chunks[1:]:
        ts_match = re.search(r'<span class="age" title="(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})"', chunk)
        if not ts_match:
            continue
        try:
            dt = datetime.fromisoformat(ts_match.group(1))
        except:
            continue
        if dt < CUTOFF:
            continue
        ct_match = re.search(r'class="commtext[^"]*"[^>]*>(.*?)</div>', chunk, re.DOTALL)
        if not ct_match:
            continue
        raw = ct_match.group(1)
        text = re.sub(r'<[^>]+>', ' ', raw)
        text = html.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()[:120]
        all_recent.append((dt, text))
    for dt, text in sorted(all_recent, reverse=True)[:15]:
        print(f"[{dt.strftime('%m-%d %H:%M')}] {text}")
