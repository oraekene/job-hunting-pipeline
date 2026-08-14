# 15 — Currency honesty: no unevidenced USD conversions

**What to build:** Two currency findings from the 2026-08-13 sweep:

1. App 13 (Peek) artifacts state `MX$950K–MX$1.2M/yr ≈ $46K–$58K USD` —
   wrong. At the 2026-08-13 rate (1 USD ≈ 17.06 MXN) the correct range is
   ≈ $55.7K–$70.3K. The conclusion (clears the $36K floor) survives, but
   the math is off ~20% and an artifact with wrong numbers is a Rule 2
   hazard.
2. App 14 (Camunda) artifacts claim Nigeria-based comp "comfortably
   exceeded by any reasonable Remote.com rate for this band" — no source,
   no rate, no disclosed Nigeria figure. Un-evidenced speculation under
   strict mode.

Fix both, and make the class of bug checkable.

**Blocked by:** None — can start immediately

**Status:** done

- [x] App 13 artifacts corrected: `MX$950K–MX$1.2M/yr ≈ $55.7K–$70.3K USD
  (17.06 MXN/USD, 2026-08-13)` in jd_analysis.md, resume_match.md
  (risk_tactics_change_log.md was rewritten by the live 2026-08-14 run and
  no longer carries the salary line — no stale numbers remain)
- [x] App 14 artifacts corrected: the unsupported "comfortably exceeded"
  claim replaced with the factual statement (US band $143,800–$231,900;
  Nigeria comp is location-adjusted via Total Rewards Calculator and is
  not disclosed; the $36K/yr floor comparison is flagged for the approval
  gate, not asserted) — resume_match.md, risk_tactics_change_log.md
- [x] App 1 (Sproxil) caught by the new check: 500,000 NGN/month was
  converted at a ~2016 rate to "≈ $43,200/yr" — real value ≈ $4.4K/yr at
  1,360 NGN/USD (2026-08-13). jd_analysis.md and risk_tactics_change_log.md
  corrected; comp_delta verdict now flags the local-market floor question
  for the approval gate instead of auto-answering "Clean"
- [x] App 19 (Poland range) caught by the new check: 31,000–40,000
  PLN/month now cited at ~3.73 PLN/USD (Aug 2026) → ≈ $99.8K–$128.7K/yr
  (was "≈ $96k–$125k" with no rate)
- [x] Cover-letter / resume guidance (06-cover-letter SKILL.md) states:
  NGN/₦ figures stay in NGN; any USD conversion must cite rate + date
  inline
- [x] dry-run static check: any artifact line with a cross-currency
  conversion (`≈ $…` + another currency code) without a rate citation in
  the same line fails the suite (same-currency rewrites like
  "$36k/yr ≈ $3k/month" are not flagged)
- [x] dry-run: currency check green. (Suite is 26/28: the 2 remaining
  failures are the in-flight `job-hunting-artifact-qa` skill — untracked
  refs + stale skill count — not this ticket's scope)
