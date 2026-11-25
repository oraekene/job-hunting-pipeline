-- Addendum 23 — distinguish automated gate rejections from human rejections
--
-- `rejected_by_kene` was written by the pipeline's automated gate checks
-- (`pipeline_processor.py --reject`, the Rule 18 location gate, the
-- keyword floor and posting-liveness checks). It reads as a human
-- decision, and on 2026-11-25 the database showed 201 rows with that
-- status, every one of them carrying an automated failure stage and none
-- carrying an approval_decision of `reject` or `skip`. The label was
-- lying about who rejected the row.
--
-- `rejected_by_gate` is now the status for an automated gate rejection.
-- `rejected_by_kene` stays reserved for an explicit human rejection.
--
-- Apply after applications_db_schema_addendum_22.sql. Fully idempotent:
-- the UPDATE only touches rows still holding the old label, and the
-- ledger insert is INSERT OR IGNORE.

UPDATE applications
   SET status = 'rejected_by_gate'
 WHERE status = 'rejected_by_kene';

INSERT OR IGNORE INTO schema_version (filename, note) VALUES
  ('applications_db_schema_addendum_23.sql', 'rename automated gate rejections from rejected_by_kene to rejected_by_gate');
