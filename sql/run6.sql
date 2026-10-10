-- Helper for index_experiment_v2.sql: run the query in :q six times.
-- Run 1 warms the cache and is thrown away; we report the median of 2-6.
\echo === :label run 1
EXPLAIN (ANALYZE, BUFFERS) :q;
\echo === :label run 2
EXPLAIN (ANALYZE, BUFFERS) :q;
\echo === :label run 3
EXPLAIN (ANALYZE, BUFFERS) :q;
\echo === :label run 4
EXPLAIN (ANALYZE, BUFFERS) :q;
\echo === :label run 5
EXPLAIN (ANALYZE, BUFFERS) :q;
\echo === :label run 6
EXPLAIN (ANALYZE, BUFFERS) :q;
