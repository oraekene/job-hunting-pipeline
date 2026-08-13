# 09 — Encoding hygiene: no mojibake in artifacts or DB

**What to build:** Kill the replacement-character corruption that shipped in
the 2026-08-12 run — `₦2.3M` rendered as `?2.3M` in cover letters and
change-logs, and `vanished � no report` in DB strings. Processor reads/writes
become explicitly UTF-8, stage skills state the currency-symbol rule, and a
dry-run static check makes regressions impossible to miss.

**Blocked by:** 07 — Repair package integrity so dry-run.py is green

**Status:** done

- [ ] All processor file reads/writes declare `encoding="utf-8"` explicitly
  (currently several `open()` calls rely on the platform default — the
  Windows locale default is the root cause)
- [ ] Cover-letter / change-log / resume guidance states: write `NGN` or a
  true `₦`, never a `?` placeholder; em-dashes and naira symbols are
  legitimate and must survive round-trip
- [ ] A new dry-run static check scans `shared/build_artifacts/` artifacts
  for U+FFFD replacement characters and fails on any hit
- [ ] Existing corrupted content is cleaned: `?2.3M` → `₦2.3M` in app 3/4
  artifacts, `vanished � no report` string in the processor replaced with
  the plain text
- [ ] Harness case: an artifact containing `₦` and `—` commits with those
  characters intact in the DB strings derived from it (e.g., open_gaps
  claim text)
- [ ] dry-run.py remains green including the new check
