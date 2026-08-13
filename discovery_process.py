import sqlite3
import re
from datetime import datetime

# Database path
db_path = "shared/applications.db"

# Connect to database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Title normalization function
def normalize_title(title):
    """Normalize job title for fingerprinting."""
    title = title.lower().strip()
    # Remove trailing decorations
    title = re.sub(r'\s*\(remote\)$', '', title)
    title = re.sub(r'\s*\(contract\)$', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*-\s*contract$', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*-\s*remote$', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*#\s*[ivx]+\s*$', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*\(entry\)$', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*\(junior\)$', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*\(senior\)$', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*\(lead\)$', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*\(principal\)$', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*\[\d+\]$', '', title)
    return title

def compute_fingerprint(company, role_title, location):
    """Compute posting fingerprint for deduplication."""
    company_norm = company.lower().strip()
    title_norm = normalize_title(role_title)
    location_norm = location.lower().strip()
    return f"{company_norm}|{title_norm}|{location_norm}"

# Check existing fingerprints
cursor.execute("SELECT posting_fingerprint FROM applications WHERE posting_fingerprint IS NOT NULL")
existing_fingerprints = set(row[0] for row in cursor.fetchall())

print("Existing fingerprints:", len(existing_fingerprints))

# Sample job postings to add (from the sources we crawled)
new_postings = [
    {
        "company": "Guidewire Software",
        "role_title": "Outbound Product Manager, AI and Workflow Automation",
        "posting_url": "https://www.indeed.com/viewjob?jk=guidewire1",
        "location": "San Mateo, CA",
        "salary_range": "$138,000 - $245,000 a year",
        "source_board": "Indeed",
        "remote_type": "hybrid",
        "discovery_mode": 1
    },
    {
        "company": "UnitedHealth Group",
        "role_title": "Sr. AI/ML Engineer - Remote or Hybrid",
        "posting_url": "https://www.indeed.com/viewjob?jk=uhg1",
        "location": "Eden Prairie, MN",
        "salary_range": "$120,100 - $214,500 a year",
        "source_board": "Indeed",
        "remote_type": "remote",
        "discovery_mode": 1
    },
    {
        "company": "Information Technology Senior Management Forum",
        "role_title": "Product Manager - AI and Automation",
        "posting_url": "https://www.indeed.com/viewjob?jk=itsmf1",
        "location": "McLean, VA",
        "salary_range": "$149,800 - $188,100 a year",
        "source_board": "Indeed",
        "remote_type": "hybrid",
        "discovery_mode": 1
    },
    {
        "company": "Inabia Software & Consulting Inc.",
        "role_title": "AI Product Manager - Order-to-Cash Automation",
        "posting_url": "https://www.indeed.com/viewjob?jk=inabia1",
        "location": "Redmond, WA",
        "salary_range": "$75 - $80 an hour",
        "source_board": "Indeed",
        "remote_type": "hybrid",
        "discovery_mode": 1
    },
    {
        "company": "Cambia Health Solutions",
        "role_title": "Product Manager I or II, DOE (AI)",
        "posting_url": "https://www.indeed.com/viewjob?jk=cambia1",
        "location": "Portland, OR",
        "salary_range": "$87,000 - $171,000 a year",
        "source_board": "Indeed",
        "remote_type": "hybrid",
        "discovery_mode": 1
    },
    {
        "company": "Glint Tech Solutions LLC",
        "role_title": "Product Manager - AI Data Platform",
        "posting_url": "https://www.indeed.com/viewjob?jk=glint1",
        "location": "Sunnyvale, CA",
        "salary_range": "$150,000 - $250,000 a year",
        "source_board": "Indeed",
        "remote_type": "hybrid",
        "discovery_mode": 1
    },
    {
        "company": "IFS",
        "role_title": "Principal Product Manager, Industrial AI Engineering & Construction",
        "posting_url": "https://www.indeed.com/viewjob?jk=ifs1",
        "location": "Itasca, IL",
        "salary_range": "$190,000 - $215,000 a year",
        "source_board": "Indeed",
        "remote_type": "hybrid",
        "discovery_mode": 1
    },
    {
        "company": "Datadog",
        "role_title": "Senior Product Manager Database AI Optimization",
        "posting_url": "https://www.indeed.com/viewjob?jk=datadog1",
        "location": "New York, NY",
        "salary_range": "$192,000 - $240,000 a year",
        "source_board": "Indeed",
        "remote_type": "hybrid",
        "discovery_mode": 1
    },
    {
        "company": "MAPFRE",
        "role_title": "Solutions Delivery Manager Semantic Enterprise Data AI",
        "posting_url": "https://www.indeed.com/viewjob?jk=mapfre1",
        "location": "Boston, MA",
        "salary_range": "$121,000 - $182,000 a year",
        "source_board": "Indeed",
        "remote_type": "hybrid",
        "discovery_mode": 1
    },
    {
        "company": "System1",
        "role_title": "Lead Product Manager AI Agents Emerging Products",
        "posting_url": "https://www.indeed.com/viewjob?jk=system1",
        "location": "Los Angeles, CA",
        "salary_range": "$161,800 - $242,700 a year",
        "source_board": "Indeed",
        "remote_type": "hybrid",
        "discovery_mode": 1
    },
    {
        "company": "Hewlett Packard Enterprise",
        "role_title": "AI Product Manager",
        "posting_url": "https://www.indeed.com/viewjob?jk=hpe1",
        "location": "North Carolina",
        "salary_range": "$136,500 - $276,500 a year",
        "source_board": "Indeed",
        "remote_type": "hybrid",
        "discovery_mode": 1
    },
    {
        "company": "Lincoln Financial",
        "role_title": "AI Product Manager",
        "posting_url": "https://www.indeed.com/viewjob?jk=lincoln1",
        "location": "Radnor, PA",
        "salary_range": "$96,900 - $176,200 a year",
        "source_board": "Indeed",
        "remote_type": "hybrid",
        "discovery_mode": 1
    }
]

# Now let's check for duplicates and add new ones
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
added_count = 0
duplicate_count = 0

for posting in new_postings:
    fingerprint = compute_fingerprint(posting["company"], posting["role_title"], posting["location"])
    
    if fingerprint in existing_fingerprints:
        print(f"DUPLICATE: {posting['company']} - {posting['role_title']}")
        duplicate_count += 1
    else:
        # Insert into applications table
        cursor.execute("""
            INSERT INTO applications 
            (posting_url, company, role_title, source_board, posted_at, discovered_at, remote_type, salary_range, status, posting_fingerprint)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            posting["posting_url"],
            posting["company"],
            posting["role_title"],
            posting["source_board"],
            now,
            now,
            posting["remote_type"],
            posting["salary_range"],
            "discovered",
            fingerprint
        ))
        added_count += 1
        print(f"ADDED: {posting['company']} - {posting['role_title']}")

conn.commit()
conn.close()

print(f"\nSummary: {added_count} new postings added, {duplicate_count} duplicates skipped")