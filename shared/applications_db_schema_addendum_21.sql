-- Addendum 21 — rotation_week on skill_self_edits
--
-- The weekly self-improvement review (11-analytics-and-learning, cron job #5)
-- uses a four-week rotation to stagger when proposals reach Kenechukwu for
-- approval (see 11-analytics-and-learning/references/metrics-schema.md
-- Section E, "Proposal release — staggered, not filtered"). Each check's
-- result row carries a rotation_week field (1=Content signal, 2=Match
-- calibration, 3=Timing and sourcing, 4=Targeting and positioning), and the
-- release logic selects pending proposals whose rotation_week matches the
-- current week.
--
-- The skill_self_edits table was created without this column, so the release
-- logic in cron/weekly_review_analysis.py (which reads p['rotation_week'])
-- silently failed — pending proposals were never released on their rotation
-- week. This addendum adds the column so the staggered-release schedule
-- actually functions once proposals start clearing the sample-size and
-- effect-size thresholds.
--
-- Apply after applications_db_schema_addendum_20.sql.

ALTER TABLE skill_self_edits ADD COLUMN rotation_week INTEGER
    -- 1=Content signal, 2=Match calibration, 3=Timing/sourcing, 4=Targeting/positioning
    -- Set when a proposal is enqueued, per the rotation group of its triggering
    -- correlation check. NULL for proposals predating this addendum (they were
    -- back-filled with their originating check's group during first run).
    DEFAULT NULL;

INSERT OR IGNORE INTO schema_version (filename, note) VALUES
  ('applications_db_schema_addendum_21.sql', 'rotation_week column on skill_self_edits for staggered proposal release');
