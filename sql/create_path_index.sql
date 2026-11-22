

\echo === settings in effect (defaults, unchanged)
SHOW maintenance_work_mem;
SELECT COUNT(*) AS rows_in_actions,
       pg_size_pretty(pg_relation_size('actions')) AS table_size
FROM actions;

\timing on
CREATE INDEX IF NOT EXISTS idx_actions_path ON actions (path);
\timing off

SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'actions';
