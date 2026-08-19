#!/usr/bin/env python3
"""
Insert queued job postings into the applications database.
Reads discovery results from shared/.discovery_results.json and inserts the queued postings.
"""
import sqlite3
import json
from datetime import datetime, timezone

DB_PATH = 'shared/applications.db'
RESULTS_PATH = 'shared/.discovery_results.json'

# Load results
with open(RESULTS_PATH, 'r') as f:
    results = json.load(f)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

inserted = 0
for posting in results['queued']:
    # Build the insert query
    cursor.execute('''
        INSERT INTO applications (
            posting_url, company, role_title, source_board, posted_at, posted_at_raw,
            discovered_at, status, posting_fingerprint, posting_last_verified_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        posting['posting_url'],
        posting['company'],
        posting['role_title'],
        posting.get('source', ''),
        posting.get('posted_at', None),
        posting.get('posted_at_raw', ''),
        now,
        'discovered',
        posting.get('fingerprint', ''),
        now
    ))
    inserted += 1
    print(f"  INSERTED: {posting['company']} | {posting['role_title']} | {posting['posting_url']}")

conn.commit()
conn.close()

print(f"\nTotal inserted: {inserted}")
print(f"Skipped duplicates: {len(results['skipped_duplicates'])}")
print(f"Skipped by filter: {len(results['skipped_filter'])}")
print(f"Overflow (waiting for tomorrow's cap): {len(results['overflow'])}")
