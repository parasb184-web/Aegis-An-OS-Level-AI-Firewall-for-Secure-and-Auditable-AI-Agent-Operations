-- Same queries, with indexes. Run this after index_experiment.sql and
-- compare the execution times.

\timing on

CREATE INDEX idx_actions_ts ON actions (ts DESC);
CREATE INDEX idx_actions_path ON actions (path);

ANALYZE actions;

-- ============================================================
-- AFTER INDEXES
-- ============================================================

EXPLAIN ANALYZE
SELECT ts, process_name, path, verdict
FROM actions
WHERE ts > now() - interval '10 minutes'
ORDER BY ts DESC
LIMIT 50;

EXPLAIN ANALYZE
SELECT ts, verdict, reason
FROM actions
WHERE path = '/home/acerparas/demo/notes/dir7/file123.txt';

EXPLAIN ANALYZE
SELECT verdict, COUNT(*) FROM actions GROUP BY verdict;

-- What the indexes cost us in disk space
SELECT pg_size_pretty(pg_relation_size('actions')) AS table_size,
       pg_size_pretty(pg_indexes_size('actions'))  AS index_size;