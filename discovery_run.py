#!/usr/bin/env python
"""Job discovery script to find and queue new postings."""
import sqlite3
import re
from datetime import datetime
import json

# Define title variants from target-profile.yaml
TITLE_VARIANTS = [
    'Product Manager', 'AI Product Manager', 'AI Engineer',
    'Automation Engineer', 'Associate Product Manager',
    'Junior Product Manager', 'Workflow Engineer', 'Product Owner',
    'Technical Product Manager', 'Growth Product Manager',
    'AI/ML Product Manager',
]

LEVEL_PREFIXES = ['senior', 'staff', 'principal', 'lead', 'jr', 'junior',
                  'associate', 'head of', 'director', 'vp']

def normalize_title(title):
    t = title.lower().strip()
    t = re.sub(r'[^\w\s,]', ' ', t)
    for prefix in LEVEL_PREFIXES:
        t = re.sub(rf'^{prefix}\s+', '', t)
    t = re.sub(r'\s+(ii|iii|iv|jr|senior|staff|principal|lead)$', '', t)
    t = t.strip()
    return t

def compute_fingerprint(company, title, location):
    norm_title = normalize_title(title)
    return f'{company.lower().strip()}|{norm_title}|{location.lower().strip()}'

def title_matches_variant(title):
    title_lower = title.lower()
    for variant in TITLE_VARIANTS:
        v = variant.lower()
        if v in title_lower:
            return True
    return False

def parse_salary_value(s):
    if re.search(r'\d+\.?\d*\s*[Kk]\b', s):
        num = re.search(r'([\d.]+)\s*[Kk]', s)
        if num:
            return float(num.group(1)) * 1000
    if re.search(r'\d+\.?\d*\s*[Mm]\b', s):
        num = re.search(r'([\d.]+)', s)
        if num:
            return float(num.group(1)) * 1000000
    num = re.search(r'([\d,]+\.?\d*)', s.replace(',', ''))
    if num:
        return float(num.group(0).replace(',', ''))
    return 0

def main():
    conn = sqlite3.connect('shared/applications.db')
    cursor = conn.cursor()
    
    # Check current daily cap
    cursor.execute("SELECT COUNT(*) FROM applications WHERE DATE(discovered_at) = DATE('now')")
    today_count = cursor.fetchone()[0]
    daily_cap = 15
    remaining = daily_cap - today_count
    
    cursor.execute("SELECT posting_fingerprint FROM applications WHERE posting_fingerprint IS NOT NULL")
    existing_fingerprints = set()
    for row in cursor.fetchall():
        existing_fingerprints.add(row[0])
    
    cursor.execute("SELECT posting_url FROM applications WHERE posting_url IS NOT NULL")
    existing_urls = set()
    for row in cursor.fetchall():
        existing_urls.add(row[0])
    
    now_iso = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
    
    # Postings found from web search
    postings = [
        {
            'company': 'Arize AI',
            'role_title': 'AI Product Manager',
            'location': 'Remote (United States)',
            'url': 'https://wellfound.com/jobs/3935668-ai-product-manager',
            'source_board': 'Wellfound',
            'ats_platform': 'wellfound',
            'posted_at_raw': None,
            'salary_disclosed': True,
            'salary_range': '150000-220000 USD',
            'remote_type': 'remote',
        }
    ]
    
    included = []
    duplicates = []
    non_matches = []
    
    salary_floor = 36000
    
    for p in postings:
        fp = compute_fingerprint(p['company'], p['role_title'], p['location'])
        
        if fp in existing_fingerprints or p['url'] in existing_urls:
            duplicates.append((p['company'], p['role_title'], p['url']))
            continue
        
        if not title_matches_variant(p['role_title']):
            non_matches.append((p['company'], p['role_title'], p['url'], 'title mismatch'))
            continue
        
        if p['salary_disclosed'] and p['salary_range']:
            min_val = parse_salary_value(p['salary_range'])
            if min_val > 0 and min_val < salary_floor:
                non_matches.append((p['company'], p['role_title'], p['url'], 'salary below floor'))
                continue
        
        # Compute match score
        base = 70
        title_lower = p['role_title'].lower()
        for variant in TITLE_VARIANTS:
            if variant.lower() in title_lower:
                base += 15
        if 'ai' in title_lower or 'ml' in title_lower:
            base += 5
        if p['salary_disclosed']:
            base += 5
            nums = re.findall(r'[\d.]+', p['salary_range'] or '')
            if nums:
                min_val = float(nums[0].replace('k', '000').replace('K', '000'))
                if min_val >= 36000:
                    base += 5
        match_score = max(50, min(95, base))
        
        included.append({
            **p,
            'fingerprint': fp,
            'match_score': match_score
        })
    
    print("Discovery Summary:")
    print(f"  - Today's count: {today_count}")
    print(f"  - Remaining slots: {remaining}")
    print(f"  - New postings found: {len(postings)}")
    print(f"  - New (queued): {len(included)}")
    print(f"  - Duplicates: {len(duplicates)}")
    print(f"  - Non-matches (excluded): {len(non_matches)}")
    
    # Insert new postings - only columns that exist in the schema
    if included:
        for p in included:
            cursor.execute('''INSERT INTO applications (
                company, role_title, posting_url, source_board, ats_platform,
                posted_at_raw, salary_disclosed, salary_range, remote_type,
                posted_at, discovered_at, status, overall_match_score, keyword_match_score,
                exact_phrase_count, title_matched, title_original, title_displayed,
                posting_fingerprint, industry, seniority, build_attempts, outcome
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (p['company'], p['role_title'], p['url'], p['source_board'], p['ats_platform'],
             p['posted_at_raw'], p['salary_disclosed'], p['salary_range'], p['remote_type'],
             None, now_iso, 'discovered', p['match_score'], p['match_score'],
             1, 1, p['role_title'], p['role_title'],
             p['fingerprint'], None, 'mid', 0, 'pending'))
            print(f"  - Queued: {p['company']} - {p['role_title']} ({p['url']}) [match score: {p['match_score']}]")
        conn.commit()
        print(f"\nInserted {len(included)} new postings to discovered queue")
    
    if duplicates:
        print("\nDuplicates (already in DB):")
        for d in duplicates:
            print(f"  - {d[0]} - {d[1]} ({d[2]})")
    
    if non_matches:
        print("\nExcluded:")
        for n in non_matches:
            print(f"  - {n[0]} - {n[1]} ({n[2]}) - {n[3]}")
    
    conn.close()
    return len(included)

if __name__ == '__main__':
    main()