#!/usr/bin/env python
"""Pre-stage visa sponsorship + posting-gone check for discovered applications."""
import sqlite3, os, re, urllib.request, ssl

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "applications.db")

def now_iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def open_db():
    con = sqlite3.connect(DB, timeout=10.0)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=5000")
    con.execute("PRAGMA synchronous=NORMAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con

def fetch_url(url, timeout=25):
    """Fetch URL content, return (status_code, text_or_None)."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
    try:
        resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        return resp.getcode(), resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        return None, str(e)

def check_visa_sponsorship(text):
    """Check if posting explicitly states no visa sponsorship.
    Returns (visa_mentioned, no_sponsorship_explicit)."""
    if not text:
        return False, False
    lower = text.lower()
    # Look for visa sponsorship mentions
    visa_phrases = re.findall(r'visa[^\n<"]{0,300}', lower)
    no_sponsorship = False
    no_visa_patterns = [
        r"not available.*visa",
        r"visa.*not available",
        r"does not sponsor",
        r"no visa",
        r"without sponsorship",
        r"sponsorship.*not.*available",
        r"cannot sponsor",
        r"unable to sponsor",
        r"will not sponsor",
        r"no sponsorship",
    ]
    for pattern in no_visa_patterns:
        if re.search(pattern, lower):
            no_sponsorship = True
            break
    return len(visa_phrases) > 0, no_sponsorship

def main():
    con = open_db()
    cur = con.cursor()
    cur.execute("""
        SELECT id, company, role_title, posting_url, status
        FROM applications
        WHERE status IN ('discovered', 'building')
        ORDER BY id
    """)
    rows = cur.fetchall()
    print(f"Found {len(rows)} applications at discovered/building status")
    print()

    results = []
    for row in rows:
        app_id = row['id']
        company = row['company']
        role_title = row['role_title']
        posting_url = row['posting_url']
        status = row['status']
        print(f"App {app_id}: {company} | {role_title}")
        print(f"  URL: {posting_url}")

        # Step 1: Check posting-gone (404)
        code, content = fetch_url(posting_url)
        if code is None or code == 404 or code == 403 or content is None:
            print(f"  → POSTING GONE: HTTP {code}")
            results.append({
                'app_id': app_id,
                'company': company,
                'role_title': role_title,
                'posting_url': posting_url,
                'status': status,
                'action': 'reject',
                'reason': 'rejected_posting_gone',
                'failure_stage': 'stage_2_jd_parser',
                'detail': f'Posting URL returned HTTP {code} or content not fetchable'
            })
            continue

        print(f"  → HTTP {code}, {len(content) if content else 0} bytes")

        # Step 2: Check visa sponsorship
        visa_mentioned, no_sponsorship = check_visa_sponsorship(content)
        if no_sponsorship:
            print(f"  → REJECTED (visa): Posting explicitly states no visa sponsorship")
            results.append({
                'app_id': app_id,
                'company': company,
                'role_title': role_title,
                'posting_url': posting_url,
                'status': status,
                'action': 'reject',
                'reason': 'rejected_visa',
                'failure_stage': 'gate_visa_sponsorship',
                'detail': 'Job board explicitly states visa sponsorship is not available'
            })
        else:
            print(f"  → SURVIVES (visa_mentioned={visa_mentioned}, no_sponsorship={no_sponsorship})")
            results.append({
                'app_id': app_id,
                'company': company,
                'role_title': role_title,
                'posting_url': posting_url,
                'status': status,
                'action': 'build',
                'reason': None,
                'failure_stage': None,
                'detail': None
            })
        print()

    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    survivors = [r for r in results if r['action'] == 'build']
    rejects = [r for r in results if r['action'] == 'reject']
    print(f"Survivors (proceed to build): {len(survivors)}")
    for r in survivors:
        print(f"  ✓ App {r['app_id']}: {r['company']} | {r['role_title']}")
    print(f"Rejects: {len(rejects)}")
    for r in rejects:
        print(f"  ✗ App {r['app_id']}: {r['company']} | {r['role_title']} — {r['reason']} ({r['failure_stage']})")

    return results

if __name__ == "__main__":
    main()
