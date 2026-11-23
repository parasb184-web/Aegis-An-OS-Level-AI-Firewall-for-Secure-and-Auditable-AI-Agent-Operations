-- Keep a running count per verdict so /counts does not have to scan the
-- whole audit log every second.
--
-- Run once on an existing database (a fresh one gets this from schema.sql):
--   psql -U aegis -d aegis -h localhost -f sql/counts_table.sql
--
-- Safe to run again: it recounts from actions and recreates the trigger.

BEGIN;

-- Stop new inserts into actions until we commit, but still allow reads.
-- Without this, a row inserted after we count but before the trigger
-- exists would never be counted, and the totals would be wrong forever.
LOCK TABLE actions IN SHARE ROW EXCLUSIVE MODE;

CREATE TABLE IF NOT EXISTS verdict_counts (
    verdict  TEXT PRIMARY KEY,
    n        BIGINT NOT NULL DEFAULT 0
);

TRUNCATE verdict_counts;

INSERT INTO verdict_counts (verdict, n)
SELECT verdict, COUNT(*) FROM actions GROUP BY verdict;

-- The dashboard expects these keys even before the first row of each.
INSERT INTO verdict_counts (verdict, n) VALUES
  ('allow', 0), ('block', 0), ('warn', 0)
ON CONFLICT (verdict) DO NOTHING;

-- Runs inside the same transaction as the INSERT into actions, so either
-- both the log row and the count change happen, or neither does.
-- ON CONFLICT means a verdict we have never seen gets its own row.
CREATE OR REPLACE FUNCTION count_verdict() RETURNS trigger AS $$
BEGIN
    INSERT INTO verdict_counts (verdict, n) VALUES (NEW.verdict, 1)
    ON CONFLICT (verdict) DO UPDATE SET n = verdict_counts.n + 1;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS actions_count_verdict ON actions;
CREATE TRIGGER actions_count_verdict
    AFTER INSERT ON actions
    FOR EACH ROW EXECUTE FUNCTION count_verdict();

COMMIT;

-- These two should agree.
SELECT verdict, n FROM verdict_counts ORDER BY verdict;
SELECT verdict, COUNT(*) FROM actions GROUP BY verdict ORDER BY verdict;
