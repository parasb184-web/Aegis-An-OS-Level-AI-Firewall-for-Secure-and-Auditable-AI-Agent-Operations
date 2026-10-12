-- Retry the path index on the real actions table. An earlier attempt on a
-- 2M-row actions table failed when WSL2 ran out of memory.
--
--   psql -U aegis -d aegis -h localhost -X -f sql/create_path_index.sql

\echo === settings in effect (defaults, unchanged)
SHOW maintenance_work_mem;
SELECT COUNT(*) AS rows_in_actions,
       pg_size_pretty(pg_relation_size('actions')) AS table_size
FROM actions;

\timing on
CREATE INDEX IF NOT EXISTS idx_actions_path ON actions (path);
\timing off

SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'actions';
