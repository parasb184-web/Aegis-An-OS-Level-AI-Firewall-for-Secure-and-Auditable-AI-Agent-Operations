-- How does the audit log behave once it is large?
--
-- Run with:
--   PGPASSWORD=aegis psql -U aegis -d aegis -h localhost -f index_experiment.sql
--
-- Take a screenshot of the output before and after the CREATE INDEX lines.

\timing on

-- How many real rows do we have right now
SELECT count(*) AS rows_before FROM actions;

-- Pad the table to roughly two million rows of realistic-looking history.
-- generate_series gives us the row count; the rest is arithmetic on it so
-- the timestamps, paths and verdicts vary the way real ones would.
INSERT INTO actions (ts, pid, process_name, path, operation, verdict, reason)
SELECT
    now() - (i || ' seconds')::interval,
    (i % 5000) + 1000,
    CASE WHEN i % 3 = 0 THEN 'python3'
         WHEN i % 3 = 1 THEN 'cat'
         ELSE 'bash' END,
    '/home/acerparas/demo/notes/dir' || (i % 200) || '/file' || (i % 900) || '.txt',
    'open',
    CASE WHEN i % 20 = 0 THEN 'block' ELSE 'allow' END,
    CASE WHEN i % 20 = 0 THEN 'risk 70: burst read' ELSE 'no rule' END
FROM generate_series(1, 2000000) AS i;

SELECT count(*) AS rows_after FROM actions;

ANALYZE actions;

-- ============================================================
-- BEFORE INDEXES
-- ============================================================

-- Q1: what happened in the last ten minutes
EXPLAIN ANALYZE
SELECT ts, process_name, path, verdict
FROM actions
WHERE ts > now() - interval '10 minutes'
ORDER BY ts DESC
LIMIT 50;

-- Q2: everything we ever decided about one file
EXPLAIN ANALYZE
SELECT ts, verdict, reason
FROM actions
WHERE path = '/home/acerparas/demo/notes/dir7/file123.txt';

-- Q3: the dashboard counts
EXPLAIN ANALYZE
SELECT verdict, COUNT(*) FROM actions GROUP BY verdict;