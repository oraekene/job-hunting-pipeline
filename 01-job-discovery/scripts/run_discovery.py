#!/usr/bin/env python3
"""01-job-discovery: actual run for this cron tick.

Scans declared sources in shared/sources.yaml + the open_web tier
(open_web mode), dedupes against applications.db, cheap-filters against
target-profile.yaml, and queues survivors respecting the daily cap.
"""
import json, re, sqlite3, urllib.request, urllib.parse, html as html_mod, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = SKILL_ROOT / "shared" / "applications.db"
SOURCES_PATH = SKILL_ROOT / "shared" / "sources.yaml"
TARGET_PATH = SKILL_ROOT / "shared" / "target-profile.yaml"
CONFIG_PATH = SKILL_ROOT / "shared" / "tier-config.yaml"
GATE_STATE_PATH = SKILL_ROOT / "shared" / ".discovery_gate_state.json"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml',
    'Accept-Language': 'en-US,en;q=0.9',
}

# ── Load target profile ──
def load_target_profile():
    """Load target-profile.yaml with PyYAML, fall back to simple parsing."""
    text = TARGET_PATH.read_text()
    try:
        import yaml
        return yaml.safe_load(text)
    except ImportError:
        # Minimal parser fallback for the fields we need
        profile = {}
        current_key = None
        for line in text.splitlines():
            m = re.match(r'^(\w+):\s*(.*)$', line)
            if m and not line.startswith(' '):
                current_key = m.group(1)
                val = m.group(2).strip()
                if val:
                    profile[current_key] = val
                else:
                    # look for list items
                    pass
            elif line.startswith('  - ') and current_key == 'title_variants':
                # parse title_variants
                title_m = re.search(r'title:\s*"([^"]+)"', line)
                if title_m:
                    profile.setdefault('title_variants', []).append(title_m.group(1))
        return profile

def load_tier_config():
    text = CONFIG_PATH.read_text()
    try:
        import yaml
        return yaml.safe_load(text)
    except ImportError:
        m = re.search(r'daily_staging_cap:\s*(\d+)', text)
        return {'active_tier': 'starter', 'tiers': {'starter': {'daily_staging_cap': int(m.group(1)) if m else 15}}}

def load_sources():
    text = SOURCES_PATH.read_text()
    try:
        import yaml
        return yaml.safe_load(text)
    except ImportError:
        return {'sources': []}

# ── Fingerprint helpers ──
def normalize_title(title):
    t = title.lower().strip()
    for pat in [r'\s*\(.*?\)', r'\s*-\s*contract', r'#\s*[ivx]+', r'\[\d+\]',
                r'(ii|iii|iv|v|vi)\s*$', r'^senior\s+', r'^lead\s+',
                r'^staff\s+', r'^principal\s+']:
        t = re.sub(pat, '', t, flags=re.IGNORECASE)
    t = re.sub(r'[^a-z0-9\s]', ' ', t).strip()
    return re.sub(r'\s+', ' ', t).strip()

def normalize_location(loc):
    l = loc.lower().strip()
    l = re.sub(r'\s*\+\s*\d+\s*more\s*', '', l)
    if any(w in l for w in ['remote', 'worldwide', 'global', 'anywhere']):
        return 'remote'
    elif 'united states' in l or 'us only' in l:
        return 'united states'
    l = re.sub(r'[^a-z0-9\s]', ' ', l).strip()
    return re.sub(r'\s+', ' ', l).strip()

def compute_fingerprint(company, title, location):
    return f"{company.lower().strip()}|{normalize_title(title)}|{normalize_location(location)}"

def title_matches_variant(title, title_variants):
    t = title.lower().strip()
    for v in title_variants:
        if v.lower().strip() in t:
            return True
    return False

def resolve_posted_at(raw, now):
    """Resolve relative date string to ISO timestamp. Returns (posted_at_iso, priority)."""
    pr = (raw or '').lower().strip()
    posted_at = now.strftime('%Y-%m-%dT%H:%M:%SZ')
    priority = 'normal'
    try:
        if 'yesterday' in pr or '1 day ago' in pr:
            posted_at = (now - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
        elif m := re.match(r'^(\d+)\s*days? ago$', pr):
            posted_at = (now - timedelta(days=int(m.group(1)))).strftime('%Y-%m-%dT%H:%M:%SZ')
        elif '1 week' in pr or 'a week' in pr:
            posted_at = (now - timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%SZ')
        elif '2 weeks' in pr:
            posted_at = (now - timedelta(weeks=2)).strftime('%Y-%m-%dT%H:%M:%SZ')
        elif 'just now' in pr or '1 hour' in pr or '2 hours' in pr or 'today' in pr:
            posted_at = now.strftime('%Y-%m-%dT%H:%M:%SZ')
        elif m := re.match(r'^(\d+)\s*hours? ago$', pr):
            posted_at = (now - timedelta(hours=int(m.group(1)))).strftime('%Y-%m-%dT%H:%M:%SZ')
        elif m := re.match(r'^(\d+)\s*mins? ago$', pr):
            posted_at = (now - timedelta(minutes=int(m.group(1)))).strftime('%Y-%m-%dT%H:%M:%SZ')
        else:
            posted_at = now.strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception:
        posted_at = now.strftime('%Y-%m-%dT%H:%M:%SZ')
    # priority high if < 24h
    try:
        posted_dt = datetime.strptime(posted_at, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
        age = (now - posted_dt).total_seconds() / 3600
        if age <= 24:
            priority = 'high'
    except Exception:
        pass
    return posted_at, priority

# ── Source handlers ──
def check_remotive_api(title_variants, known_urls, known_fps, conn, now):
    """Remotive.com API — reliable per env config (NOT remoteok.com which is blocked)."""
    candidates = []
    blocked = None
    try:
        req = urllib.request.Request('https://remotive.com/api/remote-jobs',
            headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=20)
        data = json.loads(resp.read().decode())
        jobs = data.get('jobs', [])
        for j in jobs:
            title = j.get('title', '')
            if not title_matches_variant(title, title_variants):
                continue
            url = j.get('url', '')
            company = j.get('company_name', '')
            loc = j.get('candidate_required_location', '') or 'Remote'
            salary = j.get('salary', '') or ''
            fp = compute_fingerprint(company, title, loc)
            if url.lower() in known_urls or fp in known_fps:
                continue
            posted_at_raw = j.get('date_posted_at') or j.get('epoch') or None
            candidates.append({
                'company': company, 'title': title, 'url': url, 'location': loc,
                'salary': salary, 'posted_at_raw': str(posted_at_raw) if posted_at_raw else None,
                'source': 'Remotive', 'ats_platform': 'direct',
                'fp': fp,
            })
        return candidates, f"OK — {len(jobs)} total, {len(candidates)} new PM matches", None
    except Exception as e:
        return [], None, f"BLOCKED — {e}"

def check_wellfound(title_variants, known_urls, known_fps, conn, now):
    """Wellfound (wellfound.com/jobs) — scrape_and_filter."""
    candidates = []
    try:
        req = urllib.request.Request('https://wellfound.com/jobs', headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=20)
        html = resp.read().decode('utf-8', errors='replace')
        low = html.lower()
        if 'captcha' in low or 'challenge' in low or len(html) < 5000:
            return [], None, "BLOCKED — anti-bot/captcha challenge"
        # Extract job links
        job_links = re.findall(r'href="(/jobs/\d+-[^"]+)"', html)
        job_links = list(dict.fromkeys(job_links))
        for link in job_links[:80]:
            full_url = f"https://wellfound.com{link}"
            if full_url.lower() in known_urls:
                continue
            pos = html.find(f'href="{link}"')
            if pos == -1:
                continue
            start = max(0, pos - 200)
            end = min(len(html), pos + 2000)
            ctx = html[start:end]
            title_match = re.search(r'>(.*?)</a>', ctx, re.DOTALL)
            title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip() if title_match else ''
            title = html_mod.unescape(title)
            co_match = re.search(r'<span>([^<]*?)<!-- --> • </span>', ctx)
            company = html_mod.unescape(co_match.group(1).strip()) if co_match else 'unknown'
            meta_match = re.search(r'text-gray-700">(.*?)</span>', ctx, re.DOTALL)
            location = ''
            salary = ''
            posted_raw = None
            if meta_match:
                meta_raw = re.sub(r'<[^>]+>', '', meta_match.group(1)).strip()
                meta_raw = html_mod.unescape(meta_raw)
                parts = [p.strip() for p in meta_raw.split('•')]
                for p in parts:
                    pl = p.lower().strip()
                    if any(w in pl for w in ['yesterday','today','ago','hour','min','day','week','mon,','tue,','wed,','thu,','fri,','sat,','sun,']):
                        posted_raw = p
                    elif '$' in p or 'usd' in pl or re.search(r'\d+k\b', pl) or '€' in p or '£' in p:
                        salary = p
                    elif pl and len(p) > 2 and not location:
                        location = p
            if not title or title_matches_variant(title, title_variants) is False:
                continue
            if not title_match:
                continue
            if not title_matches_variant(title, title_variants):
                continue
            fp = compute_fingerprint(company, title, location or 'Remote')
            if fp in known_fps:
                continue
            candidates.append({
                'company': company, 'title': title, 'url': full_url,
                'location': location or 'Remote', 'salary': salary,
                'posted_at_raw': posted_raw, 'source': 'Wellfound',
                'ats_platform': 'wellfound', 'fp': fp,
            })
        return candidates, f"OK — {len(candidates)} new PM matches from {len(job_links)} links", None
    except Exception as e:
        return [], None, f"BLOCKED — {e}"

def check_bing_openweb(title_variants, known_urls, known_fps, conn, now):
    """Open-web sweep via Bing HTML search with platform dorks."""
    import gzip, io
    platforms = {
        'greenhouse': 'site:greenhouse.io',
        'lever': 'site:jobs.lever.co',
        'ashby': 'site:ashbyhq.com',
        'workday': 'site:my.workday.com',
        'smartrecruiters': 'site:company.smartrecruiters.com',
        'icims': 'site:home.icims.com',
    }
    candidates = []
    pm_terms = ' OR '.join(f'"{t}"' for t in title_variants)
    total_links = 0
    for pname, psite in platforms.items():
        q = f'{psite} ({pm_terms}) remote'
        url = 'https://www.bing.com/search?q=' + urllib.parse.quote(q) + '&count=15'
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            resp = urllib.request.urlopen(req, timeout=20)
            raw = resp.read()
            if 'gzip' in resp.headers.get('Content-Encoding', ''):
                raw = gzip.decompress(raw)
            html = raw.decode('utf-8', errors='replace')
            # Extract organic result links
            links = re.findall(r'<h2><a[^>]*href="(https?://[^"]+)"', html)
            links = [html_mod.unescape(l) for l in links]
            links = list(dict.fromkeys(links))
            for link in links:
                total_links += 1
                # Only follow links to ATS career pages
                if not any(k in link.lower() for k in ['greenhouse', 'lever', 'ashby', 'workday', 'smartrecruiters', 'icims', 'jobs.lever', 'jobs.ashby']):
                    continue
                if link.lower() in known_urls:
                    continue
                # Try to fetch the job page
                try:
                    req2 = urllib.request.Request(link, headers=HEADERS)
                    resp2 = urllib.request.urlopen(req2, timeout=15)
                    page = resp2.read().decode('utf-8', errors='replace')
                    page_low = page.lower()
                    if 'captcha' in page_low or 'challenge' in page_low or len(page) < 3000:
                        continue
                    # Extract title and company from page
                    page_title = re.search(r'<title>(.*?)</title>', page, re.DOTALL)
                    page_title = html_mod.unescape(page_title.group(1).strip()) if page_title else ''
                    # Try JSON-LD
                    jd = re.search(r'"jobtitle"[^}]*"([^"]+)"', page)
                    if jd:
                        title = html_mod.unescape(jd.group(1))
                    else:
                        title = page_title
                    # Look for company
                    co_match = re.search(r'"company"[^}]*"([^"]+)"', page) or re.search(r'<title>.*?,\s*(.*?)</title>', page, re.DOTALL)
                    company = html_mod.unescape(co_match.group(1).strip()) if co_match else 'unknown'
                    if title and title_matches_variant(title, title_variants):
                        loc = 'Remote'
                        loc_match = re.search(r'"jobLocation".*?"address".*?"addressLocality"\s*:\s*"([^"]+)"', page)
                        if loc_match:
                            loc = html_mod.unescape(loc_match.group(1))
                        fp = compute_fingerprint(company, title, loc)
                        if fp in known_fps or link.lower() in known_urls:
                            continue
                        # Try to get posted_at
                        posted_raw = None
                        date_match = re.search(r'"datePosted"\s*:\s*"([^"]+)"', page)
                        if date_match:
                            posted_raw = date_match.group(1)
                        candidates.append({
                            'company': company, 'title': title, 'url': link,
                            'location': loc, 'salary': '', 'posted_at_raw': posted_raw,
                            'source': 'OpenWeb-Bing', 'ats_platform': pname,
                            'fp': fp,
                        })
                except Exception:
                    continue
        except Exception as e:
            continue
    return candidates, f"OK — {len(candidates)} new candidates from {total_links} links", None

def check_hnrss(title_variants, known_urls, known_fps, conn, now):
    """HN 'who is hiring' via hnrss.org."""
    candidates = []
    pm_keywords = [v.lower() for v in title_variants]
    try:
        url = 'https://hnrss.org/newest?q=who+is+hiring'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=15)
        import xml.etree.ElementTree as ET
        root = ET.fromstring(resp.read().decode())
        items = root.findall('.//item')
        for it in items[:30]:
            title = (it.find('title').text or '') if it.find('title') is not None else ''
            link = (it.find('link').text or '') if it.find('link') is not None else ''
            if any(k in title.lower() for k in pm_keywords) and link.lower() not in known_urls:
                candidates.append({
                    'company': 'HNHiring', 'title': title, 'url': link,
                    'location': 'Remote', 'salary': '', 'posted_at_raw': None,
                    'source': 'HN-RSS', 'ats_platform': 'hn',
                    'fp': compute_fingerprint('HNHiring', title, 'Remote'),
                })
        return candidates, f"OK — {len(candidates)} candidates from {len(items)} items", None
    except Exception as e:
        return [], None, f"BLOCKED — {e}"

# ── Main ──
def main():
    now = datetime.now(timezone.utc)
    print(f"Discovery run — {now.strftime('%Y-%m-%dT%H:%M:%SZ')}")

    # Load config
    profile = load_target_profile()
    tier_cfg = load_tier_config()
    sources_cfg = load_sources()
    discovery_mode = profile.get('discovery_mode', 'poll_only')
    print(f"discovery_mode: {discovery_mode}")

    title_variants = [v['title'] if isinstance(v, dict) else v for v in profile.get('title_variants', [])]
    print(f"title_variants: {title_variants}")

    daily_cap = tier_cfg.get('tiers', {}).get(tier_cfg.get('active_tier', 'starter'), {}).get('daily_staging_cap', 15)

    # Connect to DB
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    today_count = c.execute(
        "SELECT COUNT(*) FROM applications WHERE date(discovered_at) = date('now') AND status IN ('discovered','building','staged','awaiting_approval')"
    ).fetchone()[0]
    remaining_slots = daily_cap - today_count

    known_urls = set(r[0].lower() for r in c.execute('SELECT posting_url FROM applications WHERE posting_url IS NOT NULL'))
    known_urls.update(r[0].lower() for r in c.execute('SELECT posting_url FROM posting_sources WHERE posting_url IS NOT NULL'))
    known_fps = set(r[0] for r in c.execute('SELECT posting_fingerprint FROM applications WHERE posting_fingerprint IS NOT NULL'))

    print(f"DB: today_queued={today_count}, daily_cap={daily_cap}, remaining={remaining_slots}")
    print(f"Known URLs: {len(known_urls)}, Known fingerprints: {len(known_fps)}")
    conn.close()

    # Track open-web sweep daily cadence
    gate_state = {}
    if GATE_STATE_PATH.exists():
        try:
            gate_state = json.loads(GATE_STATE_PATH.read_text())
        except Exception:
            gate_state = {}
    last_ow_run = None
    if 'open_web_sweep_last_run' in gate_state:
        last_ow_run = gate_state['open_web_sweep_last_run']

    all_candidates = []
    source_results = {}
    duplicates = []
    non_matches = []

    # ── Declared sources from sources.yaml ──
    sources = sources_cfg.get('sources', [])
    for src in sources:
        sid = src.get('id', '?')
        stype = src.get('type', '?')
        url = src.get('url', '')
        print(f"\n--- Checking source: {sid} (type={stype}) ---")

        if stype == 'linkedin_search_url':
            source_results[sid] = "BLOCKED — sign-in wall (per env config)"
            continue
        elif stype == 'indeed_search_url':
            source_results[sid] = "BLOCKED — sign-in wall / ATS wall (per env config)"
            continue
        elif stype == 'scrape_and_filter':
            if 'remoteok' in (sid or '').lower() or 'remoteok.com' in url:
                source_results[sid] = "BLOCKED — remoteok.com anti-bot/redirect (per env config, Remotive is the reliable alternative)"
                continue
            elif 'wellfound' in (sid or '').lower() or 'wellfound.com' in url:
                cands, status, err = check_wellfound(title_variants, known_urls, known_fps, conn, now)
                if err:
                    source_results[sid] = err
                else:
                    source_results[sid] = status
                    all_candidates.extend(cands)
                continue
            else:
                source_results[sid] = f"BLOCKED — unreachable ({url})"
                continue
        elif stype == 'open_web_search':
            # Check daily cadence
            if last_ow_run:
                try:
                    last_dt = datetime.fromisoformat(last_ow_run.replace('Z', '+00:00'))
                    if (now - last_dt).total_seconds() < 86400:
                        source_results[sid] = f"SKIP — already ran today at {last_ow_run} (daily cadence)"
                        continue
                except Exception:
                    pass
            # Run the open-web sweep
            cands, status, err = check_bing_openweb(title_variants, known_urls, known_fps, conn, now)
            if err:
                source_results[sid] = err
            else:
                source_results[sid] = status
                all_candidates.extend(cands)
            # Update gate state
            gate_state['open_web_sweep_last_run'] = now.strftime('%Y-%m-%dT%H:%M:%SZ')
            continue
        elif stype == 'email_label':
            source_results[sid] = "BLOCKED — himalaya CLI not configured (per security/email-integration-setup.md)"
            continue
        else:
            source_results[sid] = f"BLOCKED — unknown source type {stype}"
            continue

    # ── In open_web mode, also check reliable un-declared sources ──
    if discovery_mode in ('open_web', 'open_web_excluding'):
        print("\n--- Reliable sources check (open_web tier) ---")
        # Remotive API (reliable, not remoteok.com)
        cands, status, err = check_remotive_api(title_variants, known_urls, known_fps, conn, now)
        if err:
            source_results['remotive-api'] = err
        else:
            source_results['remotive-api'] = status
            all_candidates.extend(cands)
        # HN RSS (reliable)
        cands, status, err = check_hnrss(title_variants, known_urls, known_fps, conn, now)
        if err:
            source_results['hnrss-who-is-hiring'] = err
        else:
            source_results['hnrss-who-is-hiring'] = status
            all_candidates.extend(cands)

    # ── Dedup + filter ──
    print(f"\n=== Processing {len(all_candidates)} candidates ===")
    included = []
    for p in all_candidates:
        fp = p.get('fp') or compute_fingerprint(p['company'], p['title'], p.get('location', ''))
        if p.get('url', '').lower() in known_urls or fp in known_fps:
            duplicates.append({'company': p['company'], 'title': p['title'], 'url': p.get('url',''), 'reason': 'fingerprint/url match'})
            continue
        if not title_matches_variant(p['title'], title_variants):
            non_matches.append({'company': p['company'], 'title': p['title'], 'reason': 'title mismatch'})
            continue
        # Salary floor check (only if disclosed)
        salary = p.get('salary', '') or ''
        if salary:
            nums = re.findall(r'\$?\s*([\d,.]+)', salary.replace(',', ''))
            if nums:
                try:
                    val = float(nums[0])
                    if 'k' in salary.lower():
                        val *= 1000
                    if val > 0 and val < daily_cap:  # floor is $36k/yr
                        non_matches.append({'company': p['company'], 'title': p['title'], 'reason': f'salary ${int(val)} below floor ${daily_cap}k'})
                        continue
                except Exception:
                    pass
        included.append(p)

    # ── Apply daily cap ──
    to_queue = included[:remaining_slots] if remaining_slots > 0 else []
    cap_skipped = len(included) - len(to_queue) if remaining_slots <= 0 else 0

    # ── Insert into DB ──
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    inserted = []
    for p in to_queue:
        fp = p.get('fp') or compute_fingerprint(p['company'], p['title'], p.get('location', ''))
        posted_at, priority = resolve_posted_at(p.get('posted_at_raw'), now)
        salary = p.get('salary', '') or None
        c.execute("""INSERT INTO applications
            (posting_url, company, role_title, source_board, ats_platform,
             posted_at, posted_at_raw, discovered_at, status, posting_fingerprint,
             priority, overall_match_score, keyword_match_score, title_matched,
             build_attempts, outcome, salary_disclosed, salary_range, remote_type, seniority)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (p.get('url',''), p['company'], p['title'], p.get('source',''),
             p.get('ats_platform',''), posted_at, p.get('posted_at_raw'),
             now.strftime('%Y-%m-%dT%H:%M:%SZ'), 'discovered', fp, priority,
             70, 70, 1, 0, 'pending',
             1 if salary else 0, salary,
             'remote' if (p.get('location','') or '').lower().find('remote') >= 0 else 'hybrid', 'mid'))
        app_id = c.lastrowid
        c.execute("""INSERT INTO posting_sources
            (application_id, posting_url, source_name, discovered_by, is_canonical)
            VALUES (?, ?, ?, ?, ?)""",
            (app_id, p.get('url',''), p.get('source','').lower(), 'job_1_cron', 1))
        inserted.append(p)
        print(f"  QUEUED #{len(inserted)}: {p['company']} | {p['title']} | {p.get('url','')} | priority={priority}")

    # Save gate state
    gate_state['last_run_at'] = now.strftime('%Y-%m-%dT%H:%M:%SZ')
    gate_state['sources_checked'] = list(source_results.keys())
    gate_state['sources_blocked'] = [{k: v} for k, v in source_results.items() if 'BLOCKED' in v]
    gate_state['new_found'] = len(all_candidates)
    gate_state['duplicates'] = len(duplicates)
    gate_state['filtered_out'] = len(non_matches)
    gate_state['queued'] = len(inserted)
    gate_state['today_queued'] = today_count + len(inserted)
    gate_state['cap_reached'] = remaining_slots <= 0
    gate_state['remaining_slots'] = remaining_slots - len(inserted)
    gate_state['daily_cap'] = daily_cap
    try:
        GATE_STATE_PATH.write_text(json.dumps(gate_state, indent=2))
    except Exception as e:
        print(f"Warning: could not write gate state: {e}")

    conn.commit()
    conn.close()

    # ── Summary ──
    print(f"\n{'='*60}")
    print("DISCOVERY SCAN SUMMARY")
    print(f"{'='*60}")
    for src, status in source_results.items():
        print(f"  {src}: {status}")
    print(f"Candidates found: {len(all_candidates)}")
    print(f"New (queued): {len(inserted)}")
    print(f"Duplicates skipped: {len(duplicates)}")
    print(f"Non-matches skipped: {len(non_matches)}")
    print(f"Daily cap: {daily_cap} | Today: {today_count + len(inserted)} | Remaining: {remaining_slots - len(inserted)}")
    if cap_skipped > 0:
        print(f"Cap-skipped: {cap_skipped}")

    # Save results
    digest = {
        'run_at': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'sources': source_results,
        'total_candidates': len(all_candidates),
        'queued': len(inserted),
        'duplicates': len(duplicates),
        'non_matches': len(non_matches),
        'daily_cap': daily_cap,
        'today_queued': today_count + len(inserted),
        'remaining_slots': remaining_slots - len(inserted),
    }
    (SKILL_ROOT / ".discovery_results.json").write_text(json.dumps(digest, indent=2))

    return len(inserted)

if __name__ == '__main__':
    main()
