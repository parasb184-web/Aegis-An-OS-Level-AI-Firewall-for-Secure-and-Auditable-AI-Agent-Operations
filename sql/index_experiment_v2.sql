-- Index experiment, redone with repeated runs.
--
-- Run soon after sql/generate_dataset.sql (the ts query looks at the last
-- 10 minutes, and the data ends at the moment the generator ran):
--   PGPASSWORD=aegis psql -U aegis -d aegis -h localhost -X \
--       -f sql/index_experiment_v2.sql > results/db/task4_explain_raw.txt
--   python3 results/db/scripts/medians.py results/db/task4_explain_raw.txt
--
-- Each query runs 6 times with EXPLAIN (ANALYZE, BUFFERS); medians.py
-- drops run 1 and reports the median of the other 5.

-- actions_exp must match the real actions table, or the results say
-- nothing about our system. This lists any column that differs.
\echo === structure check: columns that differ between actions and actions_exp (expect 0 rows)
(SELECT column_name, data_type, is_nullable, ordinal_position
   FROM information_schema.columns WHERE table_name = 'actions'
 EXCEPT
 SELECT column_name, data_type, is_nullable, ordinal_position
   FROM information_schema.columns WHERE table_name = 'actions_exp')
UNION ALL
(SELECT column_name, data_type, is_nullable, ordinal_position
   FROM information_schema.columns WHERE table_name = 'actions_exp'
 EXCEPT
 SELECT column_name, data_type, is_nullable, ordinal_position
   FROM information_schema.columns WHERE table_name = 'actions');

-- (a) dashboard-style "what happened recently"
\set qa 'SELECT ts, process_name, path, verdict FROM actions_exp WHERE ts > now() - interval ''10 minutes'' ORDER BY ts DESC LIMIT 50'
-- (b) everything decided about one file. file107 exists (~1,111 rows).
\set qb 'SELECT ts, verdict, reason FROM actions_exp WHERE path = ''/home/acerparas/demo/notes/dir7/file107.txt'''
-- (b0) the path the original experiment used. It can never match: dir7
-- needs i mod 100 = 7, file123 needs i mod 100 = 23. Kept to show what
-- the old 186 ms -> 0.082 ms number actually measured.
\set qb0 'SELECT ts, verdict, reason FROM actions_exp WHERE path = ''/home/acerparas/demo/notes/dir7/file123.txt'''
-- (c) the old /counts query vs the new one
\set qc_old 'SELECT verdict, COUNT(*) FROM actions_exp GROUP BY verdict'
\set qc_new 'SELECT verdict, n FROM verdict_counts_exp'

-- ============================================================
-- BEFORE INDEXES (only the primary key)
-- ============================================================
DROP INDEX IF EXISTS idx_exp_ts;
DROP INDEX IF EXISTS idx_exp_path;
ANALYZE actions_exp;

\set q :qa
\set label a_ts_range_before
\ir run6.sql
\set q :qb
\set label b_path_hit_before
\ir run6.sql
\set q :qb0
\set label b0_path_miss_before
\ir run6.sql
\set q :qc_old
\set label c_groupby_before
\ir run6.sql
\set q :qc_new
\set label c_summary_table
\ir run6.sql

-- ============================================================
-- BUILD INDEXES (\timing gives the build time)
-- ============================================================
\echo === index builds
\timing on
CREATE INDEX idx_exp_ts ON actions_exp (ts DESC);
CREATE INDEX idx_exp_path ON actions_exp (path);
\timing off
ANALYZE actions_exp;

-- ============================================================
-- AFTER INDEXES
-- ============================================================
\set q :qa
\set label a_ts_range_after
\ir run6.sql
\set q :qb
\set label b_path_hit_after
\ir run6.sql
\set q :qb0
\set label b0_path_miss_after
\ir run6.sql
\set q :qc_old
\set label c_groupby_after
\ir run6.sql

\echo === sizes
SELECT pg_size_pretty(pg_relation_size('actions_exp'))    AS table_size,
       pg_size_pretty(pg_relation_size('idx_exp_ts'))     AS ts_index,
       pg_size_pretty(pg_relation_size('idx_exp_path'))   AS path_index;
