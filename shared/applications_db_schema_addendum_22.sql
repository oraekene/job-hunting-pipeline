-- Addendum 22 — application priority
--
-- Discovery assigns each posting a priority so the orchestrator can prefer
-- postings posted within the last 24 hours. The live database already uses
-- this field, but the clean migration chain did not create it. Fresh
-- installs therefore could not run the discovery scripts without a schema
-- error.
--
-- Apply after applications_db_schema_addendum_21.sql.

ALTER TABLE applications ADD COLUMN priority TEXT DEFAULT 'normal';

INSERT OR IGNORE INTO schema_version (filename, note) VALUES
  ('applications_db_schema_addendum_22.sql', 'priority on applications for recency-first discovery queues');
