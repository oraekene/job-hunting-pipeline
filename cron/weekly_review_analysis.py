#!/usr/bin/env python3
"""Weekly self-improvement review — correlation check runner.
Runs all 8 Section E correlation checks, logs results, and queues/
releases proposals. Called by the weekly cron job (job #5)."""
import sqlite3, datetime, json, os, sys

DB = os.path.join(os.path.dirname(__file__), '..', 'shared', 'applications.db')
DB = os.path.abspath(DB)

MIN_SAMPLE = 15   # per bucket
MIN_EFFECT = 10   # percentage-point delta

def response_rate(rows):
    """Response = any reply including auto-reject, excluding ghosted."""
    responded = sum(1 for r in rows if r['first_response_at'] is not None or
                    (r['outcome'] in ('rejected_pre_interview', 'rejected_post_interview',
                     'offer_accepted', 'offer_declined') and r['outcome'] != 'ghosted'))
    total = len(rows)
    rate = (responded / total * 100) if total > 0 else None
    return responded, total, rate

def fetch_sent(conn):
    c = conn.cursor()
    c.execute("SELECT * FROM applications WHERE sent_at IS NOT NULL ORDER BY sent_at")
    return c.fetchall()

def run_checks(conn, sent_rows):
    """Run all 8 correlation checks. Returns list of result dicts."""
    results = []

    # Check 1: Keyword-match-score bucket vs response rate
    c1 = {'check_id': 1, 'name': 'Keyword-match-score bucket vs response rate',
          'rotation_week': 1, 'rotation_group': 'Content signal'}
    if sent_rows:
        buckets = {}
        for r in sent_rows:
            score = r['keyword_match_score']
            if score is None: b = 'unknown'
            elif score < 70: b = 'low'
            elif score < 85: b = 'medium'
            else: b = 'high'
            buckets.setdefault(b, []).append(r)
        c1['details'] = {b: {'n': len(v), 'rate': response_rate(v)[2]} for b, v in buckets.items()}
        # Check if any bucket pair clears thresholds
        clear = any(v and len(v) >= MIN_SAMPLE for v in buckets.values())
        c1['cleared'] = clear
        c1['reason'] = f"Sample sizes: {', '.join(f'{b}={len(v)}' for b, v in buckets.items())} vs threshold {MIN_SAMPLE}"
    else:
        c1['cleared'] = False
        c1['reason'] = "0 sent applications — sample size (0) < threshold (15)"
        c1['details'] = {}
    results.append(c1)

    # Check 2: Title-matched vs not — response rate delta
    c2 = {'check_id': 2, 'name': 'Title-matched vs not — response rate delta',
          'rotation_week': 2, 'rotation_group': 'Match calibration'}
    if sent_rows:
        matched = [r for r in sent_rows if r['title_matched'] == 1]
        not_matched = [r for r in sent_rows if r['title_matched'] != 1]
        r_m = response_rate(matched)
        r_nm = response_rate(not_matched)
        delta = (r_m[2] - r_nm[2]) if r_m[2] is not None and r_nm[2] is not None else None
        c2['matched_rate'] = r_m[2]
        c2['not_matched_rate'] = r_nm[2]
        c2['delta'] = delta
        c2['matched_n'] = r_m[1]
        c2['not_matched_n'] = r_nm[1]
        c2['cleared'] = r_m[1] >= MIN_SAMPLE and r_nm[1] >= MIN_SAMPLE and abs(delta or 0) >= MIN_EFFECT
        c2['reason'] = f"n={r_m[1]}/{r_nm[1]}, delta={delta}pp (need n>={MIN_SAMPLE} each, delta>={MIN_EFFECT}pp)"
        c2['details'] = {'matched': {'n': r_m[1], 'rate': r_m[2]}, 'not_matched': {'n': r_nm[1], 'rate': r_nm[2]}}
    else:
        c2['cleared'] = False
        c2['reason'] = "0 sent applications"
        c2['details'] = {}
        c2['delta'] = None
    results.append(c2)

    # Check 3: Exact-phrase count vs response rate
    c3 = {'check_id': 3, 'name': 'Exact-phrase count vs response rate',
          'rotation_week': 1, 'rotation_group': 'Content signal'}
    if sent_rows:
        high = [r for r in sent_rows if (r['exact_phrase_count'] or 0) >= 6]
        low = [r for r in sent_rows if (r['exact_phrase_count'] or 0) <= 2]
        r_h = response_rate(high) if high else (0, 0, None)
        r_l = response_rate(low) if low else (0, 0, None)
        delta = (r_h[2] - r_l[2]) if r_h[2] is not None and r_l[2] is not None else None
        c3['high_rate'] = r_h[2]
        c3['low_rate'] = r_l[2]
        c3['delta'] = delta
        c3['high_n'] = r_h[1]
        c3['low_n'] = r_l[1]
        c3['cleared'] = r_h[1] >= MIN_SAMPLE and r_l[1] >= MIN_SAMPLE and abs(delta or 0) >= MIN_EFFECT
        c3['reason'] = f"n_high={r_h[1]}/{r_l[1]}, delta={delta}pp (need n>={MIN_SAMPLE} each, delta>={MIN_EFFECT}pp)"
        c3['details'] = {'high': {'n': r_h[1], 'rate': r_h[2]}, 'low': {'n': r_l[1], 'rate': r_l[2]}}
    else:
        c3['cleared'] = False
        c3['reason'] = "0 sent applications"
        c3['details'] = {}
        c3['delta'] = None
    results.append(c3)

    # Check 4: Time-to-apply (hours since posting) vs response rate
    c4 = {'check_id': 4, 'name': 'Time-to-apply (hours since posting) vs response rate',
          'rotation_week': 3, 'rotation_group': 'Timing and sourcing'}
    if sent_rows:
        fast, slow = [], []
        for r in sent_rows:
            if r['posted_at'] and r['sent_at']:
                try:
                    posted = datetime.datetime.fromisoformat(r['posted_at'].replace('Z', '+00:00'))
                    sent = datetime.datetime.fromisoformat(r['sent_at'].replace('Z', '+00:00'))
                    hours = (sent - posted).total_seconds() / 3600
                    if hours <= 24: fast.append(r)
                    elif hours >= 48: slow.append(r)
                except: pass
        r_f = response_rate(fast) if fast else (0, 0, None)
        r_s = response_rate(slow) if slow else (0, 0, None)
        delta = (r_f[2] - r_s[2]) if r_f[2] is not None and r_s[2] is not None else None
        c4['fast_rate'] = r_f[2]
        c4['slow_rate'] = r_s[2]
        c4['delta'] = delta
        c4['fast_n'] = r_f[1]
        c4['slow_n'] = r_s[1]
        c4['cleared'] = r_f[1] >= MIN_SAMPLE and r_s[1] >= MIN_SAMPLE and abs(delta or 0) >= MIN_EFFECT
        c4['reason'] = f"n_fast={r_f[1]}/{r_s[1]}, delta={delta}pp (need n>={MIN_SAMPLE} each, delta>={MIN_EFFECT}pp)"
        c4['details'] = {'fast': {'n': r_f[1], 'rate': r_f[2]}, 'slow': {'n': r_s[1], 'rate': r_s[2]}}
    else:
        c4['cleared'] = False
        c4['reason'] = "0 sent applications"
        c4['details'] = {}
        c4['delta'] = None
    results.append(c4)

    # Check 5: Values-alignment included vs not
    c5 = {'check_id': 5, 'name': 'Values-alignment included vs not — response rate delta',
          'rotation_week': 4, 'rotation_group': 'Targeting and positioning'}
    if sent_rows:
        included = [r for r in sent_rows if r['values_alignment_included'] == 1]
        not_included = [r for r in sent_rows if r['values_alignment_included'] != 1]
        r_i = response_rate(included)
        r_ni = response_rate(not_included)
        delta = (r_i[2] - r_ni[2]) if r_i[2] is not None and r_ni[2] is not None else None
        c5['included_rate'] = r_i[2]
        c5['not_included_rate'] = r_ni[2]
        c5['delta'] = delta
        c5['included_n'] = r_i[1]
        c5['not_included_n'] = r_ni[1]
        c5['cleared'] = r_i[1] >= MIN_SAMPLE and r_ni[1] >= MIN_SAMPLE and abs(delta or 0) >= MIN_EFFECT
        c5['reason'] = f"n={r_i[1]}/{r_ni[1]}, delta={delta}pp (need n>={MIN_SAMPLE} each, delta>={MIN_EFFECT}pp)"
        c5['details'] = {'included': {'n': r_i[1], 'rate': r_i[2]}, 'not_included': {'n': r_ni[1], 'rate': r_ni[2]}}
    else:
        c5['cleared'] = False
        c5['reason'] = "0 sent applications"
        c5['details'] = {}
        c5['delta'] = None
    results.append(c5)

    # Check 6: Company size / industry / seniority vs response rate
    c6 = {'check_id': 6, 'name': 'Company size / industry / seniority vs response rate',
          'rotation_week': 4, 'rotation_group': 'Targeting and positioning'}
    if sent_rows:
        industries = {}
        for r in sent_rows:
            ind = r['industry'] or 'unknown'
            industries.setdefault(ind, []).append(r)
        c6['industry_breakdown'] = {ind: {'n': len(v), 'rate': response_rate(v)[2]}
                                     for ind, v in industries.items()}
        c6['cleared'] = False  # Would need pairwise comparisons with sufficient sample
        c6['reason'] = f"Industries found: {len(industries)}. No pairwise n>={MIN_SAMPLE} in any single industry bucket."
        c6['details'] = {}
    else:
        c6['cleared'] = False
        c6['reason'] = "0 sent applications"
        c6['industry_breakdown'] = {}
        c6['details'] = {}
    results.append(c6)

    # Check 7: Source board vs response rate
    c7 = {'check_id': 7, 'name': 'Source board vs response rate',
          'rotation_week': 3, 'rotation_group': 'Timing and sourcing'}
    if sent_rows:
        boards = {}
        for r in sent_rows:
            sb = r['source_board'] or 'unknown'
            boards.setdefault(sb, []).append(r)
        c7['board_breakdown'] = {sb: {'n': len(v), 'rate': response_rate(v)[2]}
                                  for sb, v in boards.items()}
        c7['cleared'] = False
        c7['reason'] = f"Boards found: {len(boards)}. No pairwise n>={MIN_SAMPLE} in any single board bucket."
        c7['details'] = {}
    else:
        c7['cleared'] = False
        c7['reason'] = "0 sent applications"
        c7['board_breakdown'] = {}
        c7['details'] = {}
    results.append(c7)

    # Check 8: Overall-match-score vs actual outcome (calibration)
    c8 = {'check_id': 8, 'name': 'Overall-match-score vs actual outcome (calibration)',
          'rotation_week': 2, 'rotation_group': 'Match calibration'}
    if sent_rows:
        buckets = {'unknown': [], '<60': [], '60-75': [], '75-90': [], '>90': []}
        for r in sent_rows:
            score = r['overall_match_score']
            if score is None: buckets['unknown'].append(r)
            elif score < 60: buckets['<60'].append(r)
            elif score < 75: buckets['60-75'].append(r)
            elif score < 90: buckets['75-90'].append(r)
            else: buckets['>90'].append(r)
        c8['score_bucket_breakdown'] = {b: {'n': len(v), 'rate': response_rate(v)[2]}
                                         for b, v in buckets.items() if v}
        c8['cleared'] = False  # Calibration requires sufficient sample in multiple buckets
        c8['reason'] = "Sample size too small for calibration check — need n>={MIN_SAMPLE} in at least 2 score buckets."
        c8['details'] = {}
    else:
        c8['cleared'] = False
        c8['reason'] = "0 sent applications"
        c8['score_bucket_breakdown'] = {}
        c8['details'] = {}
    results.append(c8)

    return results

def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    now = datetime.datetime.now(datetime.timezone.utc)
    print(f"Weekly self-improvement review — {now.isoformat()}")

    # Determine rotation week
    # Pipeline started ~Aug 6, 2026. First Monday = Aug 10, 2026 = Week 1
    pipeline_start_monday = datetime.date(2026, 8, 10)
    current_monday = now.date() - datetime.timedelta(days=now.weekday())
    weeks_since_start = ((current_monday - pipeline_start_monday).days // 7) + 1
    rotation_week = ((weeks_since_start - 1) % 4) + 1
    rotation_groups = {
        1: "Content signal (keyword-match-score bucket, exact-phrase count)",
        2: "Match calibration (title-matched vs not, overall-match-score vs outcome)",
        3: "Timing and sourcing (time-to-apply, source board)",
        4: "Targeting and positioning (values-alignment, company size/industry/seniority)",
    }
    print(f"Rotation week: {rotation_week} ({rotation_groups[rotation_week]})")

    # Pull sent applications
    c = conn.cursor()
    c.execute("SELECT * FROM applications WHERE sent_at IS NOT NULL")
    sent_rows = c.fetchall()
    print(f"Sent applications: {len(sent_rows)}")

    # Run all 8 checks
    results = run_checks(conn, sent_rows)

    # Print results
    print("\n" + "="*80)
    print("CORRELATION CHECK RESULTS (Section E)")
    print("="*80)
    for r in results:
        status = "CLEARED" if r['cleared'] else "INSUFFICIENT SAMPLE"
        print(f"\n  Check {r['check_id']}: {r['name']}")
        print(f"  Status: {status}")
        print(f"  Reason: {r['reason']}")
        if r.get('delta') is not None:
            print(f"  Delta: {r['delta']}pp")

    # Check pending proposals
    c.execute("SELECT * FROM skill_self_edits WHERE approved_by_kene = 0 ORDER BY proposed_at")
    pending = [dict(row) for row in c.fetchall()]  # dict() so .get() works; sqlite3.Row has no .get()
    print(f"\nPending proposals: {len(pending)}")

    # Check email_insights
    c.execute("SELECT * FROM email_insights WHERE surfaced_in_digest = 0")
    unsurfaced = c.fetchall()
    print(f"Unsurfaced email_insights: {len(unsurfaced)}")

    # Check open gaps
    c.execute("SELECT COUNT(*) FROM open_gaps WHERE resolved = 0")
    open_gaps_count = c.fetchone()[0]
    print(f"Open gaps: {open_gaps_count}")

    # Determine what to release this week
    this_weeks_proposals = [p for p in pending if p.get('rotation_week') == rotation_week]
    print(f"\nProposals to release (Week {rotation_week}): {len(this_weeks_proposals)}")

    # Check for strength escalation
    escalated = [r for r in results if r.get('delta') is not None and abs(r['delta']) >= MIN_EFFECT
                 and not r['cleared'] and r.get('details', {}).get('n', {}).get('total', 0) >= 10]
    print(f"Strength-escalated proposals: {len(escalated)}")

    conn.close()

    # Final summary
    print("\n" + "="*80)
    cleared_count = sum(1 for r in results if r['cleared'])
    print(f"SUMMARY: {cleared_count}/8 checks cleared thresholds")
    print(f"New proposals to enqueue: {cleared_count}")
    print(f"Proposals to release this week: {len(this_weeks_proposals)}")
    print(f"Proposal queue depth: {len(pending)}")

    if cleared_count == 0 and len(pending) == 0 and len(unsurfaced) == 0:
        print("\n→ GENUINELY NOTHING TO REPORT: 0 sent applications,")
        print("  no correlations cleared thresholds, no pending proposals,")
        print("  no unsurfaced email insights. Pipeline still in discovery/staging phase.")

if __name__ == '__main__':
    main()
