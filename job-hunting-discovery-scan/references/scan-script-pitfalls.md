# Discovery Scan Script — Pitfalls & Fixes

Session: 2026-08-18 cron-run (open_web mode)

This file documents bugs found and fixed, plus the verified run pattern, when executing the discovery scan scripts under `shared/01-job-discovery/scripts/`. A future session should read this before relying on `discovery_scan_new.py` or its derivatives.

## 1. Salary extraction must handle `K` suffixes inside the regex group

**Bug:** `extract_salary()` used `r'\$(\d+[,.]?\d*)'` which captures `215` from `$215K`. The `K` was consumed by the regex but not captured in `group(1)`, so the function returned `215.0` instead of `215000.0`.

**Fix:** Move the `[kK]?` suffix *inside* the capture group:

```python
patterns = [
    r'\$(\d+[,.]?\d*[kK]?)\s*-?\s*\$?(\d+[,.]?\d*[kK]?)',  # $100k - $150k
    r'\$(\d+[,.]?\d*[kK]?)',  # $100k
]
for pattern in patterns:
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        raw = match.group(1).replace(',', '').lower()
        if 'k' in raw:
            min_salary = float(raw.replace('k', '')) * 1000
        else:
            min_salary = float(raw)
        return min_salary, 'USD', 'year'
```

The original code also had a confusing double-handling (`replace('k','000')` then `* 1000`), which double-multiplied. The fix separates the two cases cleanly.

**Test case:** `$215K-257K` → 215000 | `$90K-130K` → 90000 | `$36,000` → 36000.

## 2. Sort before applying the daily cap

**Bug:** The script pushed `new_to_queue` entries directly into `final_queue[:remaining_slots]` without sorting. Because web search returns results in arbitrary order (often alphabetical or source-grouped), the first 3 items to land in the queue might be low-recency, low-priority postings, while a job posted 28 minutes ago sits in overflow.

**Fix:** Sort `new_to_queue` by `(priority, posted_hours_ago)` **before** slicing:

```python
new_to_queue.sort(key=lambda p: (
    0 if p['priority'] == 'high' else 1,       # high priority first
    p.get('posted_hours_ago', 99999)           # then most recent first
))
final_queue = new_to_queue[:remaining_slots] if remaining_slots > 0 else []
```

This is the correct ordering because Rule 5 (posted within 24h) determines `priority: high`, and speed-to-apply is the single most impactful factor in recruiter response rate.

## 3. Overflow must be captured when `remaining_slots == 0`

**Bug:** The original overflow logic was:
```python
overflow = new_to_queue[remaining_slots:] if remaining_slots > 0 and len(new_to_queue) > remaining_slots else []
```
When `remaining_slots` was 0 (cap already full from pre-existing entries), this evaluated to `[]`, silently dropping all overflow postings from the output and the `.discovery_results.json` file. They were only re-discovered on the next run.

**Fix:**
```python
overflow = new_to_queue[remaining_slots:] if len(new_to_queue) > remaining_slots else []
```
This ensures overflow is always populated when there are more filtered postings than slots, regardless of whether the cap is partially or fully consumed.

## 4. Verification pattern: re-run scan to confirm dedup

After inserting queued postings into the database, re-run the scan script. The newly inserted postings should show up under "Skipped as duplicates" with 0 queued on the second pass. This confirms:

- Fingerprints were computed and stored correctly
- The dedup query (`SELECT posting_fingerprint ...`) is working
- The daily cap check reads from the correct `discovered` status + today's date

```bash
python shared/01-job-discovery/scripts/discovery_scan_new.py 2>&1 | grep -E "(New postings found|Skipped as duplicates|Queued|Overflow)"
```

Expected on the second pass (same day, same data): `Skipped as duplicates: 3`, `Queued: 0`, `Overflow: 12`.

## 5. Gate state file (`shared/.discovery_gate_state.json`)

After each run, write a JSON blob with at minimum `last_run_at`, `mode`, `sources_checked`, `queued`, `today_queued`, `cap_reached`, and `remaining_slots`. This lets:

- The wake-gate script see when the last agent was woken
- Future runs understand why the cap was full vs. not full
- Analytics track source yield over time

Fields used by `11-analytics-and-learning`:
`new_found`, `duplicates`, `filtered_out`, `queued`, `overflow_count`, `sources_checked_count`.

## 6. Fingerprint null-handling for pre-existing rows

Older rows in `applications` may have `NULL` in the `posting_fingerprint` column (inserted before the column was added). The dedup check (`if fingerprint in existing_fingerprints`) only adds non-NULL fingerprints to the set, so NULL rows are never matched. This is the **correct** behavior — a NULL fingerprint means "we can't be sure this is a duplicate," so the posting should be re-examined rather than silently skipped. No code change needed, but document it so a developer doesn't add `.fillna()` and accidentally cause false-merge duplicates.
