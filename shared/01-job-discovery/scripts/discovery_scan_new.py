#!/usr/bin/env python3
"""
Discovery scan — scans job sources, dedupes against DB, filters against target profile, and queues new postings.
"""
import sqlite3
import json
import re
import hashlib
from datetime import datetime, timezone, timedelta

DB_PATH = 'shared/applications.db'
TARGET_PROFILE_PATH = 'shared/target-profile.yaml'
SOURCES_PATH = 'shared/sources.yaml'

# ============================================================
# Load target profile
# ============================================================
title_variants = [
    'Product Manager', 'AI Product Manager', 'AI Engineer', 'Automation Engineer',
    'Workflow Engineer', 'Associate Product Manager', 'Junior Product Manager',
    'Product Owner', 'Technical Product Manager', 'Growth Product Manager',
    'AI/ML Product Manager'
]

# Keywords that indicate a role matches (case-insensitive)
TITLE_KEYWORDS = [
    'product manager', 'ai product manager', 'technical product manager',
    'growth product manager', 'associate product manager', 'junior product manager',
    'product owner', 'ai engineer', 'automation engineer', 'workflow engineer',
    'ai/ml product manager', 'staff product manager', 'principal product manager',
    'lead product manager', 'senior product manager', 'head of product'
]

locations_allowed = ['Worldwide', 'remote', 'Remote', 'United States', 'USA', 'Canada', 'EU', 'UK', 'Europe']
salary_floor_amount = 36000
salary_floor_currency = 'USD'
salary_floor_period = 'year'

# ============================================================
# Load database
# ============================================================
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Check schema for posting_fingerprint column
cursor.execute("PRAGMA table_info(applications)")
columns = [row[1] for row in cursor.fetchall()]
print(f"Columns in applications table: {columns}")

# Get all existing fingerprints
cursor.execute("SELECT posting_fingerprint, company, role_title, posting_url FROM applications")
existing = cursor.fetchall()
existing_fingerprints = set()
existing_urls = set()
for row in existing:
    if row['posting_fingerprint']:
        existing_fingerprints.add(row['posting_fingerprint'])
    if row['posting_url']:
        existing_urls.add(row['posting_url'])

# Get today's discovered count (using discovered_at timestamp)
cursor.execute("SELECT COUNT(*) FROM applications WHERE status = 'discovered' AND date(discovered_at) = date('now')")
today_count = cursor.fetchone()[0]

daily_cap = 15
remaining_slots = daily_cap - today_count

print(f"Daily cap: {daily_cap}")
print(f"Discovered today: {today_count}")
print(f"Remaining slots: {remaining_slots}")
print(f"Total existing postings in DB: {len(existing)}")

# ============================================================
# Helper functions
# ============================================================
def normalize_title(title):
    """Normalize a job title for fingerprinting."""
    # Lowercase, strip punctuation
    normalized = title.lower().strip()
    # Remove trailing decorations like "(Remote)", "- Contract"
    normalized = re.sub(r'\s*\(remote\)\s*', '', normalized)
    normalized = re.sub(r'\s*-\s*contract\s*', '', normalized)
    # Remove roman numerals at the end
    normalized = re.sub(r'\s+ii+i*$', '', normalized)
    # Remove level suffixes
    normalized = re.sub(r'\s*(jr\.|sr\.|iii|iv|v)\s*$', '', normalized)
    return normalized.strip()

def compute_fingerprint(company, role_title, location):
    """Compute the posting fingerprint for deduplication."""
    if not company:
        company = 'unknown'
    if not location:
        location = 'unknown'
    components = [
        company.lower().strip(),
        normalize_title(role_title),
        location.lower().strip()
    ]
    return ' | '.join(components)

def title_matches(title):
    """Check if a job title matches any title variant."""
    title_lower = title.lower()
    for kw in TITLE_KEYWORDS:
        if kw in title_lower:
            return True
    return False

def extract_salary(text):
    """Extract salary from text. Returns (amount, currency, period)."""
    if not text:
        return None, None, None
    # Look for salary patterns like $100k - $150k, $116K-176K, etc.
    patterns = [
        r'\$(\d+[,.]?\d*[kK]?)\s*-?\s*\$?(\d+[,.]?\d*[kK]?)',  # $100k - $150k
        r'\$(\d+[,.]?\d*[kK]?)',  # $100k
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                raw = match.group(1).replace(',', '').lower()
                if 'k' in raw:
                    min_salary = float(raw.replace('k', '')) * 1000
                else:
                    min_salary = float(raw)
                return min_salary, 'USD', 'year'
            except:
                pass
    return None, None, None

def location_matches(location):
    """Check if location is acceptable (remote or acceptable country)."""
    if not location:
        return True  # If no location specified, don't reject
    location_lower = location.lower()
    if 'remote' in location_lower or 'united states' in location_lower or 'usa' in location_lower:
        return True
    if 'worldwide' in location_lower:
        return True
    if 'canada' in location_lower:
        return True
    if 'europe' in location_lower or 'eu' in location_lower:
        return True
    if 'uk' in location_lower or 'united kingdom' in location_lower:
        return True
    return False

# ============================================================
# New job postings discovered from web search
# ============================================================
new_postings = [
    # From BuiltInSF search
    {
        'company': 'Babylist',
        'role_title': 'Staff Product Manager, Wishlist',
        'posting_url': 'https://www.builtinsf.com/job/staff-product-manager-ai-builder/9251473',
        'location': 'Remote or Hybrid, United States',
        'posted_at': '2026-08-18T00:00:00Z',
        'posted_at_raw': '7 Hours Ago',
        'source': 'builtin_sf',
        'description': 'Staff Product Manager owning consumer surface/core customer journey, AI-native workflows. $215K-257K. Posted 7 hours ago.'
    },
    {
        'company': 'Block',
        'role_title': 'Product Manager, GTM Automation',
        'posting_url': 'https://builtin.com/job/product-manager-gtm-automation/9610550',
        'location': 'In-Office or Remote, 8 Locations',
        'posted_at': '2026-08-17T00:00:00Z',
        'posted_at_raw': 'Reposted Yesterday',
        'source': 'builtin',
        'description': 'Design and oversee AI products that enhance workflows. $240K-359K. Reposted yesterday.'
    },
    {
        'company': 'Unknown (BuiltIn)',
        'role_title': 'AI Product Manager',
        'posting_url': 'https://builtin.com/job/product-manager/9874103',
        'location': 'Remote or Hybrid, 2 Locations',
        'posted_at': '2026-08-16T00:00:00Z',
        'posted_at_raw': 'Reposted 2 Days Ago',
        'source': 'builtin',
        'description': 'Lead strategy and roadmap for AI-powered SaaS features. $90K-130K. Posted 2 days ago.'
    },
    {
        'company': 'Openly',
        'role_title': 'Product Manager',
        'posting_url': 'https://www.builtinboston.com/job/product-manager/10402477',
        'location': 'Remote, Boston, MA',
        'posted_at': '2026-08-18T10:00:00Z',
        'posted_at_raw': '28 Minutes Ago',
        'source': 'builtin_boston',
        'description': 'Lead product strategy for AI-first enterprise marketing platform. $137K-263K. Posted 28 minutes ago.'
    },
    # From Ashby search
    {
        'company': 'Runpod',
        'role_title': 'Senior Product Manager',
        'posting_url': 'https://jobs.ashbyhq.com/runpod/700a0ac4-9ca7-4bde-84f8-09005a401055',
        'location': 'Remote',
        'posted_at': '2026-08-18T00:00:00Z',
        'posted_at_raw': 'Recent',
        'source': 'ashby',
        'description': 'Lead core product initiatives at Runpod. AI/machine learning platform.'
    },
    {
        'company': 'Owner.com',
        'role_title': 'Principal Product Manager, AI Restaurant Experience',
        'posting_url': 'https://jobs.ashbyhq.com/owner/d74be412-5b98-48fb-95b0-3f0539cd9fa1',
        'location': 'Remote - United States or Canada',
        'posted_at': '2026-08-18T00:00:00Z',
        'posted_at_raw': 'Recent',
        'source': 'ashby',
        'description': 'AI Restaurant Experience product. Remote US/Canada.'
    },
    {
        'company': 'n8n',
        'role_title': 'AI Product Manager',
        'posting_url': 'https://jobs.ashbyhq.com/n8n/42e72645-d99a-4545-97b7-53ba3a699893',
        'location': 'Berlin Office; Albania; Austria; Belgium; Bosnia; Remote-first',
        'posted_at': '2026-08-18T00:00:00Z',
        'posted_at_raw': 'Recent',
        'source': 'ashby',
        'description': 'AI Product Manager at n8n (workflow automation platform). Remote-first across Europe.'
    },
    {
        'company': 'LiveKit',
        'role_title': 'Staff Product Manager, Agent Observability',
        'posting_url': 'https://jobs.ashbyhq.com/livekit/dc2e64b8-15fd-4d88-b2dd-c3106f76df4d',
        'location': 'Remote',
        'posted_at': '2026-08-18T00:00:00Z',
        'posted_at_raw': 'Recent',
        'source': 'ashby',
        'description': 'Own LiveKit Agent Observability product — how teams understand, debug, and trust voice agents. AI/dev platform focus.'
    },
    {
        'company': 'Render',
        'role_title': 'Staff/Principal Product Manager, Platform & Infrastructure',
        'posting_url': 'https://jobs.ashbyhq.com/render/d5f62097-29f5-4078-ad24-3b604380c1c0',
        'location': 'Remote',
        'posted_at': '2026-08-17T00:00:00Z',
        'posted_at_raw': 'Recent',
        'source': 'ashby',
        'description': 'Own vision and roadmap for Render infrastructure platform.'
    },
    {
        'company': 'Arcadia',
        'role_title': 'Principal Product Manager, AI Product',
        'posting_url': 'https://jobs.lever.co/arcadia/8d01e985-fc84-4097-ab31-ca2a328d8e11/apply',
        'location': 'Remote (USA)',
        'posted_at': '2026-08-17T00:00:00Z',
        'posted_at_raw': 'Recent',
        'source': 'lever',
        'description': 'AI Product role at Arcadia. Remote USA.'
    },
    {
        'company': 'CSC Generation',
        'role_title': 'Senior Product Manager, Platform, Integrations, and Data',
        'posting_url': 'https://jobs.lever.co/cscgeneration-2/bd2d826e-b2f1-489e-bbd6-5c53828b7362',
        'location': 'Remote (US or Canada)',
        'posted_at': '2026-08-17T00:00:00Z',
        'posted_at_raw': 'Recent',
        'source': 'lever',
        'description': 'Remote Senior PM role. US/Canada.'
    },
    {
        'company': 'Stripe',
        'role_title': 'Staff Product Manager, Risk Product Experience',
        'posting_url': 'https://boards.greenhouse.io/stripe/jobs/8040052',
        'location': 'Remote',
        'posted_at': '2026-08-17T00:00:00Z',
        'posted_at_raw': 'Recent',
        'source': 'greenhouse',
        'description': 'Staff PM for Risk Product Experience at Stripe. Remote.'
    },
    {
        'company': 'Domino Data Lab',
        'role_title': 'Staff Product Manager, AI Factory',
        'posting_url': 'https://boards.greenhouse.io/dominodatalab/jobs/2385331',
        'location': 'Remote US',
        'posted_at': '2026-08-17T00:00:00Z',
        'posted_at_raw': 'Recent',
        'source': 'greenhouse',
        'description': 'AI Factory product management. Remote US. MLOps focus.'
    },
    {
        'company': 'Alteryx',
        'role_title': 'Lead Product Manager',
        'posting_url': 'https://alteryx.wd108.myworkdayjobs.com/en-US/AlteryxCareers/job/Lead-Product-Manager---USA-REMOTE-_R12090',
        'location': 'Remote (USA)',
        'posted_at': '2026-08-17T00:00:00Z',
        'posted_at_raw': 'Recent',
        'source': 'workday',
        'description': 'Lead Product Manager at Alteryx. US Remote. Analytics platform.'
    },
    {
        'company': 'Lyra Health',
        'role_title': 'Lead Product Manager, Data and AI',
        'posting_url': 'https://careers.lyrahealth.com/job/remote/lead-product-manager-data-and-ai/43250/96467662960',
        'location': 'Remote, USA',
        'posted_at': '2026-08-17T00:00:00Z',
        'posted_at_raw': 'Recent',
        'source': 'careers_site',
        'description': 'Lead PM for Data and AI at Lyra Health. Remote USA. Healthcare AI.'
    },
]

# ============================================================
# Process each posting: fingerprint, dedupe, filter
# ============================================================
new_to_queue = []
skipped_duplicate = []
skipped_filter = []

now = datetime.now(timezone.utc)

for posting in new_postings:
    company = posting['company']
    role_title = posting['role_title']
    location = posting.get('location', '')
    url = posting['posting_url']
    
    # Step 1: Check if URL already exists
    if url in existing_urls:
        skipped_duplicate.append(posting)
        continue
    
    # Step 2: Compute fingerprint
    fingerprint = compute_fingerprint(company, role_title, location)
    
    if fingerprint in existing_fingerprints:
        skipped_duplicate.append(posting)
        continue
    
    # Step 3: Title filter
    if not title_matches(role_title):
        skipped_filter.append((posting, 'title_mismatch'))
        continue
    
    # Step 4: Location filter
    if not location_matches(location):
        skipped_filter.append((posting, 'location_mismatch'))
        continue
    
    # Step 5: Salary floor check (if salary info available)
    description = posting.get('description', '')
    salary, currency, period = extract_salary(description)
    if salary and currency == 'USD':
        if salary < salary_floor_amount:
            skipped_filter.append((posting, 'below_salary_floor'))
            continue
    
    # Step 6: Check date recency
    posted_at_str = posting.get('posted_at', '')
    if posted_at_str:
        try:
            posted_at = datetime.fromisoformat(posted_at_str.replace('Z', '+00:00'))
            hours_ago = (now - posted_at).total_seconds() / 3600
            priority = 'high' if hours_ago <= 24 else 'normal'
        except:
            posted_at = now
            priority = 'normal'
    else:
        posted_at = now
        priority = 'normal'
    
    new_to_queue.append({
        'company': company,
        'role_title': role_title,
        'posting_url': url,
        'location': location,
        'posted_at': posted_at_str,
        'posted_at_raw': posting.get('posted_at_raw', ''),
        'source': posting.get('source', ''),
        'priority': priority,
        'description': description,
        'fingerprint': fingerprint,
        'posted_hours_ago': hours_ago if posted_at_str else None
    })

# Sort by priority (high first) then recency (most recent first)
new_to_queue.sort(key=lambda p: (0 if p['priority'] == 'high' else 1, p.get('posted_hours_ago', 99999)))

final_queue = new_to_queue[:remaining_slots] if remaining_slots > 0 else []
overflow = new_to_queue[remaining_slots:] if len(new_to_queue) > remaining_slots else []

# ============================================================
# Output results
# ============================================================
print(f"\n{'='*60}")
print(f"DISCOVERY SCAN RESULTS")
print(f"{'='*60}")
print(f"\nExisting postings in DB: {len(existing)}")
print(f"Discovered today: {today_count}")
print(f"Remaining slots (daily cap {daily_cap}): {remaining_slots}")
print(f"\nNew postings found: {len(new_postings)}")
print(f"Skipped as duplicates: {len(skipped_duplicate)}")
print(f"Skipped by filter: {len(skipped_filter)}")
print(f"Passed all filters: {len(new_to_queue)}")
print(f"Queued (respecting daily cap): {len(final_queue)}")
print(f"Overflow (waiting for tomorrow's cap): {len(overflow)}")

print(f"\n{'='*60}")
print("NEW POSTINGS TO QUEUE:")
print(f"{'='*60}")
for p in final_queue:
    print(f"\n  Company: {p['company']}")
    print(f"  Role: {p['role_title']}")
    print(f"  URL: {p['posting_url']}")
    print(f"  Location: {p['location']}")
    print(f"  Posted: {p['posted_at']} (raw: {p['posted_at_raw']})")
    if p.get('posted_hours_ago'):
        print(f"  Hours ago: {p['posted_hours_ago']:.1f}")
    print(f"  Priority: {p['priority']}")
    print(f"  Source: {p['source']}")
    print(f"  Fingerprint: {p['fingerprint']}")
    print(f"  Description: {p['description'][:120]}...")

print(f"\n{'='*60}")
print("SKIPPED AS DUPLICATES:")
print(f"{'='*60}")
for p in skipped_duplicate:
    print(f"  {p['company']} | {p['role_title']} | {p['posting_url']}")

print(f"\n{'='*60}")
print("SKIPPED BY FILTER:")
print(f"{'='*60}")
for p, reason in skipped_filter:
    print(f"  {p['company']} | {p['role_title']} | {p['posting_url']} | reason: {reason}")

print(f"\n{'='*60}")
print("OVERFLOW (cap reached, waiting for tomorrow):")
print(f"{'='*60}")
for p in overflow:
    print(f"  {p['company']} | {p['role_title']} | {p['posting_url']}")

# Save results to JSON for the DB update step
results = {
    'queued': final_queue,
    'skipped_duplicates': [{'company': p['company'], 'role_title': p['role_title'], 'posting_url': p['posting_url']} for p in skipped_duplicate],
    'skipped_filter': [{'company': p['company'], 'role_title': p['role_title'], 'posting_url': p['posting_url'], 'reason': reason} for p, reason in skipped_filter],
    'overflow': [{'company': p['company'], 'role_title': p['role_title'], 'posting_url': p['posting_url']} for p in overflow]
}

with open('shared/.discovery_results.json', 'w') as f:
    json.dump(results, f, indent=2, default=str)

conn.close()
