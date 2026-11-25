#!/usr/bin/env python3
"""Check HN Who Is Hiring September thread for NEW comments since Sep 17."""
import urllib.request, json, datetime, sqlite3

DB_PATH = "C:/Users/rotim/AppData/Local/hermes/skills/job-hunting/shared/applications.db"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# Find the September "Who is Hiring" story
url = "https://hn.algolia.com/api/v1/search?query=Ask+HN:Who+is+hiring&restrictSearchableAttributes=title&tags=story&hitsPerPage=5"
resp = urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=15)
data = json.loads(resp.read().decode('utf-8'))
hits = data.get("hits", [])
print(f"HN Who is Hiring stories: {len(hits)}")
for h in hits:
    print(f"  - {h.get('title','')} (id={h.get('objectID')}, created={h.get('created_at')})")

# Use the first (most recent) story
story_id = hits[0].get("objectID")
print(f"\nUsing story id={story_id}")

# Get story's comment IDs
url2 = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
resp2 = urllib.request.urlopen(urllib.request.Request(url2, headers=HEADERS), timeout=15)
story = json.loads(resp2.read().decode('utf-8'))
kids = story.get("kids", [])
print(f"Top-level comments: {len(kids)}")

# Check DB for existing HN candidates
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
existing_urls = set(r[0] for r in cur.execute("SELECT DISTINCT posting_url FROM applications WHERE posting_url IS NOT NULL"))
existing_fps = set(r[0] for r in cur.execute("SELECT posting_fingerprint FROM applications WHERE posting_fingerprint IS NOT NULL"))
source_urls = set(r[0] for r in cur.execute("SELECT DISTINCT posting_url FROM posting_sources WHERE posting_url IS NOT NULL"))
all_known = existing_urls | source_urls
conn.close()

PM_KEYWORDS = [
    "product manager", "ai product", "technical product", "growth product",
    "associate product", "junior product", "product owner", "ai engineer",
    "ai/ml engineer", "machine learning engineer", "automation engineer", "workflow engineer",
    "ml engineer", "mlops engineer", "data product",
]

# Check comments posted AFTER Sep 17 15:09 UTC
cutoff_ts = datetime.datetime(2026, 9, 17, 15, 9, 0, tzinfo=datetime.timezone.utc).timestamp()
print(f"\nChecking comments posted after: {datetime.datetime.fromtimestamp(cutoff_ts).isoformat()}")

new_matches = []
checked = 0
for kid_id in kids[:300]:
    try:
        url3 = f"https://hacker-news.firebaseio.com/v0/item/{kid_id}.json"
        resp3 = urllib.request.urlopen(urllib.request.Request(url3, headers=HEADERS), timeout=10)
        comment = json.loads(resp3.read().decode('utf-8'))
        if not comment or "deleted" in comment or "dead" in comment:
            continue
        checked += 1
        text = comment.get("text", "").replace("<p>", " ").replace("</p>", " ")
        text = text.replace("&#x2014;", "—").replace("&amp;", "&").replace("&#x2F;", "/")
        ts = comment.get("time", 0)
        
        if any(kw in text.lower() for kw in PM_KEYWORDS):
            dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
            is_new = ts > cutoff_ts
            print(f"  {'NEW!' if is_new else '  old'} Comment {kid_id} ({dt.isoformat()}): {text[:120]}")
            if is_new:
                # Parse this hiring comment
                lines = text.split('\n')
                for line in lines:
                    line = line.strip()
                    if len(line) < 20:
                        continue
                    if not any(kw in line.lower() for kw in PM_KEYWORDS):
                        continue
                    if any(s in line.lower() for s in ['who is hiring', 'who\'s hiring', 'monthly', 'thread', 'discussion', 'guidelines']):
                        continue
                    parts = [p.strip() for p in line.split('|')]
                    if len(parts) < 2:
                        continue
                    company = ""
                    role = ""
                    job_url = ""
                    url_match = re.search(r'((?:https?://|www\.)[^\s|]+)', line)
                    if url_match:
                        job_url = url_match.group(1)
                    for part in parts[:6]:
                        if any(kw in part.lower() for kw in PM_KEYWORDS) and not role:
                            role = part
                        elif len(part) > 2 and len(part) < 60 and not company:
                            pl = part.lower()
                            if not any(skip in pl for skip in ['remote', 'hiring', 'contract', 'full-time', 'part-time',
                                'visa', 'salary', 'compensation', '$', 'http', 'us', 'canada', 'worldwide',
                                'onsite', 'hybrid', 'equity', 'stock', 'pto', 'benefits', 'w-2', '1099',
                                'today', 'yesterday', 'day ago', 'week ago', 'month', 'year', 'usd', 'eur', 'gbp', 'ngn']):
                                if not re.search(r'[\d\$]', pl) and re.search(r'[a-z]', pl):
                                    company = part
                    if role and company:
                        import re as _re
                        fp_company = (company or "").lower().strip()
                        fp_title = _re.sub(r'\s*#\d+\s*$', '', (role or "").lower().strip())
                        fp_title = _re.sub(r'[^\w\s]', ' ', fp_title)
                        fp_title = _re.sub(r'\s+', ' ', fp_title).strip()
                        fp = f"{fp_company}|{fp_title}|remote"
                        if fp in existing_fps:
                            print(f"      DUP FP: {fp}")
                        elif job_url and job_url in all_known:
                            print(f"      DUP URL: {job_url[:60]}")
                        else:
                            new_matches.append({
                                "company": company, "role": role, "url": job_url,
                                "posted_at": dt.isoformat(), "fp": fp
                            })
                            print(f"      NEW MATCH: {company} | {role} | {job_url[:60]}")
    except Exception as e:
        continue

print(f"\nChecked {checked} comments, found {len(new_matches)} NEW matches")
